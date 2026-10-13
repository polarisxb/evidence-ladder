import { Router, Request, Response } from 'express';
import { body, validationResult } from 'express-validator';
import { chat, DEFENSE_LEVELS } from '../services/chatService';
import { ChatRequest, ChatMessage } from '../types';

const router = Router();

const chatValidation = [
  body('message')
    .isString()
    .trim()
    .notEmpty()
    .withMessage('message must be a non-empty string')
    .isLength({ max: 4000 })
    .withMessage('message must not exceed 4000 characters'),
  body('userId')
    .optional()
    .isString()
    .trim()
    .isLength({ max: 64 })
    .withMessage('userId must not exceed 64 characters')
    .matches(/^[A-Za-z0-9_-]+$/)
    .withMessage('userId contains invalid characters'),
  body('history')
    .optional()
    .isArray({ max: 40 })
    .withMessage('history must be an array of at most 40 messages'),
  body('history.*.role')
    .optional()
    .isIn(['user', 'assistant'])
    .withMessage('history messages must have role "user" or "assistant"'),
  body('history.*.content')
    .optional()
    .isString()
    .isLength({ max: 4000 })
    .withMessage('history message content must not exceed 4000 characters'),
];

router.post('/', chatValidation, async (req: Request, res: Response): Promise<void> => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    res.set('X-Provenance-Model-Invoked', 'false');
    res.set('X-Provenance-Evaluable', 'false');
    res.set('X-Provenance-Block-Reason', 'input_validation');
    res.status(400).json({ error: 'Validation failed', details: errors.array() });
    return;
  }

  const { message, userId = 'alice', history = [] } = req.body as ChatRequest;
  // Defense strength is a red-team experimental factor (query ?defense= or body).
  // An unknown value is rejected, not mapped to 'defended': a silent fallback
  // would run a different condition than the one the harness requested.
  const rawDefense: unknown = req.query.defense ?? (req.body as { defense?: unknown }).defense ?? 'defended';
  const defense = DEFENSE_LEVELS.find((level) => level === rawDefense);
  if (!defense) {
    res.set('X-Provenance-Model-Invoked', 'false');
    res.set('X-Provenance-Evaluable', 'false');
    res.set('X-Provenance-Block-Reason', 'input_validation');
    res.status(400).json({
      error: 'Validation failed',
      details: [{ msg: `defense must be one of ${DEFENSE_LEVELS.join(', ')}`, value: rawDefense }],
    });
    return;
  }
  const result = await chat(userId, message, history as ChatMessage[], defense);
  // Optional on ChatResult: absent means not shown to be evaluable.
  const evaluable = result.evaluable === true;
  res.set('X-Provenance-Model-Invoked', String(result.modelInvoked));
  res.set('X-Provenance-Defense', defense);
  res.set('X-Provenance-Post-Processed', String(result.postProcessed));
  res.set('X-Provenance-Evaluable', String(evaluable));
  if (result.blockReason) res.set('X-Provenance-Block-Reason', result.blockReason);
  if (result.postReason) res.set('X-Provenance-Post-Reason', result.postReason);
  if (req.query.format === 'json') {
    res.json({
      response: result.response,
      tool_calls: result.toolCalls ?? [],
      modelInvoked: result.modelInvoked,
      postProcessed: result.postProcessed,
      evaluable,
    });
  } else {
    res.type('text/plain').send(result.response);
  }
});

export default router;
