import { getDb } from '../database/db';
import { User } from '../types';

export function findUserById(userId: string): User | null {
  const stmt = getDb().prepare<[string], User>(`
    SELECT id, name, email, tier, created_at as createdAt
    FROM users WHERE id = ?
  `);
  return stmt.get(userId) ?? null;
}
