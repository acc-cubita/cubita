// @vitest-environment jsdom
/**
 * «همه‌ی گزارش‌ها» در DOMِ واقعی: صفحه‌کلید، گزارشِ باز، و ترتیبِ زنده‌ی حالت.
 *
 * `reportCatalog.test.ts` داده و ترتیب را می‌سنجد؛ این‌جا چیزی سنجیده می‌شود که آن‌جا
 * دیده نمی‌شود — اینکه کاربر بی‌موس به گزارش برسد، و عوض‌کردنِ حالت فهرست را همان
 * لحظه دوباره بچیند (اشتراکِ `useSyncExternalStore`).
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ReportCatalog } from './ReportCatalog'
import { NavSectionContext } from './navContext'
import { __resetExperienceForTests, setExperience } from '../lib/experienceMode'
import type { PageKey } from '../lib/navModel'
import type { MeResponse } from '../api'

//: خالی یعنی «فیلتر نکن» — همه‌ی گزارش‌ها.
const me = { tenant_kind: 'standard', enabled_modules: [], allowed_modules: [], role_key: 'owner' } as unknown as MeResponse

let container: HTMLDivElement
let root: Root
let onNavigate: ReturnType<typeof vi.fn<(page: PageKey, section?: string) => void>>

function render(section: string | null = null) {
  act(() => {
    root.render(
      createElement(
        NavSectionContext.Provider,
        { value: { activePage: 'reports', section, setSection: vi.fn() } },
        createElement(ReportCatalog, { me, onNavigate }),
      ),
    )
  })
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  __resetExperienceForTests() // پیش‌فرض: حسابدار
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  onNavigate = vi.fn<(page: PageKey, section?: string) => void>()
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const headings = () => [...container.querySelectorAll('.rc-heading')].map((h) => h.textContent)
const items = () => [...container.querySelectorAll<HTMLButtonElement>('.rc-item')]
const filter = () => container.querySelector<HTMLInputElement>('.rc-filter')!
const key = (el: Element, k: string) =>
  act(() => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }))
  })

function type(text: string) {
  //: React مقدار را از setterِ بومی می‌خواند؛ نوشتنِ مستقیمِ `value` رویدادی نمی‌سازد.
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
  act(() => {
    set.call(filter(), text)
    filter().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('همه‌ی گزارش‌ها', () => {
  it('حسابدار با دفتر و تراز شروع می‌کند؛ گزارشِ بازِ صفحه نشان‌دار است', () => {
    render()
    expect(headings()[0]).toBe('دفاتر و ترازها')
    const on = items().filter((b) => b.getAttribute('aria-current') === 'page')
    expect(on.map((b) => b.textContent)).toEqual(['سود و زیان']) // بی‌بخش = پیش‌فرض
  })

  it('بخشِ ناوبری نشان را جابه‌جا می‌کند', () => {
    render('balance-sheet')
    expect(container.querySelector('[aria-current="page"]')?.textContent).toBe('ترازنامه')
  })

  it('**عوض‌کردنِ حالت، دسته‌ها را همان لحظه دوباره می‌چیند**', () => {
    render()
    const before = headings()
    act(() => setExperience('simple'))
    expect(headings()[0]).toBe('صورت‌های مالی')
    expect([...headings()].sort()).toEqual([...before].sort())
  })

  it('کلیک، صفحه و بخش را باز می‌کند', () => {
    render()
    act(() => items().find((b) => b.textContent === 'ترازنامه')!.click())
    expect(onNavigate).toHaveBeenCalledWith('reports', 'balance-sheet')
    act(() => items().find((b) => b.textContent === 'گزارش ترازها')!.click())
    expect(onNavigate).toHaveBeenLastCalledWith('balancereport', undefined)
  })

  it('تایپ صافی می‌کند و Enter اولین نتیجه را باز می‌کند', () => {
    render()
    type('کاردکس')
    expect(items().map((b) => b.textContent)).toEqual(['کاردکس کالا'])
    key(filter(), 'Enter')
    expect(onNavigate).toHaveBeenCalledWith('reports', 'kardex')
  })

  it('بی‌نتیجه → پیامی که می‌گوید چه کند', () => {
    render()
    type('چیزی که نیست')
    expect(items()).toHaveLength(0)
    expect(container.querySelector('.rc-empty')?.textContent).toContain('واژه‌ی کوتاه‌تری')
  })

  it('پیکان‌ها: از کادر به فهرست، بینِ ردیف‌ها، و برگشت به کادر', () => {
    render()
    filter().focus()
    key(filter(), 'ArrowDown')
    expect(document.activeElement).toBe(items()[0])
    key(items()[0], 'ArrowDown')
    expect(document.activeElement).toBe(items()[1])
    key(items()[1], 'End')
    expect(document.activeElement).toBe(items().at(-1))
    key(items().at(-1)!, 'Home')
    expect(document.activeElement).toBe(items()[0])
    key(items()[0], 'ArrowUp')
    expect(document.activeElement).toBe(filter())
  })
})
