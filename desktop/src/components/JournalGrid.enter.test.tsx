// @vitest-environment jsdom
/**
 * Enter روی مبلغِ خالی: باقی‌مانده می‌نشیند **و** فوکوس جلو می‌رود — در یک ضربه.
 *
 * پیش از این مبلغ می‌نشست و فوکوس روی همان خانه می‌ماند، در حالی که کامنتِ کد
 * می‌گفت «و بعد مثلِ همیشه جلو می‌رود». حسابدار باید دوباره Enter می‌زد.
 *
 * پیش‌نویس این‌جا با همان توابعِ خالصِ `journalLineOps` ساخته می‌شود که
 * `useJournalEntryDraft` مصرف می‌کند — نه بدل: باقی‌مانده همان `remainingOf` است.
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
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

function render(initial: JournalDraftLine[]) {
  act(() => root.render(createElement(Harness, { initial })))
}

//: ستون‌ها بی ارز/تفصیلی/پیگیری: حساب(۰) · شرح(۱) · بدهکار(۲) · بستانکار(۳)
const DEBIT = 2
const CREDIT = 3
const input = (row: number, col: number) =>
  container.querySelector<HTMLInputElement>(`[data-cell="${row}-${col}"] input`)!
const focusedCell = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell

async function enterOn(el: HTMLElement) {
  act(() => el.focus())
  await act(async () => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }))
    //: ردیفِ تازه بعد از رندر فوکوس می‌گیرد (`requestAnimationFrame`).
    await new Promise((r) => requestAnimationFrame(() => r(null)))
  })
}

describe('Enter روی مبلغِ خالی', () => {
  it('**باقی‌مانده می‌نشیند و فوکوس در همان ضربه جلو می‌رود**', async () => {
    render([line({ accountId: 'bank', debit: '20000000' }), line({ accountId: 'cust' })])
    await enterOn(input(1, DEBIT))

    expect(latest[1]).toMatchObject({ credit: '20000000', debit: '' })
    //: ردیفِ آخر بود، پس ردیفِ تازه ساخته شد و فوکوس روی حسابِ آن است — نه روی
    //: بستانکارِ همین ردیف که حالا پر است، و نه همان بدهکار.
    expect(latest).toHaveLength(3)
    expect(focusedCell()).toBe('2-0')
  })

  it('باقی‌مانده‌ی بدهکار روی ستونِ بدهکار: از بستانکارِ خالیِ همان ردیف هم رد می‌شود', async () => {
    render([line({ accountId: 'bank', credit: '750' }), line({ accountId: 'cust' }), line()])
    await enterOn(input(1, DEBIT))

    expect(latest[1]).toMatchObject({ debit: '750', credit: '' })
    expect(focusedCell()).toBe('2-0')
    expect(latest).toHaveLength(3) // ردیفِ بعدی بود؛ ردیفِ تازه لازم نشد
  })

  it('ردیفی که مبلغ دارد دست نمی‌خورد — Enterِ عادی', async () => {
    render([line({ accountId: 'bank', debit: '500' }), line({ accountId: 'cust', debit: '100' })])
    await enterOn(input(1, DEBIT))

    expect(latest[1]).toMatchObject({ debit: '100', credit: '' })
    expect(focusedCell()).toBe(`1-${CREDIT}`)
  })

  it('سندِ متوازن: پیشنهادی نیست — Enterِ عادی به بستانکار', async () => {
    render([line({ accountId: 'bank', debit: '500' }), line({ accountId: 'cust', credit: '500' }), line({ accountId: 'cust' })])
    await enterOn(input(2, DEBIT))

    expect(latest[2]).toMatchObject({ debit: '', credit: '' })
    expect(focusedCell()).toBe(`2-${CREDIT}`)
  })
})

describe('ستونِ مرکزِ هزینه — بیرون از مسیرِ Enter (§۱۵)', () => {
  const CENTERS = [{ id: 'cc1', code: '10', name: 'پروژه الف', is_active: true }]
  //: ستون‌ها با مرکز: حساب(۰) · مرکز(۱) · شرح(۲) · بدهکار(۳) · بستانکار(۴)
  const renderWithCenters = (initial: JournalDraftLine[]) =>
    act(() => root.render(createElement(Harness, { initial, costCenters: CENTERS })))
  const cell = (r: number, c: number) =>
    //: `SearchSelect` برای فهرستِ کوتاه `<select>`ِ بومی می‌گذارد، برای بلند دکمه‌ی پاپ‌آور.
    container.querySelector<HTMLElement>(
      `[data-cell="${r}-${c}"] input, [data-cell="${r}-${c}"] select, [data-cell="${r}-${c}"] button`,
    )!

  it('ستون فقط وقتی کسب‌وکار مرکز دارد', () => {
    render([line({ accountId: 'bank' }), line()])
    expect(container.querySelector('th')?.parentElement?.textContent).not.toContain('مرکز هزینه')
    renderWithCenters([line({ accountId: 'bank' }), line()])
    expect(container.querySelector('thead')?.textContent).toContain('مرکز هزینه')
  })

  it('Enter از حساب مستقیم به شرح می‌رود؛ Shift+Enter از شرح به حساب برمی‌گردد', async () => {
    renderWithCenters([line({ accountId: 'bank' }), line({ accountId: 'cust' })])
    await enterOn(cell(0, 0))
    expect(focusedCell()).toBe('0-2')

    act(() => cell(0, 2).focus())
    await act(async () => {
      cell(0, 2).dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', shiftKey: true, bubbles: true, cancelable: true }))
    })
    expect(focusedCell()).toBe('0-0')
  })

  it('↓ داخلِ ستونِ مرکز کار می‌کند — Tab/موس به آن می‌رسند و از آن‌جا عمودی می‌رود', () => {
    renderWithCenters([line({ accountId: 'bank' }), line({ accountId: 'cust' })])
    act(() => cell(0, 1).focus())
    act(() => {
      cell(0, 1).dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', code: 'ArrowDown', bubbles: true, cancelable: true }))
    })
    expect(focusedCell()).toBe('1-1')
  })
})

describe('فوکوسِ خودکار (§۴۴)', () => {
  //: صفحه‌ای شبیهِ واقعی: یک دکمه‌ی نوار بیرون از فرم، و یک فیلدِ سربرگ داخلِ فرم.
  function renderPage(focus: 'nav' | 'header') {
    const shell = (grid: boolean) =>
      createElement(
        'div',
        null,
        createElement('button', { id: 'nav', type: 'button' }, 'حسابداری'),
        createElement(
          'form',
          null,
          createElement('input', { id: 'hdr', 'aria-label': 'شرح سند' }),
          grid ? createElement(Harness, { initial: [line({ accountId: 'bank' }), line()] }) : null,
        ),
      )
    act(() => root.render(shell(false)))
    act(() => container.querySelector<HTMLElement>(focus === 'nav' ? '#nav' : '#hdr')!.focus())
    act(() => root.render(shell(true)))
  }

  it('**آمده از نوارِ بالا**: فوکوسِ جامانده روی دکمه‌ی نوار، گرید را از فوکوس محروم نمی‌کند', () => {
    renderPage('nav')
    expect(focusedCell()).toBe('0-0')
  })

  it('کاربری که از سربرگِ همین فرم شروع کرده، فوکوسش دزدیده نمی‌شود', () => {
    renderPage('header')
    expect((document.activeElement as HTMLElement).id).toBe('hdr')
  })
})
