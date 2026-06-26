import { getDb } from '../database/db';
import { AuditOperation, EmailAuditLog } from '../types';

// UI-initiated operations tag their `detail` with this prefix so the security
// probe can exclude human clicks and count only covert agent actions.
export const UI_DETAIL_PREFIX = '[ui]';

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

// Agent-only view: drop UI-initiated (human) operations so the probe attributes
// E5 to the agent, not to manual clicks in the mailbox UI.
export function getAgentEmailOps(): EmailAuditLog[] {
  return getAllEmailOps().filter((op) => !op.detail.startsWith(UI_DETAIL_PREFIX));
}

// Clear the audit trail — call before a scan run so the probe only sees the
// current evaluation's operations, never stale entries from a previous scan.
export function clearEmailOps(): number {
  return getDb().prepare(`DELETE FROM email_audit`).run().changes;
}
