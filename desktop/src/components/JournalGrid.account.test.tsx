// @vitest-environment jsdom
/**
 * خانه‌ی حسابِ گرید — کادرِ جست‌وجوی درجا (`AccountCombo`).
 *
 * * تایپ در **همان خانه** فهرست را زیرش باز و فیلتر می‌کند (کد یا نام).
 * * Enter انتخاب می‌کند، فهرست را می‌بندد، و گرید **مستقیم به بدهکار** می‌رود (شرح اختیاری
 *   است و بیرون از مسیرِ Enter).
 * * ↑/↓ مالِ فهرست است تا باز است — گرید ردیف عوض نمی‌کند.
 * * Esc و بیرون‌رفتن مقدارِ قبلی را برمی‌گرداند؛ Enter روی خانه‌ی خالی فهرست را باز می‌کند.
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
  document.documentElement.dir = 'rtl'
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const render = (initial: JournalDraftLine[]) =>
  act(() => root.render(createElement('form', null, createElement(Harness, { initial }))))
//: ستون‌ها: حساب(۰) · شرح(۱) · بدهکار(۲) · بستانکار(۳)
const combo = (row: number) => container.querySelector<HTMLInputElement>(`[data-cell="${row}-0"] input[role="combobox"]`)!
const options = () => [...document.body.querySelectorAll<HTMLElement>('[role="option"]')].map((o) => o.textContent?.trim())
const focusedCell = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell
const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!

function type(el: HTMLInputElement, text: string) {
  act(() => el.focus())
  act(() => {
    setValue.call(el, text)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function key(el: Element, code: string, init: KeyboardEventInit = {}) {
  const ev = new KeyboardEvent('keydown', { key: code === 'Escape' ? 'Escape' : code.replace(/^Arrow/, 'Arrow'), code, bubbles: true, cancelable: true, ...init })
  await act(async () => {
    el.dispatchEvent(ev)
  })
  return ev.defaultPrevented
}

describe('جست‌وجوی درجا', () => {
  it('تایپِ کد در همان خانه فهرست را باز و فیلتر می‌کند', () => {
    render([line(), line()])
    type(combo(0), '13')
    expect(combo(0).getAttribute('aria-expanded')).toBe('true')
    expect(combo(0).value).toBe('13')
    expect(options()).toEqual(['1301 — طرف حساب'])
  })

  it('نام هم پیدا می‌شود', () => {
    render([line(), line()])
    type(combo(0), 'بان')
    expect(options()).toEqual(['1101 — بانک ملی'])
  })

  it('Enter: انتخاب، بستنِ فهرست، و رفتن به بدهکار — بی ایستادن روی شرح', async () => {
    render([line(), line()])
    type(combo(0), '13')
    await key(combo(0), 'Enter')
    expect(latest[0].accountId).toBe('cust')
    expect(options()).toEqual([])
    expect(focusedCell()).toBe('0-2')
  })

  it('↑/↓ گزینه را جابه‌جا می‌کند و به گرید نمی‌رسد', async () => {
    render([line(), line()])
    type(combo(0), '1')
    expect(options()).toHaveLength(2)
    await key(combo(0), 'ArrowDown')
    expect(focusedCell()).toBe('0-0') //: ردیف عوض نشد
    const active = combo(0).getAttribute('aria-activedescendant')!
    expect(document.getElementById(active)?.textContent).toContain('1301')
    await key(combo(0), 'Enter')
    expect(latest[0].accountId).toBe('cust')
  })

  it('Esc مقدارِ قبلی را برمی‌گرداند و خانه را نگه می‌دارد', async () => {
    render([line({ accountId: 'bank' }), line()])
    type(combo(0), '13')
    await key(combo(0), 'Escape')
    expect(options()).toEqual([])
    expect(combo(0).value).toBe('1101 — بانک ملی')
    expect(latest[0].accountId).toBe('bank')
    expect(focusedCell()).toBe('0-0')
  })

  it('بیرون رفتن بی‌انتخاب چیزی را عوض نمی‌کند', () => {
    render([line({ accountId: 'bank' }), line()])
    type(combo(0), '13')
    act(() => combo(1).focus())
    expect(options()).toEqual([])
    expect(latest[0].accountId).toBe('bank')
    expect(combo(0).value).toBe('1101 — بانک ملی')
  })

  it('Enter روی خانه‌ی خالیِ بسته فهرستِ کامل را باز می‌کند و جلو نمی‌رود', async () => {
    render([line(), line()])
    act(() => combo(0).focus())
    const prevented = await key(combo(0), 'Enter')
    expect(prevented).toBe(true) //: فرم ثبت نمی‌شود
    expect(options()).toHaveLength(2)
    expect(focusedCell()).toBe('0-0')
  })

  it('Enter روی خانه‌ی پُرِ بسته مثلِ هر خانه‌ای جلو می‌رود — به بدهکار', async () => {
    render([line({ accountId: 'bank' }), line()])
    act(() => combo(0).focus())
    await key(combo(0), 'Enter')
    expect(focusedCell()).toBe('0-2')
  })

  it('Tab بعد از تایپ: همان گزینه‌ی برجسته را برمی‌دارد و به خانه‌ی بعد (شرح) می‌رود', async () => {
    render([line(), line()])
    type(combo(0), 'بان')
    await key(combo(0), 'Tab')
    expect(latest[0].accountId).toBe('bank')
    expect(focusedCell()).toBe('0-1')
  })

  it('F4 از خانه‌ی مبلغ فهرستِ حسابِ همان ردیف را باز می‌کند', async () => {
    render([line({ accountId: 'bank' }), line()])
    const debit = container.querySelector<HTMLInputElement>('[data-cell="1-2"] input')!
    act(() => debit.focus())
    await key(debit, 'F4')
    expect(focusedCell()).toBe('1-0')
    expect(combo(1).getAttribute('aria-expanded')).toBe('true')
    expect(options()).toHaveLength(2)
  })
})
