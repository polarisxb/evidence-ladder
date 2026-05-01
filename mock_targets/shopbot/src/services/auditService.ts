import { getDb } from '../database/db';
import { AuditLog, AuditOperation, CouponUseLog } from '../types';

interface RawAuditLog {
  id: number;
  operation: string;
  order_id: string | null;
  session_user_id: string;
  target_user_id: string | null;
  detail: string;
  executed_at: string;
}

interface RawCouponUseLog {
  id: number;
  coupon_code: string;
  order_id: string;
  session_user_id: string;
  discount_applied: number;
  executed_at: string;
}

export function recordOrderOp(
  operation: AuditOperation,
  orderId: string | null,
  sessionUserId: string,
  targetUserId: string | null,
  detail: string,
): void {
  const now = new Date().toISOString();
  getDb().prepare(`
    INSERT INTO audit_logs (operation, order_id, session_user_id, target_user_id, detail, executed_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(operation, orderId, sessionUserId, targetUserId, detail, now);
}

export function recordCouponUse(
  couponCode: string,
  orderId: string,
  sessionUserId: string,
  discountApplied: number,
): void {
  const now = new Date().toISOString();
  getDb().prepare(`
    INSERT INTO coupon_use_logs (coupon_code, order_id, session_user_id, discount_applied, executed_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(couponCode, orderId, sessionUserId, discountApplied, now);
}

export function getAllOrderOps(): AuditLog[] {
  return getDb().prepare<[], RawAuditLog>(`
    SELECT id, operation, order_id, session_user_id, target_user_id, detail, executed_at
    FROM audit_logs ORDER BY executed_at DESC
  `).all().map((r) => ({
    id: r.id,
    operation: r.operation as AuditOperation,
    orderId: r.order_id,
    sessionUserId: r.session_user_id,
    targetUserId: r.target_user_id,
    detail: r.detail,
    executedAt: r.executed_at,
  }));
}

export function getAllCouponUses(): CouponUseLog[] {
  return getDb().prepare<[], RawCouponUseLog>(`
    SELECT id, coupon_code, order_id, session_user_id, discount_applied, executed_at
    FROM coupon_use_logs ORDER BY executed_at DESC
  `).all().map((r) => ({
    id: r.id,
    couponCode: r.coupon_code,
    orderId: r.order_id,
    sessionUserId: r.session_user_id,
    discountApplied: r.discount_applied,
    executedAt: r.executed_at,
  }));
}
