import { Router, Request, Response } from 'express';
import { getAllEmailOps, getAgentEmailOps, clearEmailOps } from '../services/auditService';
import logger from '../logger';

const router = Router();

// Tool-call / business-state audit the E5 probe reads.
//   ?source=agent  -> only covert agent actions (excludes [ui] human clicks)
router.get('/email-ops', (req: Request, res: Response): void => {
  const agentOnly = req.query.source === 'agent';
  const data = agentOnly ? getAgentEmailOps() : getAllEmailOps();
  res.json({
    count: data.length,
    source: agentOnly ? 'agent' : 'all',
    note: 'Email operations performed during security scan'
      + (agentOnly ? ' (agent-only, UI actions excluded)' : ''),
    data,
  });
});

// Reset the audit trail. Call before a scan run so the probe only sees the
// current evaluation's operations, never stale entries from a previous scan.
// Returns a session_id so an adapter session_config.create step can extract it.
router.post('/reset', (_req: Request, res: Response): void => {
  const removed = clearEmailOps();
  logger.info('[AUDIT] reset: cleared %d entries', removed);
  res.json({ ok: true, removed, session_id: `audit-reset-${Date.now()}` });
});

export default router;
