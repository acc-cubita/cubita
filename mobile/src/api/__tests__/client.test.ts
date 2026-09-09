/**
 * تستِ کلاینتِ API — به‌ویژه رفرشِ توکن.
 *
 * **چرا این و نه چیزِ دیگر:** این منطق وقتی می‌شکند، *خطا نمی‌دهد* — کاربر را بی‌دلیل
 * از حساب بیرون می‌اندازد یا در حلقه‌ی رفرش می‌اندازد. هر دو حالت روی گوشیِ کاربر
 * دیده می‌شوند نه در لاگِ ما. این دقیقاً همان دسته‌ای است که در CLAUDE.md زیرِ
 * «چیزهایی که بی‌صدا می‌شکنند» آمده.
 */
import {
  apiGet,
  apiGetAll,
  isApiError,
  setOnTokens,
  setOnUnauthorized,
  setTokens,
} from '../client'

const BASE = 'https://acc.cubita.ir'

/** پاسخِ ساختگیِ fetch. */
function reply(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

let fetchMock: jest.Mock

beforeEach(() => {
  fetchMock = jest.fn()
  global.fetch = fetchMock as unknown as typeof fetch
  setTokens(null, null)
  setOnTokens(null)
  setOnUnauthorized(null)
})

describe('رفرشِ توکن', () => {
  it('روی ۴۰۱ یک بار رفرش می‌کند و همان درخواست را دوباره می‌زند', async () => {
    setTokens('old-access', 'the-refresh')
    fetchMock
      .mockResolvedValueOnce(reply(401))
      .mockResolvedValueOnce(reply(200, { access_token: 'new-access', refresh_token: 'new-refresh' }))
      .mockResolvedValueOnce(reply(200, { ok: true }))

    await expect(apiGet('/api/contacts')).resolves.toEqual({ ok: true })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toBe(`${BASE}/api/auth/refresh`)
    // تلاشِ دوم باید با توکنِ *تازه* برود، نه توکنِ سوخته.
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer new-access')
  })

  it('توکنِ تازه را به لایه‌ی احراز می‌دهد تا ماندگار شود', async () => {
    // بدونِ این، رفرشِ چرخشی در حافظه می‌ماند و با بستنِ اپ از بین می‌رود —
    // یعنی کاربر دفعه‌ی بعد بی‌دلیل باید دوباره وارد شود.
    const saved: string[][] = []
    setTokens('old', 'refresh-1')
    setOnTokens((a, r) => saved.push([a, r]))
    fetchMock
      .mockResolvedValueOnce(reply(401))
      .mockResolvedValueOnce(reply(200, { access_token: 'a2', refresh_token: 'r2' }))
      .mockResolvedValueOnce(reply(200, {}))

    await apiGet('/api/items')
    expect(saved).toEqual([['a2', 'r2']])
  })

  it('چند درخواستِ همزمان فقط یک بار رفرش را صدا می‌زنند', async () => {
    // بدونِ تک‌پروازه‌بودن، سه درخواستِ همزمان سه رفرشِ چرخشی می‌زنند و دوتای
    // آخر با توکنِ باطل‌شده کار می‌کنند — یعنی خروجِ بی‌دلیل.
    setTokens('old', 'refresh-1')
    fetchMock.mockImplementation(async (url: string, init?: { headers?: Record<string, string> }) => {
      if (url.endsWith('/api/auth/refresh')) return reply(200, { access_token: 'a2', refresh_token: 'r2' })
      if (init?.headers?.Authorization === 'Bearer old') return reply(401)
      return reply(200, { ok: true })
    })

    await Promise.all([apiGet('/api/a'), apiGet('/api/b'), apiGet('/api/c')])

    const refreshCalls = fetchMock.mock.calls.filter((c) => String(c[0]).endsWith('/api/auth/refresh'))
    expect(refreshCalls).toHaveLength(1)
  })

  it('اگر رفرش هم شکست بخورد، کاربر را خارج می‌کند', async () => {
    setTokens('old', 'bad-refresh')
    let loggedOut = false
    setOnUnauthorized(() => { loggedOut = true })
    fetchMock.mockResolvedValueOnce(reply(401)).mockResolvedValueOnce(reply(401))

    await expect(apiGet('/api/contacts')).rejects.toMatchObject({ status: 401 })
    expect(loggedOut).toBe(true)
  })

  it('۴۰۱ روی خودِ مسیرِ ورود، رفرش و خروج را تریگر نمی‌کند', async () => {
    // رمزِ غلط باید پیامِ سرور را به کاربر برساند، نه اینکه نشست را بترکاند.
    let loggedOut = false
    setOnUnauthorized(() => { loggedOut = true })
    fetchMock.mockResolvedValueOnce(reply(401, { detail: 'ایمیل یا رمز اشتباه است' }))

    await expect(apiGet('/api/auth/login')).rejects.toMatchObject({
      status: 401,
      message: 'ایمیل یا رمز اشتباه است',
    })
    expect(loggedOut).toBe(false)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('خطاها', () => {
  it('قطعیِ شبکه پیامِ فارسیِ قابل‌فهم می‌دهد، نه TypeError', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Network request failed'))
    await expect(apiGet('/api/x')).rejects.toMatchObject({ status: 0 })
  })

  it('پیامِ detailِ سرور به کاربر می‌رسد', async () => {
    fetchMock.mockResolvedValueOnce(reply(409, { detail: 'شماره تکراری است' }))
    await expect(apiGet('/api/x')).rejects.toMatchObject({ message: 'شماره تکراری است' })
  })

  it('بدنه‌ی غیرJSON اپ را نمی‌شکند', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => { throw new Error('not json') },
    } as unknown as Response)
    await expect(apiGet('/api/x')).rejects.toMatchObject({ status: 502 })
  })

  it('isApiError شکلِ خطا را درست تشخیص می‌دهد', () => {
    expect(isApiError({ status: 404, message: 'x' })).toBe(true)
    expect(isApiError(new Error('boom'))).toBe(false)
    expect(isApiError(null)).toBe(false)
  })
})

describe('صفحه‌بندیِ keyset', () => {
  it('صفحات را دنبال می‌کند تا cursor تمام شود', async () => {
    fetchMock
      .mockResolvedValueOnce(reply(200, { items: [1, 2], next_cursor: 'c1' }))
      .mockResolvedValueOnce(reply(200, { items: [3], next_cursor: null }))

    await expect(apiGetAll<number>('/api/items')).resolves.toEqual([1, 2, 3])
  })

  it('limit را روی ۲۰۰ می‌گذارد — سقفِ سرور', async () => {
    // MAX_LIMIT سرور ۲۰۰ است؛ بیشتر یعنی ۴۲۲ و صفحه‌ی بی‌صدا خالی.
    fetchMock.mockResolvedValueOnce(reply(200, { items: [], next_cursor: null }))
    await apiGetAll('/api/items')
    expect(String(fetchMock.mock.calls[0][0])).toContain('limit=200')
  })

  it('پاسخِ آرایه‌ای (اندپوینتِ بدونِ صفحه‌بندی) را هم می‌پذیرد', async () => {
    fetchMock.mockResolvedValueOnce(reply(200, [7, 8]))
    await expect(apiGetAll<number>('/api/warehouses')).resolves.toEqual([7, 8])
  })
})
