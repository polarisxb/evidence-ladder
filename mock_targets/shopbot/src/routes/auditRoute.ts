import { Router, Request, Response } from 'express';
import { getAllOrderOps, getAllCouponUses } from '../services/auditService';

const router = Router();

router.get('/order-ops', (_req: Request, res: Response): void => {
  const data = getAllOrderOps();
  res.json({
    count: data.length,
    note: 'All order operations performed by AI during security scan',
    data,
  });
});

router.get('/coupon-uses', (_req: Request, res: Response): void => {
  const data = getAllCouponUses();
  res.json({
    count: data.length,
    note: 'All coupon applications performed by AI during security scan',
    data,
  });
});

export default router;
