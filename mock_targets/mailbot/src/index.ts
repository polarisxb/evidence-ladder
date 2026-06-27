import express from 'express';
import * as path from 'path';
import { config } from './config';
import { getDb } from './database/db';
import chatRoute from './routes/chatRoute';
import healthRoute from './routes/healthRoute';
import auditRoute from './routes/auditRoute';
import emailRoute from './routes/emailRoute';
import authRoute from './routes/authRoute';
import { attachSession } from './middleware/auth';
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
});
