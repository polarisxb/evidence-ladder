import Database from 'better-sqlite3';
import { config } from '../config';
import { runSeed, ensureSeedPasswords } from './seed';
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
    // Backfill demo passwords for legacy databases created before auth existed.
    ensureSeedPasswords(_db);
    logger.info('[DB] SQLite ready at %s', config.dbPath);
  }
  return _db;
}

function initSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id            TEXT PRIMARY KEY,
      name          TEXT NOT NULL,
      email         TEXT NOT NULL UNIQUE,
      password_hash TEXT,
      created_at    TEXT NOT NULL
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
      starred       INTEGER NOT NULL DEFAULT 0,
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

  // Lightweight migration: add `starred` to pre-existing DBs that were created
  // before the column existed. CREATE TABLE IF NOT EXISTS won't add it, so we
  // attempt the ALTER and ignore the "duplicate column" error when it's there.
  try {
    db.exec(`ALTER TABLE emails ADD COLUMN starred INTEGER NOT NULL DEFAULT 0`);
    logger.info('[DB] Migrated: added emails.starred column');
  } catch {
    // column already present — nothing to do
  }

  // Same lightweight migration for `password_hash` on pre-auth databases.
  try {
    db.exec(`ALTER TABLE users ADD COLUMN password_hash TEXT`);
    logger.info('[DB] Migrated: added users.password_hash column');
  } catch {
    // column already present — nothing to do
  }
}

function isEmpty(db: Database.Database): boolean {
  const row = db.prepare('SELECT COUNT(*) as cnt FROM users').get() as { cnt: number };
  return row.cnt === 0;
}
