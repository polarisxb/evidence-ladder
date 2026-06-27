import { Request, Response, NextFunction } from 'express';
import { resolveSession } from '../services/sessionService';
import { findUserById } from '../models/userModel';
import { User } from '../types';

// Augment Express' Request so handlers can read the resolved session user
// in a type-safe way.
declare module 'express-serve-static-core' {
  interface Request {
    authUser?: User | null;
  }
}

// Reads the opaque session token from either the Authorization: Bearer header
// or the x-session-token header.
export function readSessionToken(req: Request): string | null {
  const header = req.headers['authorization'];
  if (typeof header === 'string' && header.toLowerCase().startsWith('bearer ')) {
    return header.slice(7).trim();
  }
  const alt = req.headers['x-session-token'];
  if (typeof alt === 'string' && alt.trim()) return alt.trim();
  return null;
}

// Non-blocking: attaches req.authUser when a valid session token is present.
// Routes decide whether authentication is required. This keeps the agent /chat
// path (which never sends a token) working exactly as before.
export function attachSession(req: Request, _res: Response, next: NextFunction): void {
  const userId = resolveSession(readSessionToken(req));
  req.authUser = userId ? findUserById(userId) : null;
  next();
}
