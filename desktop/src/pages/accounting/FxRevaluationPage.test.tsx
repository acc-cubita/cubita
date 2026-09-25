// @vitest-environment jsdom
/**
 * «صدور سند تسعیر ارز» هم‌سبکِ «سند حسابداری»: سربرگِ خانه‌ای، گریدِ اکسلیِ فقط‌خواندنی، و نوارِ
 * پایینی که سود/زیانِ خالص و دو جمع را نشان می‌دهد.
 *
 * * سود سبز («سودِ تسعیر»)، زیان قرمز، بی‌اختلاف خاکستری و دکمه غیرفعال.
 * * ارزِ بی‌نرخ هم بالای گرید هشدار دارد هم در نوارِ پایین.
 * * کلیک روی شماره‌ی ردیف: نوارِ جمعِ انتخاب.
 * * Ctrl+S (پس از تأیید) همان POSTِ قبلی را با تاریخ و شرح می‌فرستد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { FxRevaluationPage } from './FxRevaluationPage'

let container: HTMLDivElement
let root: Root
let posted: unknown = null
let preview: unknown

const item = (account: string, code: string, cur: string, book: number, market: number) => ({
  account_id: account,
  account_code: code,
  account_name: `حسابِ ${code}`,
  analytic_id: null,
  analytic_code: null,
  analytic_name: null,
  cost_center_id: null,
  cost_center_name: null,
  currency_code: cur,
  fx_balance: '100',
  rate: String(market / 100),
  rate_date: '2026-09-25',
  book_value: String(book),
  market_value: String(market),
  difference: String(market - book),
})

function stub() {
  posted = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (url.pathname === '/api/accounting/fx-revaluation/preview') return json(preview)
      if (url.pathname === '/api/accounting/fx-revaluation' && init?.method === 'POST') {
        posted = JSON.parse(String(init.body))
        return json({ entry_id: 'e1', number: 42, line_count: 3, net_difference: '300000' }, 201)
      }
      return json([])
    }),
  )
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  preview = {
    as_of: '2026-09-25',
    items: [item('a1', '1105', 'USD', 1_000_000, 1_500_000), item('a2', '2105', 'AED', 800_000, 600_000)],
    total_difference: '300000',
    missing_rates: ['EUR'],
  }
  stub()
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
    root.render(createElement(FxRevaluationPage, { token: 't' }))
  })
  await settle()
}
const foot = () => container.querySelector<HTMLElement>('.jf-foot')!
const stat = (cls: string) => container.querySelector<HTMLElement>(`.${cls} .jb-v`)!.textContent!.trim()
const submit = () => container.querySelector<HTMLButtonElement>('.jf-submit')!

describe('صدور سند تسعیر ارز — هم‌سبکِ سند', () => {
  it('سربرگِ خانه‌ای و گریدِ اکسلی با شماره‌ی ردیف', async () => {
    await render()
    const labels = [...container.querySelectorAll('.jh-label')].map((l) => l.textContent?.replace('*', '').trim())
    expect(labels).toEqual(['شرح سند', 'تاریخِ تسعیر'])
    expect(container.querySelectorAll('.fx-sheet tbody tr')).toHaveLength(2)
    expect(container.querySelector('.fx-sheet .xl-rowhead-btn')!.textContent).toBe('۱')
  })

  it('سودِ خالص: نوارِ سبز، دو جمع، و هشدارِ ارزِ بی‌نرخ', async () => {
    await render()
    expect(foot().className).toContain('jf-foot--ok')
    expect(foot().className).toContain('jf-foot--status-end')
    expect(foot().textContent).toContain('سودِ تسعیر')
    expect(stat('jb-stat--a')).toBe((1_800_000).toLocaleString('fa-IR'))
    expect(stat('jb-stat--b')).toBe((2_100_000).toLocaleString('fa-IR'))
    expect(foot().textContent).toContain('EUR بی‌نرخ')
    expect(container.querySelector('.acc-note--err')!.textContent).toContain('EUR')
    expect(submit().disabled).toBe(false)
  })

  it('انتخابِ ردیف‌ها با شماره: جمعِ همان‌ها', async () => {
    await render()
    await act(async () => {
      container.querySelectorAll<HTMLButtonElement>('.fx-sheet .xl-rowhead-btn')[1].click()
    })
    const bar = container.querySelector('.xl-selbar')!.textContent!
    expect(bar).toContain((800_000).toLocaleString('fa-IR'))
    expect(bar).toContain((-200_000).toLocaleString('fa-IR'))
  })

  it('Ctrl+S پس از تأیید سند را صادر می‌کند', async () => {
    await render()
    const desc = container.querySelector<HTMLInputElement>('.jh-field--grow input')!
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
    act(() => {
      setValue.call(desc, 'تسعیرِ پایانِ شهریور')
      desc.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => {
      desc.dispatchEvent(new KeyboardEvent('keydown', { key: 's', code: 'KeyS', ctrlKey: true, bubbles: true, cancelable: true }))
    })
    await settle()
    expect(posted).toEqual({ as_of: expect.any(String), description: 'تسعیرِ پایانِ شهریور' })
    expect(container.querySelector('.jf-msg')!.textContent).toContain('۴۲')
  })

  it('بی‌اختلاف: خاکستری، «سندی لازم نیست»، و دکمه غیرفعال', async () => {
    preview = { as_of: '2026-09-25', items: [item('a1', '1105', 'USD', 1_000_000, 1_000_000)], total_difference: '0', missing_rates: [] }
    await render()
    expect(foot().className).toContain('jf-foot--empty')
    expect(foot().textContent).toContain('سندی لازم نیست')
    expect(submit().disabled).toBe(true)
    await act(async () => {
      submit().closest('form')!.dispatchEvent(new KeyboardEvent('keydown', { key: 's', code: 'KeyS', ctrlKey: true, bubbles: true, cancelable: true }))
    })
    await settle()
    expect(posted).toBeNull()
  })
})
