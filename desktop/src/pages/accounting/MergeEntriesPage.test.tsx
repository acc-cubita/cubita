// @vitest-environment jsdom
/**
 * «ادغام اسناد» — برگه‌ی اسناد با سرگروهِ روز و پیش‌نمایشِ سندِ ادغامی (تمِ اکسلی).
 *
 * فقط روزهای چندسندی؛ کلیکِ سرگروه همه‌ی سندهای روز را انتخاب می‌کند؛ سندِ روزِ دیگر قفل است؛ سندِ ادغامی ردیف‌ها را
 * به‌ترتیبِ شماره پشتِ هم می‌گذارد و نوار جمعش را می‌گوید؛ ادغام همان شناسه‌ها را با تأیید می‌فرستد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MergeEntriesPage } from './MergeEntriesPage'

let container: HTMLDivElement
let root: Root
let writes: { path: string; body: Record<string, unknown> }[]

const line = (id: string, account: string, debit: number, credit: number) => ({ id, account_id: account, debit: String(debit), credit: String(credit), description: `ردیفِ ${id}` })
const entry = (id: string, number: number, date: string, amount: number) => ({
  id,
  number,
  atf_number: number,
  sub_number: null,
  entry_date: date,
  description: `سند ${id}`,
  source_type: 'manual',
  source: null,
  status: 'temporary',
  voided_at: null,
  reverses_entry_id: null,
  lines: [line(`${id}-d`, 'cash', amount, 0), line(`${id}-c`, 'rent', 0, amount)],
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
        writes.push({ path: url.pathname, body: JSON.parse(String(init.body ?? '{}')) })
        return json({ entry_id: 'm', number: 77, line_count: 4, merged_numbers: [12, 13] }, 201)
      }
      if (url.pathname === '/api/journal-entries')
        return json({
          items: [entry('b', 13, '2026-09-01', 50), entry('a', 12, '2026-09-01', 100), entry('c', 20, '2026-09-02', 5), entry('d', 21, '2026-09-02', 9), entry('e', 30, '2026-09-03', 7)],
          next_cursor: null,
        })
      if (url.pathname === '/api/accounts')
        return json([
          { id: 'cash', code: '1101', name: 'صندوق', is_group: false },
          { id: 'rent', code: '5101', name: 'اجاره', is_group: false },
        ])
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
    root.render(createElement(MergeEntriesPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const listRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.mg-list tbody tr')]
const entryRow = (n: string) => listRows().find((tr) => tr.querySelector('.card-title')?.textContent === `سند ${n}`)!
const foot = () => container.querySelector('.jf-foot')?.textContent ?? ''

describe('ادغام اسناد', () => {
  it('فقط روزهای چندسندی با سرگروه؛ سندها به‌ترتیبِ شماره', async () => {
    await render()
    expect(listRows().map((tr) => (tr.classList.contains('mg-day') ? 'day' : tr.querySelector('.card-title')?.textContent))).toEqual([
      'day',
      'سند ۲۰',
      'سند ۲۱',
      'day',
      'سند ۱۲',
      'سند ۱۳',
    ])
  })

  it('کلیکِ سرگروه همه‌ی سندهای روز را انتخاب می‌کند و سندِ روزِ دیگر قفل می‌شود', async () => {
    await render()
    act(() => listRows()[3].click())
    expect(entryRow('۱۲').className).toContain('is-selected')
    expect(entryRow('۱۳').className).toContain('is-selected')
    expect(entryRow('۲۰').className).toContain('is-blocked')
    act(() => entryRow('۲۰').click())
    expect(entryRow('۲۰').className).not.toContain('is-selected')
  })

  it('سندِ ادغامی ردیف‌ها را به‌ترتیبِ شماره پشتِ هم می‌گذارد؛ نوار متوازن با جمع', async () => {
    await render()
    act(() => entryRow('۱۳').click())
    act(() => entryRow('۱۲').click())
    const doc = [...container.querySelectorAll<HTMLTableRowElement>('.mg-doc tbody tr')]
    expect(doc.map((tr) => tr.querySelector('td[data-label="از سند"]')?.textContent)).toEqual(['۱۲', '۱۲', '۱۳', '۱۳'])
    expect(doc[0].querySelector('.card-title')?.textContent).toBe('1101 — صندوق')
    expect(foot()).toContain('متوازن')
    expect(foot()).toContain('۱۵۰')
    expect(container.querySelector<HTMLInputElement>('.jh-bar input')!.placeholder).toBe('ادغامِ اسنادِ ۱۲، ۱۳')
  })

  it('یک سند ادغام نمی‌شود؛ دو سند با تأیید ادغام می‌شوند', async () => {
    await render()
    act(() => entryRow('۱۲').click())
    expect(container.querySelector<HTMLButtonElement>('.jf-submit')!.disabled).toBe(true)
    act(() => entryRow('۱۳').click())
    await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
    await settle()
    expect(writes).toEqual([{ path: '/api/accounting/entries/merge', body: { entry_ids: ['b', 'a'], description: '' } }])
    expect(foot()).toContain('شماره ۷۷')
  })
})
