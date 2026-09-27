// @vitest-environment jsdom
/**
 * «دوره‌های بسته‌شده» — دفترِ قفل‌های دوره با تمِ اکسلی: تازه‌ترین اول با بازه‌ی هر قفل، نشانِ «مرزِ ثبتِ سند» روی آخرین،
 * جمعِ دوره‌ها در پانویس، و بازشدنِ سندِ بستن با کلیک روی ردیف.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PeriodCloseListPage } from './PeriodCloseListPage'

vi.mock('../../components/JournalEntryDrawer', () => ({
  JournalEntryDrawer: ({ entryId }: { entryId: string }) => createElement('div', { className: 'fake-entry-drawer' }, entryId),
}))

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const url = new URL(input, 'http://x')
      if (url.pathname === '/api/fiscal-period-closes')
        return new Response(
          JSON.stringify([
            { id: 'a', closing_date: '2026-03-20', net_profit: '-200', notes: 'سالِ اول', journal_entry_id: 'je-a' },
            { id: 'b', closing_date: '2026-06-30', net_profit: '500', notes: '', journal_entry_id: 'je-b' },
          ]),
        )
      return new Response('[]')
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

async function render() {
  await act(async () => {
    root.render(createElement(PeriodCloseListPage, { token: 't' }))
  })
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.pcl-sheet tbody tr')]

describe('دوره‌های بسته‌شده', () => {
  it('تازه‌ترین اول با بازه‌ی هر قفل؛ آخرین «مرزِ ثبتِ سند»', async () => {
    await render()
    expect(rows().map((tr) => tr.querySelector('td[data-label="بازه"]')?.textContent)).toEqual([
      '۱۴۰۵/۰۱/۰۱ تا ۱۴۰۵/۰۴/۰۹',
      'ابتدای دفتر تا ۱۴۰۴/۱۲/۲۹',
    ])
    expect(rows()[0].className).toContain('pcl-latest')
    expect(rows()[0].textContent).toContain('مرزِ ثبتِ سند')
    expect(rows()[1].textContent).not.toContain('مرزِ ثبتِ سند')
  })

  it('جمعِ دوره‌ها در پانویس؛ زیان در پرانتز', async () => {
    await render()
    expect(container.querySelector('.pcl-sheet tfoot')?.textContent).toContain('۳۰۰')
    expect(rows()[1].querySelector('.rp-neg')?.textContent).toBe('(۲۰۰)')
  })

  it('کلیک روی ردیف سندِ بستنِ همان قفل را باز می‌کند', async () => {
    await render()
    act(() => rows()[1].click())
    expect(container.querySelector('.fake-entry-drawer')?.textContent).toBe('je-a')
  })
})
