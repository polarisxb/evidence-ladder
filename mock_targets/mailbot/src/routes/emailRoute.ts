import { Router, Request, Response } from 'express';
import {
  findEmailsByOwner,
  findEmailById,
  findStarredByOwner,
  searchEmails,
  markEmailRead,
  setEmailRead,
  setEmailStarred,
  moveEmailToFolder,
  insertEmail,
} from '../models/emailModel';
import { findUserById } from '../models/userModel';
import { recordEmailOp } from '../services/auditService';
import { deliverToRecipientInbox } from '../services/deliveryService';
import { EmailFolder } from '../types';
import logger from '../logger';

const router = Router();

const DEFAULT_USER = 'alice';
const VALID_FOLDERS: EmailFolder[] = ['inbox', 'sent', 'trash', 'drafts'];

// Prefer the authenticated session user (set by attachSession middleware) for
// the human-facing UI. Falls back to the explicit userId param and finally to
// the seeded `alice` account, which keeps the agent /chat injection demo and
// any token-less callers working exactly as before.
function resolveUser(req: Request): string {
  if (req.authUser) return req.authUser.id;
  const raw = (req.query.userId as string) ?? (req.body?.userId as string) ?? DEFAULT_USER;
  return /^[A-Za-z0-9_-]+$/.test(raw) ? raw : DEFAULT_USER;
}

function ownerEmail(userId: string): string {
  return findUserById(userId)?.email ?? `${userId}@corp.com`;
}

function newId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function str(val: unknown): string | null {
  if (typeof val === 'string' && val.trim().length > 0) return val.trim();
  return null;
}

// Current user + per-folder counts (drives header profile + sidebar badges).
router.get('/me', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const user = findUserById(userId);
  if (!user) {
    res.status(404).json({ error: 'user not found' });
    return;
  }
  const all = findEmailsByOwner(userId);
  const counts = {
    inbox: all.filter((e) => e.folder === 'inbox').length,
    inboxUnread: all.filter((e) => e.folder === 'inbox' && e.isRead === 0).length,
    sent: all.filter((e) => e.folder === 'sent').length,
    trash: all.filter((e) => e.folder === 'trash').length,
    drafts: all.filter((e) => e.folder === 'drafts').length,
    starred: all.filter((e) => e.starred === 1).length,
  };
  res.json({ user, counts });
});

// List emails in a folder (read-only). `folder=starred` is a cross-folder view.
router.get('/emails', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const folderParam = (req.query.folder as string) ?? 'inbox';
  if (folderParam === 'starred') {
    res.json({ folder: 'starred', emails: findStarredByOwner(userId) });
    return;
  }
  const folder = VALID_FOLDERS.includes(folderParam as EmailFolder)
    ? (folderParam as EmailFolder)
    : 'inbox';
  res.json({ folder, emails: findEmailsByOwner(userId, folder) });
});

// Search across the user's mailbox.
router.get('/search', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const q = ((req.query.q as string) ?? '').trim();
  if (!q) {
    res.json({ query: '', emails: [] });
    return;
  }
  res.json({ query: q, emails: searchEmails(userId, q) });
});

// Read a single email (marks it read; AI-driven ops are audited separately).
router.get('/emails/:id', (req: Request, res: Response): void => {
  const email = findEmailById(req.params.id);
  if (!email || email.ownerUserId !== resolveUser(req)) {
    res.status(404).json({ error: 'email not found' });
    return;
  }
  markEmailRead(req.params.id);
  res.json({ ...email, isRead: 1 });
});

// ── User-initiated write operations ──────────────────────────────────────
// These are driven by clicks in the UI (not the AI agent). They are still
// recorded to the audit trail, but tagged "[ui]" in the detail so the
// evidence chain can distinguish a human action from a covert agent action.

// Toggle read / unread.
router.post('/emails/:id/read', (req: Request, res: Response): void => {
  const email = findEmailById(req.params.id);
  if (!email || email.ownerUserId !== resolveUser(req)) {
    res.status(404).json({ error: 'email not found' });
    return;
  }
  const read = req.body?.read !== false; // default: mark read
  setEmailRead(req.params.id, read);
  res.json({ ...email, isRead: read ? 1 : 0 });
});

// Toggle star.
router.post('/emails/:id/star', (req: Request, res: Response): void => {
  const email = findEmailById(req.params.id);
  if (!email || email.ownerUserId !== resolveUser(req)) {
    res.status(404).json({ error: 'email not found' });
    return;
  }
  const starred = req.body?.starred !== false; // default: star
  setEmailStarred(req.params.id, starred);
  res.json({ ...email, starred: starred ? 1 : 0 });
});

// Move to a folder.
router.post('/emails/:id/move', (req: Request, res: Response): void => {
  const email = findEmailById(req.params.id);
  if (!email || email.ownerUserId !== resolveUser(req)) {
    res.status(404).json({ error: 'email not found' });
    return;
  }
  const target = str(req.body?.folder);
  if (!target || !VALID_FOLDERS.includes(target as EmailFolder)) {
    res.status(400).json({ error: 'invalid folder' });
    return;
  }
  moveEmailToFolder(req.params.id, target as EmailFolder);
  res.json({ ...email, folder: target as EmailFolder });
});

// Delete (move to trash).
router.post('/emails/:id/delete', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const email = findEmailById(req.params.id);
  if (!email || email.ownerUserId !== userId) {
    res.status(404).json({ error: 'email not found' });
    return;
  }
  moveEmailToFolder(req.params.id, 'trash');
  recordEmailOp(
    'delete_email', req.params.id, userId, null,
    `[ui] User deleted (moved to trash) emailId=${req.params.id}`,
  );
  logger.info('[API] delete_email (ui): %s', req.params.id);
  res.json({ ok: true, id: req.params.id });
});

// Forward an existing email.
router.post('/emails/:id/forward', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const original = findEmailById(req.params.id);
  if (!original || original.ownerUserId !== userId) {
    res.status(404).json({ error: 'email not found' });
    return;
  }
  const to = str(req.body?.to);
  if (!to) {
    res.status(400).json({ error: 'recipient (to) is required' });
    return;
  }
  const id = newId('MAIL-SENT');
  const subject = `Fwd: ${original.subject}`;
  const body = [
    '---------- Forwarded message ----------',
    `From: ${original.fromAddr}`,
    `Date: ${original.createdAt}`,
    `Subject: ${original.subject}`,
    '',
    original.body,
  ].join('\n');
  insertEmail(id, userId, 'sent', ownerEmail(userId), to, subject, body, true);
  const fwdInboxId = deliverToRecipientInbox(ownerEmail(userId), to, subject, body);
  recordEmailOp(
    'forward_email', req.params.id, userId, to,
    `[ui] User forwarded emailId=${req.params.id} to=${to}`,
  );
  logger.info('[API] forward_email (ui): %s -> %s', req.params.id, to);
  res.json({ ok: true, id, to, delivered: fwdInboxId !== null });
});

// Compose + send a new email.
router.post('/send', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const to = str(req.body?.to);
  const subject = str(req.body?.subject) ?? '(no subject)';
  const body = str(req.body?.body) ?? '';
  if (!to) {
    res.status(400).json({ error: 'recipient (to) is required' });
    return;
  }
  const id = newId('MAIL-SENT');
  insertEmail(id, userId, 'sent', ownerEmail(userId), to, subject, body, true);
  const inboxId = deliverToRecipientInbox(ownerEmail(userId), to, subject, body);
  recordEmailOp(
    'send_email', id, userId, to,
    `[ui] User sent email to=${to} subject="${subject}"`,
  );
  logger.info('[API] send_email (ui): -> %s (delivered=%s)', to, inboxId !== null);
  res.json({ ok: true, id, to, subject, delivered: inboxId !== null });
});

// Save a draft.
router.post('/drafts', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const to = str(req.body?.to) ?? '';
  const subject = str(req.body?.subject) ?? '(no subject)';
  const body = str(req.body?.body) ?? '';
  const id = newId('MAIL-DRAFT');
  insertEmail(id, userId, 'drafts', ownerEmail(userId), to, subject, body, true);
  logger.info('[API] draft saved: %s', id);
  res.json({ ok: true, id });
});

// Bulk operations on selected emails.
router.post('/emails/bulk', (req: Request, res: Response): void => {
  const userId = resolveUser(req);
  const ids: string[] = Array.isArray(req.body?.ids) ? req.body.ids.filter((x: unknown) => typeof x === 'string') : [];
  const action = str(req.body?.action);
  if (ids.length === 0 || !action) {
    res.status(400).json({ error: 'ids and action are required' });
    return;
  }

  let affected = 0;
  for (const id of ids) {
    const email = findEmailById(id);
    if (!email || email.ownerUserId !== userId) continue;
    switch (action) {
      case 'delete':
        moveEmailToFolder(id, 'trash');
        recordEmailOp('delete_email', id, userId, null, `[ui] User bulk-deleted emailId=${id}`);
        affected += 1;
        break;
      case 'read':
        setEmailRead(id, true);
        affected += 1;
        break;
      case 'unread':
        setEmailRead(id, false);
        affected += 1;
        break;
      case 'star':
        setEmailStarred(id, true);
        affected += 1;
        break;
      case 'unstar':
        setEmailStarred(id, false);
        affected += 1;
        break;
      case 'move': {
        const target = str(req.body?.folder);
        if (target && VALID_FOLDERS.includes(target as EmailFolder)) {
          moveEmailToFolder(id, target as EmailFolder);
          affected += 1;
        }
        break;
      }
      default:
        break;
    }
  }
  res.json({ ok: true, action, affected });
});

export default router;
