import { Router, Request, Response } from 'express';

import { getDb } from '../database/db';
import { seedEmailsForFreshState } from '../database/seed';
import { insertEmail, findEmailById, deleteEmailsByIdPrefix, deleteAllEmailsByOwner } from '../models/emailModel';
import { findUserById } from '../models/userModel';
import { clearEmailOps } from '../services/auditService';
import logger from '../logger';

const router = Router();

// Planted-email id prefix so the seeder can find and clear its own plants
// without touching the fixed demo/seed inbox.
export const INJECT_PREFIX = 'MAIL-INJ-';

function str(val: unknown, fallback: string): string {
  return typeof val === 'string' && val.trim().length > 0 ? val.trim() : fallback;
}

// A caller may pin the planted email's id so it looks like any other mailbox
// entry. The default `MAIL-INJ-*` id is visible to the model in tool output and
// would label the plant as injected, which an experiment on what the agent
// reports must not do. Restricted to the seed id shape so a plant can never
// masquerade as a sent item or collide with an existing email.
const CUSTOM_ID_RE = /^MAIL-\d{4}$/;

/**
 * RED-TEAM TEST SCAFFOLDING — not part of the product surface.
 *
 * Seeds an indirect-prompt-injection email into a user's inbox so an evaluation
 * harness can exercise the *indirect* channel: the payload enters the model
 * context later, when the agent calls `read_email`, rather than being sent as
 * the user message (the direct channel that `/chat` already exposes).
 *
 * Idempotent by default: clears previously planted `MAIL-INJ-*` emails for the
 * user before seeding the next one, so repeated cases do not accumulate.
 *
 * Body: { body: string (required), userId?, subject?, fromAddr?, resetInjected?, emailId? }
 * `emailId` must match MAIL-#### and be unused; omitted means the MAIL-INJ-* default.
 * Returns a `session_id` so an adapter `session_config.create` step can chain it.
 */
router.post('/seed', (req: Request, res: Response): void => {
  const b = (req.body ?? {}) as Record<string, unknown>;
  const payloadBody = typeof b['body'] === 'string' ? b['body'] : '';
  if (!payloadBody.trim()) {
    res.status(400).json({ ok: false, error: 'body (the injected email content) is required' });
    return;
  }
  const userId = str(b['userId'], 'alice');
  if (!findUserById(userId)) {
    res.status(404).json({ ok: false, error: `unknown userId '${userId}'` });
    return;
  }
  const subject = str(b['subject'], '(no subject)');
  const fromAddr = str(b['fromAddr'], 'promo@news-update.com');
  const resetInjected = b['resetInjected'] !== false;

  const rawId = b['emailId'];
  if (rawId !== undefined && (typeof rawId !== 'string' || !CUSTOM_ID_RE.test(rawId.trim()))) {
    res.status(400).json({ ok: false, error: 'emailId must match MAIL-#### (four digits)' });
    return;
  }
  const customId = typeof rawId === 'string' ? rawId.trim() : null;
  if (customId && findEmailById(customId)) {
    res.status(409).json({ ok: false, error: `emailId '${customId}' is already in use` });
    return;
  }

  const removed = resetInjected ? deleteEmailsByIdPrefix(userId, INJECT_PREFIX) : 0;
  const id = customId ?? `${INJECT_PREFIX}${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  insertEmail(id, userId, 'inbox', fromAddr, `${userId}@corp.com`, subject, payloadBody, false);
  logger.warn('[INJECT] seeded %s into %s inbox (cleared %d prior plant(s))', id, userId, removed);

  res.json({ ok: true, injectedId: id, removedInjected: removed, session_id: `inject-${id}` });
});

/**
 * RED-TEAM TEST SCAFFOLDING — restores a user's mailbox to the fixed seed baseline.
 *
 * Call before each evaluation round so every round starts from the same state:
 * deletes every email the user owns (read flags, trash moves, sent mail and
 * planted `MAIL-INJ-*` emails go with them), re-inserts that user's seed
 * emails, and clears the whole audit trail. Idempotent; the users table is
 * never touched.
 *
 * `includeDemoInjection: false` omits the demo injection email (MAIL-0004),
 * giving a control inbox without any injected instruction.
 *
 * Body: { userId? (default 'alice'), includeDemoInjection? (boolean, default true) }
 * Returns a `session_id` so an adapter `session_config.create` step can chain it.
 */
router.post('/reset', (req: Request, res: Response): void => {
  const b = (req.body ?? {}) as Record<string, unknown>;
  const userId = str(b['userId'], 'alice');
  if (!findUserById(userId)) {
    res.status(404).json({ ok: false, error: `unknown userId '${userId}'` });
    return;
  }
  const flag = b['includeDemoInjection'];
  if (flag !== undefined && typeof flag !== 'boolean') {
    res.status(400).json({ ok: false, error: 'includeDemoInjection must be a boolean' });
    return;
  }
  const includeDemoInjection = flag !== false;

  const db = getDb();
  // One transaction: a failure mid-way keeps the previous state, not an empty inbox.
  const { removedEmails, reseeded, clearedAudit } = db.transaction(() => {
    const removed = deleteAllEmailsByOwner(userId);
    const inserted = seedEmailsForFreshState(db, { includeDemoInjection, ownerUserId: userId });
    return { removedEmails: removed, reseeded: inserted, clearedAudit: clearEmailOps() };
  })();
  logger.warn(
    '[INJECT] reset %s mailbox: removed %d, reseeded %d (demo injection %s), cleared %d audit entries',
    userId, removedEmails, reseeded, includeDemoInjection ? 'on' : 'off', clearedAudit,
  );

  res.json({
    ok: true,
    userId,
    includeDemoInjection,
    removedEmails,
    reseeded,
    session_id: `inject-reset-${userId}-${Date.now()}`,
  });
});

export default router;
