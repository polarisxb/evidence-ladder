const levels = { error: 0, warn: 1, info: 2, debug: 3 } as const;
type Level = keyof typeof levels;

function log(level: Level, message: string, ...args: unknown[]): void {
  const ts = new Date().toISOString();
  let msg = message;
  for (const arg of args) {
    msg = msg.replace('%s', String(arg)).replace('%d', String(arg));
  }
  const line = `${ts} [${level.toUpperCase().padEnd(5)}] ${msg}`;
  if (level === 'error' || level === 'warn') {
    process.stderr.write(line + '\n');
  } else {
    process.stdout.write(line + '\n');
  }
}

const logger = {
  info:  (msg: string, ...args: unknown[]) => log('info',  msg, ...args),
  warn:  (msg: string, ...args: unknown[]) => log('warn',  msg, ...args),
  error: (msg: string, ...args: unknown[]) => log('error', msg, ...args),
  debug: (msg: string, ...args: unknown[]) => log('debug', msg, ...args),
};

export default logger;
