// @vitest-environment jsdom
/**
 * «گزارش دفتر» (تمِ اکسلی) — دفترِ حساب: «مانده‌ی ابتدای دوره» در خودِ گرید، «جمعِ بازه» و مانده‌ی پایان در پانویس،
 * انتخاب با شماره‌ی ردیف بی بازکردنِ سند و جمعِ نوار، صفحه‌کلید، و دفترِ تفصیلی که تفصیلی را به سطرِ اولِ سربرگ می‌برد.
 * روزنامه تست‌های خودش را در `Daybook.test.tsx` دارد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LedgerReportPage } from './LedgerReportPage'

let container: HTMLDivElement
let root: Root
let calls: string[]

const acc = (id: string, parent: string | null, group = false) => ({
  id,
  code: id,
  name: `حساب ${id}`,
  type: 'asset',
  parent_id: parent,
  is_group: group,
})
const CHART = [acc('1', null, true), acc('11', '1', true), acc('1101', '11'), acc('1102', '11')]

const ledgerLine = (i: number, debit: number, credit: number, balance: number) => ({
  line_id: `l${i}`,
  entry_id: `e${i}`,
  entry_number: 100 + i,
  entry_date: '2026-09-10',
  entry_status: i === 1 ? 'temporary' : 'permanent',
  source_type: 'manual',
  account_code: '1101',
  account_name: 'صندوق',
  description: `ردیفِ ${i}`,
  debit: String(debit),
  credit: String(credit),
  balance: String(balance),
  currency_code: null,
  fx_amount: null,
  fx_rate: null,
  tracking_no: null,
  tracking_date: null,
})

const LEDGER = {
  account_id: '1101',
  account_code: '1101',
  account_name: 'صندوق',
  opening_balance: '500',
  closing_balance: '650',
  fx_totals: [],
  limit: null,
  lines: [ledgerLine(0, 200, 0, 700), ledgerLine(1, 0, 80, 620), ledgerLine(2, 30, 0, 650)],
}

function respond(url: string): unknown {
  const u = new URL(url)
  if (u.pathname === '/api/accounts') return CHART
  if (u.pathname === '/api/accounting/analytics') return [{ id: 'an1', code: 'P1', name: 'پروژه‌ی الف' }]
  if (u.pathname.startsWith('/api/reports/general-ledger')) return LEDGER
  if (u.pathname.startsWith('/api/journal-entries/e')) return { id: 'e0', number: 100, entry_date: '2026-09-10', description: '', source_type: 'manual', source: null, lines: [], status: 'permanent', voided_at: null }
  if (u.pathname === '/api/journal-entries') return { items: [], next_cursor: null }
  if (u.pathname === '/api/journal-entries/summary') return { entry_count: 0, line_count: 0, total_debit: '0', total_credit: '0' }
  return []
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      return { ok: true, status: 200, json: async () => respond(url) }
    }),
  )
  Element.prototype.scrollIntoView = () => {}
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

const wait = () => act(() => new Promise<void>((r) => setTimeout(r, 0)))
const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel)
const $$ = (sel: string) => [...document.querySelectorAll<HTMLElement>(sel)]
const text = (el: Element | null | undefined) => el?.textContent?.replace(/\s+/g, ' ').trim() ?? ''
const book = (label: string) => $$('[aria-label="دفتر"] button').find((b) => b.textContent === label)!
const click = (el: Element, init: MouseEventInit = {}) =>
  act(() => el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, ...init })))
const key = (el: Element, k: string, init: KeyboardEventInit = {}) =>
  act(() => el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...init })))

async function choose(select: HTMLSelectElement, value: string) {
  act(() => {
    select.value = value
    select.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await wait()
  await wait()
}

async function openLedger() {
  act(() => root.render(createElement(LedgerReportPage, { token: 't' })))
  await wait()
  await wait()
  click(book('معین'))
  await choose($<HTMLSelectElement>('.lr-param select')!, '1101')
}

describe('گزارش دفتر — دفترِ حساب', () => {
  it('مانده‌ی ابتدای دوره ردیفِ اول، جمعِ بازه و مانده‌ی پایان در پانویس', async () => {
    await openLedger()
    expect(calls.some((c) => c.includes('/api/reports/general-ledger/1101'))).toBe(true)
    expect(text($('.lr-ledger tr.lr-carry'))).toContain('مانده‌ی ابتدای دوره')
    expect(text($('.lr-ledger tr.lr-carry td[data-label="مانده"]'))).toBe('۵۰۰')
    //: جمعِ ردیف‌ها (سرور period_debit نفرستاده): ۲۳۰ بدهکار، ۸۰ بستانکار؛ مانده‌ی پایان ۶۵۰.
    expect(text($('.lr-ledger tfoot td[data-label="جمعِ بدهکار"]'))).toBe('۲۳۰')
    expect(text($('.lr-ledger tfoot td[data-label="جمعِ بستانکار"]'))).toBe('۸۰')
    expect(text($('.lr-ledger tfoot td[data-label="مانده‌ی پایان"]'))).toBe('۶۵۰')
    //: دفترِ معین ستونِ «حساب» ندارد — همه‌ی ردیف‌ها یک حساب‌اند.
    expect($$('.lr-ledger thead th').map((th) => th.textContent)).not.toContain('حساب')
    expect(text($('.lr-ledger tbody tr#lr-line-1 .lr-badge'))).toBe('موقت')
  })

  it('شماره‌ی ردیف فقط انتخاب می‌کند و نوار جمع می‌دهد؛ کلیکِ ردیف سند را باز می‌کند', async () => {
    await openLedger()
    const heads = $$('.lr-ledger tbody .xl-rowhead-btn')
    click(heads[0])
    click(heads[1], { shiftKey: true })
    expect($('.drawer-panel')).toBeNull()
    expect(text($('.xl-selbar'))).toContain('۲ ردیف انتخاب شد')
    expect(text($('.xl-selbar'))).toContain('بدهکار ۲۰۰')
    expect(text($('.xl-selbar'))).toContain('بستانکار ۸۰')
    click($('.lr-ledger tbody tr#lr-line-2 td[data-label="شرح"]')!)
    await wait()
    expect(calls.some((c) => c.endsWith('/api/journal-entries/e2'))).toBe(true)
  })

  it('صفحه‌کلید: ↓ حرکت، Space انتخاب، Esc لغو، Enter سند', async () => {
    await openLedger()
    const grid = $('.lr-scroll')!
    key(grid, 'ArrowDown')
    expect($('.lr-ledger tbody tr.is-active')!.id).toBe('lr-line-1')
    key(grid, ' ')
    key(grid, 'ArrowDown', { shiftKey: true })
    expect($$('.lr-ledger tbody tr.is-selected').map((tr) => tr.id)).toEqual(['lr-line-1', 'lr-line-2'])
    key(grid, 'Escape')
    expect($$('.lr-ledger tbody tr.is-selected')).toHaveLength(0)
    key(grid, 'Enter')
    await wait()
    expect(calls.some((c) => c.endsWith('/api/journal-entries/e2'))).toBe(true)
  })

  it('دفترِ کل فقط حساب‌های سطحِ کل را می‌دهد و ستونِ «حساب» دارد', async () => {
    act(() => root.render(createElement(LedgerReportPage, { token: 't' })))
    await wait()
    await wait()
    click(book('کل'))
    const select = $<HTMLSelectElement>('.lr-param select')!
    expect([...select.options].map((o) => o.value)).toEqual(['', '11'])
    await choose(select, '11')
    expect(calls.some((c) => c.includes('/api/reports/general-ledger/11'))).toBe(true)
    expect($$('.lr-ledger thead th').map((th) => th.textContent)).toContain('حساب')
  })

  it('دفترِ تفصیلی: تفصیلی در سطرِ اولِ سربرگ است و از نوارِ فیلتر برداشته می‌شود', async () => {
    act(() => root.render(createElement(LedgerReportPage, { token: 't' })))
    await wait()
    await wait()
    click(book('تفصیلی'))
    await wait()
    expect(text($('.lr-param .jh-label'))).toBe('تفصیلی')
    expect($$('.rh-row--filters .jh-label').map((l) => l.textContent)).not.toContain('تفصیلی')
    expect(text($('.page, body'))).toContain('یک تفصیلی از سربرگ انتخاب کنید')
    await choose($<HTMLSelectElement>('.lr-param select')!, 'an1')
    const req = calls.filter((c) => new URL(c).pathname === '/api/reports/general-ledger').at(-1)!
    expect(new URL(req).searchParams.get('analytic_id')).toBe('an1')
  })
})
