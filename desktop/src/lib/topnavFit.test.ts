/**
 * نردبانِ کوچک‌شدنِ نوارِ بالا.
 *
 * قیدی که این فایل نگه می‌دارد: **جست‌وجو در هیچ عرضی از نوار غایب نمی‌شود.**
 * پیش از این دو جا پنهانش می‌کرد و زیرِ ۷۶۰px هیچ راهی به آن نمی‌ماند. اگر روزی
 * حالتِ سومی به نردبان اضافه شود، تست‌های «ناوردا» پایینِ همین فایل قرمز می‌شوند.
 */
import { describe, it, expect } from 'vitest'

import { fitBar, type BarMetrics } from './topnavFit'

//: اندازه‌های واقعی‌نما: حسابی با ۱۴ ماژول روی نوار.
const M = { bare: 420, menu: 620, hamburger: 52, pill: 156, icon: 42 }
const at = (avail: number, over: Partial<BarMetrics> = {}): BarMetrics => ({ ...M, avail, ...over })

describe('نردبان', () => {
  it('جا هست → منو روی نوار، قرصِ کامل', () => {
    expect(fitBar(at(1920))).toEqual({ search: 'pill', menu: 'bar' })
  })

  it('اول قرص جمع می‌شود، نه اینکه منو به کشو برود', () => {
    //: برای «۱۰۴۰ + قرص» کم است ولی برای «۱۰۴۰ + ذره‌بین» بس.
    expect(fitBar(at(1100))).toEqual({ search: 'icon', menu: 'bar' })
  })

  it('وقتی ذره‌بین هم جا نشد، منو به کشو می‌رود', () => {
    expect(fitBar(at(900)).menu).toBe('drawer')
  })

  it('منو که به کشو رفت، جای آزادشده دوباره به قرص می‌رسد', () => {
    //: همبرگر (۵۲) خیلی از منو (۶۲۰) باریک‌تر است، پس بعد از جمع‌شدنِ منو معمولاً
    //: نوشته‌ی جست‌وجو برمی‌گردد — و برگرداندنش بهتر از نگه‌داشتنِ ذره‌بین است.
    expect(fitBar(at(900))).toEqual({ search: 'pill', menu: 'drawer' })
  })

  it('باریک‌ترین حالت: کشو + ذره‌بین — ولی باز هم جست‌وجو هست', () => {
    expect(fitBar(at(320))).toEqual({ search: 'icon', menu: 'drawer' })
  })

  it('روی مرزِ دقیق، حالتِ بهتر می‌ماند', () => {
    const edge = M.bare + M.menu + M.pill
    expect(fitBar(at(edge))).toEqual({ search: 'pill', menu: 'bar' })
    expect(fitBar(at(edge - 1)).search).toBe('icon')
  })
})

describe('همبرگر جایگزینِ منوست، نه اضافه بر آن', () => {
  it('وقتی منو روی نوار می‌ماند، هزینه‌ی همبرگر شمرده نمی‌شود', () => {
    //: نوارِ درست‌جا‌شونده نباید به‌خاطرِ همبرگری که اصلاً رندر نمی‌شود به کشو برود.
    const avail = M.bare + M.menu + M.pill + 10
    expect(fitBar(at(avail, { hamburger: 400 })).menu).toBe('bar')
  })

  it('وقتی منو در کشوست، هزینه‌ی همبرگر شمرده می‌شود', () => {
    //: بدونِ این، روی ۳۹۰px نوار فکر می‌کرد جا دارد و ۴۴px از لبه بیرون می‌زد.
    const avail = M.bare + 52 + M.pill
    expect(fitBar(at(avail, { menu: 9999 })).search).toBe('pill')
    expect(fitBar(at(avail - 1, { menu: 9999 })).search).toBe('icon')
  })
})

describe('ناوردا', () => {
  //: عرضِ گوشیِ باریک تا نمایشگرِ بزرگ.
  const widths = Array.from({ length: 1601 }, (_, i) => 320 + i)

  it('در هیچ عرضی جست‌وجو از نوار حذف نمی‌شود', () => {
    const shapes = new Set(widths.map((w) => fitBar(at(w)).search))
    expect([...shapes].sort()).toEqual(['icon', 'pill'])
  })

  it('هیچ عرضی نیست که منو روی نوار بماند ولی نوار سرریز کند', () => {
    const bad = widths.filter((w) => {
      const f = fitBar(at(w))
      const used =
        M.bare +
        (f.menu === 'bar' ? M.menu : M.hamburger) +
        (f.search === 'pill' ? M.pill : M.icon)
      return used > w
    })
    //: تنها استثنای مجاز، باریک‌ترین حالتِ ممکن است که دیگر چیزی برای کوچک‌کردن ندارد.
    expect(bad.every((w) => M.bare + M.hamburger + M.icon > w)).toBe(true)
  })

  it('با باریک‌شدن، هر پله فقط یک‌طرفه رد می‌شود (نوسان نمی‌کند)', () => {
    let seenDrawer = false
    for (const w of [...widths].reverse()) {
      const f = fitBar(at(w))
      if (f.menu === 'drawer') seenDrawer = true
      else expect(seenDrawer).toBe(false)
    }
  })

  it('نوارِ خلوت (حسابِ کم‌ماژول) روی موبایل هم قرص را نگه می‌دارد', () => {
    //: با سه ماژول `menu` کوچک است و روی ۳۹۰px هنوز جا دارد — همان چیزی که
    //: بریک‌پوینتِ ثابت نمی‌توانست بفهمد.
    expect(fitBar(at(390, { bare: 120, menu: 100 }))).toEqual({ search: 'pill', menu: 'bar' })
  })
})
