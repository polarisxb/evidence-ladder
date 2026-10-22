import express from 'express';
import { createHash } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { config } from './config';
import { getDb } from './database/db';
import chatRoute from './routes/chatRoute';
import healthRoute from './routes/healthRoute';
import auditRoute from './routes/auditRoute';
import emailRoute from './routes/emailRoute';
import authRoute from './routes/authRoute';
import injectRoute from './routes/injectRoute';
import { attachSession } from './middleware/auth';
import { DEFENSE_LEVELS, systemPromptPathFor } from './services/chatService';
import { errorHandler } from './middleware/errorHandler';
import logger from './logger';

const app = express();

const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');

app.use(express.json({ limit: '64kb' }));

app.use((req, _res, next) => {
  logger.info('[REQ] %s %s', req.method, req.path);
  next();
});

// Resolve the session token (if any) into req.authUser before routes run.
// Non-blocking: the agent /chat path sends no token and is unaffected.
app.use(attachSession);

app.use('/health',   healthRoute);
app.use('/chat',     chatRoute);
app.use('/audit',    auditRoute);
app.use('/inject',   injectRoute);  // red-team indirect-injection seeder (mock only)
app.use('/api/auth', authRoute);
app.use('/api',      emailRoute);

// Static frontend (the mailbox UI). Served from the same Express process so the
// whole service — UI, /chat, /audit — runs on a single port.
app.use(express.static(PUBLIC_DIR));

app.get('/', (_req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

app.use(errorHandler);

getDb();

app.listen(config.port, () => {
  logger.info('[APP] MailBot listening on port %d', config.port);
  logger.info('[APP] GET /  (mailbox UI)  |  POST /chat  |  GET /api/emails  |  GET /health  |  GET /audit/email-ops');
  // Hashes only, never prompt text: the defended prompt contains the canary.
  for (const level of DEFENSE_LEVELS) {
    const promptPath = systemPromptPathFor(level);
    const sha256 = fs.existsSync(promptPath)
      ? createHash('sha256').update(fs.readFileSync(promptPath)).digest('hex')
      : 'MISSING';
    logger.info('[APP] system prompt defense=%s path=%s sha256=%s', level, promptPath, sha256);
  }
});
