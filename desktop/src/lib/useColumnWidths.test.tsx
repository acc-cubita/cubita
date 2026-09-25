// @vitest-environment jsdom
/**
 * عرضِ ستون‌های جدولِ اکسلی — **جدول هرگز باریک‌تر از قاب نمی‌شود.**
 *
 * باریک‌کردنِ ستون‌ها قبلاً کنارِ جدول فضای سفید می‌گذاشت (جدول = جمعِ ستون‌ها). حالا جدول دست‌کم
 * تمام‌عرض است و ستونِ کشسان عرضِ صریح نمی‌گیرد تا جای اضافه مالِ او شود.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useColumnWidths } from './useColumnWidths'

let container: HTMLDivElement
let root: Root
let api: ReturnType<typeof useColumnWidths>

function Probe() {
  api = useColumnWidths('test.widths', { a: 100, b: 200, c: 50 }, 'b')
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
  it('تا کاربر دست نزده: هیچ سبکی — چیدمانِ پیش‌فرضِ جدول می‌ماند', () => {
    act(() => root.render(createElement(Probe)))
    expect(api.customized).toBe(false)
    expect(api.col('a')).toBeUndefined()
    expect(api.table(['a', 'b', 'c'])).toBeUndefined()
  })

  it('بعد از کشیدن: ستون‌ها پیکسلی، ستونِ کشسان `auto`، و جدول دست‌کم تمام‌عرض', () => {
    localStorage.setItem('test.widths', JSON.stringify({ a: 60, b: 180, c: 50 }))
    act(() => root.render(createElement(Probe)))
    expect(api.col('a')).toEqual({ width: 60 })
    //: صریحاً `auto` — «بی‌سبک» عرضِ پیش‌فرضِ کلاسِ ستون را نگه می‌داشت.
    expect(api.col('b')).toEqual({ width: 'auto' })
    //: جمعِ همه (کفِ ستونِ کشسان هم) — و `minInlineSize: 100%` تا فضای سفید نماند.
    expect(api.table(['a', 'b', 'c'])).toEqual({ width: 290, minInlineSize: '100%' })
  })

  it('عرضِ نامعتبرِ ذخیره‌شده نادیده گرفته می‌شود', () => {
    localStorage.setItem('test.widths', JSON.stringify({ a: 'x', b: 10 }))
    act(() => root.render(createElement(Probe)))
    expect(api.customized).toBe(false)
  })
})
