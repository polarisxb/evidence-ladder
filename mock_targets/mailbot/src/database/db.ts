import Database from 'better-sqlite3';
import { config } from '../config';
import { runSeed } from './seed';
import logger from '../logger';

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(config.dbPath);
    _db.pragma('journal_mode = WAL');
    _db.pragma('foreign_keys = ON');
    initSchema(_db);
    if (isEmpty(_db)) {
      runSeed(_db);
      logger.info('[DB] Seed data loaded');
    }
    logger.info('[DB] SQLite ready at %s', config.dbPath);
  }
  return _db;
}

function initSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id          TEXT PRIMARY KEY,
      name        TEXT NOT NULL,
      email       TEXT NOT NULL UNIQUE,
      created_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS emails (
      id            TEXT PRIMARY KEY,
      owner_user_id TEXT NOT NULL REFERENCES users(id),
      folder        TEXT NOT NULL DEFAULT 'inbox',
      from_addr     TEXT NOT NULL,
      to_addr       TEXT NOT NULL,
      subject       TEXT NOT NULL,
      body          TEXT NOT NULL,
      is_read       INTEGER NOT NULL DEFAULT 0,
      created_at    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS email_audit (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      operation       TEXT NOT NULL,
      email_id        TEXT,
      session_user_id TEXT NOT NULL,
      recipient       TEXT,
      detail          TEXT NOT NULL,
      executed_at     TEXT NOT NULL
    );
  `);
}

function isEmpty(db: Database.Database): boolean {
  const row = db.prepare('SELECT COUNT(*) as cnt FROM users').get() as { cnt: number };
  return row.cnt === 0;
}
