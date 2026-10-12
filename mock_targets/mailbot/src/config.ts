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

// Vendor-specific request fields (e.g. DeepSeek V4 / Qwen3.5 `thinking` switch)
// merged into every chat/completions body. Must be a JSON object; anything else
// is rejected at startup so a typo cannot silently change the experiment.
function parseExtraRequestBody(raw: string | undefined): Record<string, unknown> {
  if (!raw || !raw.trim()) return {};
  const parsed: unknown = JSON.parse(raw);
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('TARGET_EXTRA_BODY_JSON must be a JSON object');
  }
  return parsed as Record<string, unknown>;
}

const DEFAULT_TEMPERATURE = 0.2;
const DEFAULT_MAX_TOKENS = 1024;

// Sampling parameters are experimental factors that /health reports for the run
// manifest. A value that does not parse, or that the chat API would reject,
// falls back to the default. Note 0 is a valid temperature, so no `||` here.
function parseTemperature(raw: string | undefined): number {
  const value = parseFloat(raw ?? '');
  return Number.isFinite(value) && value >= 0 ? value : DEFAULT_TEMPERATURE;
}

function parseMaxTokens(raw: string | undefined): number {
  const value = parseInt(raw ?? '', 10);
  return value > 0 ? value : DEFAULT_MAX_TOKENS;
}

export const config = {
  port: parseInt(process.env['PORT'] ?? '8003', 10),
  openaiApiKey: process.env['OPENAI_API_KEY'] ?? 'change-me',
  openaiBaseUrl: (process.env['OPENAI_BASE_URL'] ?? 'https://api.openai.com/v1').replace(/\/+$/, ''),
  openaiModel: process.env['TARGET_MODEL'] ?? process.env['OPENAI_MODEL'] ?? 'gpt-4o',
  extraRequestBody: parseExtraRequestBody(process.env['TARGET_EXTRA_BODY_JSON']),
  dbPath: process.env['DB_PATH'] ?? path.resolve(process.cwd(), 'mailbot.db'),
  systemPromptPath: path.resolve(process.cwd(), 'src', 'prompts', 'system.txt'),
  systemPromptUndefendedPath: path.resolve(process.cwd(), 'src', 'prompts', 'system_undefended.txt'),
  temperature: parseTemperature(process.env['TARGET_TEMPERATURE']),
  maxTokens: parseMaxTokens(process.env['TARGET_MAX_TOKENS']),
  maxToolRounds: 6,
} as const;
