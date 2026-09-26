// @vitest-environment jsdom
/**
 * «گزارش ترازها» (تمِ اکسلی) در DOM.
 *
 * `fetch` با مسیریابِ کوچکی جایگزین می‌شود، پس آدرسِ واقعیِ ترازها هم سنجیده می‌شود. ارقامِ سطحِ آخر از پاسخِ جعلیِ
 * سرورند؛ تجمیعِ سطح و جمع‌ها کارِ `lib/balanceReport` است و این‌جا فقط نمایششان سنجیده می‌شود: سرستونِ دوطبقه،
 * «جمع» با نشانِ توازن، انتخاب با شماره‌ی ردیف بی بازکردنِ دفتر، کیبورد و قالبِ «سند کل».
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { BalanceRow } from '../../api'
import { BalanceReportPage } from './BalanceReportPage'

let container: HTMLDivElement
let root: Root
let calls: string[]
let balances: BalanceRow[]

const acc = (id: string, parent: string | null) => ({ id, code: id, name: `حساب ${id}`, type: 'asset', parent_id: parent })
//: ۱۱ (کل) ← ۱۱۰۱ و ۱۱۰۲؛ ۴۱ (کل) ← ۴۱۰۱.
const CHART = [acc('1', null), acc('11', '1'), acc('1101', '11'), acc('1102', '11'), acc('4', null), acc('41', '4'), acc('4101', '41')]

const row = (id: string, name: string, n: Partial<Record<'od' | 'oc' | 'pd' | 'pc' | 'cd' | 'cc', number>>, active = true): BalanceRow => ({
  account_id: id,
  account_code: id,
  account_name: name,
  account_type: 'asset',
  parent_id: null,
  opening_debit: String(n.od ?? 0),
  opening_credit: String(n.oc ?? 0),
  period_debit: String(n.pd ?? 0),
  period_credit: String(n.pc ?? 0),
  closing_debit: String(n.cd ?? 0),
  closing_credit: String(n.cc ?? 0),
  balance: '0',
  has_activity: active,
})

//: ترازِ متوازن: صندوق و بانک بدهکار، فروش بستانکار.
const balanced = () => [
  row('1101', 'صندوق', { od: 100, pd: 50, pc: 20, cd: 130 }),
  row('1102', 'بانک', { pd: 70, cd: 70 }),
  row('4101', 'فروش', { oc: 100, pc: 100, cc: 200 }),
]

function respond(url: string): unknown {
  const u = new URL(url)
  if (u.pathname === '/api/accounting/balances') return balances
  if (u.pathname === '/api/accounts') return CHART
  if (u.pathname.startsWith('/api/reports/general-ledger/'))
    return { account_id: '1101', opening_balance: '0', closing_balance: '0', lines: [], fx_totals: [] }
  return []
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  calls = []
  balances = balanced()
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

const wait = (ms = 0) => act(() => new Promise<void>((r) => setTimeout(r, ms)))
const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel)
const $$ = (sel: string) => [...document.querySelectorAll<HTMLElement>(sel)]
const text = (sel: string) => $(sel)?.textContent?.replace(/\s+/g, ' ').trim() ?? ''
const bodyCodes = () => $$('.br-table tbody tr .br-code').map((td) => td.textContent)
const button = (scope: string, label: string) => $$(`${scope} button`).find((b) => b.textContent?.trim() === label)!

function key(el: Element, k: string, init: KeyboardEventInit = {}) {
  act(() => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...init }))
  })
}
function click(el: Element, init: MouseEventInit = {}) {
  act(() => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, ...init }))
  })
}

async function mount() {
  act(() => root.render(createElement(BalanceReportPage, { token: 't' })))
  await wait()
  await wait()
}

describe('گزارش ترازها — گریدِ اکسلی', () => {
  it('سرستونِ دوطبقه، ردیف‌های سرور و «جمع» با نشانِ توازن', async () => {
    await mount()
    //: قالبِ پیش‌فرض شش‌ستونی است: افتتاحیه، گردش، مانده — هر کدام بالای بدهکار/بستانکار.
    expect($$('.br-table thead th.br-group').map((t) => t.textContent)).toEqual(['افتتاحیه', 'گردش', 'مانده'])
    expect($$('.br-table thead tr:nth-child(2) th')).toHaveLength(6)
    expect(bodyCodes()).toEqual(['1101', '1102', '4101'])
    //: جمعِ گردش ۱۲۰ و ۱۲۰، مانده ۲۰۰ و ۲۰۰ → تراز.
    expect(text('.br-table tfoot .card-title')).toContain('تراز است')
    expect($$('.br-table tfoot td.num').map((td) => td.textContent)).toEqual(['۱۰۰', '۱۰۰', '۱۲۰', '۱۲۰', '۲۰۰', '۲۰۰'])
    //: «همه» حساب‌های بی‌گردش را هم می‌خواهد؛ بازه‌ی «امسال» به درخواست می‌رسد.
    const req = calls.find((c) => c.includes('/api/accounting/balances'))!
    expect(req).toContain('include_zero_activity=true')
    expect(req).toContain('date_from=')
  })

  it('سطحِ «کل» زیرحساب‌ها را جمع و مانده را خالص می‌کند', async () => {
    await mount()
    click(button('.br-level', 'کل'))
    expect(bodyCodes()).toEqual(['11', '41'])
    const first = $$('.br-table tbody tr')[0]
    //: مانده‌ی «۱۱» = ۱۳۰ + ۷۰ = ۲۰۰ بدهکار.
    expect(first.querySelector('td[data-label="مانده بدهکار"]')!.textContent).toBe('۲۰۰')
    expect(text('.br-table tfoot .card-title')).toContain('تراز است')
  })

  it('شماره‌ی ردیف فقط انتخاب می‌کند و نوارِ انتخاب جمع می‌دهد؛ کلیکِ ردیف دفتر را باز می‌کند', async () => {
    await mount()
    const heads = $$('.br-table tbody .xl-rowhead-btn')
    click(heads[0])
    click(heads[1], { shiftKey: true })
    expect($('.drawer-panel')).toBeNull()
    expect($$('.br-table tbody tr.is-selected')).toHaveLength(2)
    //: گردشِ بدهکارِ انتخاب ۵۰ + ۷۰؛ مانده ۱۳۰ + ۷۰ بدهکار.
    expect(text('.xl-selbar')).toContain('۲ حساب انتخاب شد')
    expect(text('.xl-selbar')).toContain('گردش بدهکار ۱۲۰')
    expect(text('.xl-selbar')).toContain('مانده ۲۰۰ بدهکار')
    click($$('.br-table tbody tr')[2].querySelector('.br-name')!)
    await wait()
    expect($('.drawer-panel')).not.toBeNull()
    expect(calls.some((c) => c.includes('/api/reports/general-ledger/4101'))).toBe(true)
  })

  it('کیبورد: ↓ حرکت، Space انتخاب، Esc لغوِ انتخاب، Enter دفتر', async () => {
    await mount()
    const grid = $('.br-scroll')!
    key(grid, 'ArrowDown')
    expect($('.br-table tbody tr.is-active')!.id).toBe('br-row-1')
    key(grid, ' ')
    expect($$('.br-table tbody tr.is-selected').map((tr) => tr.id)).toEqual(['br-row-1'])
    key(grid, 'ArrowDown', { shiftKey: true })
    expect($$('.br-table tbody tr.is-selected').map((tr) => tr.id)).toEqual(['br-row-1', 'br-row-2'])
    key(grid, 'Escape')
    expect($$('.br-table tbody tr.is-selected')).toHaveLength(0)
    key(grid, 'Enter')
    await wait()
    expect(calls.some((c) => c.includes('/api/reports/general-ledger/4101'))).toBe(true)
  })

  it('ناترازی گروهش را قرمز می‌کند؛ فیلترِ نوعِ مانده هشدارِ دروغین نمی‌دهد', async () => {
    balances = [...balanced(), row('1102b', 'تنخواه', { pd: 5, cd: 5 })]
    await mount()
    expect(text('.br-table tfoot .card-title')).toContain('ناتراز در گردش و مانده')
    expect($$('.br-table tfoot td.br-off')).toHaveLength(4)
    //: جست‌وجو یعنی بخشی از دفتر — جمعش سنجیده نمی‌شود.
    const find = $<HTMLInputElement>('.jg-find input')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(find, 'صندوق')
      find.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(bodyCodes()).toEqual(['1101'])
    expect(text('.br-table tfoot .card-title')).toContain('ردیف‌های فیلترشده')
    expect($$('.br-table tfoot td.br-off')).toHaveLength(0)
  })

  it('«سند کل»: فقط گردش، سطحِ کل، و گزینه‌های تراز غیرفعال', async () => {
    await mount()
    click(button('.br-view', 'سند کل'))
    await wait()
    expect($$('.br-table thead th.br-group').map((t) => t.textContent)).toEqual(['گردش'])
    expect(bodyCodes()).toEqual(['11', '41'])
    expect($$('.br-cols button').every((b) => (b as HTMLButtonElement).disabled)).toBe(true)
    expect($$('.br-level button').every((b) => (b as HTMLButtonElement).disabled)).toBe(true)
    //: سند کل برگه‌ی ماهانه است: «امسال» به «این ماه» می‌رود و حساب‌های بی‌گردش لازم نیست.
    expect(button('.rh-range', 'این ماه').getAttribute('aria-pressed')).toBe('true')
    expect(calls.filter((c) => c.includes('/api/accounting/balances')).at(-1)).not.toContain('include_zero_activity')
  })
})
