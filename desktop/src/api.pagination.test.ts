/**
 * صفحه‌بندیِ `api.ts` — لایه‌ای که بینِ کلِ رابط و سرور نشسته.
 *
 * **چرا این اولین تستِ `api.ts` است.** سقفِ صفحه‌بندیِ سرور ۲۰۰ ردیف است و
 * عددِ بزرگ‌تر **۴۲۲ می‌گیرد، نه پاسخِ کوتاه‌ترِ بی‌خطر**. این یک بار واقعاً
 * اتفاق افتاد و فهرستِ اسناد از روزِ اول خالی بود — بی‌آنکه خطایی دیده شود.
 *
 * تا امروز `authedGetAll` عددِ ۲۰۰ را هارد‌کد کرده بود در حالی که ثابتِ
 * `SERVER_PAGE_MAX` کنارش بود: دو جا با یک معنی، که با عوض‌شدنِ سقفِ سرور
 * واگرا می‌شدند.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { SERVER_PAGE_MAX, authedGetPage, fetchItemsLive } from './api'

type Captured = { url: string; init?: RequestInit }

let calls: Captured[] = []

/** `fetch` را جعل می‌کند و صفحه‌ها را به ترتیب برمی‌گرداند. */
function mockPages(pages: { items: unknown[]; next_cursor: string | null }[]) {
  let i = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init })
    const body = pages[Math.min(i, pages.length - 1)]
    i++
    return { ok: true, status: 200, json: async () => body } as unknown as Response
  }))
}

const q = (url: string) => new URL(url, 'http://x').searchParams

beforeEach(() => { calls = [] })
afterEach(() => { vi.unstubAllGlobals() })

describe('authedGetPage — ساختنِ کوئری', () => {
  it('limit و cursor را می‌گذارد', async () => {
    mockPages([{ items: [], next_cursor: null }])
    await authedGetPage('t', '/api/items', { limit: 50, cursor: 'abc' })
    expect(q(calls[0].url).get('limit')).toBe('50')
    expect(q(calls[0].url).get('cursor')).toBe('abc')
  })

  it('بدونِ گزینه هیچ پارامتری اضافه نمی‌کند — پیش‌فرض = رفتارِ سرور', async () => {
    mockPages([{ items: [], next_cursor: null }])
    await authedGetPage('t', '/api/items')
    expect(calls[0].url).not.toContain('?')
  })

  it('cursorِ تهی فرستاده نمی‌شود', async () => {
    mockPages([{ items: [], next_cursor: null }])
    await authedGetPage('t', '/api/items', { limit: 10, cursor: null })
    expect(q(calls[0].url).has('cursor')).toBe(false)
  })

  it('مسیری که از قبل کوئری دارد با & ادامه می‌یابد، نه ?', async () => {
    //: با `?` دوم، سرور پارامترِ اول را نمی‌بیند و فیلتر بی‌صدا از بین می‌رود.
    mockPages([{ items: [], next_cursor: null }])
    await authedGetPage('t', '/api/payslips?period_id=7', { limit: 10 })
    expect(calls[0].url).toContain('period_id=7')
    expect(q(calls[0].url).get('limit')).toBe('10')
    expect(calls[0].url.split('?').length).toBe(2)
  })

  it('توکن در هدرِ Authorization می‌رود', async () => {
    mockPages([{ items: [], next_cursor: null }])
    await authedGetPage('secret-token', '/api/items')
    const headers = calls[0].init?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer secret-token')
  })
})

describe('دنبال‌کردنِ همه‌ی صفحه‌ها', () => {
  it('هیچ درخواستی از سقفِ سرور فراتر نمی‌رود', async () => {
    //: **هسته‌ی این فایل.** عددِ بزرگ‌تر ۴۲۲ می‌گیرد و فهرست خالی می‌ماند.
    mockPages([{ items: [{ id: 1 }], next_cursor: null }])
    await fetchItemsLive('t')
    for (const c of calls) {
      const limit = Number(q(c.url).get('limit'))
      expect(limit).toBeLessThanOrEqual(SERVER_PAGE_MAX)
    }
  })

  it('تا پایانِ کرسر ادامه می‌دهد و نتیجه را مسطح می‌کند', async () => {
    mockPages([
      { items: [{ id: 1 }, { id: 2 }], next_cursor: 'c1' },
      { items: [{ id: 3 }], next_cursor: null },
    ])
    const rows = await fetchItemsLive('t')
    expect(rows).toHaveLength(3)
    expect(calls).toHaveLength(2)
    //: صفحه‌ی دوم باید کرسرِ صفحه‌ی اول را ببرد، وگرنه همان صفحه تکرار می‌شود.
    expect(q(calls[1].url).get('cursor')).toBe('c1')
  })

  it('یک صفحه‌ی بی‌کرسر یعنی یک درخواست، نه بیشتر', async () => {
    mockPages([{ items: [{ id: 1 }], next_cursor: null }])
    await fetchItemsLive('t')
    expect(calls).toHaveLength(1)
  })

  it('کرسرِ خراب حلقه‌ی بی‌پایان نمی‌سازد — با خطا می‌ایستد', async () => {
    //: سروری که همیشه کرسر می‌دهد، بدونِ سقف مرورگر را قفل می‌کند.
    mockPages([{ items: [{ id: 1 }], next_cursor: 'همیشه' }])
    await expect(fetchItemsLive('t')).rejects.toThrow()
  })
})
