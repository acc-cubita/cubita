// @vitest-environment jsdom
/**
 * حافظه‌ی شرح (§۲۰) و رفتن به ردیف (§۴۲) — داخلِ خودِ گرید، با کلیدهای واقعی.
 *
 * چیزی که این‌جا باید ثابت شود و `descriptionMemory.test.ts` نمی‌تواند: فهرستِ
 * پیشنهاد کلیدهای گرید را **نمی‌دزدد** و گرید کلیدهای فهرست را. ↓ وقتی فهرست باز است
 * گزینه را عوض می‌کند نه ردیف را، و Enterِ بی‌انتخاب همان Enterِ گرید است.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { Harness, latest, line } from '../test/journalGridHarness'
import type { JournalDraftLine } from '../lib/journalEntryDraft'

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  sessionStorage.clear()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const render = (initial: JournalDraftLine[]) => act(() => root.render(createElement(Harness, { initial })))
//: ستون‌ها: حساب(۰) · شرح(۱) · بدهکار(۲) · بستانکار(۳)
const desc = (row: number) => container.querySelector<HTMLInputElement>(`[data-cell="${row}-1"] input`)!
const options = () => [...document.body.querySelectorAll<HTMLLIElement>('[role="option"]')]
const focusedCell = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell
const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!

function type(el: HTMLInputElement, text: string) {
  act(() => el.focus())
  act(() => {
    setValue.call(el, text)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
const key = (el: Element, k: string, init: KeyboardEventInit = {}) =>
  act(() => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k, bubbles: true, cancelable: true, ...init }))
  })

describe('حافظه‌ی شرح در گرید', () => {
  const doc = () => [
    line({ accountId: 'bank', debit: '100', description: 'بابت خرید مواد اولیه' }),
    line({ accountId: 'cust', credit: '100', description: 'بابت هزینه حمل' }),
    line({ accountId: 'cust' }),
  ]

  it('تایپ پیشنهاد می‌دهد، ولی **هیچ‌چیز خودکار نمی‌نشیند**', () => {
    render(doc())
    type(desc(2), 'بابت')
    expect(options().map((o) => o.textContent)).toEqual(['بابت هزینه حمل', 'بابت خرید مواد اولیه'])
    expect(latest[2].description).toBe('بابت') // همان که تایپ شد
    expect(desc(2).getAttribute('aria-activedescendant')).toBeNull() // چیزی انتخاب نشده
  })

  it('↓ گزینه را عوض می‌کند نه ردیف را؛ Enter همان را می‌نشاند و فوکوس سرِ جایش می‌ماند', () => {
    render(doc())
    type(desc(2), 'بابت')
    key(desc(2), 'ArrowDown')
    key(desc(2), 'ArrowDown')
    expect(focusedCell()).toBe('2-1')
    expect(options()[1].getAttribute('aria-selected')).toBe('true')

    key(desc(2), 'Enter')
    expect(latest[2].description).toBe('بابت خرید مواد اولیه')
    expect(options()).toHaveLength(0)
    expect(focusedCell()).toBe('2-1')
  })

  it('Enterِ بی‌انتخاب همان Enterِ گرید است: فهرست بسته و خانه‌ی بعد', () => {
    render(doc())
    type(desc(2), 'بابت')
    key(desc(2), 'Enter')
    expect(options()).toHaveLength(0)
    expect(latest[2].description).toBe('بابت')
    expect(focusedCell()).toBe('2-2')
  })

  it('Escape فقط فهرست را می‌بندد، متن دست نمی‌خورد', () => {
    render(doc())
    type(desc(2), 'بابت')
    key(desc(2), 'Escape')
    expect(options()).toHaveLength(0)
    expect(latest[2].description).toBe('بابت')
    expect(focusedCell()).toBe('2-1')
  })

  it('فهرستِ بسته: ↓ مثلِ همیشه ردیف را عوض می‌کند', () => {
    render(doc())
    act(() => desc(0).focus())
    key(desc(0), 'ArrowDown')
    expect(focusedCell()).toBe('1-1')
  })
})

describe('رفتن به ردیف', () => {
  const big = () => Array.from({ length: 300 }, (_, i) => line({ accountId: i % 2 ? 'cust' : 'bank' }))
  const jump = () => container.querySelector<HTMLInputElement>('.jg-jump input')!

  it('Ctrl+G از هر خانه به کادرِ «رفتن به ردیف» می‌رود', () => {
    render(big())
    act(() => desc(10).focus())
    key(desc(10), 'KeyG', { ctrlKey: true })
    expect(document.activeElement).toBe(jump())
  })

  it('۲۳۶ + Enter: فوکوس روی اولین خانه‌ی ردیفِ ۲۳۶ — رقمِ فارسی هم', () => {
    render(big())
    type(jump(), '۲۳۶')
    key(jump(), 'Enter')
    expect(focusedCell()).toBe('235-0')
  })

  it('بیرون از محدوده: پیام، و فوکوس جابه‌جا نمی‌شود', () => {
    render(big())
    type(jump(), '400')
    key(jump(), 'Enter')
    expect(container.querySelector('.jg-jump-msg')?.textContent).toBe('ردیفِ ۴۰۰ نیست — سند ۳۰۰ ردیف دارد.')
    expect(document.activeElement).toBe(jump())
  })
})
