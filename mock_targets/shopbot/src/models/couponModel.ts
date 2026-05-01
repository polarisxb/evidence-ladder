import { getDb } from '../database/db';
import { CouponCode } from '../types';

interface RawCoupon {
  code: string;
  discountType: string;
  discountValue: number;
  minOrderAmount: number;
  isInternal: number;
  description: string;
  usageCount: number;
}

export function findCouponByCode(code: string): CouponCode | null {
  const row = getDb().prepare<[string], RawCoupon>(`
    SELECT code,
           discount_type      as discountType,
           discount_value     as discountValue,
           min_order_amount   as minOrderAmount,
           is_internal        as isInternal,
           description,
           usage_count        as usageCount
    FROM coupon_codes WHERE code = ?
  `).get(code);
  if (!row) return null;
  return row as CouponCode;
}

export function incrementCouponUsage(code: string): void {
  getDb().prepare<[string]>(`
    UPDATE coupon_codes SET usage_count = usage_count + 1 WHERE code = ?
  `).run(code);
}
