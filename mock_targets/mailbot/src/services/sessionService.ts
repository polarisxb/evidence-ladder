import { randomBytes } from 'crypto';

// In-memory session store. Tokens map to a userId for the lifetime of the
// process. This is intentionally lightweight — MailBot is a demo target, not
// a production identity provider. On restart, clients simply log in again.
const sessions = new Map<string, string>();

export function createSession(userId: string): string {
  const token = randomBytes(24).toString('hex');
  sessions.set(token, userId);
  return token;
}

export function resolveSession(token: string | undefined | null): string | null {
  if (!token) return null;
  return sessions.get(token) ?? null;
}

export function destroySession(token: string | undefined | null): void {
  if (token) sessions.delete(token);
}
