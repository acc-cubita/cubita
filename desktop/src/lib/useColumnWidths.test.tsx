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

import { MIN_COL_WIDTH, dragBoundary, useColumnWidths } from './useColumnWidths'

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
