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
      parent_id TEXT,
      has_tracking INTEGER NOT NULL DEFAULT 0,
      accepts_tafsili INTEGER NOT NULL DEFAULT 0
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

    -- نشستِ ورود — تنها راهِ اپِ دسکتاپ برای زنده‌ماندن بدونِ اینترنت در بدو اجرا.
    -- تا امروز توکن فقط متغیرِ حافظه‌ی main.ts بود (authToken)، پس با هر بازکردنِ
    -- اپ صفر می‌شد و صفحه‌ی ورود می‌آمد — آنلاین یا آفلاین، فرقی نداشت. یک ردیفِ
    -- ثابت (id=1) کافی است چون هر نصبِ دسکتاپ یک‌بار یک کاربر را نگه می‌دارد.
    -- me_json کشِ آخرین پاسخِ /api/auth/me است تا داشبورد بدونِ شبکه هم چیزی
    -- برای نمایش داشته باشد؛ authSession.ts مالکِ خواندن/نوشتنِ این جدول است.
    CREATE TABLE IF NOT EXISTS session (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      access_token TEXT NOT NULL,
      refresh_token TEXT NOT NULL,
      me_json TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `)

  for (const table of OUTBOX_TABLES) db.exec(outboxTableDdl(table))

  // ستون‌هایی که بعد از انتشارِ اولین نسخه به کش اضافه شده‌اند. `CREATE TABLE IF
  // NOT EXISTS` روی دیتابیسِ موجود کاری نمی‌کند، پس بدونِ این حلقه، کاربری که از
  // قبل نصب داشته ستونِ تازه را هرگز نمی‌گرفت و همگام‌سازی با خطای SQL می‌خورد.
  // امن است چون این جدول‌ها *کش*اند: هر مقدارِ پیش‌فرضی با اولین pull درست می‌شود.
  ensureColumn(db, 'accounts_cache', 'has_tracking', 'INTEGER NOT NULL DEFAULT 0')
  ensureColumn(db, 'accounts_cache', 'accepts_tafsili', 'INTEGER NOT NULL DEFAULT 0')

  return db
}

/** ستون را اگر نبود اضافه می‌کند. SQLite دستورِ «ADD COLUMN IF NOT EXISTS» ندارد. */
function ensureColumn(
  database: Database.Database,
  table: string,
  column: string,
  definition: string,
): void {
  const columns = database.prepare(`PRAGMA table_info(${table})`).all() as { name: string }[]
  if (columns.some((c) => c.name === column)) return
  database.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`)
}

/** مجموعِ رکوردهای همگام‌نشده در همه‌ی صف‌ها. */
export function pendingOutboxCount(): number {
  const database = getLocalDb()
  let total = 0
  for (const table of OUTBOX_TABLES) {
    const row = database.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE synced = 0`).get() as { n: number }
    total += row.n
  }
  return total
}

/**
 * کشِ مرجع را خالی می‌کند — **و به صف دست نمی‌زند**.
 *
 * موقعِ تعویضِ کسب‌وکار لازم است: این جدول‌ها ستونِ مستأجر ندارند، پس داده‌ی
 * کسب‌وکارِ قبلی زیرِ نامِ جدید دیده می‌شد. صف عمداً دست‌نخورده می‌ماند چون
 * **داده است نه کش**؛ گاردِ تعویض اصلاً نمی‌گذارد با صفِ پر جابه‌جا شوی.
 */
export function clearReferenceCaches(): void {
  const database = getLocalDb()
  for (const table of ['accounts_cache', 'warehouses_cache', 'items_cache', 'bank_accounts_cache']) {
    database.exec(`DELETE FROM ${table}`)
  }
}

export function getLocalDb(): Database.Database {
  if (!db) throw new Error('دیتابیس محلی هنوز مقداردهی نشده؛ initLocalDb باید اول اجرا شود')
  return db
}
