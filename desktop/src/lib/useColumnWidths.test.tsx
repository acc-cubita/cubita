// @vitest-environment jsdom
/**
 * عرضِ ستون‌های جدولِ اکسلی در حالتِ «جا در قاب».
 *
 * * کشیدنِ لبه‌ی میانِ دو ستون **فقط همان دو** را عوض می‌کند — جمعشان ثابت، بقیه دست‌نخورده، و
 *   عرضِ کلِ جدول همان؛ پس نه فضای سفید می‌ماند نه اسکرولِ افقی.
 * * ستون‌های ثابت (شماره‌ی ردیف، آیکون‌ها) هرگز عوض نمی‌شوند و لبه‌ی کنارشان کشیدنی نیست.
 * * ستونِ کشسان (حساب/شرح) عرضِ صریح ندارد و باقی را می‌گیرد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { MIN_COL_WIDTH, dragBoundary, fitShares, useColumnWidths } from './useColumnWidths'

const LAYOUT = { fixed: ['num', 'actions'], auto: 'account', autoMin: 160 }
const IDS = ['num', 'account', 'desc', 'debit', 'credit', 'actions']
const PX = { num: 44, account: 300, desc: 120, debit: 160, credit: 160, actions: 104 }
const TOTAL = 888
const px = (shares: Record<string, number>, id: string) => (shares[id] / 100) * TOTAL

describe('dragBoundary — فقط دو ستونِ هم‌سایه', () => {
  it('شرح پهن‌تر، بدهکار به همان اندازه باریک‌تر؛ بستانکار دست‌نخورده', () => {
    const s = dragBoundary(PX, IDS, 'desc', 40, LAYOUT)!
    expect(px(s, 'desc')).toBeCloseTo(160, 0)
    expect(px(s, 'debit')).toBeCloseTo(120, 0)
    expect(px(s, 'credit')).toBeCloseTo(160, 0)
    //: ستون‌های ثابت و کشسان درصد نمی‌گیرند.
    expect(Object.keys(s).sort()).toEqual(['credit', 'debit', 'desc'])
  })

  it('لبه‌ی کنارِ ستونِ ثابت کشیدنی نیست', () => {
    expect(dragBoundary(PX, IDS, 'credit', 30, LAYOUT)).toBeNull()
    expect(dragBoundary(PX, IDS, 'num', 30, LAYOUT)).toBeNull()
  })

  it('لبه‌ی حساب (کشسان): هم‌سایه‌اش باریک می‌شود و حساب خودکار جایش را می‌گیرد', () => {
    const s = dragBoundary(PX, IDS, 'account', 50, LAYOUT)!
    expect(px(s, 'desc')).toBeCloseTo(70, 0)
    expect(px(s, 'debit')).toBeCloseTo(160, 0)
  })

  it('کمینه‌ها: هیچ ستونی زیرِ ۴۸px نمی‌رود، حساب زیرِ کفِ خودش هم', () => {
    const s = dragBoundary(PX, IDS, 'desc', 500, LAYOUT)!
    expect(px(s, 'debit')).toBeCloseTo(MIN_COL_WIDTH, 0)
    expect(px(s, 'desc')).toBeCloseTo(120 + 160 - MIN_COL_WIDTH, 0)
    //: کشیدنِ شرح به سمتِ حساب؟ نه — لبه‌ی چپِ شرح مالِ شرح/بدهکار است؛ حساب با لبه‌ی خودش.
    const t = dragBoundary(PX, IDS, 'account', -500, LAYOUT)!
    expect(px(t, 'desc')).toBeCloseTo(120 + (300 - 160), 0)
  })
})

let container: HTMLDivElement
let root: Root
let api: ReturnType<typeof useColumnWidths>
function Probe() {
  api = useColumnWidths('test.shares', LAYOUT)
  return null
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('useColumnWidths', () => {
  it('تا کاربر دست نزده: هیچ سبکی — چیدمانِ پیش‌فرضِ CSS', () => {
    act(() => root.render(createElement(Probe)))
    expect(api.customized).toBe(false)
    expect(api.col('desc')).toBeUndefined()
    expect(api.col('account')).toBeUndefined()
  })

  it('بعد از کشیدن: درصد برای ستون‌های معمولی، `auto` برای کشسان، هیچ برای ثابت', () => {
    localStorage.setItem('test.shares', JSON.stringify({ desc: 18, debit: 13.5 }))
    act(() => root.render(createElement(Probe)))
    expect(api.col('desc')).toEqual({ width: '18%' })
    expect(api.col('account')).toEqual({ width: 'auto' })
    expect(api.col('actions')).toBeUndefined()
    expect(api.col('num')).toBeUndefined()
    //: ستونی که تازه پیدا شده و درصدی ندارد، پیش‌فرضِ CSS.
    expect(api.col('credit')).toBeUndefined()
  })

  it('canResize: کنارِ ستونِ ثابت نه', () => {
    act(() => root.render(createElement(Probe)))
    expect(api.canResize('credit', 'actions')).toBe(false)
    expect(api.canResize('debit', 'credit')).toBe(true)
    expect(api.canResize('amount', undefined)).toBe(false)
  })

  it('عرض‌های پیکسلیِ نسخه‌ی قبل (بالای ۱۰۰) نادیده گرفته می‌شوند', () => {
    localStorage.setItem('test.shares', JSON.stringify({ desc: 240, debit: 'x' }))
    act(() => root.render(createElement(Probe)))
    expect(api.customized).toBe(false)
  })
})

describe('fitShares — کفِ ستونِ کشسان در زمانِ نمایش', () => {
  const pct = (s: Record<string, number>, ids: string[]) => ids.reduce((t, id) => t + s[id], 0)

  it('اگر جا هست، همان ورودی', () => {
    const s = { desc: 20, debit: 15 }
    expect(fitShares(s, ['desc', 'debit'], 1000, 148, 160)).toBe(s)
  })

  it('سهم‌هایی که همه‌ی جا را گرفته‌اند (باگِ «ستونِ حساب ناپدید شد») به یک نسبت کوچک می‌شوند', () => {
    //: عیناً داده‌ی ذخیره‌شده در اپِ کاربر: شرح ۷۲٪ — حساب با پنجره‌ی ۱۵۰۰ پیکسلی صفر می‌شد.
    const s = { description: 72.07, debit: 7.07, credit: 10.97 }
    const ids = ['description', 'debit', 'credit']
    const out = fitShares(s, ids, 1500, 148, 160)
    const left = 1500 - 148 - (pct(out, ids) / 100) * 1500
    expect(left).toBeGreaterThanOrEqual(159)
    expect(left).toBeLessThan(162)
    //: نسبتِ ستون‌ها به هم همان می‌ماند — فقط همه با هم کوچک شدند.
    expect(out.description / out.debit).toBeCloseTo(s.description / s.debit, 1)
  })

  it('هیچ ستونی زیرِ کمینه نمی‌رود، حتی در جدولِ خیلی باریک', () => {
    const out = fitShares({ desc: 50, debit: 40 }, ['desc', 'debit'], 400, 148, 160)
    expect((out.debit / 100) * 400).toBeGreaterThanOrEqual(MIN_COL_WIDTH - 0.01)
  })
})

describe('useColumnWidths — با جدولِ واقعی', () => {
  let rect: typeof HTMLElement.prototype.getBoundingClientRect
  beforeEach(() => {
    rect = HTMLElement.prototype.getBoundingClientRect
    //: jsdom چیدمان ندارد؛ عرض‌ها از خودِ عنصر: جدول ۱۰۰۰، شماره ۴۴، کنش‌ها ۱۰۴.
    HTMLElement.prototype.getBoundingClientRect = function (this: HTMLElement) {
      const w = this.tagName === 'TABLE' ? 1000 : ({ num: 44, actions: 104 } as Record<string, number>)[this.dataset.col ?? ''] ?? 100
      return { width: w, height: 30, x: 0, y: 0, top: 0, left: 0, right: w, bottom: 30, toJSON: () => ({}) } as DOMRect
    }
  })
  afterEach(() => {
    HTMLElement.prototype.getBoundingClientRect = rect
  })

  function Table() {
    api = useColumnWidths('test.shares', LAYOUT)
    return createElement(
      'table',
      { ref: api.frame },
      createElement(
        'thead',
        null,
        createElement(
          'tr',
          null,
          IDS.map((id) => createElement('th', { key: id, 'data-col': id })),
        ),
      ),
    )
  }

  it('سهم‌های بیش‌ازحد روی صفحه کوچک می‌شوند تا «حساب» کمینه‌اش را داشته باشد', () => {
    localStorage.setItem('test.shares', JSON.stringify({ desc: 60, debit: 20, credit: 10 }))
    act(() => root.render(createElement(Table)))
    const w = (id: string) => parseFloat(String(api.col(id)?.width))
    const used = ((w('desc') + w('debit') + w('credit')) / 100) * 1000
    expect(1000 - 148 - used).toBeGreaterThanOrEqual(159)
    expect(w('desc') / w('debit')).toBeCloseTo(3, 1)
    expect(api.col('account')).toEqual({ width: 'auto' })
    //: ذخیره‌ی کاربر دست نمی‌خورد — پنجره که پهن شود، همان سهم‌ها برمی‌گردند.
    expect(JSON.parse(localStorage.getItem('test.shares')!)).toEqual({ desc: 60, debit: 20, credit: 10 })
  })

  it('ذخیره‌ی نسخه‌های پیش از «جا در قاب» (با شماره و حساب) کنار می‌رود', () => {
    localStorage.setItem(
      'test.shares',
      JSON.stringify({ desc: 72.07, debit: 7.07, credit: 10.97, num: 44, account: 320, actions: 104 }),
    )
    act(() => root.render(createElement(Table)))
    expect(api.customized).toBe(false)
    expect(api.col('desc')).toBeUndefined()
  })
})
