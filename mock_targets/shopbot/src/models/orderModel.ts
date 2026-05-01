import { getDb } from '../database/db';
import { Order, OrderItem, OrderStatus } from '../types';

interface RawOrder {
  id: string;
  userId: string;
  status: OrderStatus;
  items: string;
  total: number;
  shippingAddress: string;
  trackingNumber: string | null;
  createdAt: string;
  updatedAt: string;
}

function mapRow(row: RawOrder): Order {
  return {
    ...row,
    items: JSON.parse(row.items) as OrderItem[],
  };
}

export function findOrdersByUserId(userId: string): Order[] {
  const rows = getDb().prepare<[string], RawOrder>(`
    SELECT id, user_id as userId, status, items, total,
           shipping_address as shippingAddress, tracking_number as trackingNumber,
           created_at as createdAt, updated_at as updatedAt
    FROM orders WHERE user_id = ?
    ORDER BY created_at DESC
  `).all(userId);
  return rows.map(mapRow);
}

export function findOrderById(orderId: string): Order | null {
  const row = getDb().prepare<[string], RawOrder>(`
    SELECT id, user_id as userId, status, items, total,
           shipping_address as shippingAddress, tracking_number as trackingNumber,
           created_at as createdAt, updated_at as updatedAt
    FROM orders WHERE id = ?
  `).get(orderId);
  return row ? mapRow(row) : null;
}

export function updateOrderStatus(orderId: string, newStatus: OrderStatus): boolean {
  const now = new Date().toISOString();
  const result = getDb().prepare<[string, string, string]>(`
    UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
  `).run(newStatus, now, orderId);
  return result.changes > 0;
}

export function updateShippingAddress(orderId: string, newAddress: string): boolean {
  const now = new Date().toISOString();
  const result = getDb().prepare<[string, string, string]>(`
    UPDATE orders SET shipping_address = ?, updated_at = ? WHERE id = ?
  `).run(newAddress, now, orderId);
  return result.changes > 0;
}

export function applyDiscount(orderId: string, discountAmount: number): boolean {
  const now = new Date().toISOString();
  const result = getDb().prepare<[number, string, string]>(`
    UPDATE orders
    SET total = MAX(0, total - ?), updated_at = ?
    WHERE id = ? AND status NOT IN ('CANCELLED','REFUNDED')
  `).run(discountAmount, now, orderId);
  return result.changes > 0;
}
