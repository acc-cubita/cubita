// @vitest-environment jsdom
/**
 * «اسناد حسابداری» — دفترِ کاملِ اسناد با تمِ اکسلی.
 *
 * صفحه‌بندی از سرور با «سندِ بعدی» (پیش از این ۳۰۰ سندِ اول و بقیه بی‌صدا نه)، «جمعِ بازه» از `/summary` با نشانِ توازن،
 * فیلترهای سرستون و «وضعیت»ِ سربرگ هم به فهرست و هم به جمع می‌روند، کلیک روی ردیف خودِ سند را باز می‌کند و شماره‌ی ردیف
 * انتخاب می‌کند.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { EntryListPage } from './EntryListPage'

vi.mock('../../components/JournalEntryDrawer', () => ({
  JournalEntryDrawer: ({ entryId }: { entryId: string }) => createElement('div', { className: 'fake-entry-drawer' }, entryId),
}))

let container: HTMLDivElement
let root: Root
let listQueries: URLSearchParams[]
let summaryQueries: URLSearchParams[]

const entry = (n: number, status = 'temporary', voided = false) => ({
  id: `e${n}`,
  number: n,
  atf_number: n + 100,
  sub_number: null,
  entry_date: '2026-09-01',
  description: `سند ${n}`,
  source_type: 'manual',
  created_by_name: n === 1 ? 'مریم احمدی' : null,
  source: null,
  status,
  voided_at: voided ? '2026-09-02' : null,
  reverses_entry_id: null,
  lines: [
    { id: `l${n}a`, account_id: 'a', debit: String(n * 10), credit: '0', description: '' },
    { id: `l${n}b`, account_id: 'b', debit: '0', credit: String(n * 10), description: '' },
  ],
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  listQueries = []
  summaryQueries = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200 })
      if (url.pathname === '/api/journal-entries') {
        listQueries.push(url.searchParams)
        return url.searchParams.get('cursor')
          ? json({ items: [entry(3, 'permanent')], next_cursor: null })
          : json({ items: [entry(1), entry(2, 'permanent', true)], next_cursor: 'c1' })
      }
      if (url.pathname === '/api/journal-entries/summary') {
        summaryQueries.push(url.searchParams)
        return json({ entry_count: 3, line_count: 6, total_debit: '60', total_credit: '60' })
      }
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
})

const settle = (ms = 0) =>
  act(async () => {
    await new Promise((r) => setTimeout(r, ms))
  })
async function render() {
  await act(async () => {
    root.render(createElement(EntryListPage, { token: 't' }))
  })
  await settle(400)
  await settle()
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.el-sheet tbody tr')]
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!

describe('اسناد حسابداری', () => {
  it('نام ثبت‌کنندهٔ ذخیره‌شده را کنار منشأ دستی نشان می‌دهد و برای نامِ ناموجود حدس نمی‌زند', async () => {
    await render()
    expect(rows()[0].querySelector('[data-label="منشأ"]')?.textContent).toContain('ثبت‌کننده: مریم احمدی')
    expect(rows()[1].querySelector('[data-label="منشأ"]')?.textContent).toContain('ثبت‌کننده: نام در دسترس نیست')
  })
  it('صفحه‌ی اول، «جمعِ بازه» از سرور با نشانِ توازن، و «سندِ بعدی» صفحه‌ی بعد را اضافه می‌کند', async () => {
    await render()
    expect(rows().map((tr) => tr.querySelector('.card-title')?.textContent)).toEqual(['سند ۱', 'سند ۲'])
    const foot = container.querySelector('.el-sheet tfoot')!.textContent ?? ''
    expect(foot).toContain('جمعِ بازه')
    expect(foot).toContain('۶۰')
    expect(container.querySelector('.el-sheet tfoot .xl-check--ok')).not.toBeNull()
    expect(container.querySelector('.daybook-more')?.textContent).toContain('نمایشِ ۲ از ۳ سند')
    await act(async () => button('۱۰۰ سندِ بعدی').click())
    await settle()
    expect(rows()).toHaveLength(3)
    expect(listQueries.at(-1)!.get('cursor')).toBe('c1')
    expect(container.querySelector('.daybook-more button')).toBeNull()
  })

  it('فیلترِ سرستون و «وضعیت» هم به فهرست می‌روند و هم به جمع', async () => {
    await render()
    const atf = container.querySelector<HTMLInputElement>('input[aria-label="فیلترِ عطف"]')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(atf, '۱۰۲')
      atf.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await settle(400)
    expect(listQueries.at(-1)!.get('atf')).toBe('102')
    expect(summaryQueries.at(-1)!.get('atf')).toBe('102')
    act(() => button('دائم').click())
    await settle()
    expect(listQueries.at(-1)!.get('status')).toBe('permanent')
    expect(summaryQueries.at(-1)!.get('status')).toBe('permanent')
  })

  it('کلیک روی ردیف سند را باز می‌کند؛ شماره‌ی ردیف فقط انتخاب می‌کند', async () => {
    await render()
    act(() => rows()[0].querySelector<HTMLButtonElement>('.xl-rowhead-btn')!.click())
    expect(rows()[0].className).toContain('is-selected')
    expect(container.querySelector('.fake-entry-drawer')).toBeNull()
    act(() => rows()[1].click())
    expect(container.querySelector('.fake-entry-drawer')?.textContent).toBe('e2')
  })

  it('سندِ باطل خط‌خورده است و دکمه‌ی ابطالش بسته', async () => {
    await render()
    expect(rows()[1].className).toContain('acc-row--void')
    const voidBtn = rows()[1].querySelector<HTMLButtonElement>('button[aria-label="ابطال"], button[title="این سند قبلاً باطل شده است."]')
    expect(voidBtn?.disabled).toBe(true)
  })
})
