// @vitest-environment jsdom
/**
 * «مالیات بر ارزش افزوده» (تمِ اکسلی) در DOM: برگه‌ی محاسبه مثلِ اظهارنامه، مالیاتِ خالص از سرور با نشانِ
 * پرداختنی/استردادی، بازه‌ی فصلِ شمسی در درخواست، و فاکتورهای ناهمخوان.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { VatReport } from '../../api'
import { VatPage } from './VatPage'

let container: HTMLDivElement
let root: Root
let calls: string[]
let body: Partial<VatReport>

const breakdown = (a: number, b: number, c: number, d: number) => ({
  taxable_goods: String(a),
  taxable_services: String(b),
  exempt_goods: String(c),
  exempt_services: String(d),
})

const base = (): VatReport => ({
  date_from: null,
  date_to: null,
  sales_net: '1000',
  output_vat: '100',
  sales_returns_net: '200',
  sales_returns_vat: '20',
  purchase_net: '500',
  input_vat: '50',
  purchase_returns_net: '100',
  purchase_returns_vat: '10',
  net_vat: '40',
  sales_breakdown: breakdown(600, 300, 100, 0),
  purchase_breakdown: breakdown(400, 0, 0, 100),
  mixed_sales_invoices: [],
  mixed_purchase_invoices: [],
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  calls = []
  body = {}
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      return { ok: true, status: 200, json: async () => ({ ...base(), ...body }) }
    }),
  )
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const wait = () => act(() => new Promise<void>((r) => setTimeout(r, 0)))
const $ = <T extends Element = HTMLElement>(sel: string) => container.querySelector<T>(sel)
const $$ = (sel: string) => [...container.querySelectorAll<HTMLElement>(sel)]
const text = (el: Element | null | undefined) => el?.textContent?.replace(/\s+/g, ' ').trim() ?? ''

async function mount() {
  act(() => root.render(createElement(VatPage, { token: 't' })))
  await wait()
  await wait()
}

describe('مالیات بر ارزش افزوده — برگه‌ی اظهارنامه', () => {
  it('دو بخش با برگشتِ منفی و جمعِ هر بخش؛ خالصِ فصل از سرور با نشانِ پرداختنی', async () => {
    await mount()
    expect($$('.vat-calc tbody tr.rp-sec').map(text)).toEqual(['مالیاتِ فروش', 'اعتبارِ مالیاتیِ خرید'])
    const returns = $$('.vat-calc tbody tr').find((tr) => text(tr).startsWith('برگشت از فروش'))!
    expect($$('.rp-neg').length).toBeGreaterThan(0)
    expect(text(returns.querySelector('td[data-label="مالیات و عوارض"]'))).toBe('(۲۰)')
    expect($$('.vat-calc tbody tr.rp-sub td[data-label="مالیات و عوارض"]').map(text)).toEqual(['۸۰', '۴۰'])
    expect(text($('.vat-calc tfoot'))).toContain('قابلِ پرداخت')
    expect(text($('.vat-calc tfoot td[data-label="مالیاتِ خالص"]'))).toBe('۴۰')
    expect($$('.vat-base tfoot td.num').map(text)).toEqual(['۱٬۰۰۰', '۵۰۰'])
  })

  it('فصل بازه‌ی شمسی را به درخواست می‌برد', async () => {
    await mount()
    const spring = $$('button').find((b) => b.textContent === 'بهار')!
    act(() => spring.click())
    await wait()
    const last = new URL(calls.at(-1)!)
    expect(last.pathname).toBe('/api/reports/vat')
    expect(last.searchParams.get('date_to')!.slice(5)).toBe('06-21')
    expect(spring.getAttribute('aria-pressed')).toBe('true')
  })

  it('خالصِ منفی استردادی است؛ فاکتورهای ناهمخوان با هشدار', async () => {
    body = {
      net_vat: '-15',
      mixed_sales_invoices: [{ invoice_id: 'i1', number: 12, invoice_date: '2026-07-01', tax_amount: '9', exempt_net: '100' }],
    }
    await mount()
    expect(text($('.vat-calc tfoot'))).toContain('قابلِ استرداد')
    expect(text($('.vat-calc tfoot .rp-neg'))).toBe('(۱۵)')
    expect(text($('.fy-note--warn'))).toContain('۱ فاکتور')
    expect(text($('.vat-mixed tbody tr'))).toContain('فروش ۱۲')
  })
})
