// @vitest-environment jsdom
/**
 * انتخابِ ردیف در گریدِ سند — ستونِ شماره مثلِ سرستونِ ردیفِ اکسل.
 *
 * * کلیک / Shift+کلیک / Ctrl+کلیک، و نوارِ وضعیت با تعداد و جمعِ بدهکار و بستانکارِ انتخاب‌شده‌ها.
 * * Ctrl+Delete با انتخاب، **همه‌ی** انتخاب‌شده‌ها را با هم حذف می‌کند (بی انتخاب همان یک ردیف).
 * * Esc از داخلِ گرید انتخاب را برمی‌دارد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { Harness, latest, line } from '../test/journalGridHarness'
import type { JournalDraftLine } from '../lib/journalEntryDraft'

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const render = (initial: JournalDraftLine[]) => act(() => root.render(createElement(Harness, { initial })))
const heads = () => [...container.querySelectorAll<HTMLButtonElement>('.xl-rowhead-btn')]
const bar = () => container.querySelector('.xl-selbar')
const selectedRows = () => [...container.querySelectorAll('tbody tr.is-selected')].map((tr) => tr.querySelector('.xl-rowhead-btn')?.textContent)
const click = (el: HTMLElement, init: MouseEventInit = {}) =>
  act(() => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, ...init }))
  })
const key = (el: Element, code: string, init: KeyboardEventInit = {}) =>
  act(() => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: code === 'Escape' ? 'Escape' : code, code, bubbles: true, cancelable: true, ...init }))
  })

const doc = () => [
  line({ accountId: 'bank', debit: '100', description: 'a' }),
  line({ accountId: 'cust', credit: '40', description: 'b' }),
  line({ accountId: 'cust', credit: '60', description: 'c' }),
  line({ accountId: 'bank', debit: '5', description: 'd' }),
]

describe('انتخابِ ردیف با ستونِ شماره', () => {
  it('کلیک یکی، Shift+کلیک بازه، Ctrl+کلیک افزودن — و نوارِ وضعیت با جمع‌ها', () => {
    render(doc())
    expect(bar()).toBeNull()
    click(heads()[0])
    click(heads()[2], { shiftKey: true })
    expect(selectedRows()).toEqual(['۱', '۲', '۳'])
    expect(bar()?.textContent).toContain('۳ ردیف انتخاب شد')
    //: بدهکار ۱۰۰، بستانکار ۴۰+۶۰
    expect(bar()?.textContent).toContain('جمع بدهکار ۱۰۰')
    expect(bar()?.textContent).toContain('جمع بستانکار ۱۰۰')
    click(heads()[1], { ctrlKey: true })
    expect(selectedRows()).toEqual(['۱', '۳'])
  })

  it('Ctrl+Delete همه‌ی انتخاب‌شده‌ها را با هم حذف می‌کند', () => {
    render(doc())
    click(heads()[1])
    click(heads()[2], { shiftKey: true })
    const cell = container.querySelector<HTMLInputElement>('[data-cell="0-1"] input')!
    act(() => cell.focus())
    key(cell, 'Delete', { ctrlKey: true })
    expect(latest.map((l) => l.description)).toEqual(['a', 'd'])
    expect(bar()).toBeNull()
  })

  it('دکمه‌ی حذفِ نوار و کفِ دو ردیف', () => {
    render([line({ accountId: 'bank', debit: '1' }), line({ accountId: 'cust', credit: '1' })])
    click(heads()[0])
    click(heads()[1], { shiftKey: true })
    click(container.querySelector<HTMLButtonElement>('.xl-selbar-danger')!)
    expect(latest).toHaveLength(2)
    expect(latest.every((l) => !l.accountId)).toBe(true)
  })

  it('Esc از داخلِ گرید انتخاب را برمی‌دارد', () => {
    render(doc())
    click(heads()[0])
    const cell = container.querySelector<HTMLInputElement>('[data-cell="1-1"] input')!
    act(() => cell.focus())
    key(cell, 'Escape')
    expect(selectedRows()).toEqual([])
  })
})
