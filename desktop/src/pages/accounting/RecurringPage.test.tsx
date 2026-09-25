// @vitest-environment jsdom
/**
 * «اسناد تکرارشونده» هم‌سبکِ «سند حسابداری» — فرمِ قالب یک سند است (سربرگ، گریدِ ردیف‌ها، نوارِ توازن)
 * و فهرستِ قالب‌ها گریدِ فقط‌خواندنی.
 *
 * * قالبِ تازه با صفحه‌کلیدِ گریدِ سند پر می‌شود و Ctrl+S همان بدنه‌ی سرور را می‌فرستد، با شرحِ ردیف.
 * * خطای قالب پیش از ارسال در نوار می‌آید و درخواستی نمی‌رود.
 * * «ویرایش» قالب را با ردیف‌هایش در همان فرم باز می‌کند و ذخیره `PUT` می‌زند.
 * * فهرست: سررسیدشده بالا با نشان؛ خانه‌ی وضعیت فعال/غیرفعال می‌کند؛ حذف با تأیید.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RecurringListPage } from './RecurringPage'

let container: HTMLDivElement
let root: Root
let calls: { method: string; path: string; body?: unknown }[]

const ACCOUNTS = [
  { id: 'grp', code: '61', name: 'هزینه‌ها', is_group: true },
  { id: 'rent', code: '6101', name: 'هزینه اجاره', is_group: false },
  { id: 'bank', code: '1102', name: 'بانک', is_group: false },
]
const tpl = (over: Record<string, unknown>) => ({
  id: 'x',
  title: 't',
  description: '',
  frequency: 'monthly',
  interval: 1,
  start_date: '2026-09-01',
  end_date: null,
  next_run_date: '2026-10-01',
  last_run_date: null,
  is_active: true,
  cost_center_id: null,
  created_at: null,
  is_due: false,
  amount: '50000000',
  lines: [
    { id: 'l1', account_id: 'rent', account_code: '6101', account_name: 'هزینه اجاره', debit: '50000000', credit: '0', description: 'مهر' },
    { id: 'l2', account_id: 'bank', account_code: '1102', account_name: 'بانک', debit: '0', credit: '50000000', description: '' },
  ],
  ...over,
})
const TEMPLATES = [
  tpl({ id: 'later', title: 'بیمه', next_run_date: '2026-12-01' }),
  tpl({ id: 'off', title: 'قدیمی', is_active: false }),
  tpl({ id: 'due', title: 'اجاره‌ی دفتر', is_due: true, next_run_date: '2026-09-20' }),
]

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  //: jsdom اسکرول ندارد؛ «ویرایش» فرم را به دید می‌آورد.
  Element.prototype.scrollIntoView = vi.fn()
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const method = init?.method ?? 'GET'
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (method !== 'GET') {
        calls.push({ method, path: url.pathname + url.search, body: init?.body ? JSON.parse(String(init.body)) : undefined })
        if (method === 'DELETE') return new Response(null, { status: 204 })
        if (url.pathname.endsWith('/run')) return json({ generated: 1, skipped: 0, entries: [] })
        return json(tpl({}))
      }
      if (url.pathname === '/api/recurring-entries') return json(TEMPLATES)
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
  vi.restoreAllMocks()
})

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render() {
  await act(async () => {
    root.render(createElement(RecurringListPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const frame = () => act(async () => new Promise<void>((r) => requestAnimationFrame(() => r())))
const cell = (row: number, col: number) => container.querySelector<HTMLInputElement>(`.rc-lines [data-cell="${row}-${col}"] input`)!
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
const listRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.rc-list tbody tr')]
const titleInput = () => container.querySelector<HTMLInputElement>('.jh-bar input')!

describe('قالبِ تازه — گریدِ سند', () => {
  it('Enter: حساب → شرح → بدهکار → حسابِ ردیفِ بعد؛ Ctrl+S بدنه‌ی کامل با شرحِ ردیف', async () => {
    await render()
    type(titleInput(), 'اجاره‌ی انبار')
    type(cell(0, 0), '6101')
    await key(cell(0, 0), 'Enter')
    await frame()
    expect(focused()).toBe('0-1')
    type(cell(0, 1), 'اجاره‌ی ماهانه')
    await key(cell(0, 1), 'Enter')
    expect(focused()).toBe('0-2')
    type(cell(0, 2), '30000000')
    await key(cell(0, 2), 'Enter')
    expect(focused()).toBe('1-0')
    type(cell(1, 0), '1102')
    await key(cell(1, 0), 'Enter')
    await frame()
    type(cell(1, 3), '30000000')
    expect(foot().className).toContain('jf-foot--ok')
    await key(cell(1, 3), 'KeyS', { ctrlKey: true })
    await settle()
    const post = calls.find((c) => c.method === 'POST' && c.path === '/api/recurring-entries')
    expect(post?.body).toMatchObject({
      title: 'اجاره‌ی انبار',
      frequency: 'monthly',
      interval: 1,
      end_date: null,
      lines: [
        { account_id: 'rent', debit: 30000000, credit: 0, description: 'اجاره‌ی ماهانه' },
        { account_id: 'bank', debit: 0, credit: 30000000, description: '' },
      ],
    })
    //: پس از ثبت فرم خالی می‌شود.
    expect(titleInput().value).toBe('')
  })

  it('قالبِ ناقص: پیام در نوار و هیچ درخواستی', async () => {
    await render()
    type(cell(0, 2), '100')
    await key(cell(0, 2), 'KeyS', { ctrlKey: true })
    await settle()
    expect(foot().textContent).toContain('عنوانِ قالب را بنویسید.')
    type(titleInput(), 'آزمون')
    await key(cell(0, 2), 'KeyS', { ctrlKey: true })
    await settle()
    expect(foot().textContent).toContain('ردیفِ ۱ حساب ندارد.')
    expect(calls).toHaveLength(0)
  })
})

describe('فهرستِ قالب‌ها', () => {
  it('سررسیدشده بالا با نشان و ته‌رنگ؛ غیرفعال ته و کم‌رنگ', async () => {
    await render()
    const rows = listRows()
    expect(rows.map((r) => r.querySelector('td[data-label="عنوان"]')!.firstChild!.textContent)).toEqual([
      'اجاره‌ی دفتر',
      'بیمه',
      'قدیمی',
    ])
    expect(rows[0].className).toContain('xl-row--temp')
    expect(rows[0].textContent).toContain('سررسید')
    expect(rows[2].className).toContain('acc-row--muted')
  })

  it('«ویرایش» قالب را با ردیف‌ها و شرح‌ها در فرم باز می‌کند و ذخیره PUT می‌زند', async () => {
    await render()
    const edit = listRows()[1].querySelector<HTMLButtonElement>('button[aria-label="ویرایش در فرم"]')!
    await act(async () => edit.click())
    await frame()
    expect(titleInput().value).toBe('بیمه')
    expect(cell(0, 0).value).toBe('6101 — هزینه اجاره')
    expect(cell(0, 1).value).toBe('مهر')
    expect(listRows()[1].className).toContain('xl-row--editing')
    //: فوکوس به عنوانِ قالب می‌رود تا کاربر همان‌جا ادامه دهد.
    expect(document.activeElement).toBe(titleInput())
    type(cell(0, 2), '60000000')
    type(cell(1, 3), '60000000')
    await key(cell(1, 3), 'KeyS', { ctrlKey: true })
    await settle()
    const put = calls.find((c) => c.method === 'PUT')
    expect(put?.path).toBe('/api/recurring-entries/later')
    expect(put?.body).toMatchObject({ title: 'بیمه', lines: [{ debit: 60000000, description: 'مهر' }, { credit: 60000000 }] })
  })

  it('خانه‌ی وضعیت فعال/غیرفعال می‌کند؛ حذف با تأیید', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await render()
    const toggle = listRows()[0].querySelector<HTMLButtonElement>('.xl-toggle')!
    expect(toggle.textContent).toBe('فعال')
    await act(async () => toggle.click())
    await settle()
    expect(calls.at(-1)).toMatchObject({ method: 'POST', path: '/api/recurring-entries/due/set-active?is_active=false' })
    const del = listRows()[2].querySelector<HTMLButtonElement>('button[aria-label="حذف"]')!
    await act(async () => del.click())
    await settle()
    expect(window.confirm).toHaveBeenCalled()
    expect(calls.at(-1)).toMatchObject({ method: 'DELETE', path: '/api/recurring-entries/off' })
  })
})
