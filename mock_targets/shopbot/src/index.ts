import express from 'express';
import { config } from './config';
import { getDb } from './database/db';
import chatRoute from './routes/chatRoute';
import healthRoute from './routes/healthRoute';
import auditRoute from './routes/auditRoute';
import { errorHandler } from './middleware/errorHandler';
import logger from './logger';

const app = express();

app.use(express.json({ limit: '64kb' }));

app.use((req, _res, next) => {
  logger.info('[REQ] %s %s', req.method, req.path);
  next();
});

app.use('/health', healthRoute);
app.use('/chat',   chatRoute);
app.use('/audit',  auditRoute);

app.use(errorHandler);

getDb();

app.listen(config.port, () => {
  logger.info('[APP] ShopBot listening on port %d', config.port);
  logger.info('[APP] POST /chat  |  GET /health  |  GET /audit/order-ops  |  GET /audit/coupon-uses');
});
