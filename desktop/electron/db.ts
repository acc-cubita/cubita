import Database from 'better-sqlite3'
import { app } from 'electron'
import path from 'node:path'
import fs from 'node:fs'

// دیتابیس محلی کلاینت: کش فقط‌خواندنی داده‌های مرجع + صف خروجی (outbox) برای رکوردهای ثبت‌شده در حالت آفلاین.
// نکته‌ی طراحی مطابق پلن: شماره‌ی رسمی سند/فاکتور اینجا هرگز ساخته نمی‌شود، فقط بعد از sync موفق از سرور می‌آید.
let db: Database.Database

const OUTBOX_TABLES = ['outbox_journal_entries', 'outbox_sales_invoices', 'outbox_checks', 'outbox_purchase_invoices']

function outboxTableDdl(table: string): string {
  return `
    CREATE TABLE IF NOT EXISTS ${table} (
      local_id TEXT PRIMARY KEY,
      payload TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      synced INTEGER NOT NULL DEFAULT 0,
      server_id TEXT,
      server_number INTEGER,
      sync_error TEXT
    );
  `
}

export function initLocalDb(): Database.Database {
  const dir = path.join(app.getPath('userData'), 'data')
  fs.mkdirSync(dir, { recursive: true })
  db = new Database(path.join(dir, 'cubita-local.db'))
  db.pragma('journal_mode = WAL')

  db.exec(`
    CREATE TABLE IF NOT EXISTS accounts_cache (
      id TEXT PRIMARY KEY,
      code TEXT NOT NULL,
      name TEXT NOT NULL,
      type TEXT NOT NULL,
      is_group INTEGER NOT NULL,
      parent_id TEXT
    );

    CREATE TABLE IF NOT EXISTS warehouses_cache (
      id TEXT PRIMARY KEY,
      code TEXT NOT NULL,
      name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS items_cache (
      id TEXT PRIMARY KEY,
      sku TEXT NOT NULL,
      name TEXT NOT NULL,
      unit TEXT NOT NULL,
      sales_price TEXT NOT NULL,
      is_service INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bank_accounts_cache (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      bank_name TEXT NOT NULL
    );
  `)

  for (const table of OUTBOX_TABLES) db.exec(outboxTableDdl(table))

  return db
}

export function getLocalDb(): Database.Database {
  if (!db) throw new Error('دیتابیس محلی هنوز مقداردهی نشده؛ initLocalDb باید اول اجرا شود')
  return db
}
