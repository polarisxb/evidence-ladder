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
      tier        TEXT NOT NULL DEFAULT 'REGULAR',
      created_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
      id               TEXT PRIMARY KEY,
      user_id          TEXT NOT NULL REFERENCES users(id),
      status           TEXT NOT NULL DEFAULT 'PENDING',
      items            TEXT NOT NULL,
      total            REAL NOT NULL,
      shipping_address TEXT NOT NULL,
      tracking_number  TEXT,
      created_at       TEXT NOT NULL,
      updated_at       TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products (
      id          TEXT PRIMARY KEY,
      name        TEXT NOT NULL,
      category    TEXT NOT NULL,
      price       REAL NOT NULL,
      stock       INTEGER NOT NULL DEFAULT 0,
      rating      REAL NOT NULL DEFAULT 0,
      description TEXT NOT NULL,
      tier_required TEXT NOT NULL DEFAULT 'REGULAR'
    );

    CREATE TABLE IF NOT EXISTS coupon_codes (
      code               TEXT PRIMARY KEY,
      discount_type      TEXT NOT NULL,
      discount_value     REAL NOT NULL,
      min_order_amount   REAL NOT NULL DEFAULT 0,
      is_internal        INTEGER NOT NULL DEFAULT 0,
      description        TEXT NOT NULL,
      usage_count        INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      operation      TEXT NOT NULL,
      order_id       TEXT,
      session_user_id TEXT NOT NULL,
      target_user_id  TEXT,
      detail         TEXT NOT NULL,
      executed_at    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS coupon_use_logs (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      coupon_code      TEXT NOT NULL,
      order_id         TEXT NOT NULL,
      session_user_id  TEXT NOT NULL,
      discount_applied REAL NOT NULL,
      executed_at      TEXT NOT NULL
    );
  `);
}

function isEmpty(db: Database.Database): boolean {
  const row = db.prepare('SELECT COUNT(*) as cnt FROM users').get() as { cnt: number };
  return row.cnt === 0;
}
