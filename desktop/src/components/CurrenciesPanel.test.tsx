// @vitest-environment jsdom
/**
 * «ارزها» و «نرخ برابری» به‌صورتِ دو برگه‌ی اکسلی با یک «ذخیره تغییرات».
 *
 * * ارزِ ثبت‌شده فقط‌خواندنی است (سرور ویرایشِ ارز ندارد)؛ ارزِ تازه در ردیفِ خالیِ ته، کدش بزرگ‌حرف، و
 *   کدِ تکراری پیش از ارسال رد می‌شود.
 * * نرخ‌ها به ترتیبِ زمان با ستونِ «تغییر»؛ در نرخِ ثبت‌شده فقط خودِ عدد عوض می‌شود و ذخیره همان ارز و
 *   تاریخ را دوباره ثبت (جایگزین) می‌کند.
 * * Enter در نرخِ ثبت‌شده به نرخِ ردیفِ بعد می‌رود. پس از ذخیره‌ی موفق `onSaved` صدا زده می‌شود.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CurrenciesPanel } from './CurrenciesPanel'
import { setTenantScope } from '../lib/tenantScope'

let container: HTMLDivElement
let root: Root
let calls: { method: string; path: string; body?: unknown }[]
let onSaved: ReturnType<typeof vi.fn<() => void>>

function stub() {
  calls = []
  const currencies = [
    { id: 'u', code: 'USD', name: 'دلار آمریکا', symbol: '$' },
    { id: 'e', code: 'EUR', name: 'یورو', symbol: '€' },
  ]
  const rates = [
    { id: 'r2', currency_code: 'USD', rate_date: '2026-09-02', rate: '630000' },
    { id: 'r1', currency_code: 'USD', rate_date: '2026-09-01', rate: '600000' },
    { id: 'r3', currency_code: 'EUR', rate_date: '2026-09-01', rate: '700000' },
  ]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const method = init?.method ?? 'GET'
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (method !== 'GET') calls.push({ method, path: url.pathname, body })
      if (url.pathname === '/api/currencies' && method === 'GET') return json(currencies)
      if (url.pathname === '/api/currencies/rates' && method === 'GET') return json(rates)
      if (method === 'POST') return json({ id: 'new', ...body }, 201)
      return json([])
    }),
  )
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  setTenantScope('t1')
  sessionStorage.clear()
  stub()
  onSaved = vi.fn<() => void>()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  setTenantScope(null)
})

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render() {
  await act(async () => {
    root.render(createElement(CurrenciesPanel, { token: 't', onSaved }))
  })
  await settle()
}
const curRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.cur-list tbody tr')]
const rateRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.cur-rates tbody tr')]
const curCell = (row: number, col: number) => container.querySelector<HTMLInputElement>(`.cur-list [data-cell="${row}-${col}"] input`)!
const rateInput = (row: number) => container.querySelector<HTMLInputElement>(`.cur-rates [data-cell="${row}-2"] input`)!
const focused = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell
const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!

function type(el: HTMLInputElement, text: string) {
  act(() => el.focus())
  act(() => {
    setValue.call(el, text)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
async function key(el: Element, code: string, init: KeyboardEventInit = {}) {
  await act(async () => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: code === 'KeyS' ? 's' : code, code, bubbles: true, cancelable: true, ...init }))
  })
}
async function save(from: Element) {
  await key(from, 'KeyS', { ctrlKey: true })
  await settle()
  await settle()
}

describe('ارزها — برگه‌ی اکسلی', () => {
  it('ارزِ ثبت‌شده فقط‌خواندنی؛ ردیفِ خالیِ ته با آخرین نرخ در ستونِ «نرخِ آخر»', async () => {
    await render()
    expect(curRows()).toHaveLength(3)
    expect(curRows()[0].querySelector('input')).toBeNull()
    expect(curRows()[0].textContent).toContain('USD')
    expect(curRows()[0].querySelector('.xl-ro')!.textContent).toContain((630000).toLocaleString('fa-IR'))
    expect(curCell(2, 0)).not.toBeNull()
  })

  it('ارزِ تازه: کد بزرگ‌حرف، ردیفِ خالیِ بعدی، و ذخیره POST می‌کند', async () => {
    await render()
    type(curCell(2, 0), 'aed')
    expect(curCell(2, 0).value).toBe('AED')
    expect(curRows()).toHaveLength(4)
    type(curCell(2, 1), 'درهم امارات')
    await save(curCell(2, 1))
    expect(calls).toEqual([{ method: 'POST', path: '/api/currencies', body: { code: 'AED', name: 'درهم امارات', symbol: '' } }])
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it('کدِ تکراری پیش از ارسال رد می‌شود', async () => {
    await render()
    type(curCell(2, 0), 'usd')
    type(curCell(2, 1), 'دلارِ دوم')
    await save(curCell(2, 1))
    expect(calls).toEqual([])
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('ارزِ USD از قبل هست.')
    expect(onSaved).not.toHaveBeenCalled()
  })
})

describe('نرخ برابری — برگه‌ی اکسلی', () => {
  it('ترتیبِ زمانی و ستونِ «تغییر»', async () => {
    await render()
    const texts = rateRows().map((r) => r.querySelector('.xl-txt')?.textContent ?? '')
    expect(texts.slice(0, 3).map((t) => t.slice(0, 3))).toEqual(['EUR', 'USD', 'USD'])
    //: ۶۰۰٬۰۰۰ → ۶۳۰٬۰۰۰ یعنی ٪۵+
    expect(rateRows()[2].querySelector('.xl-ro')!.textContent).toContain('۵')
    expect(rateRows()[2].querySelector('.xl-ro')!.className).toContain('pos-in')
  })

  it('ویرایشِ نرخِ ثبت‌شده: ته‌رنگ، و ذخیره همان ارز و تاریخ را جایگزین می‌کند', async () => {
    await render()
    type(rateInput(2), '640000')
    expect(rateInput(2).closest('td')!.className).toContain('is-changed')
    await save(rateInput(2))
    expect(calls).toEqual([{ method: 'POST', path: '/api/currencies/rates', body: { currency_code: 'USD', rate_date: '2026-09-02', rate: 640000 } }])
    expect(onSaved).toHaveBeenCalled()
  })

  it('Enter در نرخِ ثبت‌شده: نرخِ ردیفِ بعد', async () => {
    await render()
    act(() => rateInput(0).focus())
    await key(rateInput(0), 'Enter')
    expect(focused()).toBe('1-2')
  })

  it('نرخِ تازه از پیش‌نویسِ نشست برمی‌گردد و ذخیره می‌شود', async () => {
    sessionStorage.setItem(
      'cubita.currencies.draft:t1',
      JSON.stringify({ currencies: [], rates: [{ key: 'k1', currency_code: 'EUR', rate_date: '2026-09-25', rate: '710000' }], edits: {} }),
    )
    await render()
    expect(container.querySelector('.jf-msg')!.textContent).toContain('برگشت')
    await save(rateInput(0))
    expect(calls).toEqual([{ method: 'POST', path: '/api/currencies/rates', body: { currency_code: 'EUR', rate_date: '2026-09-25', rate: 710000 } }])
  })
})
