// @vitest-environment jsdom
/**
 * کشوی موبایل آکاردئون است و **پیش‌فرض همه بسته** (۱۴۰۵/۰۷/۰۶، خواستِ آرش): هر بار که باز می‌شود هیچ گروهی باز
 * نیست، باز کردنِ یک گروه گروهِ بازِ قبلی را می‌بندد، و گروهِ صفحه‌ی فعال فقط نقطه می‌گیرد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TopNav } from './TopNav'
import { __resetExperienceForTests } from '../lib/experienceMode'

class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  ;(globalThis as Record<string, unknown>).ResizeObserver = NoopResizeObserver
  __resetExperienceForTests()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root.render(
      createElement(TopNav, {
        active: 'journalentry',
        onNavigate: vi.fn(),
        userName: 'آزمون',
        roleName: 'مالک',
        businessName: 'نمونه',
        tenantKind: 'standard',
        enabledModules: [],
        allowedModules: [],
        onOpenSearch: vi.fn(),
        onLogout: vi.fn(),
      }),
    )
  })
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const openDrawer = () => act(() => container.querySelector<HTMLButtonElement>('.topnav-hamburger')!.click())
const closeDrawer = () => act(() => container.querySelector<HTMLButtonElement>('.topnav-mobile-close')!.click())
const openGroups = () =>
  [...container.querySelectorAll('.topnav-mobile-group.open > .mob-row--group .mob-row-label')].map((e) => e.textContent)
const groupRow = (label: string) =>
  [...container.querySelectorAll<HTMLButtonElement>('.mob-row--group')].find(
    (b) => b.querySelector('.mob-row-label')?.textContent === label,
  )!

describe('کشوی موبایل — آکاردئون، پیش‌فرض همه بسته', () => {
  it('با باز شدن هیچ گروهی باز نیست؛ گروهِ صفحه‌ی فعال فقط نقطه دارد', () => {
    openDrawer()
    expect(openGroups()).toEqual([])
    expect(groupRow('حسابداری').querySelector('.mob-dot')).not.toBeNull()
    expect(groupRow('دریافت و پرداخت').querySelector('.mob-dot')).toBeNull()
  })

  it('باز کردنِ یک گروه گروهِ بازِ قبلی را می‌بندد؛ ضربه‌ی دوباره خودش را می‌بندد', () => {
    openDrawer()
    act(() => groupRow('حسابداری').click())
    expect(openGroups()).toEqual(['حسابداری'])
    act(() => groupRow('دریافت و پرداخت').click())
    expect(openGroups()).toEqual(['دریافت و پرداخت'])
    act(() => groupRow('دریافت و پرداخت').click())
    expect(openGroups()).toEqual([])
  })

  it('بستن و باز کردنِ دوباره‌ی کشو دوباره همه را بسته نشان می‌دهد', () => {
    openDrawer()
    act(() => groupRow('حسابداری').click())
    closeDrawer()
    openDrawer()
    expect(openGroups()).toEqual([])
  })
})
