import { getDb } from '../database/db';
import { AuditOperation, EmailAuditLog } from '../types';

interface RawEmailAudit {
  id: number;
  operation: string;
  email_id: string | null;
  session_user_id: string;
  recipient: string | null;
  detail: string;
  executed_at: string;
}

export function recordEmailOp(
  operation: AuditOperation,
  emailId: string | null,
  sessionUserId: string,
  recipient: string | null,
  detail: string,
): void {
  const now = new Date().toISOString();
  getDb().prepare(`
    INSERT INTO email_audit (operation, email_id, session_user_id, recipient, detail, executed_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(operation, emailId, sessionUserId, recipient, detail, now);
}

export function getAllEmailOps(): EmailAuditLog[] {
  return getDb().prepare<[], RawEmailAudit>(`
    SELECT id, operation, email_id, session_user_id, recipient, detail, executed_at
    FROM email_audit ORDER BY executed_at DESC
  `).all().map((r) => ({
    id: r.id,
    operation: r.operation as AuditOperation,
    emailId: r.email_id,
    sessionUserId: r.session_user_id,
    recipient: r.recipient,
    detail: r.detail,
    executedAt: r.executed_at,
  }));
}
