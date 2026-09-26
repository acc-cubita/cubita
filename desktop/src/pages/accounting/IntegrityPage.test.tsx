// @vitest-environment jsdom
/**
 * «بررسی یکپارچگی» — یک گرید برای همه‌ی بررسی‌ها.
 *
 * سرگروهِ هر بررسی با وضعیت و شمار، یافته‌ها زیرش و بازوبسته با کلیک، «فقط یافته‌ها»، «جمعِ دفتر» با نتیجه‌ی کل، و بردنِ
 * کاربر به خودِ سند از یافته (کلیک یا Enter).
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { IntegrityPage } from './IntegrityPage'

vi.mock('../../components/JournalEntryDrawer', () => ({
  JournalEntryDrawer: ({ entryId }: { entryId: string }) => createElement('div', { className: 'fake-entry-drawer' }, entryId),
}))

let container: HTMLDivElement
let root: Root

const REPORT = {
  date_from: null,
  date_to: null,
  total_debit: '1000',
  total_credit: '990',
  difference: '10',
  ok: false,
  checks: [
    {
      key: 'unbalanced',
      title: 'سندِ نامتوازن',
      description: 'جمعِ بدهکار و بستانکارِ این سندها یکی نیست.',
      severity: 'error',
      ok: false,
      count: 1,
      truncated: false,
      rows: [{ label: 'سند ۱۲', detail: 'فروش', debit: '100', credit: '90', difference: '10', entry_id: 'e12' }],
    },
    { key: 'leaves', title: 'برگِ دارای زیرحساب', description: 'حساب‌هایی که…', severity: 'error', ok: true, count: 0, truncated: false, rows: [] },
    {
      key: 'empty',
      title: 'سندِ بی‌ردیف',
      description: 'سندهایی که ردیفی ندارند.',
      severity: 'warning',
      ok: false,
      count: 60,
      truncated: true,
      rows: [{ label: 'سند ۲', detail: '', debit: '0', credit: '0', difference: '0', entry_id: 'e2' }],
    },
  ],
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200 })
      if (url.pathname === '/api/reports/integrity') return json(REPORT)
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

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render() {
  await act(async () => {
    root.render(createElement(IntegrityPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const kinds = () =>
  [...container.querySelectorAll<HTMLTableRowElement>('.ig-sheet tbody tr')].map((tr) =>
    tr.classList.contains('ig-check') ? `check:${tr.querySelector('.ig-title')?.textContent}` : tr.classList.contains('ig-more') ? 'more' : 'finding',
  )
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!

describe('بررسی یکپارچگی — گرید', () => {
  it('سرگروهِ هر بررسی با وضعیتش، یافته‌ها زیرش و «بقیه» برای بریده‌شده', async () => {
    await render()
    //: یافته‌ها اول — خطا، هشدار، بعد سالم.
    expect(kinds()).toEqual(['check:سندِ نامتوازن', 'finding', 'check:سندِ بی‌ردیف', 'finding', 'more', 'check:برگِ دارای زیرحساب'])
    const heads = [...container.querySelectorAll('.ig-sheet tr.ig-check .xl-check')].map((c) => c.textContent)
    expect(heads).toEqual(['۱ مورد · خطا', '۶۰ مورد · هشدار', 'بدونِ یافته'])
    expect(container.querySelector('.ig-more')?.textContent).toContain('۱ مورد از ۶۰')
    //: شرحِ بررسیِ سالم فقط راهنماست؛ روی سرگروهِ دارای یافته دیده می‌شود.
    expect(container.querySelectorAll('.ig-desc')).toHaveLength(2)
  })

  it('«جمعِ دفتر» با اختلاف و نتیجه‌ی کل در پانویس', async () => {
    await render()
    const foot = container.querySelector('.ig-sheet tfoot')!.textContent ?? ''
    expect(foot).toContain('جمعِ دفتر')
    expect(foot).toContain('نیازمندِ رسیدگی')
    expect(foot).toContain('۱٬۰۰۰')
    expect(foot).toContain('۹۹۰')
    expect(container.textContent).toContain('۱ خطا و ۱ هشدار')
  })

  it('کلیکِ سرگروه یافته‌ها را می‌بندد؛ «فقط یافته‌ها» بررسیِ سالم را برمی‌دارد', async () => {
    await render()
    act(() => container.querySelector<HTMLTableRowElement>('.ig-sheet tr.ig-check--error')!.click())
    expect(kinds()).toEqual(['check:سندِ نامتوازن', 'check:سندِ بی‌ردیف', 'finding', 'more', 'check:برگِ دارای زیرحساب'])
    act(() => button('فقط یافته‌ها').click())
    expect(kinds()).toEqual(['check:سندِ نامتوازن', 'check:سندِ بی‌ردیف', 'finding', 'more'])
  })

  it('کلیکِ یافته و Enter روی آن خودِ سند را باز می‌کنند', async () => {
    await render()
    act(() => container.querySelector<HTMLTableRowElement>('.ig-sheet tr.ig-finding')!.click())
    expect(container.querySelector('.fake-entry-drawer')?.textContent).toBe('e12')
  })

  it('صفحه‌کلید: ↓ به یافته می‌رود و Enter سندش را باز می‌کند', async () => {
    await render()
    const grid = container.querySelector<HTMLDivElement>('.lr-scroll')!
    act(() => {
      grid.focus()
      grid.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }))
    })
    expect(container.querySelector('.ig-sheet tr.is-active')?.classList.contains('ig-finding')).toBe(true)
    act(() => {
      grid.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    })
    expect(container.querySelector('.fake-entry-drawer')?.textContent).toBe('e12')
  })
})
