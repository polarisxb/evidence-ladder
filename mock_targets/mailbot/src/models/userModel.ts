import { getDb } from '../database/db';
import { User } from '../types';

export function findUserById(userId: string): User | null {
  const stmt = getDb().prepare<[string], User>(`
    SELECT id, name, email, created_at as createdAt
    FROM users WHERE id = ?
  `);
  return stmt.get(userId) ?? null;
}

// Case-insensitive lookup by email address. Accepts a bare address
// ("bob@corp.com") — callers should normalize display-name forms first.
export function findUserByEmail(email: string): User | null {
  const stmt = getDb().prepare<[string], User>(`
    SELECT id, name, email, created_at as createdAt
    FROM users WHERE lower(email) = lower(?)
  `);
  return stmt.get(email.trim()) ?? null;
}

// Returns the stored bcrypt hash for a user, or null if the account has
// no password (e.g. legacy rows created before auth existed).
export function getPasswordHash(userId: string): string | null {
  const row = getDb()
    .prepare<[string], { passwordHash: string | null }>(`
      SELECT password_hash as passwordHash FROM users WHERE id = ?
    `)
    .get(userId);
  return row?.passwordHash ?? null;
}

export function createUser(
  id: string,
  name: string,
  email: string,
  passwordHash: string,
): User {
  const now = new Date().toISOString();
  getDb()
    .prepare<[string, string, string, string, string]>(`
      INSERT INTO users (id, name, email, password_hash, created_at)
      VALUES (?, ?, ?, ?, ?)
    `)
    .run(id, name, email, passwordHash, now);
  return { id, name, email, createdAt: now };
}
