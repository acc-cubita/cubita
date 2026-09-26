// @vitest-environment jsdom
/**
 * «شماره‌گذاری مجدد اسناد» — نقشه‌ی شماره‌ها با تمِ اکسلی.
 *
 * بی انتخاب نقشه‌ی کلِ بازه؛ با انتخاب، نقشه‌ی **همان انتخاب** از سرور (شماره‌ی تازه‌ی هر سند به انتخاب بستگی دارد) و
 * سندِ بیرونِ انتخاب «—»؛ شماره‌ی تکراری پیش از اعمال گفته می‌شود و اعمال بسته است؛ اعمال همان بدنه را با تأیید می‌فرستد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RenumberEntriesPage } from './RenumberEntriesPage'

let container: HTMLDivElement
let root: Root
let writes: { path: string; body: Record<string, unknown> }[]
let clash: number | null
let previews: string[]

const ROWS = [
  { id: 'a', entry_date: '2026-09-01', description: 'اول', atf_number: 1, old_number: 5, status: 'temporary', source_type: 'manual', accounts: [] },
  { id: 'b', entry_date: '2026-09-02', description: 'دوم', atf_number: 2, old_number: 2, status: 'temporary', source_type: 'manual', accounts: [] },
  { id: 'c', entry_date: '2026-09-03', description: 'سوم', atf_number: 3, old_number: 9, status: 'temporary', source_type: 'manual', accounts: [] },
]

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  writes = []
  previews = []
  clash = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (init?.method === 'POST') {
        writes.push({ path: url.pathname, body: JSON.parse(String(init.body ?? '{}')) })
        return json({ count: 2, changed_count: 2, first_number: 1, last_number: 2 })
      }
      if (url.pathname === '/api/accounting/entries/renumber/preview') {
        previews.push(url.search)
        const start = Number(url.searchParams.get('start_number'))
        const ids = url.searchParams.getAll('entry_ids')
        const plan = (ids.length ? ROWS.filter((r) => ids.includes(r.id)) : ROWS).map((r, i) => ({
          ...r,
          new_number: start + i,
          changed: r.old_number !== start + i,
        }))
        return json({
          count: plan.length,
          changed_count: plan.filter((r) => r.changed).length,
          skipped_permanent: 1,
          rows: plan,
          truncated: false,
          first_clash: clash,
        })
      }
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
    root.render(createElement(RenumberEntriesPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.rn-sheet tbody tr')]
const newNumbers = () => rows().map((tr) => tr.querySelector('td[data-label="شماره‌ی تازه"]')?.textContent)
const foot = () => container.querySelector('.jf-foot')?.textContent ?? ''

describe('شماره‌گذاری مجدد اسناد', () => {
  it('بی انتخاب نقشه‌ی کلِ بازه؛ شماره‌ی عوض‌شونده پررنگ و عطف ثابت', async () => {
    await render()
    expect(newNumbers()).toEqual(['۱', '۲', '۳'])
    expect(rows()[1].querySelector('td[data-label="شماره‌ی تازه"]')!.className).toContain('rn-same')
    expect(rows()[0].querySelector('td[data-label="شماره‌ی تازه"]')!.className).toContain('rn-changed')
    expect(foot()).toContain('آماده')
    expect(foot()).toContain('۲ سند')
    expect(container.textContent).toContain('۱ سندِ دائم دست نمی‌خورد')
  })

  it('با انتخاب نقشه‌ی همان انتخاب از سرور می‌آید و سندِ بیرونِ انتخاب «—» است', async () => {
    await render()
    act(() => rows()[2].click())
    act(() => rows()[0].click())
    await settle(300)
    await settle()
    expect(previews.at(-1)).toContain('entry_ids=a')
    expect(previews.at(-1)).toContain('entry_ids=c')
    expect(previews.at(-1)).not.toContain('date_from')
    expect(newNumbers()).toEqual(['۱', '—', '۲'])
    await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
    await settle()
    expect(writes).toEqual([
      {
        path: '/api/accounting/entries/renumber',
        body: { date_from: null, date_to: null, entry_ids: ['a', 'c'], start_number: 1 },
      },
    ])
  })

  it('شماره‌ی تکراری پیش از اعمال گفته می‌شود و اعمال بسته است', async () => {
    clash = 2
    await render()
    expect(foot()).toContain('شماره‌ی ۲ تکراری')
    expect(container.querySelector('.acc-note--err')?.textContent).toContain('شماره‌ی ۲')
    expect(container.querySelector<HTMLButtonElement>('.jf-submit')!.disabled).toBe(true)
  })
})
