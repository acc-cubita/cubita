import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  EXPERIENCES,
  adoptServerExperience,
  getStoredMode,
  setExperience,
  __resetExperienceForTests,
} from './experienceMode'

/**
 * محیطِ تست `node` است و نه DOM دارد نه localStorage. هر دو با بدلِ حداقلی
 * ساخته می‌شوند — همان چیزی که ماژول واقعاً لمس می‌کند، نه بیشتر.
 */
const store = new Map<string, string>()
const attrs = new Map<string, string>()

beforeEach(() => {
  store.clear()
  attrs.clear()
  __resetExperienceForTests()
  ;(globalThis as Record<string, unknown>).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  }
  ;(globalThis as Record<string, unknown>).document = {
    documentElement: { setAttribute: (k: string, v: string) => void attrs.set(k, v) },
  }
})

describe('رجیستریِ حالت‌ها', () => {
  it('دقیقاً دو حالت، با برچسبِ فارسی', () => {
    expect(EXPERIENCES.map((x) => x.id)).toEqual(['simple', 'accountant'])
    expect(EXPERIENCES[0].label).toBe('حالت ساده')
    expect(EXPERIENCES[1].label).toBe('حالت حسابدار')
  })
})

describe('ماندگاری', () => {
  it('پیش‌فرض حسابدار است — تصمیمِ ۰۱۸۳', () => {
    expect(getStoredMode()).toBe('accountant')
  })

  it('مقدارِ ناشناخته به پیش‌فرض برمی‌گردد', () => {
    store.set('cubita.experience', 'wizard')
    expect(getStoredMode()).toBe('accountant')
  })

  it('نبودِ localStorage برنامه را نمی‌شکند', () => {
    ;(globalThis as Record<string, unknown>).localStorage = {
      getItem: () => {
        throw new Error('پنجره‌ی ناشناس')
      },
      setItem: () => {
        throw new Error('پنجره‌ی ناشناس')
      },
    }
    expect(getStoredMode()).toBe('accountant')
    expect(() => setExperience('simple')).not.toThrow()
  })
})

describe('تغییرِ حالت', () => {
  it('صفتِ سند و ذخیره‌ی محلی را می‌نشاند', () => {
    setExperience('simple')
    expect(attrs.get('data-experience')).toBe('simple')
    expect(store.get('cubita.experience')).toBe('simple')
  })

  it('به سرور می‌فرستد', async () => {
    const persist = vi.fn().mockResolvedValue({})
    setExperience('simple', persist)
    expect(persist).toHaveBeenCalledWith('simple')
  })

  it('حالتِ تکراری هیچ کاری نمی‌کند — نه رندر، نه درخواست', () => {
    const persist = vi.fn().mockResolvedValue({})
    setExperience('accountant', persist)
    expect(persist).not.toHaveBeenCalled()
  })

  it('شکستِ ذخیره‌ی سرور انتخابِ کاربر را پس نمی‌گیرد', async () => {
    const persist = vi.fn().mockRejectedValue(new Error('شبکه'))
    setExperience('simple', persist)
    await Promise.resolve()
    //: کاربر همین الان انتخابش را دیده؛ پس‌گرفتنِ بی‌صدا بدتر از ترجیحِ
    //: ذخیره‌نشده است.
    expect(attrs.get('data-experience')).toBe('simple')
  })
})

describe('پذیرشِ مقدارِ سرور', () => {
  it('مقدارِ معتبر را می‌نشاند', () => {
    adoptServerExperience('simple')
    expect(attrs.get('data-experience')).toBe('simple')
  })

  it('مقدارِ نامعتبر یا تهی را نادیده می‌گیرد', () => {
    adoptServerExperience(undefined)
    adoptServerExperience(null)
    adoptServerExperience('pro')
    expect(attrs.size).toBe(0)
  })
})
