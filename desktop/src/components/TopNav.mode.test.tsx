// @vitest-environment jsdom
/**
 * منوی بالا با حالتِ تجربه عوض می‌شود — در DOMِ واقعی، نه فقط در `orderNavGroups`.
 *
 * `navModel.test.ts` ترتیب را می‌سنجد؛ آنچه آن‌جا دیده نمی‌شود این است که **نوار
 * همان لحظه‌ی عوض‌شدنِ حالت** دوباره چیده شود، و کلیک روی «حسابداری» واقعاً به سند
 * برود. اولی به اشتراکِ `useSyncExternalStore` بسته است: اگر `TopNav` حالت را یک‌بار
 * بخواند، کاربر حالت را عوض می‌کند و منو تا رفرش همان می‌ماند — بی هیچ خطایی.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TopNav } from './TopNav'
import { __resetExperienceForTests, setExperience } from '../lib/experienceMode'
import type { PageKey } from '../lib/navModel'

//: jsdom `ResizeObserver` ندارد؛ سنجشِ جاشدنِ نوار این‌جا موضوعِ تست نیست.
class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

let container: HTMLDivElement
let root: Root
let onNavigate: ReturnType<typeof vi.fn<(page: PageKey, section?: string) => void>>

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  ;(globalThis as Record<string, unknown>).ResizeObserver = NoopResizeObserver
  __resetExperienceForTests() // پیش‌فرض: حسابدار
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  onNavigate = vi.fn<(page: PageKey, section?: string) => void>()
  act(() => {
    root.render(
      createElement(TopNav, {
        active: 'overview',
        onNavigate,
        userName: 'آزمون',
        roleName: 'مالک',
        businessName: 'نمونه',
        tenantKind: 'standard',
        //: خالی یعنی «فیلتر نکن» — همه‌ی گروه‌ها.
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

const bar = () =>
  [...container.querySelectorAll<HTMLButtonElement>('.topnav-menu .topnav-item')].map((b) => b.textContent ?? '')

const click = (label: string) => {
  const btn = [...container.querySelectorAll<HTMLButtonElement>('.topnav-menu .topnav-item')].find(
    (b) => b.textContent === label,
  )
  expect(btn, label).toBeDefined()
  act(() => btn!.click())
}

describe('منوی بالا در هر حالت', () => {
  it('حسابدار: حسابداری و دریافت و پرداخت بلافاصله بعد از داشبورد', () => {
    expect(bar().slice(0, 3)).toEqual(['داشبورد', 'حسابداری', 'دریافت و پرداخت'])
  })

  it('**عوض‌کردنِ حالت، نوار را همان لحظه دوباره می‌چیند** — بی رفرش', () => {
    const before = bar()
    act(() => setExperience('simple'))
    const after = bar()

    expect(after[1]).toBe('مشتریان و فروش')
    expect(after).not.toEqual(before)
    //: فقط ترتیب عوض شد، نه محتوا.
    expect([...after].sort()).toEqual([...before].sort())
  })

  it('کلیک روی «حسابداری» در حالتِ حسابدار سند را باز می‌کند', () => {
    click('حسابداری')
    expect(onNavigate).toHaveBeenCalledWith('journalentry', undefined)
  })

  it('در حالتِ ساده همان پیش‌فرضِ قبلی — اولین صفحه‌ی گروه', () => {
    act(() => setExperience('simple'))
    click('حسابداری')
    expect(onNavigate).toHaveBeenCalledWith('acctchart', undefined)
  })
})

describe('سوییچِ سریعِ حالت در منوی کاربر (§۷)', () => {
  const radios = () => [...container.querySelectorAll<HTMLButtonElement>('[role="radio"]')]

  function renderWithToken(fetchMock: ReturnType<typeof vi.fn>) {
    vi.stubGlobal('fetch', fetchMock)
    act(() => {
      root.render(
        createElement(TopNav, {
          active: 'overview',
          onNavigate,
          userName: 'آزمون',
          roleName: 'مالک',
          businessName: 'نمونه',
          token: 't',
          tenantKind: 'standard',
          enabledModules: [],
          allowedModules: [],
          onOpenSearch: vi.fn(),
          onLogout: vi.fn(),
        }),
      )
    })
  }

  afterEach(() => vi.unstubAllGlobals())

  it('از منوی کاربر: همان لحظه عوض می‌شود و **همان ترجیحِ پروفایل** به سرور می‌رود', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }))
    renderWithToken(fetchMock)
    act(() => container.querySelector<HTMLButtonElement>('.topnav-user')!.click())

    const [simple, accountant] = radios()
    expect(simple.textContent).toBe('حالت ساده')
    expect(accountant.getAttribute('aria-checked')).toBe('true')

    await act(async () => simple.click())
    expect(simple.getAttribute('aria-checked')).toBe('true')
    expect(bar()[1]).toBe('مشتریان و فروش') // نوار همان لحظه دوباره چیده شد
    //: منو باز می‌ماند تا نتیجه دیده شود.
    expect(container.querySelector('.topnav-user-panel')).not.toBeNull()

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toMatch(/\/api\/auth\/me$/)
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(String(init.body))).toEqual({ experience_mode: 'simple' })
  })

  it('در کشوی موبایل هم هست — گزینه‌ی radio، نه «صفحه‌ی فعال»', () => {
    renderWithToken(vi.fn(async () => new Response('{}', { status: 200 })))
    act(() => container.querySelector<HTMLButtonElement>('.topnav-hamburger')!.click())
    const rows = radios().filter((r) => r.classList.contains('mob-row'))
    expect(rows.map((r) => r.textContent)).toEqual(['حالت ساده', 'حالت حسابدار'])
    expect(rows[1].getAttribute('aria-checked')).toBe('true')
    expect(rows[1].hasAttribute('aria-current')).toBe(false)
  })
})
