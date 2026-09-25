// @vitest-environment jsdom
/**
 * «بودجه‌بندی» به‌صورتِ برگه‌ی اکسلیِ حساب × دوازده ماه.
 *
 * * ردیف‌ها به کدِ حساب، جمعِ ردیف و جمعِ هر ماه؛ حسابِ ردیفِ ثبت‌شده فقط‌خواندنی است.
 * * خانه‌ی عوض‌شده upsert با یادداشتِ قبلی، خانه‌ی خالی‌شده حذف — Ctrl+S، پشتِ‌سرِ‌هم.
 * * ردیفِ تازه: حساب در ردیفِ خالیِ ته، Enter به فروردین، «تکرار در ماه‌های خالی» دوازده ماه را پر می‌کند.
 * * خانه‌ای که سرور رد کرد در برگه می‌ماند و ردیفش قرمز می‌شود.
 * * «از سالِ قبل» فقط خانه‌های خالی را پر می‌کند و چیزی نمی‌فرستد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BudgetListPage } from './BudgetPage'
import { isoToJalali, jalaliToIso, todayIso } from '../../lib/jalali'
import { setTenantScope } from '../../lib/tenantScope'

const JY = isoToJalali(todayIso()).jy
let container: HTMLDivElement
let root: Root
let calls: { method: string; path: string; body?: Record<string, unknown> }[]
let rejectMonth: number | null

const ACCOUNTS = [
  { id: 'grp', code: '62', name: 'هزینه‌های اداری', is_group: true },
  { id: 'rent', code: '6201', name: 'اجاره', is_group: false },
  { id: 'salary', code: '6101', name: 'حقوق', is_group: false },
  { id: 'fuel', code: '6205', name: 'سوخت', is_group: false },
]
const line = (id: string, acc: string, code: string, name: string, jy: number, jm: number, amount: number, notes = '') => ({
  id,
  account_id: acc,
  account_code: code,
  account_name: name,
  account_type: 'expense',
  period_date: jalaliToIso(jy, jm, 1),
  amount: String(amount),
  notes,
  cost_center_id: null,
  cost_center_name: '',
})
const LINES = [
  line('r1', 'rent', '6201', 'اجاره', JY, 1, 500, 'قرارداد'),
  line('r2', 'rent', '6201', 'اجاره', JY, 2, 500),
  line('s1', 'salary', '6101', 'حقوق', JY, 1, 900),
  line('p1', 'fuel', '6205', 'سوخت', JY - 1, 3, 40),
]

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  setTenantScope('t1')
  sessionStorage.clear()
  calls = []
  rejectMonth = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const method = init?.method ?? 'GET'
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (method !== 'GET') {
        const body = init?.body ? JSON.parse(String(init.body)) : undefined
        calls.push({ method, path: url.pathname, body })
        if (method === 'DELETE') return new Response(null, { status: 204 })
        if (rejectMonth && body?.period_date === jalaliToIso(JY, rejectMonth, 1)) return json({ detail: 'مرکز هزینه‌ی انتخاب‌شده معتبر نیست' }, 400)
        return json({ id: 'new', ...body }, 201)
      }
      if (url.pathname === '/api/budgets') return json(LINES)
      if (url.pathname === '/api/accounts') return json(ACCOUNTS)
      return json([])
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
  setTenantScope(null)
})

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render() {
  await act(async () => {
    root.render(createElement(BudgetListPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const frame = () => act(async () => new Promise<void>((r) => requestAnimationFrame(() => r())))
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.bg-sheet tbody tr')]
const cell = (row: number, col: number) => container.querySelector<HTMLInputElement>(`.bg-sheet [data-cell="${row}-${col}"] input`)!
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
const fa = (n: number) => n.toLocaleString('fa-IR')
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.includes(text))!

describe('برگه‌ی بودجه', () => {
  it('ردیف به کدِ حساب، حسابِ ثبت‌شده فقط‌خواندنی، جمعِ ردیف و ماه؛ سالِ قبل در برگه نیست', async () => {
    await render()
    //: حقوق (۶۱۰۱) پیش از اجاره (۶۲۰۱)؛ سوختِ پارسال نیست؛ ردیفِ خالیِ ته.
    expect(rows()).toHaveLength(3)
    expect(rows()[0].textContent).toContain('حقوق')
    expect(rows()[0].querySelector('[data-cell="0-0"] input')).toBeNull()
    expect(cell(1, 1).value).toBe(fa(500))
    expect(rows()[1].querySelector('td[data-label="جمعِ سال"]')!.textContent).toBe(fa(1000))
    const foot = container.querySelector('.bg-sheet tfoot tr')!
    expect(foot.querySelectorAll('td.xl-ro')[0].textContent).toBe(fa(1400))
    expect(foot.querySelector('.bg-grand')!.textContent).toBe(fa(1900))
  })

  it('Ctrl+S: خانه‌ی عوض‌شده upsert با یادداشت، خالی‌شده حذف', async () => {
    await render()
    type(cell(1, 1), '600')
    type(cell(1, 2), '')
    expect(container.querySelector('.jf-foot')!.textContent).toContain(fa(2))
    await save(cell(1, 2))
    expect(calls).toEqual([
      {
        method: 'POST',
        path: '/api/budgets',
        body: { account_id: 'rent', period_date: jalaliToIso(JY, 1, 1), amount: 600, notes: 'قرارداد', cost_center_id: null },
      },
      { method: 'DELETE', path: '/api/budgets/r2', body: undefined },
    ])
  })

  it('ردیفِ تازه: حساب، Enter به فروردین، تکرار در ماه‌های خالی، دوازده upsert', async () => {
    await render()
    type(cell(2, 0), '6205')
    await key(cell(2, 0), 'Enter')
    await frame()
    expect(focused()).toBe('2-1')
    type(cell(2, 1), '70')
    await act(async () => rows()[2].querySelector<HTMLButtonElement>('button[aria-label="تکرار در ماه‌های خالی"]')!.click())
    expect(cell(2, 12).value).toBe(fa(70))
    expect(rows()[2].querySelector('td[data-label="جمعِ سال"]')!.textContent).toBe(fa(840))
    await save(cell(2, 12))
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(12)
    expect(calls[11].body).toMatchObject({ account_id: 'fuel', period_date: jalaliToIso(JY, 12, 1), amount: 70 })
  })

  it('خانه‌ای که سرور رد کرد می‌ماند و ردیفش قرمز می‌شود', async () => {
    rejectMonth = 3
    await render()
    type(cell(1, 3), '550')
    type(cell(1, 4), '560')
    await save(cell(1, 4))
    expect(calls).toHaveLength(2)
    const rent = rows().find((r) => r.textContent?.includes('اجاره'))!
    expect(rent.className).toContain('xl-row--error')
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('خرداد')
    expect(cell(1, 3).value).toBe(fa(550))
  })

  it('«از سالِ قبل» خانه‌های خالی را پر می‌کند و چیزی نمی‌فرستد', async () => {
    await render()
    await act(async () => button('از سالِ قبل').click())
    //: سوختِ پارسال ردیفِ تازه شد، خرداد ۴۰.
    const fuel = rows().find((r) => r.querySelector('[data-cell$="-0"] input') && r.querySelector<HTMLInputElement>('[data-cell$="-3"] input')?.value === fa(40))
    expect(fuel).toBeTruthy()
    expect(container.querySelector('.jf-foot')!.className).toContain('jf-foot--warn')
    expect(calls).toHaveLength(0)
  })
})
