import { beforeEach, describe, expect, it } from 'vitest'

import {
  SUGGEST_LIMIT,
  dedupe,
  poolFor,
  rememberDescriptions,
  sessionDescriptions,
  suggestDescriptions,
} from './descriptionMemory'
import { setTenantScope } from './tenantScope'

/**
 * محیطِ تست `node` است و `sessionStorage` ندارد؛ بدلِ حداقلی، همان چیزی که ماژول
 * واقعاً لمس می‌کند — مثلِ `experienceMode.test.ts`.
 */
const store = new Map<string, string>()
beforeEach(() => {
  store.clear()
  ;(globalThis as Record<string, unknown>).sessionStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  }
  setTenantScope('t-a')
})

describe('پیشنهادِ شرح', () => {
  const pool = ['بابت خرید مواد اولیه', 'بابت هزینه حمل', 'تسویه فاکتور ۱۲', 'هزینه حمل بار', 'بابت تسویه فاکتور']

  it('کادرِ خالی هیچ پیشنهادی نمی‌گیرد', () => {
    expect(suggestDescriptions(pool, '')).toEqual([])
    expect(suggestDescriptions(pool, '   ')).toEqual([])
  })

  it('آغازشونده‌ها اول، بعد آن‌هایی که واژه را جای دیگری دارند', () => {
    expect(suggestDescriptions(pool, 'هزینه')).toEqual(['هزینه حمل بار', 'بابت هزینه حمل'])
  })

  it('ی/ک عربی و نیم‌فاصله فرقی نمی‌کنند', () => {
    expect(suggestDescriptions(pool, 'بابت خريد')).toEqual(['بابت خرید مواد اولیه'])
  })

  it('متنی که دقیقاً همان تایپ‌شده است پیشنهاد نمی‌شود', () => {
    expect(suggestDescriptions(pool, 'بابت هزینه حمل')).toEqual([])
  })

  it(`تکراری‌ها یکی می‌شوند و بیش از ${SUGGEST_LIMIT} تا نمی‌آید`, () => {
    const many = Array.from({ length: 20 }, (_, i) => `بابت ردیف ${i}`)
    expect(suggestDescriptions([...many, ...many], 'بابت')).toHaveLength(SUGGEST_LIMIT)
    expect(dedupe(['بابت حمل', ' بابت حمل ', 'بابت‌حمل', 'بابت حمل'])).toEqual(['بابت حمل'])
  })
})

describe('مخزن و حافظه‌ی جلسه', () => {
  it('ردیف‌های بالایی نزدیک‌ترین اول، بعد پایینی‌ها، بعد جلسه — بی خودِ ردیف', () => {
    rememberDescriptions(['از سندِ قبلی'])
    expect(poolFor(['a', 'b', 'SELF', 'c'], 2)).toEqual(['b', 'a', 'c', 'از سندِ قبلی'])
  })

  it('ثبتِ سند شرح‌هایش را تازه‌ترین‌اول نگه می‌دارد؛ خالی و تکراری نه', () => {
    rememberDescriptions(['اول', ''])
    rememberDescriptions(['دوم', 'اول'])
    expect(sessionDescriptions()).toEqual(['دوم', 'اول'])
  })

  it('سقفِ ۵۰ — قدیمی‌ترها بیرون می‌روند', () => {
    rememberDescriptions(Array.from({ length: 70 }, (_, i) => `شرح ${i}`))
    expect(sessionDescriptions()).toHaveLength(50)
    expect(sessionDescriptions()[0]).toBe('شرح 0')
  })

  it('بی `sessionStorage` نمی‌شکند — فقط حافظه‌ی جلسه نیست', () => {
    ;(globalThis as Record<string, unknown>).sessionStorage = undefined
    expect(() => rememberDescriptions(['x'])).not.toThrow()
    expect(sessionDescriptions()).toEqual([])
  })
})

describe('حافظه به‌ازای کسب‌وکار', () => {
  it('شرح‌های کسب‌وکارِ دیگر پیشنهاد نمی‌شوند', () => {
    rememberDescriptions(['بابت اجاره‌ی انبارِ شرکتِ الف'])
    expect(sessionDescriptions()).toEqual(['بابت اجاره‌ی انبارِ شرکتِ الف'])

    //: تعویضِ کسب‌وکار همین تب را دوباره بار می‌کند؛ `sessionStorage` سرِ جایش است.
    setTenantScope('t-b')
    expect(sessionDescriptions()).toEqual([])

    setTenantScope('t-a')
    expect(sessionDescriptions()).toEqual(['بابت اجاره‌ی انبارِ شرکتِ الف'])
  })

  it('پیش از ورود (بی کسب‌وکار) چیزی نه خوانده می‌شود نه نوشته', () => {
    setTenantScope(null)
    rememberDescriptions(['بی‌صاحب'])
    expect(store.size).toBe(0)
    expect(sessionDescriptions()).toEqual([])
  })
})
