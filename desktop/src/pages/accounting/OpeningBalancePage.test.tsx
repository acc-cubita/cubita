// @vitest-environment jsdom
/**
 * «مانده اول دوره» هم‌سبکِ «سند حسابداری» — همان گرید، همان صفحه‌کلید، همان نوارِ پایین.
 *
 * * Enter از حساب به بدهکار می‌رود؛ ردیفی که بدهکار گرفته تمام است و Enter به حسابِ ردیفِ بعد
 *   می‌پرد (بستانکارش را رد می‌کند). در انتهای آخرین ردیف، ردیفِ تازه.
 * * اختلافی که به سرمایه بسته می‌شود «تراز خودکار» است (رنگِ خبر)، نه «نامتوازن»؛ بی حسابِ تراز همان
 *   اختلاف خطاست.
 * * Ctrl+S از داخلِ گرید سند را با همان بدنه‌ی قبلی می‌فرستد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { OpeningBalancePage } from './OpeningBalancePage'

let container: HTMLDivElement
let root: Root
let posted: unknown = null

const ACCOUNTS = [
  { id: 'grp', code: '11', name: 'دارایی جاری', is_group: true },
  { id: 'cash', code: '1101', name: 'صندوق', is_group: false },
  { id: 'bank', code: '1102', name: 'بانک', is_group: false },
  { id: 'cap', code: '3101', name: 'سرمایه', is_group: false },
]

function stub() {
  posted = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200 })
      if (url.pathname === '/api/opening-balances/status') return json({ exists: false, entry_id: null, entry_number: null, entry_date: null })
      if (url.pathname === '/api/opening-balances' && init?.method === 'POST') {
        posted = JSON.parse(String(init.body))
        return json({ id: 'e1', number: 1 })
      }
      if (url.pathname === '/api/accounts') return json(ACCOUNTS)
      if (url.pathname === '/api/items') return json({ items: [], next_cursor: null })
      return json([])
    }),
  )
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  stub()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function render() {
  await act(async () => {
    root.render(createElement(OpeningBalancePage, { token: 't' }))
  })
  //: چهار درخواستِ بارگذاری.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
}
const frame = () => act(async () => new Promise<void>((r) => requestAnimationFrame(() => r())))
const cell = (row: number, col: number) => container.querySelector<HTMLInputElement>(`.ob-accounts [data-cell="${row}-${col}"] input`)!
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
const foot = () => container.querySelector<HTMLElement>('.jf-foot')!

describe('مانده اول دوره — گریدِ اکسلی', () => {
  it('Enter: حساب → بدهکار → حسابِ ردیفِ بعد (بستانکارِ ردیفِ پُر رد می‌شود)', async () => {
    await render()
    type(cell(0, 0), '1101')
    await key(cell(0, 0), 'Enter')
    await frame()
    expect(focused()).toBe('0-1')
    type(cell(0, 1), '5000000')
    await key(cell(0, 1), 'Enter')
    expect(focused()).toBe('1-0')
  })

  it('در انتهای آخرین ردیف، Enter ردیفِ تازه می‌سازد', async () => {
    await render()
    const rows = () => container.querySelectorAll('.ob-accounts tbody tr').length
    expect(rows()).toBe(2)
    await key(cell(1, 2), 'Enter')
    await frame()
    expect(rows()).toBe(3)
    expect(focused()).toBe('2-0')
  })

  it('حساب‌های گروه در فهرست نیستند', async () => {
    await render()
    type(cell(0, 0), '11')
    const opts = [...document.body.querySelectorAll('[role="option"]')].map((o) => o.textContent?.trim())
    expect(opts).toEqual(['1101 — صندوق', '1102 — بانک'])
    await key(cell(0, 0), 'Escape')
  })

  it('اختلاف با حسابِ سرمایه «تراز خودکار» است؛ بی آن «نامتوازن»', async () => {
    await render()
    expect(foot().className).toContain('jf-foot--empty')
    type(cell(0, 1), '5000000')
    expect(foot().className).toContain('jf-foot--auto')
    expect(foot().textContent).toContain('تراز خودکار')
    expect(foot().textContent).toContain('به سرمایه')
    type(cell(1, 2), '5000000')
    expect(foot().className).toContain('jf-foot--ok')
  })

  it('Ctrl+S از داخلِ گرید همان بدنه را می‌فرستد', async () => {
    await render()
    type(cell(0, 0), '1101')
    await key(cell(0, 0), 'Enter')
    type(cell(0, 1), '7000000')
    await key(cell(0, 1), 'KeyS', { ctrlKey: true })
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })
    expect(posted).toMatchObject({
      lines: [{ account_id: 'cash', debit: 7000000, credit: 0 }],
      stock: [],
      balancing_account_id: 'cap',
    })
  })
})
