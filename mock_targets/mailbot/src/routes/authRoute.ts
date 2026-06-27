import { Router, Request, Response } from 'express';
import { body, validationResult } from 'express-validator';
import bcrypt from 'bcryptjs';
import {
  findUserById,
  findUserByEmail,
  getPasswordHash,
  createUser,
} from '../models/userModel';
import { createSession, destroySession } from '../services/sessionService';
import { readSessionToken } from '../middleware/auth';
import logger from '../logger';

const router = Router();

const registerValidation = [
  body('name').isString().trim().notEmpty().isLength({ max: 60 })
    .withMessage('name is required (max 60 chars)'),
  body('email').isString().trim().isEmail().isLength({ max: 120 })
    .withMessage('a valid email is required'),
  body('password').isString().isLength({ min: 6, max: 128 })
    .withMessage('password must be 6-128 characters'),
];

const loginValidation = [
  body('email').isString().trim().isEmail().withMessage('a valid email is required'),
  body('password').isString().notEmpty().withMessage('password is required'),
];

// Derive a route-safe userId (matches /^[A-Za-z0-9_-]+$/) from the email
// local part, guaranteeing uniqueness against existing accounts.
function deriveUserId(email: string): string {
  const base = email.split('@')[0].replace(/[^A-Za-z0-9_-]/g, '').toLowerCase() || 'user';
  let candidate = base;
  let n = 1;
  while (findUserById(candidate)) {
    candidate = `${base}${n}`;
    n += 1;
  }
  return candidate;
}

router.post('/register', registerValidation, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    res.status(400).json({ error: errors.array()[0].msg });
    return;
  }
  const name = String(req.body.name).trim();
  const email = String(req.body.email).trim().toLowerCase();
  const password = String(req.body.password);

  if (findUserByEmail(email)) {
    res.status(409).json({ error: '该邮箱已被注册，请直接登录' });
    return;
  }

  const id = deriveUserId(email);
  const passwordHash = bcrypt.hashSync(password, 10);
  const user = createUser(id, name, email, passwordHash);
  const token = createSession(user.id);
  logger.info('[AUTH] register: %s (%s)', user.id, user.email);
  res.status(201).json({ token, user });
});

router.post('/login', loginValidation, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    res.status(400).json({ error: errors.array()[0].msg });
    return;
  }
  const email = String(req.body.email).trim().toLowerCase();
  const password = String(req.body.password);

  const user = findUserByEmail(email);
  const hash = user ? getPasswordHash(user.id) : null;
  if (!user || !hash || !bcrypt.compareSync(password, hash)) {
    res.status(401).json({ error: '邮箱或密码不正确' });
    return;
  }
  const token = createSession(user.id);
  logger.info('[AUTH] login: %s (%s)', user.id, user.email);
  res.json({ token, user });
});

// Validate the current session token and return the logged-in user.
router.get('/session', (req: Request, res: Response): void => {
  const user = (req as Request & { authUser?: ReturnType<typeof findUserById> }).authUser;
  if (!user) {
    res.status(401).json({ error: 'not authenticated' });
    return;
  }
  res.json({ user });
});

router.post('/logout', (req: Request, res: Response): void => {
  destroySession(readSessionToken(req));
  res.json({ ok: true });
});

export default router;
