import { getLocalDb } from './db.js'
import { randomUUID } from 'node:crypto'

// Sync Engine حداقلی: pull چارت حساب/کالاها/انبارها از سرور، push اسناد صف‌شده‌ی آفلاین (outbox).
// طبق پلن: تعارض روی سندهای append-only بی‌معناست چون فقط create می‌شوند، نه update همزمان؛
// شماره‌ی رسمی سند/فاکتور اینجا هرگز ساخته نمی‌شود، فقط بعد از sync موفق از سرور می‌آید.

interface SyncConfig {
  apiBaseUrl: string
  getToken: () => string | null
}

// بعضی اندپوینت‌ها آرایه‌ی خام می‌دهند (accounts/warehouses/bank-accounts) و بعضی
// پاسخِ صفحه‌بندی‌شده‌ی keyset `{ items, next_cursor }` (items). این تابع هر دو را
// می‌شناسد و اندپوینتِ صفحه‌بندی‌شده را تا آخرین صفحه دنبال می‌کند تا کشِ آفلاین کامل
// شود، نه فقط صفحه‌ی اول. پیش‌ازاین فقط شکلِ آرایه فرض می‌شد و روی پاسخِ صفحه‌بندی‌شده
// «g is not iterable» می‌داد.
async function fetchAllRows<T>(config: SyncConfig, endpoint: string, token: string): Promise<T[]> {
  const all: T[] = []
  const sep = endpoint.includes('?') ? '&' : '?'
  let cursor: string | null = null

  for (;;) {
    const url = `${config.apiBaseUrl}${endpoint}${sep}limit=200${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) throw new Error(`pull ${endpoint} failed: ${res.status}`)
    const data = (await res.json()) as unknown

    if (Array.isArray(data)) {
      all.push(...(data as T[]))
      break
    }

    const page = data as { items?: T[]; next_cursor?: string | null }
    if (Array.isArray(page.items)) all.push(...page.items)
    cursor = page.next_cursor ?? null
    if (!cursor) break
  }

  return all
}

async function pullTable<T extends { id: string }>(
  config: SyncConfig,
  endpoint: string,
  table: string,
  columns: string[],
  toRow: (item: T) => Record<string, unknown>,
): Promise<void> {
  const token = config.getToken()
  if (!token) return

  const items = await fetchAllRows<T>(config, endpoint, token)

  const db = getLocalDb()
  const cols = ['id', ...columns]
  const placeholders = cols.map((c) => `@${c}`).join(', ')
  const updates = columns.map((c) => `${c}=excluded.${c}`).join(', ')
  const upsert = db.prepare(
    `INSERT INTO ${table} (${cols.join(', ')}) VALUES (${placeholders})
     ON CONFLICT(id) DO UPDATE SET ${updates}`,
  )
  const tx = db.transaction((rows: T[]) => {
    for (const item of rows) upsert.run(toRow(item))
  })
  tx(items)
}

export async function pullAccounts(config: SyncConfig): Promise<void> {
  return pullTable(
    config,
    '/api/accounts',
    'accounts_cache',
    ['code', 'name', 'type', 'is_group', 'parent_id', 'has_tracking', 'accepts_tafsili'],
    (a: {
      id: string
      code: string
      name: string
      type: string
      is_group: boolean
      parent_id: string | null
      has_tracking?: boolean
      accepts_tafsili?: boolean
    }) => ({
      ...a,
      is_group: a.is_group ? 1 : 0,
      // پیگیری در کش می‌ماند تا فرمِ سندِ آفلاین هم بداند کدام حساب فیلدِ پیگیری
      // می‌خواهد؛ بدونش، سندِ صف‌شده موقعِ همگام‌سازی از سرور ۴۰۰ می‌گرفت.
      has_tracking: a.has_tracking ? 1 : 0,
      accepts_tafsili: a.accepts_tafsili ? 1 : 0,
    }),
  )
}

export async function pullWarehouses(config: SyncConfig): Promise<void> {
  return pullTable(config, '/api/warehouses', 'warehouses_cache', ['code', 'name'], (w: {
    id: string
    code: string
    name: string
  }) => w)
}

export async function pullItems(config: SyncConfig): Promise<void> {
  return pullTable(
    config,
    '/api/items',
    'items_cache',
    ['sku', 'name', 'unit', 'sales_price', 'is_service'],
    (i: { id: string; sku: string; name: string; unit: string; sales_price: string; is_service: boolean }) => ({
      ...i,
      is_service: i.is_service ? 1 : 0,
    }),
  )
}

export async function pullBankAccounts(config: SyncConfig): Promise<void> {
  return pullTable(config, '/api/bank-accounts', 'bank_accounts_cache', ['name', 'bank_name'], (b: {
    id: string
    name: string
    bank_name: string
  }) => b)
}

export function queueJournalEntry(payload: unknown): string {
  const db = getLocalDb()
  const localId = randomUUID()
  db.prepare('INSERT INTO outbox_journal_entries (local_id, payload) VALUES (?, ?)').run(
    localId,
    JSON.stringify(payload),
  )
  return localId
}

export function queueSalesInvoice(payload: unknown): string {
  const db = getLocalDb()
  const localId = randomUUID()
  db.prepare('INSERT INTO outbox_sales_invoices (local_id, payload) VALUES (?, ?)').run(
    localId,
    JSON.stringify(payload),
  )
  return localId
}

export function queueCheck(payload: unknown): string {
  const db = getLocalDb()
  const localId = randomUUID()
  db.prepare('INSERT INTO outbox_checks (local_id, payload) VALUES (?, ?)').run(localId, JSON.stringify(payload))
  return localId
}

export function queuePurchaseInvoice(payload: unknown): string {
  const db = getLocalDb()
  const localId = randomUUID()
  db.prepare('INSERT INTO outbox_purchase_invoices (local_id, payload) VALUES (?, ?)').run(
    localId,
    JSON.stringify(payload),
  )
  return localId
}

async function pushOutboxTable(
  config: SyncConfig,
  table: string,
  endpoint: string,
): Promise<{ pushed: number; failed: number }> {
  const token = config.getToken()
  if (!token) return { pushed: 0, failed: 0 }

  const db = getLocalDb()
  const pending = db
    .prepare(`SELECT local_id, payload FROM ${table} WHERE synced = 0`)
    .all() as Array<{ local_id: string; payload: string }>

  let pushed = 0
  let failed = 0

  for (const item of pending) {
    try {
      const res = await fetch(`${config.apiBaseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          // local_id همان کلید یکتاسازی است و از ابتدا هم برای همین ساخته می‌شد،
          // فقط هرگز فرستاده نمی‌شد.
          //
          // حالتی که این حل می‌کند: سرور فاکتور را ثبت می‌کند ولی پاسخ در شبکه گم
          // می‌شود. کد به catch می‌رود، synced صفر می‌ماند، و دور بعدی دوباره POST
          // می‌کند — یعنی **سند مالی دوم**، بدون هیچ خطایی. برای نرم‌افزار حسابداری
          // این از هر باگی بدتر است چون دفتر را بی‌صدا غلط می‌کند.
          //
          // چون local_id در همان ردیف صف ذخیره شده، در همه‌ی تلاش‌های مجدد یکسان
          // است. سرور بار دوم همان فاکتور اول را برمی‌گرداند، نه فاکتور تازه.
          'Idempotency-Key': item.local_id,
          // این ردیف از صفِ آفلاین می‌آید، نه از دستِ کاربرِ آنلاین. سرور با
          // دیدنِ این سرآیند گاردِ سقفِ اعتبار را نمی‌گیرد: آن فروش قبلاً انجام
          // شده و کالایش رفته؛ ردّش این‌جا یعنی نابودکردنِ کارِ فروشنده. تصمیمِ
          // «نفروش» در لحظه‌ی فروش گرفته می‌شود، نه ساعت‌ها بعد سرِ همگام‌سازی.
          'X-Cubita-Offline-Replay': '1',
        },
        body: item.payload,
      })
      if (!res.ok) {
        const text = await res.text()
        db.prepare(`UPDATE ${table} SET sync_error = ? WHERE local_id = ?`).run(text, item.local_id)
        failed++
        continue
      }
      const created = (await res.json()) as { id: string; number: number }
      db.prepare(
        `UPDATE ${table} SET synced = 1, server_id = ?, server_number = ?, sync_error = NULL WHERE local_id = ?`,
      ).run(created.id, created.number, item.local_id)
      pushed++
    } catch (err) {
      db.prepare(`UPDATE ${table} SET sync_error = ? WHERE local_id = ?`).run(String(err), item.local_id)
      failed++
    }
  }

  return { pushed, failed }
}

const OUTBOX_ENDPOINTS: Array<[table: string, endpoint: string]> = [
  ['outbox_journal_entries', '/api/journal-entries'],
  ['outbox_sales_invoices', '/api/sales-invoices'],
  ['outbox_checks', '/api/checks'],
  ['outbox_purchase_invoices', '/api/purchase-invoices'],
]

export async function pushOutbox(config: SyncConfig): Promise<{ pushed: number; failed: number }> {
  const results = await Promise.all(
    OUTBOX_ENDPOINTS.map(([table, endpoint]) => pushOutboxTable(config, table, endpoint)),
  )
  return {
    pushed: results.reduce((sum, r) => sum + r.pushed, 0),
    failed: results.reduce((sum, r) => sum + r.failed, 0),
  }
}
