// @vitest-environment jsdom
/**
 * «انتقال مانده به حساب دیگر» — برگه‌ی مبدأها با تمِ اکسلی.
 *
 * کلیک روی ردیف مبدأ را انتخاب می‌کند؛ با مبدأ و مقصد، پیش‌نمایشِ سرور خودش می‌آید و بدهکار/بستانکارِ هر مبدأ و جمعِ مقصد
 * را پر می‌کند؛ تفصیلیِ مقصد از فهرست انتخاب می‌شود (نه شناسه‌ی تایپی)؛ صدور همان بدنه را با تأیید می‌فرستد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BalanceReclassPage } from './BalanceReclassPage'

let container: HTMLDivElement
let root: Root
let writes: { path: string; body: Record<string, unknown> }[]

const src = (account: string, code: string, name: string, balance: string, analytic?: [string, string]) => ({
  account_id: account,
  account_code: code,
  account_name: name,
  analytic_id: analytic?.[0] ?? null,
  analytic_code: null,
  analytic_name: analytic?.[1] ?? null,
  balance,
  system_role: null,
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  writes = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body ?? '{}'))
        writes.push({ path: url.pathname, body })
        if (url.pathname.endsWith('/preview')) {
          const items = (body.sources as { account_id: string; analytic_id: string | null }[]).map((s) => {
            const bal = s.account_id === 'a1' ? 2000 : -900
            return {
              account_id: s.account_id,
              account_code: s.account_id === 'a1' ? '1104' : '2101',
              account_name: 'x',
              analytic_id: s.analytic_id,
              analytic_name: null,
              balance: String(bal),
              source_debit: String(bal < 0 ? -bal : 0),
              source_credit: String(bal > 0 ? bal : 0),
              dest_debit: String(bal > 0 ? bal : 0),
              dest_credit: String(bal < 0 ? -bal : 0),
            }
          })
          const total = items.reduce((t, i) => t + Number(i.source_debit) + Number(i.dest_debit), 0)
          return json({
            as_of: body.as_of,
            items,
            dest_account_id: body.dest_account_id,
            dest_account_code: '1105',
            dest_account_name: 'مقصدِ درست',
            dest_analytic_id: body.dest_analytic_id,
            dest_analytic_name: body.dest_analytic_id ? 'شرکت گاما' : null,
            total_debit: String(total),
            total_credit: String(total),
            difference: '0',
            warnings: [],
          })
        }
        return json({ entry_id: 'e', number: 77, line_count: 4, total: '2900' }, 201)
      }
      if (url.pathname === '/api/accounting/balance-reclass/sources')
        return json([src('a1', '1104', 'حساب‌های دریافتنی', '2000', ['t1', 'شرکت آلفا']), src('a2', '2101', 'حساب‌های پرداختنی', '-900')])
      if (url.pathname === '/api/accounts')
        return json([
          { id: 'd1', code: '1105', name: 'مقصدِ درست', is_group: false, is_active: true },
          { id: 'g', code: '11', name: 'سرفصل', is_group: true, is_active: true },
        ])
      if (url.pathname === '/api/accounting/analytics') return json([{ id: 'an3', code: 'C3', name: 'شرکت گاما' }])
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

const settle = (ms = 0) =>
  act(async () => {
    await new Promise((r) => setTimeout(r, ms))
  })
async function render() {
  await act(async () => {
    root.render(createElement(BalanceReclassPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const bodyRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.rb-sheet tbody tr')]
/** `SearchSelect` زیرِ آستانه `<select>`ِ بومی است و بالاتر دکمه و پاپ‌آور؛ هر دو را می‌گیرد. */
async function pick(label: string, option: string) {
  const native = container.querySelector<HTMLSelectElement>(`select[aria-label="${label}"]`)
  if (native) {
    const value = [...native.options].find((o) => o.textContent?.includes(option))!.value
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!.call(native, value)
      native.dispatchEvent(new Event('change', { bubbles: true }))
    })
    return
  }
  await act(async () => container.querySelector<HTMLButtonElement>(`.item-picker-trigger[aria-label="${label}"]`)!.click())
  await act(async () => [...document.querySelectorAll<HTMLElement>('.item-picker-opt')].find((o) => o.textContent?.includes(option))!.click())
}
const previews = () => writes.filter((w) => w.path.endsWith('/preview'))

describe('انتقال مانده به حساب دیگر', () => {
  it('کلیک روی ردیف انتخاب می‌کند؛ بی مقصد پیش‌نمایشی نمی‌رود و نوار «مقصد انتخاب نشده» می‌گوید', async () => {
    await render()
    act(() => bodyRows()[1].click())
    expect(bodyRows()[1].className).toContain('is-selected')
    await settle(300)
    expect(previews()).toEqual([])
    expect(container.querySelector('.jf-foot')?.textContent).toContain('مقصد انتخاب نشده')
    act(() => bodyRows()[1].click())
    expect(bodyRows()[1].className).not.toContain('is-selected')
  })

  it('با مبدأ و مقصد پیش‌نمایشِ سرور خودش می‌آید: مبدأها به‌ترتیبِ فهرست، مبلغِ هر ردیف و جمعِ مقصد', async () => {
    await render()
    act(() => bodyRows()[1].click())
    act(() => bodyRows()[0].click())
    await pick('حسابِ مقصد', 'مقصدِ درست')
    await pick('تفصیلیِ مقصد', 'شرکت گاما')
    await settle(300)
    await settle()
    expect(previews().at(-1)!.body).toMatchObject({
      sources: [
        { account_id: 'a1', analytic_id: 't1' },
        { account_id: 'a2', analytic_id: null },
      ],
      dest_account_id: 'd1',
      dest_analytic_id: 'an3',
    })
    //: مانده‌ی بدهکارِ ۲٬۰۰۰ بستانکار می‌شود؛ مانده‌ی بستانکارِ ۹۰۰ بدهکار.
    expect([...bodyRows()[0].querySelectorAll('td.num')].map((td) => td.textContent)).toEqual(['۲٬۰۰۰ بد', '—', '۲٬۰۰۰'])
    expect([...bodyRows()[1].querySelectorAll('td.num')].map((td) => td.textContent)).toEqual(['۹۰۰ بس', '۹۰۰', '—'])
    const dest = container.querySelector('.rb-sheet tfoot')!.textContent ?? ''
    expect(dest).toContain('مقصدِ درست / شرکت گاما')
    expect(container.querySelector('.jf-foot')?.textContent).toContain('متوازن')
  })

  it('صدور همان بدنه را با تأیید می‌فرستد و انتخاب پاک می‌شود', async () => {
    await render()
    act(() => bodyRows()[0].click())
    await pick('حسابِ مقصد', 'مقصدِ درست')
    await settle(300)
    await settle()
    await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
    await settle()
    const issued = writes.filter((w) => w.path === '/api/accounting/balance-reclass')
    expect(issued).toEqual([
      {
        path: '/api/accounting/balance-reclass',
        body: expect.objectContaining({ sources: [{ account_id: 'a1', analytic_id: 't1' }], dest_account_id: 'd1', dest_analytic_id: null }),
      },
    ])
    expect(container.querySelector('.jf-foot')?.textContent).toContain('شماره ۷۷')
    expect(container.querySelectorAll('.rb-sheet tbody tr.is-selected')).toHaveLength(0)
  })

  it('جست‌وجو و «انتخاب‌شده‌ها» فهرست را کوتاه می‌کنند', async () => {
    await render()
    act(() => bodyRows()[1].click())
    const buttons = [...container.querySelectorAll('button')]
    act(() => buttons.find((b) => b.textContent === 'انتخاب‌شده‌ها')!.click())
    expect(bodyRows()).toHaveLength(1)
    expect(bodyRows()[0].textContent).toContain('2101')
  })
})
