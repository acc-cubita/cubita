/**
 * پیش‌نویسِ محلیِ انبارگردانی.
 *
 * مهم‌ترین چیزی که اینجا سنجیده می‌شود **جزئی‌بودنِ ارسال** است: بک‌اند
 * `PUT /counts` را patch می‌بیند. اگر این ماژول کلِ فهرست را بفرستد، شمارشی که
 * همکار روی گوشیِ دوم وارد کرده با مقدارِ کهنه بازنویسی می‌شود — بی هیچ خطایی.
 */
let mockDisk: string | null = null
let mockFailWrites = false

jest.mock('expo-file-system', () => ({
  Paths: { document: '/doc' },
  File: class {
    get exists() {
      return mockDisk !== null
    }
    create() {
      mockDisk = mockDisk ?? ''
    }
    async text() {
      if (mockDisk === null) throw new Error('missing')
      return mockDisk
    }
    write(content: string) {
      if (mockFailWrites) throw new Error('disk full')
      mockDisk = content
    }
    delete() {
      mockDisk = null
    }
  },
}))

const mockSet = jest.fn()
jest.mock('../../api/stock', () => ({
  setStockCounts: (...args: unknown[]) => mockSet(...args),
}))

import {
  clearDrafts,
  discardDraft,
  getDraft,
  rejectionFor,
  setCount,
  subscribeDrafts,
  syncAllDrafts,
  syncSession,
} from '../countDraft'

const S = 'session-1'
const apiError = (status: number, message = 'خطا') => ({ status, message })

beforeEach(() => {
  mockDisk = null
  mockFailWrites = false
  mockSet.mockReset().mockResolvedValue({})
  clearDrafts()
})

describe('ارسالِ جزئی — قاعده‌ی سختِ این ماژول', () => {
  it('فقط ردیف‌هایی می‌روند که کاربر دست زده', async () => {
    await setCount(S, 'line-a', '5')
    await setCount(S, 'line-c', '2')

    await syncSession(S)

    expect(mockSet).toHaveBeenCalledTimes(1)
    const [sessionId, lines] = mockSet.mock.calls[0]
    expect(sessionId).toBe(S)
    // ردیفِ b هرگز دست نخورده — نباید در درخواست باشد، وگرنه شمارشِ گوشیِ دوم
    // را با مقدارِ کهنه بازنویسی می‌کند.
    expect(lines).toEqual([
      { line_id: 'line-a', counted_qty: '5' },
      { line_id: 'line-c', counted_qty: '2' },
    ])
  })

  it('اصلاحِ چندباره‌ی یک ردیف فقط آخرین مقدار را می‌فرستد', async () => {
    // «شمردم ۵، اشتباه بود، ۷»: یک درخواست با ۷، نه سه درخواست.
    await setCount(S, 'line-a', '5')
    await setCount(S, 'line-a', '6')
    await setCount(S, 'line-a', '7')

    await syncSession(S)

    expect(mockSet.mock.calls[0][1]).toEqual([{ line_id: 'line-a', counted_qty: '7' }])
  })

  it('بدونِ شمارشِ ثبت‌نشده اصلاً درخواستی نمی‌زند', async () => {
    expect(await syncSession(S)).toBe('nothing')
    expect(mockSet).not.toHaveBeenCalled()
  })
})

describe('ماندگاری', () => {
  it('شمارش پیش از هر تلاشِ شبکه روی دیسک می‌نشیند', async () => {
    // انبارِ بدونِ آنتن: اگر اول بفرستیم و بعد بنویسیم، کارِ کاربر با بستنِ اپ می‌رود.
    await setCount(S, 'line-a', '3')
    expect(mockDisk).not.toBeNull()
    expect(await getDraft(S)).toEqual({ 'line-a': '3' })
  })

  it('جلسه‌های مختلف قاطیِ هم نمی‌شوند', async () => {
    await setCount(S, 'line-a', '1')
    await setCount('session-2', 'line-a', '9')

    expect(await getDraft(S)).toEqual({ 'line-a': '1' })
    expect(await getDraft('session-2')).toEqual({ 'line-a': '9' })
  })

  it('دیسکِ پر اپ را نمی‌شکند', async () => {
    mockFailWrites = true
    await expect(setCount(S, 'line-a', '3')).resolves.toBeUndefined()
  })

  it('فایلِ خراب مثلِ خالی رفتار می‌کند', async () => {
    mockDisk = '}{ نه JSON'
    expect(await getDraft(S)).toEqual({})
  })
})

describe('پاک‌کردن پس از ارسال', () => {
  it('ارسالِ موفق پیش‌نویس را خالی می‌کند', async () => {
    await setCount(S, 'line-a', '5')
    expect(await syncSession(S)).toBe('synced')
    expect(await getDraft(S)).toEqual({})
  })

  it('شمارشی که وسطِ ارسال وارد شود بلعیده نمی‌شود', async () => {
    // انباردار حین رفتنِ درخواست کالای بعدی را می‌شمارد. اگر کلِ پیش‌نویس پاک
    // شود، آن شمارش نه در حافظه می‌ماند نه به سرور می‌رسد.
    await setCount(S, 'line-a', '5')
    mockSet.mockImplementation(async () => {
      await setCount(S, 'line-b', '8')
    })

    await syncSession(S)

    expect(await getDraft(S)).toEqual({ 'line-b': '8' })
  })

  it('مقداری که وسطِ ارسال *عوض* شود هم می‌ماند', async () => {
    await setCount(S, 'line-a', '5')
    mockSet.mockImplementation(async () => {
      await setCount(S, 'line-a', '6')
    })

    await syncSession(S)

    // ۵ رفت، ولی ۶ هنوز نرفته — پس باید ثبت‌نشده بماند.
    expect(await getDraft(S)).toEqual({ 'line-a': '6' })
  })
})

describe('رفتار در برابرِ خطا', () => {
  it('قطعیِ شبکه یعنی بماند', async () => {
    mockSet.mockRejectedValue(apiError(0, 'اتصال برقرار نشد'))
    await setCount(S, 'line-a', '5')

    expect(await syncSession(S)).toBe('retry')
    expect(await getDraft(S)).toEqual({ 'line-a': '5' })
    expect(rejectionFor(S)).toBeUndefined()
  })

  it('۴۰۱ یعنی بماند — نشست خراب است نه شمارش', async () => {
    mockSet.mockRejectedValue(apiError(401))
    await setCount(S, 'line-a', '5')

    expect(await syncSession(S)).toBe('retry')
    expect(await getDraft(S)).toEqual({ 'line-a': '5' })
  })

  it('۵۰۰ یعنی بماند', async () => {
    mockSet.mockRejectedValue(apiError(500))
    await setCount(S, 'line-a', '5')
    expect(await syncSession(S)).toBe('retry')
  })

  it('۴۰۰ («جلسه بسته است») علامت می‌خورد ولی شمارش حذف نمی‌شود', async () => {
    mockSet.mockRejectedValue(apiError(400, 'فقط جلسه‌ی باز قابل ویرایش است'))
    await setCount(S, 'line-a', '5')

    expect(await syncSession(S)).toBe('rejected')
    expect(rejectionFor(S)).toBe('فقط جلسه‌ی باز قابل ویرایش است')
    // کارِ کاربر بی‌صدا ناپدید نمی‌شود؛ خودش تصمیم می‌گیرد.
    expect(await getDraft(S)).toEqual({ 'line-a': '5' })
  })

  it('ارسالِ موفقِ بعدی علامتِ رد را برمی‌دارد', async () => {
    mockSet.mockRejectedValueOnce(apiError(400, 'بسته'))
    await setCount(S, 'line-a', '5')
    await syncSession(S)
    expect(rejectionFor(S)).toBeTruthy()

    await syncSession(S)
    expect(rejectionFor(S)).toBeUndefined()
  })
})

describe('ارسالِ همه‌ی جلسه‌ها', () => {
  it('هر جلسه یک درخواستِ جدا می‌گیرد', async () => {
    await setCount('s1', 'a', '1')
    await setCount('s2', 'b', '2')

    await syncAllDrafts()

    expect(mockSet).toHaveBeenCalledTimes(2)
  })

  it('روی اولین شکستِ شبکه متوقف می‌شود', async () => {
    // ادامه‌دادن وقتی شبکه قطع است فقط درخواستِ بی‌فایده می‌سازد.
    await setCount('s1', 'a', '1')
    await setCount('s2', 'b', '2')
    mockSet.mockRejectedValue(apiError(0))

    await syncAllDrafts()

    expect(mockSet).toHaveBeenCalledTimes(1)
  })

  it('جلسه‌ی ردشده دوباره تلاش نمی‌شود', async () => {
    mockSet.mockRejectedValueOnce(apiError(400, 'بسته'))
    await setCount('s1', 'a', '1')
    await syncSession('s1')
    mockSet.mockClear()

    await syncAllDrafts()
    expect(mockSet).not.toHaveBeenCalled()
  })
})

describe('پاک‌سازی', () => {
  it('کاربر می‌تواند پیش‌نویسِ یک جلسه را دور بیندازد', async () => {
    await setCount(S, 'line-a', '5')
    await discardDraft(S)
    expect(await getDraft(S)).toEqual({})
  })

  it('خروج از حساب همه‌چیز را پاک می‌کند — گوشیِ مشترک', async () => {
    await setCount('s1', 'a', '1')
    await setCount('s2', 'b', '2')

    clearDrafts()

    expect(await getDraft('s1')).toEqual({})
    expect(await getDraft('s2')).toEqual({})
  })
})

describe('اشتراک', () => {
  it('UI با هر شمارش خبردار می‌شود', async () => {
    const seen: number[] = []
    const stop = subscribeDrafts((d) => seen.push(Object.keys(d[S] ?? {}).length))

    await setCount(S, 'line-a', '1')
    await setCount(S, 'line-b', '2')
    stop()

    expect(seen[seen.length - 1]).toBe(2)
  })
})
