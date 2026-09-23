// @vitest-environment jsdom
/**
 * صفحه‌ی «گزارش‌ها» از بخشِ ناوبری باز می‌شود — `reports/balance-sheet` ترازنامه را باز
 * می‌کند، نه سود و زیان.
 *
 * بی این، هر ردیفِ «همه‌ی گزارش‌ها» که به یکی از دوازده تب اشاره می‌کند فقط صفحه را
 * باز می‌کرد و کاربر باید دوباره تب را پیدا می‌کرد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Reports } from './Reports'
import { NavSectionContext } from './navContext'

let container: HTMLDivElement
let root: Root
let fetchMock: ReturnType<typeof vi.fn>
let setSection: ReturnType<typeof vi.fn<(key: string | null) => void>>

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  //: درخواستی که هرگز برنمی‌گردد: گزارش در حالِ بارگذاری می‌ماند و این تست فقط تبِ
  //: انتخاب‌شده و درخواست‌های رفته را می‌سنجد.
  fetchMock = vi.fn(() => new Promise(() => {}))
  vi.stubGlobal('fetch', fetchMock)
  setSection = vi.fn<(key: string | null) => void>()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

function render(section: string | null) {
  act(() => {
    root.render(
      createElement(
        NavSectionContext.Provider,
        { value: { activePage: 'reports', section, setSection } },
        createElement(Reports, { token: 't' }),
      ),
    )
  })
}

const activeTab = () => container.querySelector('.report-tabs .btn-primary')?.textContent
const requested = () => fetchMock.mock.calls.map((c) => String(c[0]))

describe('صفحه‌ی «گزارش‌ها» و بخشِ ناوبری', () => {
  it('بی‌بخش: پیش‌فرض، سود و زیان', () => {
    render(null)
    expect(activeTab()).toBe('سود و زیان')
  })

  it('با بخش: همان گزارش باز می‌شود', () => {
    render('balance-sheet')
    expect(activeTab()).toBe('ترازنامه')
  })

  it('بخشِ ناشناخته نادیده گرفته می‌شود', () => {
    render('nonsense')
    expect(activeTab()).toBe('سود و زیان')
  })

  it('کاردکسِ مستقیم فهرستِ کالاها را هم می‌گیرد — وگرنه انتخاب‌گرش خالی می‌ماند', () => {
    render('kardex')
    expect(activeTab()).toBe('کاردکس کالا')
    expect(requested().some((u) => u.includes('/api/items'))).toBe(true)
  })

  it('عوض‌شدنِ بخش روی همان صفحه، تب را عوض می‌کند', () => {
    render(null)
    render('cash-flow')
    expect(activeTab()).toBe('جریان وجوه نقد')
  })

  it('کلیکِ تب بخشِ ناوبری را عوض می‌کند، تا «همه‌ی گزارش‌ها» هم بداند', () => {
    render(null)
    const btn = [...container.querySelectorAll<HTMLButtonElement>('.report-tabs button')].find(
      (b) => b.textContent === 'ترازنامه',
    )!
    act(() => btn.click())
    expect(setSection).toHaveBeenCalledWith('balance-sheet')
  })
})
