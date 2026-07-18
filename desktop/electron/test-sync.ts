// اسکریپت تست واقعی: همان initLocalDb/sync.ts اپ اصلی را زیر Electron واقعی (نه mock) با بک‌اند واقعی اجرا می‌کند.
// اجرا: npx esbuild electron/test-sync.ts --bundle --platform=node --external:electron --external:better-sqlite3 --outfile=dist-electron/test-sync.js --format=cjs
//       سپس: ELECTRON_RUN_AS_NODE=1 ./node_modules/.bin/electron.cmd dist-electron/test-sync.js
import { app } from 'electron'
import { initLocalDb, getLocalDb } from './db.js'
import { pullAccounts, pullWarehouses, pullItems, pullBankAccounts, queueJournalEntry, pushOutbox } from './sync.js'

// اعتبارنامه از محیط خوانده می‌شود تا رمز کاربر مدیر داخل مخزن ننشیند.
// اجرا: TEST_SYNC_EMAIL=... TEST_SYNC_PASSWORD=... <دستور بالا>
const API_BASE_URL = process.env.TEST_SYNC_API_URL ?? 'http://127.0.0.1:8000'
const TEST_EMAIL = process.env.TEST_SYNC_EMAIL ?? ''
const TEST_PASSWORD = process.env.TEST_SYNC_PASSWORD ?? ''

async function main() {
  if (!TEST_EMAIL || !TEST_PASSWORD) {
    throw new Error('TEST_SYNC_EMAIL و TEST_SYNC_PASSWORD باید در محیط تنظیم شوند')
  }

  console.log('--- initLocalDb ---')
  initLocalDb()
  const db = getLocalDb()

  console.log('--- login (real backend) ---')
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
  })
  if (!res.ok) throw new Error(`login failed: ${res.status}`)
  const { access_token: token } = (await res.json()) as { access_token: string }
  console.log('token acquired, length =', token.length)

  const config = { apiBaseUrl: API_BASE_URL, getToken: () => token }

  console.log('--- pull reference data into local SQLite ---')
  await Promise.all([pullAccounts(config), pullWarehouses(config), pullItems(config), pullBankAccounts(config)])

  const accountsCount = (db.prepare('SELECT COUNT(*) as c FROM accounts_cache').get() as { c: number }).c
  const warehousesCount = (db.prepare('SELECT COUNT(*) as c FROM warehouses_cache').get() as { c: number }).c
  const itemsCount = (db.prepare('SELECT COUNT(*) as c FROM items_cache').get() as { c: number }).c
  const bankAccountsCount = (db.prepare('SELECT COUNT(*) as c FROM bank_accounts_cache').get() as { c: number }).c
  console.log({ accountsCount, warehousesCount, itemsCount, bankAccountsCount })
  if (accountsCount === 0) throw new Error('FAIL: accounts_cache خالی ماند بعد از pull')
  if (itemsCount === 0) throw new Error('FAIL: items_cache خالی ماند بعد از pull')

  const cashAccount = db.prepare("SELECT id FROM accounts_cache WHERE code = '1101'").get() as { id: string }
  const capitalAccount = db.prepare("SELECT id FROM accounts_cache WHERE code = '3101'").get() as { id: string }
  console.log('found cash/capital accounts in local cache:', !!cashAccount, !!capitalAccount)

  console.log('--- queue a journal entry OFFLINE (outbox) ---')
  const localId = queueJournalEntry({
    entry_date: '2026-07-14',
    description: 'تست واقعی از Electron/outbox',
    lines: [
      { account_id: cashAccount.id, debit: 500000, credit: 0 },
      { account_id: capitalAccount.id, debit: 0, credit: 500000 },
    ],
  })
  console.log('queued with local_id =', localId)

  const outboxBefore = db.prepare('SELECT synced FROM outbox_journal_entries WHERE local_id = ?').get(localId) as {
    synced: number
  }
  console.log('outbox row before sync, synced =', outboxBefore.synced)
  if (outboxBefore.synced !== 0) throw new Error('FAIL: outbox باید قبل از sync، synced=0 باشد')

  console.log('--- push outbox to real backend ---')
  const pushResult = await pushOutbox(config)
  console.log('push result:', pushResult)
  if (pushResult.pushed !== 1 || pushResult.failed !== 0) {
    throw new Error(`FAIL: انتظار pushed=1 failed=0 بود، گرفتیم ${JSON.stringify(pushResult)}`)
  }

  const outboxAfter = db
    .prepare('SELECT synced, server_id, server_number FROM outbox_journal_entries WHERE local_id = ?')
    .get(localId) as { synced: number; server_id: string; server_number: number }
  console.log('outbox row after sync:', outboxAfter)
  if (outboxAfter.synced !== 1 || !outboxAfter.server_id || !outboxAfter.server_number) {
    throw new Error('FAIL: بعد از sync باید synced=1 و server_id/server_number پر شده باشد')
  }

  console.log('--- verify on real backend that the entry exists with matching number ---')
  const verifyRes = await fetch(`${API_BASE_URL}/api/journal-entries`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const entries = (await verifyRes.json()) as Array<{ number: number; description: string }>
  const found = entries.find((e) => e.number === outboxAfter.server_number)
  if (!found || found.description !== 'تست واقعی از Electron/outbox') {
    throw new Error('FAIL: سند pushشده روی بک‌اند واقعی پیدا نشد یا مطابقت نداشت')
  }
  console.log('VERIFIED on backend:', found)

  console.log('\n=== ALL REAL SYNC TESTS PASSED ===')
  app.exit(0)
}

app.whenReady().then(() => {
  main().catch((err) => {
    console.error('TEST FAILED:', err)
    app.exit(1)
  })
})
