// @vitest-environment jsdom
/**
 * «کارتابل اسناد موقت» — برگه‌ی اکسلیِ صفِ بازبینی.
 *
 * کلیک روی ردیف انتخاب می‌کند و «نمایش» سند را باز؛ منشأها برگه را فیلتر می‌کنند و «دائم‌کردنِ همه‌ی …» همان منشأ را
 * با بازه می‌فرستد؛ نوار سندهای انتخابی را با Ctrl+S دائم می‌کند؛ بریدگیِ ۲۰۰تاییِ سرور گفته می‌شود.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { EntryCartablePage } from './EntryCartablePage'

vi.mock('../../components/JournalEntryDrawer', () => ({
  JournalEntryDrawer: ({ entryId }: { entryId: string }) => createElement('div', { className: 'fake-entry-drawer' }, entryId),
}))

let container: HTMLDivElement
let root: Root
let writes: { path: string; body: Record<string, unknown> }[]
let totalCount: number

const entry = (id: string, number: number, source: string, description: string, total: string) => ({
  id,
  number,
  atf_number: number,
  sub_number: null,
  entry_date: '2026-09-01',
  description,
  source_type: source,
  status: 'temporary',
  voided_at: null,
  total,
  line_count: 2,
  accounts: ['صندوق'],
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  writes = []
  totalCount = 3
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body ?? '{}'))
        writes.push({ path: url.pathname, body })
        return json({ count: body.entry_ids?.length ?? 2, first_date: '2026-09-01', last_date: '2026-09-01' })
      }
      if (url.pathname === '/api/accounting/cartable')
        return json({
          total_count: totalCount,
          groups: [
            { source_type: 'sales_invoice', count: 2, total: '1200' },
            { source_type: 'manual', count: 1, total: '300' },
          ],
          entries: [
            entry('e1', 1, 'sales_invoice', 'فروشِ نقدی', '500'),
            entry('e2', 2, 'manual', 'اجاره', '300'),
            entry('e3', 3, 'sales_invoice', 'فروشِ اقساطی', '700'),
          ],
        })
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
    root.render(createElement(EntryCartablePage, { token: 't' }))
  })
  await settle()
  await settle()
}
const bodyRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.cb-sheet tbody tr')]
const foot = () => container.querySelector('.jf-foot')?.textContent ?? ''
/** `SearchSelect` زیرِ آستانه `<select>`ِ بومی است و بالاتر دکمه و پاپ‌آور؛ هر دو را می‌گیرد. */
async function pickSource(option: string) {
  const native = container.querySelector<HTMLSelectElement>('select[aria-label="منشأ"]')
  if (native) {
    const value = [...native.options].find((o) => o.textContent?.includes(option))!.value
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!.call(native, value)
      native.dispatchEvent(new Event('change', { bubbles: true }))
    })
    return
  }
  await act(async () => container.querySelector<HTMLButtonElement>('.item-picker-trigger[aria-label="منشأ"]')!.click())
  await act(async () => [...document.querySelectorAll<HTMLElement>('.item-picker-opt')].find((o) => o.textContent?.includes(option))!.click())
}

describe('کارتابل اسناد موقت', () => {
  it('کلیک روی ردیف انتخاب می‌کند و نوار شمار و مبلغ را می‌گوید؛ Ctrl+S همان‌ها را دائم می‌کند', async () => {
    await render()
    act(() => bodyRows()[0].click())
    act(() => bodyRows()[2].click())
    expect(container.querySelectorAll('.cb-sheet tr.is-selected')).toHaveLength(2)
    expect(foot()).toContain('دائم‌کردنِ ۲ سند')
    expect(foot()).toContain('۱٬۲۰۰')
    await act(async () =>
      container.querySelector('form')!.dispatchEvent(new KeyboardEvent('keydown', { key: 's', code: 'KeyS', ctrlKey: true, bubbles: true, cancelable: true })),
    )
    await settle()
    expect(writes).toEqual([{ path: '/api/accounting/entries/finalize', body: { entry_ids: ['e1', 'e3'] } }])
    expect(foot()).toContain('۲ سند دائم شد')
  })

  it('«نمایش» خودِ سند را باز می‌کند و ردیف را انتخاب نمی‌کند', async () => {
    await render()
    act(() => bodyRows()[1].querySelector<HTMLButtonElement>('.cb-open')!.click())
    expect(container.querySelector('.fake-entry-drawer')?.textContent).toBe('e2')
    expect(bodyRows()[1].className).not.toContain('is-selected')
  })

  it('منشأ برگه را فیلتر می‌کند و «دائم‌کردنِ همه‌ی …» همان منشأ را با بازه می‌فرستد', async () => {
    await render()
    await pickSource('فاکتور فروش')
    expect(bodyRows()).toHaveLength(2)
    const scopeBtn = [...container.querySelectorAll('button')].find((b) => b.textContent?.includes('دائم‌کردنِ همه‌ی «'))!
    await act(async () => scopeBtn.click())
    await settle()
    expect(writes).toEqual([
      { path: '/api/accounting/entries/finalize', body: { source_type: 'sales_invoice' } },
    ])
  })

  it('سرستونِ ردیف همه‌ی دیده‌شده‌ها را انتخاب و دوباره لغو می‌کند', async () => {
    await render()
    const all = container.querySelector<HTMLButtonElement>('.cb-sheet thead .xl-rowhead-btn')!
    act(() => all.click())
    expect(container.querySelectorAll('.cb-sheet tr.is-selected')).toHaveLength(3)
    act(() => all.click())
    expect(container.querySelectorAll('.cb-sheet tr.is-selected')).toHaveLength(0)
  })

  it('بریدگیِ سرور گفته می‌شود', async () => {
    totalCount = 250
    await render()
    expect(container.textContent).toContain('۳ سندِ اول از ۲۵۰')
  })
})
