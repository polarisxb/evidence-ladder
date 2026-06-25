import { Request, Response, NextFunction } from 'express';
import logger from '../logger';

export function errorHandler(
  err: unknown,
  _req: Request,
  res: Response,
  _next: NextFunction,
): void {
  const msg = err instanceof Error ? err.message : String(err);
  logger.error('[ERROR] Unhandled exception: %s', msg);
  res.status(500).json({ error: 'An internal error occurred. Please try again later.' });
}
