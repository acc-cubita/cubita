// @vitest-environment jsdom
/**
 * «تفصیلی سایر» به‌صورتِ برگه‌ی اکسلی با ویرایشِ درجا.
 *
 * * خانه‌ی ویرایش‌شده ته‌رنگ می‌گیرد و نوارِ پایین «تغییرِ ذخیره‌نشده» می‌گوید؛ Ctrl+S فقط فیلدِ عوض‌شده را
 *   PATCH می‌کند.
 * * تایپ در ردیفِ خالیِ ته، ردیفِ تازه می‌سازد و ردیفِ خالیِ بعدی خودش می‌آید؛ ذخیره POST می‌کند.
 * * ردیفی که سرور نپذیرفت (کدِ تکراری) با نوشته‌اش می‌ماند، قرمز می‌شود و دلیلش زیرِ برگه است.
 * * Enter: کد → نام → دسته → کدِ ردیفِ بعد. جست‌وجو ردیف‌های ثبت‌شده را پنهان می‌کند، ردیفِ تازه را نه.
 * * پیش‌نویسِ ذخیره‌نشده با برگشتن به صفحه برمی‌گردد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AnalyticsPage } from './AnalyticsPage'
import { setTenantScope } from '../../lib/tenantScope'

let container: HTMLDivElement
let root: Root
let server: { id: string; code: string; name: string; group_name: string; description: string; is_active: boolean; line_count: number }[]
let calls: { method: string; path: string; body?: unknown }[]

function stub() {
  server = [
    { id: 'a', code: 'V-2', name: 'پژو', group_name: 'خودرو', description: '', is_active: true, line_count: 3 },
    { id: 'b', code: 'V-1', name: 'پراید', group_name: 'خودرو', description: '', is_active: true, line_count: 0 },
    { id: 'c', code: 'P-1', name: 'قراردادِ الف', group_name: 'پروژه', description: '', is_active: true, line_count: 0 },
  ]
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const method = init?.method ?? 'GET'
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (!url.pathname.startsWith('/api/accounting/analytics')) return json([])
      if (method !== 'GET') calls.push({ method, path: url.pathname, body })
      if (method === 'GET') return json(server)
      if (method === 'POST') {
        if (server.some((r) => r.code === body.code)) return json({ detail: 'کدِ تکراری است.' }, 409)
        const r = { id: `s${server.length}`, is_active: true, line_count: 0, ...body }
        server.push(r)
        return json(r, 201)
      }
      const id = url.pathname.split('/').pop()
      if (method === 'PATCH') {
        server = server.map((r) => (r.id === id ? { ...r, ...body } : r))
        return json(server.find((r) => r.id === id))
      }
      return new Response(null, { status: 204 })
    }),
  )
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  setTenantScope('t1')
  sessionStorage.clear()
  stub()
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
    root.render(createElement(AnalyticsPage, { token: 't' }))
  })
  await settle()
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.an-sheet tbody tr')]
const cell = (row: number, col: number) => container.querySelector<HTMLInputElement>(`.an-sheet [data-cell="${row}-${col}"] input`)!
const focused = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell
const foot = () => container.querySelector<HTMLElement>('.jf-foot')!
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
async function save() {
  await key(cell(0, 0), 'KeyS', { ctrlKey: true })
  await settle()
  await settle()
}

describe('تفصیلی سایر — برگه‌ی اکسلی', () => {
  it('دسته، بعد کد؛ و یک ردیفِ خالیِ ته', async () => {
    await render()
    expect(rows().map((r) => r.querySelector<HTMLInputElement>('[data-cell$="-0"] input')!.value)).toEqual(['P-1', 'V-1', 'V-2', ''])
    expect(foot().className).toContain('jf-foot--ok')
  })

  it('ویرایشِ یک خانه: ته‌رنگ، نوارِ زرد، و Ctrl+S فقط همان فیلد را PATCH می‌کند', async () => {
    await render()
    type(cell(1, 1), 'پراید ۱۳۱')
    expect(cell(1, 1).closest('td')!.className).toContain('is-changed')
    expect(rows()[1].className).toContain('xl-row--dirty')
    expect(foot().className).toContain('jf-foot--warn')
    await save()
    expect(calls).toEqual([{ method: 'PATCH', path: '/api/accounting/analytics/b', body: { name: 'پراید ۱۳۱' } }])
    expect(foot().className).toContain('jf-foot--ok')
    expect(cell(1, 1).value).toBe('پراید ۱۳۱')
  })

  it('ردیفِ خالیِ ته: تایپ ردیفِ تازه می‌سازد و ذخیره POST می‌کند', async () => {
    await render()
    type(cell(3, 0), 'V-3')
    expect(rows()).toHaveLength(5)
    type(cell(3, 1), 'سمند')
    type(cell(3, 2), 'خودرو')
    await save()
    expect(calls).toEqual([
      { method: 'POST', path: '/api/accounting/analytics', body: { code: 'V-3', name: 'سمند', group_name: 'خودرو', description: '' } },
    ])
    expect(rows()).toHaveLength(5)
    expect(rows()[4].querySelector('input')!.value).toBe('')
  })

  it('کدِ تکراری: ردیف با نوشته‌اش می‌ماند، قرمز می‌شود و دلیلش زیرِ برگه است', async () => {
    await render()
    type(cell(3, 0), 'V-1')
    type(cell(3, 1), 'پرایدِ دوم')
    await save()
    expect(rows()[3].className).toContain('xl-row--error')
    expect(cell(3, 1).value).toBe('پرایدِ دوم')
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('کدِ تکراری است.')
    expect(foot().className).toContain('jf-foot--err')
  })

  it('ردیفِ تازه‌ی ناقص پیش از ارسال رد می‌شود', async () => {
    await render()
    type(cell(3, 1), 'بی‌کد')
    await save()
    expect(calls).toEqual([])
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('کد را وارد کنید.')
  })

  it('Enter: کد → نام → دسته → کدِ ردیفِ بعد', async () => {
    await render()
    act(() => cell(0, 0).focus())
    await key(cell(0, 0), 'Enter')
    expect(focused()).toBe('0-1')
    await key(cell(0, 1), 'Enter')
    expect(focused()).toBe('0-2')
    await key(cell(0, 2), 'Enter')
    expect(focused()).toBe('1-0')
  })

  it('جست‌وجو ثبت‌شده‌ها را می‌پالاید، ردیفِ تازه را نه', async () => {
    await render()
    const find = container.querySelector<HTMLInputElement>('.jg-find input')!
    type(find, 'پژو')
    expect(rows().map((r) => r.querySelector<HTMLInputElement>('input')!.value)).toEqual(['V-2', ''])
  })

  it('پیش‌نویسِ ذخیره‌نشده با برگشتن به صفحه برمی‌گردد', async () => {
    await render()
    type(cell(0, 3), 'فازِ یک')
    act(() => root.unmount())
    root = createRoot(container)
    await render()
    expect(cell(0, 3).value).toBe('فازِ یک')
    expect(foot().className).toContain('jf-foot--warn')
    expect(container.querySelector('.jf-msg')!.textContent).toContain('برگشت')
  })
})
