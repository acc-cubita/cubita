// @vitest-environment jsdom
/**
 * داشبورد با حالتِ تجربه عوض می‌شود — در DOMِ واقعی، نه فقط در `resolveCards`.
 *
 * `launchers.test.ts` منطقِ انتخابِ کارت را می‌سنجد؛ آنچه آن‌جا دیده نمی‌شود این است
 * که **با عوض‌کردنِ حالت، کارت‌های روی صفحه همان لحظه عوض شوند**. آن به اشتراکِ
 * `useSyncExternalStore`ِ `experienceMode.ts` بسته است: اگر `useDashboardCards`
 * حالت را یک‌بار بخواند و مشترک نشود، کاربر حالت را عوض می‌کند و داشبورد تا رفرش
 * همان می‌ماند — بی هیچ خطایی.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LauncherBoard } from './LauncherBoard'
import { __resetExperienceForTests, setExperience } from '../lib/experienceMode'
import type { MeResponse } from '../api'

const baseMe = {
  id: 'u1',
  name: 'آزمون',
  email: 'a@b.c',
  phone: null,
  phone_verified: false,
  email_verified: true,
  role_key: 'owner',
  role_name: 'مالک',
  permissions: {},
  tenant_id: 't1',
  tenant_name: 'نمونه',
  tenant_kind: 'standard',
  is_trial: false,
  trial_days_left: null,
  trial_expired: false,
  locked_features: [],
  dashboard_cards: null,
  industry: 'general',
  trade: null,
  //: خالی یعنی «فیلتر نکن» — همان کاتالوگِ کاملی که `launchers.test.ts` می‌سازد.
  enabled_modules: [],
  allowed_modules: [],
} as unknown as MeResponse

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  __resetExperienceForTests() // پیش‌فرض: حسابدار
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

function render(me: MeResponse) {
  act(() => {
    root.render(
      createElement(LauncherBoard, {
        token: 't',
        me,
        onMeUpdated: vi.fn(),
        onNavigate: vi.fn(),
      }),
    )
  })
}

const titles = () =>
  [...container.querySelectorAll('.action-card-title')].map((el) => el.textContent ?? '')

describe('داشبوردِ هر حالت', () => {
  it('حسابدار: کارت‌های §۵۳ — سند و دفتر و تراز', () => {
    render(baseMe)
    expect(titles()).toHaveLength(8)
    expect(titles()).toContain('سند حسابداری')
    expect(titles()).toContain('گزارش ترازها')
  })

  it('**عوض‌کردنِ حالت، کارت‌ها را همان لحظه عوض می‌کند** — بی رفرش', () => {
    render(baseMe)
    const before = titles()

    act(() => setExperience('simple'))

    const after = titles()
    expect(after).toHaveLength(7)
    expect(after).toContain('فاکتور فروش')
    expect(after).not.toContain('سند حسابداری')
    expect(after).not.toEqual(before)
  })

  it('کسی که کارت‌هایش را خودش چیده، با عوض‌کردنِ حالت چیزی از دست نمی‌دهد', () => {
    render({ ...baseMe, dashboard_cards: ['quotations', 'salesinvoice'] })
    const mine = titles()
    expect(mine).toHaveLength(2)

    act(() => setExperience('simple'))

    expect(titles()).toEqual(mine)
  })
})
