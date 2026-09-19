/**
 * جاگذاریِ پاپ‌آورِ فهرست‌های انتخاب.
 *
 * قیدِ اصلی: **پاپ‌آور هرگز از ویوپورت بیرون نمی‌زند.** چون `position: fixed`
 * است، هر پیکسلی که بیرون بزند نه دیده می‌شود و نه با اسکرول به آن می‌رسی — یعنی
 * آن گزینه‌ها عملاً وجود ندارند. تستِ «جاروب» پایین همین را روی همه‌ی جاهای ممکنِ
 * فیلد می‌سنجد.
 */
import { describe, it, expect } from 'vitest'

import { placePopover, type Anchor, type Viewport } from './popover'

const M = 8
const GAP = 4
const CHROME = 44
const opts = { margin: M, gap: GAP, chrome: CHROME, maxH: 320, minH: 96, minWidth: 240 }

/** فیلدی به ارتفاعِ ۳۶px که لبه‌ی بالایش روی `top` است. */
const field = (top: number, width = 200, right = 400): Anchor => ({
  top,
  bottom: top + 36,
  right,
  width,
})

/** بازه‌ی عمودیِ کلِ پاپ‌آور، از خروجیِ تابع. */
function box(p: ReturnType<typeof placePopover>, vp: Viewport) {
  const total = p.maxH + CHROME
  if (p.top !== undefined) return { start: p.top, end: p.top + total }
  return { start: vp.height - p.bottom! - total, end: vp.height - p.bottom! }
}

describe('سمتِ بازشدن', () => {
  const vp: Viewport = { width: 1440, height: 900 }

  it('جا هست → زیرِ فیلد', () => {
    const p = placePopover(field(200), vp, opts)
    expect(p.top).toBe(240)
    expect(p.bottom).toBeUndefined()
    expect(p.maxH).toBe(320)
  })

  it('فیلدِ نزدیکِ پایین → بالای فیلد باز می‌شود', () => {
    //: زیرِ فیلد فقط ~۶۰px می‌ماند؛ حسابِ قبلی همان‌جا ۱۴۰px تحمیل می‌کرد و
    //: فهرست از پایینِ صفحه می‌زد بیرون.
    const p = placePopover(field(804), vp, opts)
    expect(p.bottom).toBe(vp.height - 804 + GAP)
    expect(p.top).toBeUndefined()
    expect(box(p, vp).start).toBeGreaterThanOrEqual(M)
  })

  it('فضای کم ولی کافیِ پایین، ارتفاع را کوتاه می‌کند نه اینکه بپرد', () => {
    //: زیرِ فیلد ۲۰۰px است: جا هست، فقط کمتر از سقف.
    const p = placePopover(field(652), vp, opts)
    expect(p.top).toBe(692)
    expect(p.maxH).toBe(vp.height - 692 - M - CHROME)
  })

  it('پنجره‌ی خیلی کوتاه: به بالای ویوپورت می‌چسبد و کوتاه می‌شود', () => {
    const short: Viewport = { width: 1440, height: 240 }
    const p = placePopover(field(100), short, opts)
    expect(p.top).toBe(M)
    expect(box(p, short).end).toBeLessThanOrEqual(short.height - M)
  })
})

describe('جاروب: هیچ‌جا بیرون نمی‌زند', () => {
  for (const vp of [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
    { width: 740, height: 360 },
  ] satisfies Viewport[]) {
    it(`${vp.width}×${vp.height}`, () => {
      for (let top = 0; top <= vp.height - 36; top += 4) {
        const p = placePopover(field(top, 200, Math.min(400, vp.width - 20)), vp, opts)
        const b = box(p, vp)
        expect(b.start).toBeGreaterThanOrEqual(M)
        expect(b.end).toBeLessThanOrEqual(vp.height - M)
        expect(p.left).toBeGreaterThanOrEqual(M)
        expect(p.left + p.width).toBeLessThanOrEqual(vp.width - M)
      }
    })
  }
})

describe('عرض', () => {
  it('فیلدِ باریک، کمینه‌ی عرض می‌گیرد', () => {
    expect(placePopover(field(100, 90), { width: 1440, height: 900 }, opts).width).toBe(240)
  })

  it('فیلدِ پهن، عرضِ خودش را نگه می‌دارد', () => {
    expect(placePopover(field(100, 520), { width: 1440, height: 900 }, opts).width).toBe(520)
  })

  it('روی ۳۹۰px به عرضِ صفحه کلامپ می‌شود', () => {
    //: فیلدی که خودش از صفحه پهن‌تر است — داخلِ جدولِ لغزان چنین چیزی رخ می‌دهد.
    const p = placePopover(field(100, 420, 380), { width: 390, height: 844 }, opts)
    expect(p.width).toBe(390 - M * 2)
    expect(p.left).toBe(M)
  })
})
