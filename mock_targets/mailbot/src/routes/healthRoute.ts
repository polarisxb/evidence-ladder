import { Router, Request, Response } from 'express';

import { config } from '../config';

const router = Router();

router.get('/', (_req: Request, res: Response): void => {
  res.json({
    status: 'UP',
    service: 'MailBot',
    platform: 'Corp Mail',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    // Non-secret model configuration so an evaluation harness can record the
    // exact target setup in its run manifest instead of inferring it.
    model: {
      name: config.openaiModel,
      baseUrl: config.openaiBaseUrl,
      extraRequestBody: config.extraRequestBody,
      temperature: config.temperature,
      maxTokens: config.maxTokens,
      maxToolRounds: config.maxToolRounds,
    },
  });
});

export default router;
