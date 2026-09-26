// @vitest-environment jsdom
/**
 * «بستن حساب‌های سود و زیان» — پیش‌نمایشِ سندِ بستن با تمِ اکسلی.
 *
 * گرید همان سندی است که زده می‌شود (ردیف‌ها با شرحِ سرور و خطِ «سود انباشته» ته آن)، نوارِ پایین سود/زیانِ دوره و جمع‌ها را
 * می‌گوید، صدور و قفل دو گامِ جدا با تأییدِ جدا می‌مانند.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ClosePnlPage } from './ClosePnlPage'

let container: HTMLDivElement
let root: Root
let writes: { method: string; path: string; body: Record<string, unknown> }[]
let preview: Record<string, unknown>

const row = (id: string, code: string, name: string, type: string, debit: string, credit: string, description: string, analytic?: string) => ({
  account_id: id,
  account_code: code,
  account_name: name,
  account_type: type,
  analytic_id: analytic ? `an-${id}` : null,
  analytic_code: null,
  analytic_name: analytic ?? null,
  cost_center_id: null,
  cost_center_name: null,
  debit,
  credit,
  side: Number(debit) ? 'debit' : 'credit',
  amount: Number(debit) ? debit : credit,
  description,
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  writes = []
  preview = {
    date_from: '2026-03-21',
    date_to: '2026-09-26',
    rows: [
      row('r1', '4101', 'فروش', 'income', '1000', '0', 'بستن حساب درآمد / شرکت آلفا', 'شرکت آلفا'),
      row('e1', '5101', 'اجاره', 'expense', '0', '700', 'بستن حساب هزینه'),
    ],
    total_income: '1000',
    total_expenses: '700',
    net_profit: '300',
    destination_account_code: '3201',
    destination_account_name: 'سود انباشته',
    destination_description: 'انتقال سود دوره به سود انباشته',
    total_debit: '1000',
    total_credit: '1000',
    difference: '0',
    temporary_in_range: 3,
    already_closed: false,
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (init?.method && init.method !== 'GET') {
        const body = JSON.parse(String(init.body ?? '{}'))
        writes.push({ method: init.method, path: url.pathname, body })
        if (url.pathname === '/api/accounting/pnl-close')
          return json({ entry_id: 'x', number: 42, line_count: 3, total_income: '1000', total_expenses: '700', net_profit: '300' }, 201)
        return json({ id: 'c', closing_date: body.closing_date, net_profit: '300', notes: '', journal_entry_id: 'x' }, 201)
      }
      if (url.pathname === '/api/accounting/pnl-close/preview') return json(preview)
      if (url.pathname === '/api/fiscal-period-closes')
        return json([{ id: 'p', closing_date: '2026-03-20', net_profit: '-50', notes: '', journal_entry_id: 'y' }])
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
    root.render(createElement(ClosePnlPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const bodyRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.pc-sheet tbody tr')]
const foot = () => container.querySelector('.jf-foot')?.textContent ?? ''

describe('بستن حساب‌های سود و زیان', () => {
  it('گرید همان سند است: ردیف‌ها با شرحِ سرور و خطِ سود انباشته ته آن', async () => {
    await render()
    expect(bodyRows().map((tr) => tr.textContent)).toEqual([
      expect.stringContaining('بستن حساب درآمد / شرکت آلفا'),
      expect.stringContaining('بستن حساب هزینه'),
      expect.stringContaining('انتقال سود دوره به سود انباشته'),
    ])
    expect(bodyRows()[2].className).toContain('pc-dest')
    expect(bodyRows()[2].querySelectorAll('td.num')[1].textContent).toBe('۳۰۰')
    //: شروعِ بازه از روزِ بعد از آخرین قفل می‌آید، نه از کاربر.
    expect(container.querySelector('.jh-static')?.textContent).toBe('۱۴۰۵/۰۱/۰۱')
  })

  it('نوارِ پایین: سودِ دوره و جمعِ بدهکار و بستانکار', async () => {
    await render()
    expect(foot()).toContain('سودِ دوره')
    expect(foot()).toContain('۳۰۰')
    expect(foot()).toContain('۱٬۰۰۰')
    expect(container.querySelector('.jf-foot')?.className).toContain('jf-foot--ok')
  })

  it('زیان قرمز و خطِ مقصد بدهکار', async () => {
    preview = { ...preview, net_profit: '-200', destination_description: 'انتقال زیان دوره به سود انباشته' }
    await render()
    expect(foot()).toContain('زیانِ دوره')
    expect(container.querySelector('.jf-foot')?.className).toContain('jf-foot--err')
    expect(bodyRows()[2].querySelectorAll('td.num')[0].textContent).toBe('۲۰۰')
  })

  it('صدور با تأیید؛ قفل گامِ جدا با تأییدِ خودش', async () => {
    await render()
    await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
    await settle()
    expect(writes).toEqual([{ method: 'POST', path: '/api/accounting/pnl-close', body: { as_of: expect.any(String), description: '' } }])
    expect(foot()).toContain('شماره ۴۲')

    await act(async () => [...container.querySelectorAll('button')].find((b) => b.textContent?.includes('قفل کردنِ دوره'))!.click())
    await settle()
    expect(writes[1]).toMatchObject({ method: 'POST', path: '/api/fiscal-period-closes' })
    expect(window.confirm).toHaveBeenCalledTimes(2)
  })

  it('بی فعالیتِ درآمد و هزینه صدور بسته است و نوار «سندی لازم نیست» می‌گوید', async () => {
    preview = { ...preview, rows: [], net_profit: '0', total_debit: '0', total_credit: '0' }
    await render()
    expect(container.querySelector<HTMLButtonElement>('.jf-submit')!.disabled).toBe(true)
    expect(foot()).toContain('سندی لازم نیست')
  })
})
