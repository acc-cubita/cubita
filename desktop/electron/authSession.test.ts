import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// authSession.ts از طریقِ db.ts به `electron` (برای app.getPath) و به
// better-sqlite3 (باینریِ نیتیو) وابسته است — هیچ‌کدام در محیطِ vitest (Node
// خالص) در دسترس نیستند. پس db.ts کاملاً mock می‌شود؛ authSession.ts خودش
// هیچ‌جا مستقیم به electron/better-sqlite3 وابسته نیست، فقط به `getLocalDb`.
//
// فیکِ دیتابیس یک موتورِ SQL نیست — فقط همان چند کوئری‌ای را می‌شناسد که
// authSession.ts واقعاً می‌زند (با تطبیقِ زیررشته‌ی متنِ SQL). شکننده است در
// برابرِ بازنویسیِ کوئری‌ها، ولی برای این ماژول کافی و صادقانه است: تستِ رفتار،
// نه تستِ SQL.
interface FakeRow {
  access_token: string
  refresh_token: string
  me_json: string
}

function makeFakeDb() {
  let row: FakeRow | null = null

  const db = {
    prepare(sql: string) {
      if (sql.includes('SELECT access_token, refresh_token, me_json FROM session')) {
        return { get: () => (row ? { ...row } : undefined) }
      }
      if (sql.includes('SELECT refresh_token FROM session')) {
        return { get: () => (row ? { refresh_token: row.refresh_token } : undefined) }
      }
      if (sql.includes('INSERT INTO session')) {
        return {
          run: (params: { access_token: string; refresh_token: string; me_json: string }) => {
            row = { access_token: params.access_token, refresh_token: params.refresh_token, me_json: params.me_json }
          },
        }
      }
      if (sql.includes('UPDATE session SET access_token')) {
        return {
          run: (params: { a: string; r: string }) => {
            if (row) {
              row = { ...row, access_token: params.a, refresh_token: params.r }
            }
          },
        }
      }
      if (sql.includes('UPDATE session SET me_json')) {
        return {
          run: (params: { m: string }) => {
            if (row) row = { ...row, me_json: params.m }
          },
        }
      }
      if (sql.includes('DELETE FROM session')) {
        return { run: () => { row = null } }
      }
      throw new Error(`فیکِ دیتابیس این کوئری را نمی‌شناسد: ${sql}`)
    },
  }

  return { db, reset: () => { row = null } }
}

const fake = makeFakeDb()

vi.mock('./db.js', () => ({
  getLocalDb: () => fake.db,
}))

// ایمپورت *بعد از* vi.mock تا هویستینگِ vitest اثر کند.
const { persistSession, clearSession, currentRefreshToken, restoreSession, bestEffortLogout } = await import(
  './authSession.js'
)

const API = 'https://api.test'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('authSession — نشستِ آفلاینِ دسکتاپ', () => {
  beforeEach(() => {
    fake.reset()
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('persistSession می‌نویسد و currentRefreshToken همان را می‌خواند', () => {
    persistSession('acc-1', 'ref-1', { tenant_name: 'الف' })
    expect(currentRefreshToken()).toBe('ref-1')
  })

  it('clearSession نشست را پاک می‌کند', () => {
    persistSession('acc-1', 'ref-1', { tenant_name: 'الف' })
    clearSession()
    expect(currentRefreshToken()).toBeNull()
  })

  it('بدونِ نشستِ ذخیره‌شده، restoreSession چیزی صدا نمی‌زند و null برمی‌گرداند', async () => {
    const result = await restoreSession({ apiBaseUrl: API })
    expect(result).toBeNull()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('مسیرِ آنلاین: رفرش و /me هر دو موفق — offline:false، توکن‌های چرخشی ذخیره می‌شوند', async () => {
    persistSession('old-acc', 'old-ref', { tenant_name: 'قدیم' })
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ access_token: 'new-acc', refresh_token: 'new-ref' }))
      .mockResolvedValueOnce(jsonResponse({ tenant_name: 'تازه' }))

    const result = await restoreSession({ apiBaseUrl: API })

    expect(result).toEqual({
      session: { access_token: 'new-acc', refresh_token: 'new-ref', me: { tenant_name: 'تازه' } },
      offline: false,
    })
    // رفرش قبل از /me ذخیره شده — یعنی currentRefreshToken همین حالا رفرشِ تازه را می‌بیند.
    expect(currentRefreshToken()).toBe('new-ref')
  })

  it('قطعیِ شبکه در رفرش: نشستِ قبلی دست‌نخورده برمی‌گردد، offline:true، چیزی پاک نمی‌شود', async () => {
    persistSession('old-acc', 'old-ref', { tenant_name: 'قدیم' })
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))

    const result = await restoreSession({ apiBaseUrl: API })

    expect(result).toEqual({
      session: { access_token: 'old-acc', refresh_token: 'old-ref', me: { tenant_name: 'قدیم' } },
      offline: true,
    })
    // نشستِ محلی دست‌نخورده — این دقیقاً همان باگی است که در نسخه‌ی وب/قدیم بود.
    expect(currentRefreshToken()).toBe('old-ref')
  })

  it('۵۰۰ی گذرای سرور هم مثلِ قطعیِ شبکه رفتار می‌کند، نه بطلان', async () => {
    persistSession('old-acc', 'old-ref', { tenant_name: 'قدیم' })
    vi.mocked(fetch).mockResolvedValueOnce(new Response('boom', { status: 500 }))

    const result = await restoreSession({ apiBaseUrl: API })

    expect(result?.offline).toBe(true)
    expect(currentRefreshToken()).toBe('old-ref')
  })

  it('۴۰۱ِ صریح: نشست پاک می‌شود و null برمی‌گردد — تنها حالتی که باید صفحه‌ی ورود بیاید', async () => {
    persistSession('old-acc', 'old-ref', { tenant_name: 'قدیم' })
    vi.mocked(fetch).mockResolvedValueOnce(new Response('نامعتبر', { status: 401 }))

    const result = await restoreSession({ apiBaseUrl: API })

    expect(result).toBeNull()
    expect(currentRefreshToken()).toBeNull()
  })

  it('رفرش موفق ولی /me با قطعیِ شبکه: توکنِ چرخشی ذخیره می‌ماند، me کهنه برمی‌گردد، offline:true', async () => {
    persistSession('old-acc', 'old-ref', { tenant_name: 'قدیم' })
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ access_token: 'new-acc', refresh_token: 'new-ref' }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))

    const result = await restoreSession({ apiBaseUrl: API })

    expect(result).toEqual({
      session: { access_token: 'new-acc', refresh_token: 'new-ref', me: { tenant_name: 'قدیم' } },
      offline: true,
    })
    // توکنِ رفرش‌شده باید ذخیره مانده باشد — وگرنه دفعه‌ی بعد با رفرشِ مرده ۴۰۱ می‌گرفت.
    expect(currentRefreshToken()).toBe('new-ref')
  })

  it('bestEffortLogout بدونِ نشست چیزی صدا نمی‌زند', async () => {
    await bestEffortLogout({ apiBaseUrl: API })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('bestEffortLogout با نشست، رفرشِ فعلی را به /logout می‌فرستد', async () => {
    persistSession('acc-1', 'ref-1', { tenant_name: 'الف' })
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }))

    await bestEffortLogout({ apiBaseUrl: API })

    expect(fetch).toHaveBeenCalledWith(
      `${API}/api/auth/logout`,
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ refresh_token: 'ref-1' }) }),
    )
  })

  it('bestEffortLogout شکستش خروجِ محلی را متوقف نمی‌کند (throw نمی‌کند)', async () => {
    persistSession('acc-1', 'ref-1', { tenant_name: 'الف' })
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(bestEffortLogout({ apiBaseUrl: API })).resolves.toBeUndefined()
  })
})
