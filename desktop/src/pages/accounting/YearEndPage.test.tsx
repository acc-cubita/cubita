// @vitest-environment jsdom
/**
 * «صدور سند اختتامیه و افتتاحیه» — دو سند با یک برگه (تمِ اکسلی).
 *
 * گرید همان سند است (شرحِ ردیف‌ها و خطِ توازن از سرور)؛ اختتامیه تا سود و زیان باز است بسته می‌ماند؛ افتتاحیه مبنایش را از
 * فهرستِ اختتامیه‌ها می‌گیرد و تاریخش پیش‌فرض روزِ بعد از آن است؛ افتتاحیه‌ی تکراری پیش از صدور گفته می‌شود.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ClosingOpeningPage } from './YearEndPage'

let container: HTMLDivElement
let root: Root
let writes: { path: string; body: Record<string, unknown> }[]
let closing: Record<string, unknown>
let opening: Record<string, unknown>
let openingQueries: string[]

const row = (id: string, code: string, name: string, type: string, debit: string, credit: string, description: string) => ({
  account_id: id,
  account_code: code,
  account_name: name,
  account_type: type,
  analytic_id: null,
  analytic_code: null,
  analytic_name: null,
  cost_center_id: null,
  cost_center_name: null,
  debit,
  credit,
  balance: String(Number(credit) - Number(debit)),
  description,
})
const balancing = (name: string, debit: string, credit: string, total: string) => ({
  balance_account_code: name === 'حساب اختتامیه' ? '3901' : '3902',
  balance_account_name: name,
  balance_description: name,
  balance_debit: debit,
  balance_credit: credit,
  total_debit: total,
  total_credit: total,
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  writes = []
  openingQueries = []
  closing = {
    as_of: '2026-09-26',
    rows: [row('c', '1101', 'صندوق', 'asset', '0', '900', 'بستنِ صندوق'), row('k', '3101', 'سرمایه', 'equity', '900', '0', 'بستنِ سرمایه')],
    total: '1800',
    open_pnl_total: '0',
    temporary_count: 2,
    ...balancing('حساب اختتامیه', '0', '0', '900'),
  }
  opening = {
    as_of: '2026-03-21',
    source_date: '2026-03-20',
    rows: [row('c', '1101', 'صندوق', 'asset', '900', '0', 'افتتاحِ صندوق')],
    closing_entry_id: 'ce',
    closing_entry_number: 90,
    total: '900',
    existing_opening_number: null,
    ...balancing('حساب افتتاحیه', '0', '900', '900'),
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (init?.method === 'POST') {
        writes.push({ path: url.pathname, body: JSON.parse(String(init.body ?? '{}')) })
        return json({ entry_id: 'x', number: 99, line_count: 3, total: '1800' }, 201)
      }
      if (url.pathname === '/api/accounting/closing-entry/preview') return json(closing)
      if (url.pathname === '/api/accounting/opening-entry/preview') {
        openingQueries.push(url.search)
        return json({ ...opening, as_of: url.searchParams.get('as_of'), source_date: url.searchParams.get('source_date') })
      }
      if (url.pathname === '/api/journal-entries')
        return json({
          items: [
            { id: 'ce-old', number: 10, entry_date: '2025-03-20', source_type: 'closing_entry', voided_at: null },
            { id: 'ce', number: 90, entry_date: '2026-03-20', source_type: 'closing_entry', voided_at: null },
          ],
          next_cursor: null,
        })
      return json([])
    }),
  )
  vi.stubGlobal('confirm', vi.fn(() => true))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render() {
  await act(async () => {
    root.render(createElement(ClosingOpeningPage, { token: 't' }))
  })
  await settle()
  await settle()
  await settle()
}
const bodyRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.ye-sheet tbody tr')]
const foot = () => container.querySelector('.jf-foot')?.textContent ?? ''
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!

describe('اختتامیه', () => {
  it('گرید همان سند است: ردیف‌ها با شرح و «نوع»، و نوار متوازن با جمع‌ها', async () => {
    await render()
    expect(bodyRows().map((tr) => tr.querySelector('.ye-desc')?.textContent)).toEqual(['بستنِ صندوق', 'بستنِ سرمایه'])
    expect(bodyRows()[0].textContent).toContain('دارایی')
    expect(foot()).toContain('متوازن')
    expect(foot()).toContain('۹۰۰')
    expect(container.textContent).toContain('۲ سندِ موقت')
  })

  it('خطِ توازن وقتی مبلغ دارد ته سند می‌نشیند', async () => {
    closing = { ...closing, rows: [row('c', '1101', 'صندوق', 'asset', '0', '900', 'بستنِ صندوق')], ...balancing('حساب اختتامیه', '900', '0', '900') }
    await render()
    const bal = container.querySelector('.ye-sheet tr.ye-bal')!
    expect(bal.textContent).toContain('3901')
    expect(bal.textContent).toContain('حساب اختتامیه')
  })

  it('سود و زیانِ باز صدور را می‌بندد و دلیلش را می‌گوید', async () => {
    closing = { ...closing, open_pnl_total: '250' }
    await render()
    expect(container.querySelector<HTMLButtonElement>('.jf-submit')!.disabled).toBe(true)
    expect(foot()).toContain('سود و زیان باز است')
    expect(container.querySelector('.acc-note--err')?.textContent).toContain('۲۵۰')
  })

  it('صدور با تأیید همان تاریخ و شرح را می‌فرستد', async () => {
    await render()
    await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
    await settle()
    expect(writes).toEqual([{ path: '/api/accounting/closing-entry', body: { as_of: expect.any(String), description: '' } }])
    expect(foot()).toContain('شماره ۹۹')
  })
})

describe('افتتاحیه', () => {
  it('مبنا تازه‌ترین اختتامیه است و تاریخِ افتتاحیه روزِ بعدش', async () => {
    await render()
    act(() => button('افتتاحیه').click())
    await settle()
    await settle()
    expect(openingQueries.at(-1)).toBe('?as_of=2026-03-21&source_date=2026-03-20')
    expect(bodyRows()[0].querySelector('.ye-desc')?.textContent).toBe('افتتاحِ صندوق')
    expect(container.querySelector('.ye-sheet tr.ye-bal')?.textContent).toContain('حساب افتتاحیه')
    await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
    await settle()
    expect(writes.at(-1)).toEqual({
      path: '/api/accounting/opening-entry',
      body: { as_of: '2026-03-21', source_date: '2026-03-20', description: '' },
    })
  })

  it('افتتاحیه‌ی تکراری پیش از صدور گفته می‌شود و صدور بسته است', async () => {
    opening = { ...opening, existing_opening_number: 91 }
    await render()
    act(() => button('افتتاحیه').click())
    await settle()
    await settle()
    expect(foot()).toContain('قبلاً صادر شده')
    expect(container.querySelector('.acc-note--warn')?.textContent).toContain('۹۱')
    expect(container.querySelector<HTMLButtonElement>('.jf-submit')!.disabled).toBe(true)
  })
})
