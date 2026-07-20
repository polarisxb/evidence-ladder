import * as fs from 'fs';
import * as path from 'path';

function loadEnvFile(envPath: string): void {
  if (!fs.existsSync(envPath)) return;
  const lines = fs.readFileSync(envPath, 'utf-8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx === -1) continue;
    const key = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
    if (key && !(key in process.env)) {
      process.env[key] = value;
    }
  }
}

// Local .env takes priority (loaded first), root .env fills missing values.
loadEnvFile(path.resolve(process.cwd(), '.env'));
loadEnvFile(path.resolve(process.cwd(), '..', '..', '.env'));

export const config = {
  port: parseInt(process.env['PORT'] ?? '8003', 10),
  openaiApiKey: process.env['OPENAI_API_KEY'] ?? 'change-me',
  openaiBaseUrl: (process.env['OPENAI_BASE_URL'] ?? 'https://api.openai.com/v1').replace(/\/+$/, ''),
  openaiModel: process.env['TARGET_MODEL'] ?? process.env['OPENAI_MODEL'] ?? 'gpt-4o',
  dbPath: process.env['DB_PATH'] ?? path.resolve(process.cwd(), 'mailbot.db'),
  // Defense level is swappable via SYSTEM_PROMPT_PATH (relative to cwd) so the
  // same agent can be run hardened (default) or intentionally vulnerable for
  // security demos. Defaults to the hardened prompt.
  systemPromptPath: process.env['SYSTEM_PROMPT_PATH']
    ? path.resolve(process.cwd(), process.env['SYSTEM_PROMPT_PATH'])
    : path.resolve(process.cwd(), 'src', 'prompts', 'system.txt'),
  maxToolRounds: 6,
  // Fixture switch for the concealed-success demo (see chatService). When on,
  // the agent deterministically exfiltrates + hides it; NOT real model behavior.
  compromisedDemo: process.env['COMPROMISED_DEMO'] === '1',
} as const;
