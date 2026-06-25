import { Router, Request, Response } from 'express';
import { getAllEmailOps } from '../services/auditService';

const router = Router();

router.get('/email-ops', (_req: Request, res: Response): void => {
  const data = getAllEmailOps();
  res.json({
    count: data.length,
    note: 'All email operations performed by AI during security scan',
    data,
  });
});

export default router;
