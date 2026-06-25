import { TOOL_SCHEMA } from './toolSchema';
import {
  findEmailsByOwner,
  findEmailById,
  searchEmails as dbSearchEmails,
  markEmailRead,
  moveEmailToFolder,
  insertSentEmail,
} from '../models/emailModel';
import { findUserById } from '../models/userModel';
import { recordEmailOp } from '../services/auditService';
import { Email, EmailFolder } from '../types';
import logger from '../logger';

export { TOOL_SCHEMA };

type ToolArgs = Record<string, unknown>;

const VALID_FOLDERS: EmailFolder[] = ['inbox', 'sent', 'trash'];

export function dispatch(
  functionName: string,
  args: ToolArgs,
  sessionUserId: string,
): string {
  switch (functionName) {
    case 'list_emails':   return toolListEmails(args, sessionUserId);
    case 'read_email':    return toolReadEmail(args, sessionUserId);
    case 'send_email':    return toolSendEmail(args, sessionUserId);
    case 'forward_email': return toolForwardEmail(args, sessionUserId);
    case 'delete_email':  return toolDeleteEmail(args, sessionUserId);
    case 'search_emails': return toolSearchEmails(args, sessionUserId);
    default:              return `Unknown tool: ${functionName}`;
  }
}

function str(val: unknown): string | null {
  if (typeof val === 'string' && val.trim().length > 0) return val.trim();
  return null;
}

function ownerEmail(sessionUserId: string): string {
  return findUserById(sessionUserId)?.email ?? `${sessionUserId}@corp.com`;
}

function newSentId(): string {
  return `MAIL-SENT-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function summarizeEmail(e: Email): string {
  const flag = e.isRead ? ' ' : '*';
  return `${flag} [${e.id}] from ${e.fromAddr} — "${e.subject}" (${e.folder}, ${e.createdAt.slice(0, 10)})`;
}

function toolListEmails(args: ToolArgs, sessionUserId: string): string {
  const requested = str(args['folder']);
  const folder: EmailFolder =
    requested && (VALID_FOLDERS as string[]).includes(requested)
      ? (requested as EmailFolder)
      : 'inbox';

  logger.info('[TOOL] list_emails: session=%s folder=%s', sessionUserId, folder);

  const emails = findEmailsByOwner(sessionUserId, folder);
  if (emails.length === 0) return `No emails found in ${folder}.`;

  return `Emails in ${folder} (${emails.length} total):\n` +
    emails.map(summarizeEmail).join('\n');
}

function toolReadEmail(args: ToolArgs, sessionUserId: string): string {
  const emailId = str(args['emailId']);
  if (!emailId) return 'Error: emailId is required.';

  logger.info('[TOOL] read_email: session=%s emailId=%s', sessionUserId, emailId);

  const email = findEmailById(emailId);
  if (!email) return `Email ${emailId} not found.`;

  markEmailRead(emailId);

  // NOTE: the full body is returned verbatim into the model context — this is
  // where an indirect prompt-injection payload hidden in an email body enters.
  return [
    `Email: ${email.id}`,
    `  Folder:  ${email.folder}`,
    `  From:    ${email.fromAddr}`,
    `  To:      ${email.toAddr}`,
    `  Date:    ${email.createdAt.slice(0, 10)}`,
    `  Subject: ${email.subject}`,
    '',
    email.body,
  ].join('\n');
}

function toolSendEmail(args: ToolArgs, sessionUserId: string): string {
  const to      = str(args['to']);
  const subject = str(args['subject']) ?? '(no subject)';
  const body    = str(args['body']) ?? '';
  if (!to) return 'Error: recipient (to) is required.';

  logger.warn('[TOOL] send_email: session=%s to=%s', sessionUserId, to);

  const id = newSentId();
  insertSentEmail(id, sessionUserId, ownerEmail(sessionUserId), to, subject, body);
  recordEmailOp(
    'send_email', id, sessionUserId, to,
    `Sent email to=${to} subject="${subject}"`,
  );
  return `Email sent to ${to} (subject: "${subject}"). Saved as ${id} in your sent folder.`;
}

function toolForwardEmail(args: ToolArgs, sessionUserId: string): string {
  const emailId = str(args['emailId']);
  const to      = str(args['to']);
  if (!emailId) return 'Error: emailId is required.';
  if (!to)      return 'Error: recipient (to) is required.';

  logger.warn('[TOOL] forward_email: session=%s emailId=%s to=%s', sessionUserId, emailId, to);

  const original = findEmailById(emailId);
  if (!original) return `Email ${emailId} not found.`;

  const id = newSentId();
  const subject = `Fwd: ${original.subject}`;
  const body = [
    `---------- Forwarded message ----------`,
    `From: ${original.fromAddr}`,
    `Date: ${original.createdAt}`,
    `Subject: ${original.subject}`,
    '',
    original.body,
  ].join('\n');
  insertSentEmail(id, sessionUserId, ownerEmail(sessionUserId), to, subject, body);
  recordEmailOp(
    'forward_email', emailId, sessionUserId, to,
    `Forwarded emailId=${emailId} to=${to}`,
  );
  return `Email ${emailId} forwarded to ${to}. Saved as ${id} in your sent folder.`;
}

function toolDeleteEmail(args: ToolArgs, sessionUserId: string): string {
  const emailId = str(args['emailId']);
  if (!emailId) return 'Error: emailId is required.';

  logger.warn('[TOOL] delete_email: session=%s emailId=%s', sessionUserId, emailId);

  const email = findEmailById(emailId);
  if (!email) return `Email ${emailId} not found.`;

  moveEmailToFolder(emailId, 'trash');
  recordEmailOp(
    'delete_email', emailId, sessionUserId, null,
    `Deleted (moved to trash) emailId=${emailId}`,
  );
  return `Email ${emailId} has been moved to trash.`;
}

function toolSearchEmails(args: ToolArgs, sessionUserId: string): string {
  const query = str(args['query']);
  if (!query) return 'Error: A search query is required.';

  logger.info('[TOOL] search_emails: session=%s query=%s', sessionUserId, query);

  const results = dbSearchEmails(sessionUserId, query);
  if (results.length === 0) return `No emails found matching "${query}".`;

  return `Search results for "${query}" (${results.length} found):\n` +
    results.map(summarizeEmail).join('\n');
}
