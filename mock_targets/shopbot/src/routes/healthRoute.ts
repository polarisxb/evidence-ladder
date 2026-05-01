import { Router, Request, Response } from 'express';

const router = Router();

router.get('/', (_req: Request, res: Response): void => {
  res.json({
    status: 'UP',
    service: 'ShopBot',
    platform: 'ShopNow Mall',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
  });
});

export default router;
