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
