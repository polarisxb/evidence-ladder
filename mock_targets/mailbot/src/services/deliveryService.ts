import { findUserByEmail } from '../models/userModel';
import { insertEmail } from '../models/emailModel';
import logger from '../logger';

// Extracts a bare email address from a recipient string that may be in
// "Display Name <user@corp.com>" form or just "user@corp.com".
export function normalizeAddress(raw: string): string {
  const angle = raw.match(/<([^>]+)>/);
  const candidate = angle ? angle[1] : raw;
  const token = candidate.split(/[\s,;]+/).find((t) => t.includes('@'));
  return (token ?? candidate).trim().toLowerCase();
}

// If the recipient address belongs to a known user, drop a copy of the
// message into that user's inbox so cross-user delivery actually works.
// Returns the new inbox email id, or null when the recipient is external
// (e.g. the attacker exfil address in the injection demo — left untouched).
export function deliverToRecipientInbox(
  fromAddr: string,
  toAddr: string,
  subject: string,
  body: string,
): string | null {
  const recipient = findUserByEmail(normalizeAddress(toAddr));
  if (!recipient) return null;

  const id = `MAIL-INBOX-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  insertEmail(id, recipient.id, 'inbox', fromAddr, recipient.email, subject, body, false);
  logger.info('[DELIVERY] delivered to inbox of %s (%s)', recipient.id, recipient.email);
  return id;
}
