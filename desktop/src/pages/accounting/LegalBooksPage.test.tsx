// @vitest-environment jsdom
/**
 * «دفاتر تجارت الکترونیک» — گریدِ اکسلیِ دفترِ روزنامه‌ی قانونی.
 *
 * شماره‌ی ردیفِ پیوسته، دامنه‌ی «دائم/موقت» که دفترِ جدا می‌سازد (از ۱ شماره می‌خورد)، جست‌وجویی که شماره‌ی ردیف را نگه
 * می‌دارد و توازن را نمی‌سنجد، جمعِ انتخاب، و ساختنِ ردیف‌ها تکه‌تکه با «همه».
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LegalBooksPage } from './LegalBooksPage'

let container: HTMLDivElement
let root: Root
let bookRows: Record<string, unknown>[]

const line = (entry: string, number: number, status: string, code: string, name: string, debit: string, credit: string, voided = false) => ({
  entry_id: entry,
  entry_number: number,
  entry_date: '2026-04-01',
  status,
  voided,
  account_code: code,
  account_name: name,
  description: '',
  debit,
  credit,
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  bookRows = [
    line('e1', 1, 'permanent', '1101', 'صندوق', '500', '0'),
    line('e1', 1, 'permanent', '3101', 'سرمایه', '0', '500'),
    line('e2', 2, 'temporary', '5101', 'اجاره', '120', '0'),
    line('e2', 2, 'temporary', '1101', 'صندوق', '0', '120'),
    line('e3', 3, 'permanent', '1101', 'صندوق', '80', '0', true),
    line('e3', 3, 'permanent', '4101', 'فروش', '0', '80', true),
  ]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200 })
      if (url.pathname === '/api/accounting/legal-book') {
        const sum = (k: 'debit' | 'credit') => String(bookRows.reduce((s, r) => s + Number(r[k]), 0))
        return json({ date_from: '2026-03-21', date_to: '2027-03-20', rows: bookRows, total_debit: sum('debit'), total_credit: sum('credit') })
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

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render() {
  await act(async () => {
    root.render(createElement(LegalBooksPage, { token: 't' }))
  })
  await settle()
  await settle()
}
const bodyRows = () => [...container.querySelectorAll<HTMLTableRowElement>('.eb-sheet tbody tr')]
const rowNumbers = () => bodyRows().map((tr) => tr.querySelector('.xl-rowhead-btn')?.textContent)
const foot = () => container.querySelector('.eb-sheet tfoot')!.textContent ?? ''
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!
function type(el: HTMLInputElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(el, value)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('دفاتر تجارت الکترونیک — گرید', () => {
  it('یک ردیف به‌ازای هر ردیفِ سند با شماره‌ی پیوسته؛ ردیفِ اولِ هر سند نشان دارد و «جمعِ دفتر» تراز است', async () => {
    await render()
    expect(rowNumbers()).toEqual(['۱', '۲', '۳', '۴', '۵', '۶'])
    expect(bodyRows().map((tr) => tr.classList.contains('eb-first'))).toEqual([true, false, true, false, true, false])
    expect(bodyRows()[2].textContent).toContain('موقت')
    expect(bodyRows()[4].className).toContain('eb-void')
    expect(foot()).toContain('جمعِ دفتر')
    expect(foot()).toContain('۷۰۰')
    expect(container.querySelector('.eb-sheet tfoot .xl-check--ok')?.textContent).toContain('تراز است')
  })

  it('«دائم» دفترِ جداست و از ۱ شماره می‌خورد', async () => {
    await render()
    act(() => button('دائم').click())
    expect(rowNumbers()).toEqual(['۱', '۲', '۳', '۴'])
    expect(bodyRows().some((tr) => tr.textContent?.includes('اجاره'))).toBe(false)
  })

  it('جست‌وجو شماره‌ی ردیف را نگه می‌دارد، جمعِ منطبق‌ها را می‌گوید و توازن را نمی‌سنجد', async () => {
    await render()
    type(container.querySelector<HTMLInputElement>('input[aria-label="جست‌وجو در دفتر"]')!, 'صندوق')
    expect(rowNumbers()).toEqual(['۱', '۴', '۵'])
    expect(foot()).toContain('جمعِ ردیف‌های منطبق')
    expect(container.querySelector('.eb-sheet tfoot .xl-check')).toBeNull()
  })

  it('انتخاب با شماره‌ی ردیف جمعِ بدهکار و بستانکار را پایین می‌آورد', async () => {
    await render()
    act(() => bodyRows()[0].querySelector<HTMLButtonElement>('.xl-rowhead-btn')!.click())
    act(() =>
      bodyRows()[2].querySelector<HTMLButtonElement>('.xl-rowhead-btn')!.dispatchEvent(
        new MouseEvent('click', { bubbles: true, ctrlKey: true }),
      ),
    )
    const bar = container.querySelector('.xl-selbar, [role="status"]')?.textContent ?? container.textContent ?? ''
    expect(bar).toContain('۲')
    expect(bar).toContain('۶۲۰')
  })

  it('دفترِ بزرگ تکه‌تکه ساخته می‌شود؛ «نمایشِ همه» بقیه را می‌آورد و جمع از اول کلِ دفتر است', async () => {
    bookRows = Array.from({ length: 1200 }, (_, i) =>
      line(`e${Math.floor(i / 2)}`, Math.floor(i / 2) + 1, 'permanent', i % 2 ? '3101' : '1101', 'ح', i % 2 ? '0' : '10', i % 2 ? '10' : '0'),
    )
    await render()
    expect(bodyRows()).toHaveLength(500)
    expect(container.querySelector('.eb-more')?.textContent).toContain('۵۰۰ از ۱٬۲۰۰')
    expect(foot()).toContain('۶٬۰۰۰')
    act(() => button('نمایشِ همه').click())
    expect(bodyRows()).toHaveLength(1200)
    expect(container.querySelector('.eb-more')).toBeNull()
  })
})
