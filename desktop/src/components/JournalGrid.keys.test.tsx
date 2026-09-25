// @vitest-environment jsdom
/**
 * کلیدهای تازه‌ی گریدِ سند: Tab خانه‌به‌خانه (و ردیفِ تازه در انتها)، ←/→ با قاعده‌ی
 * لبه‌ی مکان‌نما، F2 و F4. منطقِ «کدام خانه» در `journalGridNav.test.ts` سنجیده شده؛
 * این‌جا سیم‌کشیِ کلید به DOM است — همان جایی که رفتارِ بدِ واقعی پیدا می‌شود.
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

//: گریدِ داخلِ فرم، با دکمه‌ی ثبت — مقصدِ Tab در انتهای سندِ کامل.
function render(initial: JournalDraftLine[]) {
  act(() =>
    root.render(
      createElement(
        'form',
        null,
        createElement(Harness, { initial }),
        createElement('button', { type: 'submit', id: 'submit' }, 'ثبت سند'),
      ),
    ),
  )
}

//: ستون‌ها: حساب(۰) · شرح(۱) · بدهکار(۲) · بستانکار(۳)
const DESC = 1
const DEBIT = 2
const CREDIT = 3
const cellEl = (row: number, col: number) =>
  container.querySelector<HTMLElement>(
    `[data-cell="${row}-${col}"] input, [data-cell="${row}-${col}"] select, [data-cell="${row}-${col}"] button`,
  )!
const focusedCell = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell

async function press(el: HTMLElement, code: string, opts: KeyboardEventInit = {}) {
  act(() => el.focus())
  let prevented = false
  await act(async () => {
    const ev = new KeyboardEvent('keydown', { key: code, code, bubbles: true, cancelable: true, ...opts })
    el.dispatchEvent(ev)
    prevented = ev.defaultPrevented
    await new Promise((r) => requestAnimationFrame(() => r(null)))
  })
  return prevented
}

describe('Tab در گرید', () => {
  it('خانه‌به‌خانه، و از بستانکار مستقیم به حسابِ ردیفِ بعد — بی سه دکمه‌ی کنشِ ردیف', async () => {
    render([line({ accountId: 'bank', debit: '100' }), line({ accountId: 'cust', credit: '100' })])
    await press(cellEl(0, DESC), 'Tab')
    expect(focusedCell()).toBe(`0-${DEBIT}`)
    await press(cellEl(0, CREDIT), 'Tab')
    expect(focusedCell()).toBe('1-0')
  })

  it('در انتهای ردیفِ آخرِ پر: ردیفِ تازه و فوکوس روی حسابِ آن', async () => {
    render([line({ accountId: 'bank', debit: '100' }), line({ accountId: 'cust', credit: '100' })])
    await press(cellEl(1, CREDIT), 'Tab')
    expect(latest).toHaveLength(3)
    expect(focusedCell()).toBe('2-0')
  })

  it('در انتهای ردیفِ آخرِ خالی: ردیف نمی‌سازد و به «ثبت سند» می‌رود', async () => {
    render([line({ accountId: 'bank', debit: '100' }), line({ accountId: 'cust', credit: '100' }), line()])
    await press(cellEl(2, CREDIT), 'Tab')
    expect(latest).toHaveLength(3)
    expect(document.activeElement?.id).toBe('submit')
  })

  it('Shift+Tab از حسابِ ردیفِ دوم به بستانکارِ ردیفِ اول', async () => {
    render([line({ accountId: 'bank' }), line({ accountId: 'cust' })])
    await press(cellEl(1, 0), 'Tab', { shiftKey: true })
    expect(focusedCell()).toBe(`0-${CREDIT}`)
  })
})

describe('← / → در گریدِ راست‌به‌چپ', () => {
  it('خانه‌ی تازه‌رسیده (کلِ مقدار انتخاب‌شده): ← به خانه‌ی بعد، → به قبل', async () => {
    render([line({ accountId: 'bank', debit: '1500' }), line()])
    const debit = cellEl(0, DEBIT) as HTMLInputElement
    act(() => debit.focus())
    debit.select()
    await press(debit, 'ArrowLeft')
    expect(focusedCell()).toBe(`0-${CREDIT}`)

    const credit = cellEl(0, CREDIT) as HTMLInputElement
    await press(credit, 'ArrowRight') // خالی است → حرکت
    expect(focusedCell()).toBe(`0-${DEBIT}`)
  })

  it('مکان‌نما وسطِ عدد: پیکان مالِ خودِ فیلد است', async () => {
    render([line({ accountId: 'bank', debit: '1500' }), line()])
    const debit = cellEl(0, DEBIT) as HTMLInputElement
    act(() => debit.focus())
    debit.setSelectionRange(2, 2)
    const prevented = await press(debit, 'ArrowLeft')
    expect(prevented).toBe(false)
    expect(focusedCell()).toBe(`0-${DEBIT}`)
  })

  it('F2 مکان‌نما را به انتهای متن می‌برد — بعدش ← داخلِ عدد می‌ماند', async () => {
    render([line({ accountId: 'bank', debit: '1500' }), line()])
    const debit = cellEl(0, DEBIT) as HTMLInputElement
    act(() => debit.focus())
    debit.select()
    await press(debit, 'F2')
    expect([debit.selectionStart, debit.selectionEnd]).toEqual([debit.value.length, debit.value.length])
    //: فیلدِ عددی چپ‌به‌راست است: ← از انتها به‌سمتِ ابتدا — هنوز داخلِ متن.
    const prevented = await press(debit, 'ArrowLeft')
    expect(prevented).toBe(false)
    expect(focusedCell()).toBe(`0-${DEBIT}`)
  })

  it('در لبه‌ی ردیف نمی‌پیچد', async () => {
    render([line({ accountId: 'bank' }), line()])
    await press(cellEl(0, CREDIT), 'ArrowLeft')
    expect(focusedCell()).toBe(`0-${CREDIT}`)
  })
})

describe('F4 — فهرستِ حساب‌ها', () => {
  it('از هر خانه‌ی ردیف فوکوس را به انتخاب‌گرِ حسابِ همان ردیف می‌برد', async () => {
    render([line({ accountId: 'bank' }), line()])
    const prevented = await press(cellEl(1, DEBIT), 'F4')
    expect(prevented).toBe(true)
    expect(focusedCell()).toBe('1-0')
  })
})
