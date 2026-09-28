import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// هیچ فایل SQLite یا سرورِ نصب‌شده‌ای باز نمی‌شود؛ فقط مرزهای واقعیِ HTTP و SQL سنجیده می‌شوند.
const state = vi.hoisted(() => ({
  writes: [] as { sql: string; args: unknown[] }[],
  pending: {} as Record<string, { local_id: string; payload: string }[]>,
}))
vi.mock('./db.js', () => ({
  getLocalDb: () => ({
    transaction: (fn: (rows: unknown[]) => void) => fn,
    prepare: (sql: string) => ({
      all: () => state.pending[/FROM (\w+)/.exec(sql)?.[1] ?? ''] ?? [],
      get: (id: string) => state.pending[/FROM (\w+)/.exec(sql)?.[1] ?? '']?.find((row) => row.local_id === id),
      run: (...args: unknown[]) => {
        state.writes.push({ sql, args })
        if (/SET synced = 1/.test(sql)) {
          const table = /UPDATE (\w+)/.exec(sql)![1]
          state.pending[table] = state.pending[table].filter((item) => item.local_id !== args[2])
        }
      },
    }),
  }),
}))
import { pullAll, pushOutbox } from './sync'

const config = { apiBaseUrl: 'http://server.invalid:8420', getToken: () => 'token' }
const account = { id: 'a', code: '1101', name: 'بانک', type: 'asset', is_group: false, parent_id: null }
const bank = { id: 'b', name: 'ملی', bank_name: 'ملی' }
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
beforeEach(() => { state.writes = []; state.pending = {} })
afterEach(() => vi.unstubAllGlobals())

describe('موتور همگام‌سازی با دسترسی محدود', () => {
  it('سناریوی واقعیِ کلاینت: حساب و بانک ۲۰۰، انبار و کالا ۴۰۳؛ کش حساب موفق می‌ماند', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const path = new URL(url).pathname
      if (path === '/api/accounts') return json([account])
      if (path === '/api/bank-accounts') return json([bank])
      return json({ detail: 'مجاز نیست' }, 403)
    })
    vi.stubGlobal('fetch', fetchMock)
    const result = await pullAll(config)
    expect(result).toEqual({ pulled: ['accounts', 'bankAccounts'], skipped: ['warehouses', 'items'], failed: [] })
    expect(state.writes.find((write) => write.sql.includes('INSERT INTO accounts_cache'))?.args[0]).toMatchObject({ id: 'a', is_group: 0 })
    expect(state.writes.filter((write) => write.sql.startsWith('DELETE')).map((write) => write.sql)).toEqual([
      'DELETE FROM warehouses_cache', 'DELETE FROM items_cache',
    ])
    expect(state.writes.some((write) => write.sql.includes('outbox'))).toBe(false)
  })

  it('با نقشهٔ مجوز، برای انبارِ غیرمجاز حتی درخواست نمی‌رود', async () => {
    const fetchMock = vi.fn(async (url: string) => json(new URL(url).pathname === '/api/accounts' ? [account] : [bank]))
    vi.stubGlobal('fetch', fetchMock)
    await pullAll(config, { accounting: ['view'], checks_bank: ['view'] })
    expect(fetchMock.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(['/api/accounts', '/api/bank-accounts'])
  })

  it('نبودن توکن گزارشِ موفقیتِ دروغین نمی‌دهد', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const result = await pullAll({ ...config, getToken: () => null })
    expect(result.failed).toHaveLength(4)
    expect(result.pulled).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
    expect(state.writes).toEqual([])
  })

  it('کالای صفحه‌بندی‌شده تا آخر دریافت می‌شود و سقف ۲۰۰ حفظ است', async () => {
    const item = (id: string) => ({ id, sku: id, name: id, unit: 'عدد', sales_price: '10', is_service: false })
    const fetchMock = vi.fn(async (url: string) => {
      const request = new URL(url)
      if (request.pathname !== '/api/items') return json([])
      return json(request.searchParams.has('cursor')
        ? { items: [item('second')], next_cursor: null }
        : { items: [item('first')], next_cursor: 'next value' })
    })
    vi.stubGlobal('fetch', fetchMock)
    await pullAll(config)
    expect(state.writes.filter((write) => write.sql.includes('INSERT INTO items_cache'))).toHaveLength(2)
    expect(fetchMock.mock.calls.every(([url]) => new URL(url).searchParams.get('limit') === '200')).toBe(true)
    expect(fetchMock.mock.calls.some(([url]) => new URL(url).searchParams.get('cursor') === 'next value')).toBe(true)
  })

  it('شکست دریافت مرجع، ارسال صف را متوقف نمی‌کند؛ retry همان کلید و payload را دارد', async () => {
    const payload = JSON.stringify({ entry_date: '2026-09-28', lines: [] })
    state.pending.outbox_journal_entries = [{ local_id: 'existing-local-id', payload }]
    const posts: RequestInit[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        posts.push(init)
        return posts.length === 1 ? json({ detail: 'در هیچ سال مالی تعریف‌شده‌ای نیست' }, 400) : json({ id: 'server-id', number: 1 })
      }
      if (new URL(url).pathname === '/api/items') throw new TypeError('fetch failed')
      return json([])
    }))
    expect((await pullAll(config)).failed).toHaveLength(1)
    expect(await pushOutbox(config)).toEqual({ pushed: 0, failed: 1 })
    expect(state.pending.outbox_journal_entries[0]).toEqual({ local_id: 'existing-local-id', payload })
    expect(await pushOutbox(config)).toEqual({ pushed: 1, failed: 0 })
    expect(await pushOutbox(config)).toEqual({ pushed: 0, failed: 0 })
    expect(posts).toHaveLength(2)
    for (const post of posts) {
      expect(post.body).toBe(payload)
      expect(post.headers).toMatchObject({ 'Idempotency-Key': 'existing-local-id', 'X-Cubita-Offline-Replay': '1' })
    }
  })
})
