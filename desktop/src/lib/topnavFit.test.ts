/**
 * نردبانِ کوچک‌شدنِ نوارِ بالا.
 *
 * قیدهایی که این فایل نگه می‌دارد:
 *  - **روی دسکتاپ همه‌ی ماژول‌ها روی نوار می‌مانند** و به یک نسبت کوچک می‌شوند؛ کشو فقط وقتی که
 *    قلم زیرِ حدِ خوانایی برود (خواستِ آرش: همبرگر فقط برای تبلت و گوشی).
 *  - **جست‌وجو در هیچ عرضی از نوار غایب نمی‌شود.**
 *  - در هیچ عرضی نوار سرریز نمی‌کند و با باریک‌شدن هیچ پله‌ای برنمی‌گردد (نوسان).
 */
import { describe, it, expect } from 'vitest'

import { fitBar, MIN_MENU_SCALE, sameFit, type BarMetrics } from './topnavFit'

//: اندازه‌های سنجیده در مرورگر روی حسابی با ۱۳ ماژول (نسخه‌ی وب، ۱۴۰۵/۰۷/۰۶): منو با قلمِ ۱۳px
//: ~۱۱۲۷px، بقیه‌ی نوار ~۳۳۰px و فشرده‌اش ~۱۴۶px.
const M = { bare: 330, compactBare: 146, menu: 1127, menuFixed: 8, hamburger: 44, pill: 164, icon: 38 }
const at = (avail: number, over: Partial<BarMetrics> = {}): BarMetrics => ({ ...M, avail, ...over })
const used = (m: BarMetrics) => {
  const f = fitBar(m)
  const bare = f.compact ? m.compactBare : m.bare
  const menu = f.menu === 'bar' ? m.menuFixed + m.menu * f.scale : m.hamburger
  return bare + menu + (f.search === 'pill' ? m.pill : m.icon)
}

describe('نردبانِ دسکتاپ', () => {
  it('جا هست → همه‌چیز در اندازه‌ی استاندارد، قرصِ کامل', () => {
    expect(fitBar(at(1920))).toEqual({ search: 'pill', menu: 'bar', compact: false, scale: 1 })
  })

  it('اول قرص جمع می‌شود، هنوز قلمِ استاندارد', () => {
    expect(fitBar(at(1560))).toEqual({ search: 'icon', menu: 'bar', compact: false, scale: 1 })
  })

  it('بعد نوار فشرده می‌شود (نام و نوشته‌ی دانلود)، هنوز قلمِ استاندارد', () => {
    expect(fitBar(at(1420))).toEqual({ search: 'icon', menu: 'bar', compact: true, scale: 1 })
  })

  it('لپ‌تاپِ ۱۳۶۶: نوارِ فشرده کافی است و قلم استاندارد می‌ماند', () => {
    expect(fitBar(at(1366))).toEqual({ search: 'icon', menu: 'bar', compact: true, scale: 1 })
  })

  it('۱۲۸۰: همه‌ی ماژول‌ها روی نوار، کمی کوچک‌تر', () => {
    const f = fitBar(at(1280))
    expect(f.menu).toBe('bar')
    expect(f.scale).toBeLessThan(1)
    expect(f.scale).toBeGreaterThanOrEqual(MIN_MENU_SCALE)
  })

  it('۱۰۹۳ (۱۳۶۶ با بزرگ‌نماییِ ۱۲۵٪ِ ویندوز) و ۱۰۵۰: هنوز همه‌ی ماژول‌ها روی نوار', () => {
    expect(fitBar(at(1093)).menu).toBe('bar')
    expect(fitBar(at(1050)).menu).toBe('bar')
  })

  it('کشو روی دسکتاپ فقط وقتی که قلم زیرِ حدِ خوانایی می‌رفت', () => {
    const f = fitBar(at(1000))
    expect(f.menu).toBe('drawer')
    //: با همین عرض، ضریبِ لازم زیرِ حد است.
    expect((1000 - M.compactBare - M.menuFixed - M.icon) / M.menu).toBeLessThan(MIN_MENU_SCALE)
  })

  it('در کشو نوار دوباره کامل است و جای آزادشده به قرص می‌رسد', () => {
    expect(fitBar(at(1000))).toEqual({ search: 'pill', menu: 'drawer', compact: false, scale: 1 })
  })

  it('روی مرزِ دقیق، حالتِ بهتر می‌ماند', () => {
    const edge = M.bare + M.menuFixed + M.menu + M.pill
    expect(fitBar(at(edge)).search).toBe('pill')
    expect(fitBar(at(edge - 1)).search).toBe('icon')
  })
})

describe('تبلت و گوشی: CSS منو را برداشته', () => {
  it('منوی برداشته‌شده در هیچ عرضی به نوار برنمی‌گردد', () => {
    for (const w of [390, 820, 1024, 1194, 1280]) expect(fitBar(at(w, { menu: Infinity })).menu).toBe('drawer')
  })

  it('هزینه‌ی همبرگر شمرده می‌شود', () => {
    //: بدونِ این، روی ۳۹۰px نوار فکر می‌کرد جا دارد و ۴۴px از لبه بیرون می‌زد.
    const avail = M.bare + M.hamburger + M.pill
    expect(fitBar(at(avail, { menu: Infinity })).search).toBe('pill')
    expect(fitBar(at(avail - 1, { menu: Infinity })).search).toBe('icon')
  })

  it('وقتی منو روی نوار می‌ماند، هزینه‌ی همبرگر شمرده نمی‌شود', () => {
    expect(fitBar(at(1920, { hamburger: 400 })).menu).toBe('bar')
  })
})

describe('ناوردا', () => {
  //: عرضِ گوشیِ باریک تا نمایشگرِ بزرگ.
  const widths = Array.from({ length: 1761 }, (_, i) => 320 + i)

  it('در هیچ عرضی جست‌وجو از نوار حذف نمی‌شود', () => {
    const shapes = new Set(widths.map((w) => fitBar(at(w)).search))
    expect([...shapes].sort()).toEqual(['icon', 'pill'])
  })

  it('هیچ عرضی نیست که نوار سرریز کند', () => {
    const bad = widths.filter((w) => used(at(w)) > w)
    //: تنها استثنای مجاز، باریک‌ترین حالتِ ممکن است که دیگر چیزی برای کوچک‌کردن ندارد.
    expect(bad.every((w) => M.bare + M.hamburger + M.icon > w)).toBe(true)
  })

  it('ضریب همیشه بین حدِ خوانایی و ۱ است، و کمتر از ۱ فقط در حالتِ فشرده و با ذره‌بین', () => {
    for (const w of widths) {
      const f = fitBar(at(w))
      if (f.menu === 'drawer') expect(f.scale).toBe(1)
      else {
        expect(f.scale).toBeGreaterThanOrEqual(MIN_MENU_SCALE)
        expect(f.scale).toBeLessThanOrEqual(1)
        if (f.scale < 1) expect(f).toMatchObject({ compact: true, search: 'icon' })
      }
    }
  })

  it('با باریک‌شدن، هر پله فقط یک‌طرفه رد می‌شود و ضریب هرگز بزرگ نمی‌شود', () => {
    let seenDrawer = false
    let last = 1
    for (const w of [...widths].reverse()) {
      const f = fitBar(at(w))
      if (f.menu === 'drawer') seenDrawer = true
      else {
        expect(seenDrawer).toBe(false)
        expect(f.scale).toBeLessThanOrEqual(last)
        last = f.scale
      }
    }
  })

  it('حسابِ کم‌ماژول روی عرضِ کم هم قلمِ استاندارد را نگه می‌دارد', () => {
    expect(fitBar(at(1100, { menu: 300 }))).toEqual({ search: 'pill', menu: 'bar', compact: false, scale: 1 })
  })

  it('حسابِ پرماژول زودتر به کشو می‌رسد، نه به قلمِ ناخوانا', () => {
    const f = fitBar(at(1100, { menu: 1500 }))
    expect(f.menu).toBe('drawer')
  })
})

describe('sameFit', () => {
  it('فقط وقتی همه‌ی فیلدها یکی‌اند', () => {
    const a = fitBar(at(1280))
    expect(sameFit(a, { ...a })).toBe(true)
    expect(sameFit(a, { ...a, scale: a.scale - 0.001 })).toBe(false)
  })
})
