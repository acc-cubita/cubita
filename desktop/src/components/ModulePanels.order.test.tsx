// @vitest-environment jsdom
/**
 * جابه‌جاییِ منوهای کارت‌های «عملیات» و «فهرست» — فلشِ بالا/پایین روی هر ردیف و Alt+↑/↓.
 *
 * * ترتیب روی دستگاه می‌ماند (بعد از سوارشدنِ دوباره هم).
 * * منو یک فهرست است (بی تیترِ «عملیات»/«فهرست»)؛ درونِ هر دسته اول کارها، بعد دفترها، و جابه‌جاییِ یک
 *   کار از مرزِ دفترها رد نمی‌شود.
 * * با صفحه‌کلید، فوکوس روی همان منو می‌ماند.
 * * «ترتیبِ پیش‌فرض» فقط وقتی ترتیب عوض شده پیدا می‌شود و برش می‌گرداند.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ModulePanels } from './ModulePanels'
import { NAV_GROUPS } from '../lib/navModel'

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

const noop = () => {}
function render() {
  act(() =>
    root.render(
      createElement(ModulePanels, {
        page: 'journalentry',
        section: null,
        onSelectSection: noop,
        onNavigate: noop,
        groups: NAV_GROUPS,
        token: 't',
      }),
    ),
  )
}
function remount() {
  act(() => root.unmount())
  root = createRoot(container)
  render()
}

const panels = () => [...container.querySelectorAll<HTMLElement>('.mod-panel')]
const labels = (panel: HTMLElement) => [...panel.querySelectorAll('.mod-op > span')].map((s) => s.textContent)
const arrow = (panel: HTMLElement, label: string, dir: 'بالا' | 'پایین') =>
  panel.querySelector<HTMLButtonElement>(`[aria-label="${dir} بردنِ «${label}»"]`)!

describe('جابه‌جاییِ منوهای عملیات و فهرست', () => {
  it('فلشِ پایین منو را یک خانه پایین می‌برد و ترتیب بعد از سوارشدنِ دوباره می‌ماند', () => {
    render()
    const [ops] = panels()
    const before = labels(ops)
    expect(before.length).toBeGreaterThan(2)
    //: اولی بالا نمی‌رود، آخری پایین نمی‌رود.
    expect(arrow(ops, before[0]!, 'بالا').disabled).toBe(true)
    expect(arrow(ops, before[before.length - 1]!, 'پایین').disabled).toBe(true)

    act(() => arrow(ops, before[0]!, 'پایین').click())
    expect(labels(panels()[0]).slice(0, 2)).toEqual([before[1], before[0]])

    remount()
    expect(labels(panels()[0]).slice(0, 2)).toEqual([before[1], before[0]])
  })

  it('یک منو، بی تیترِ «عملیات»/«فهرست»؛ دفتر ته دسته‌ی کارش و جابه‌جاییِ کار به آن نمی‌رسد', () => {
    render()
    expect(panels()).toHaveLength(1)
    expect(container.querySelector('.mod-panel-head')).toBeNull()
    expect(container.textContent).not.toMatch(/^عملیات|فهرست$/)
    const [menu] = panels()
    //: «ثبت سند»: سه کار، بعد دفترش.
    expect(labels(menu).slice(0, 4)).toEqual(['سند حسابداری', 'مانده اول دوره', 'اسناد تکرارشونده', 'اسناد حسابداری'])
    //: آخرین کار پایین نمی‌رود (دفتر دامنه‌ی خودش را دارد) و تنها دفترِ دسته جابه‌جا نمی‌شود.
    expect(arrow(menu, 'اسناد تکرارشونده', 'پایین').disabled).toBe(true)
    expect(menu.querySelector(`[aria-label="بالا بردنِ «اسناد حسابداری»"]`)).toBeNull()
    act(() => arrow(menu, 'مانده اول دوره', 'بالا').click())
    expect(labels(panels()[0]).slice(0, 4)).toEqual(['مانده اول دوره', 'سند حسابداری', 'اسناد تکرارشونده', 'اسناد حسابداری'])
  })

  it('Alt+↑/↓ روی خودِ منو، و فوکوس روی همان منو می‌ماند', async () => {
    render()
    const opsBefore = labels(panels()[0])
    const second = [...panels()[0].querySelectorAll<HTMLButtonElement>('.mod-op')][1]
    act(() => second.focus())
    await act(async () => {
      second.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', altKey: true, bubbles: true, cancelable: true }))
      await new Promise((r) => requestAnimationFrame(() => r(null)))
    })
    expect(labels(panels()[0]).slice(0, 2)).toEqual([opsBefore[1], opsBefore[0]])
    expect(document.activeElement?.textContent).toBe(opsBefore[1])
  })

  it('«ترتیبِ پیش‌فرض» فقط بعد از تغییر پیدا می‌شود و برمی‌گرداند', () => {
    render()
    const reset = () => panels()[0].querySelector<HTMLButtonElement>('.mod-order-reset')
    const before = labels(panels()[0])
    expect(reset()).toBeNull()
    act(() => arrow(panels()[0], before[0]!, 'پایین').click())
    expect(labels(panels()[0])).not.toEqual(before)
    act(() => reset()!.click())
    expect(labels(panels()[0])).toEqual(before)
    expect(reset()).toBeNull()
  })
})

describe('دسته‌های منوی عملیات', () => {
  const heads = (panel: HTMLElement) => [...panel.querySelectorAll('.mod-section-label .mod-section-title')].map((e) => e.textContent)

  it('حسابداری: کارِ هرروزه اول، ساختار ته — هر تیتر بالای منوهای خودش (۱۴۰۵/۰۷/۰۶)', () => {
    render()
    const [ops] = panels()
    expect(heads(ops)).toEqual(['ثبت سند', 'بازبینی اسناد', 'گزارش و کنترل', 'اصلاح و تعدیل', 'پایان دوره', 'ساختار و تعریف‌ها'])
    //: تیترِ «ثبت سند» درست پیش از «سند حسابداری» است.
    const head = ops.querySelector('.mod-section-label')!
    expect(head.nextElementSibling?.textContent).toContain('سند حسابداری')
  })

  it('جابه‌جایی فقط درونِ دسته: منوی اولِ دسته بالا نمی‌رود و آخرش پایین', () => {
    render()
    const [ops] = panels()
    expect(arrow(ops, 'سند حسابداری', 'بالا').disabled).toBe(true)
    expect(arrow(ops, 'اسناد تکرارشونده', 'پایین').disabled).toBe(true)
    act(() => arrow(ops, 'مانده اول دوره', 'بالا').click())
    const after = labels(panels()[0])
    expect(after.indexOf('مانده اول دوره')).toBeLessThan(after.indexOf('سند حسابداری'))
    //: دسته‌ی بعدی سرِ جایش است.
    expect(after.indexOf('کارتابل اسناد موقت')).toBeGreaterThan(after.indexOf('اسناد تکرارشونده'))
  })
})

describe('دسته‌ی بازوبسته', () => {
  const head = (panel: HTMLElement, title: string) =>
    [...panel.querySelectorAll<HTMLButtonElement>('.mod-section-label')].find((b) => b.querySelector('.mod-section-title')?.textContent === title)!

  it('«ساختار و تعریف‌ها» پیش‌فرض بسته است و تعدادِ ردیف‌هایش را می‌گوید — شش کار و دفترِ «مراکز هزینه»', () => {
    render()
    const [ops] = panels()
    const h = head(ops, 'ساختار و تعریف‌ها')
    expect(h.getAttribute('aria-expanded')).toBe('false')
    expect(h.querySelector('.mod-section-count')?.textContent).toBe((7).toLocaleString('fa-IR'))
    expect(labels(ops)).not.toContain('درختواره حساب‌ها')
  })

  it('«پایان دوره» هم پیش‌فرض بسته است — کارِ سالانه، نه روزانه', () => {
    render()
    expect(head(panels()[0], 'پایان دوره').getAttribute('aria-expanded')).toBe('false')
    expect(labels(panels()[0])).not.toContain('عملیات پایان سال')
  })

  it('باز کردن می‌ماند — بعد از سوارشدنِ دوباره هم', () => {
    render()
    act(() => head(panels()[0], 'ساختار و تعریف‌ها').click())
    expect(labels(panels()[0])).toContain('درختواره حساب‌ها')
    remount()
    expect(labels(panels()[0])).toContain('درختواره حساب‌ها')
  })

  it('صفحه‌ی فعال زیرِ دسته‌ی پیش‌فرض‌بسته گم نمی‌شود', () => {
    act(() =>
      root.render(
        createElement(ModulePanels, {
          page: 'acctchart',
          section: null,
          onSelectSection: noop,
          onNavigate: noop,
          groups: NAV_GROUPS,
          token: 't',
        }),
      ),
    )
    const [ops] = panels()
    expect(head(ops, 'ساختار و تعریف‌ها').getAttribute('aria-expanded')).toBe('true')
    expect(labels(ops)).toContain('درختواره حساب‌ها')
  })

  it('دسته‌ای که کاربر بسته و صفحه‌ی فعال در آن است نشان می‌گیرد', () => {
    render()
    act(() => head(panels()[0], 'ثبت سند').click())
    const h = head(panels()[0], 'ثبت سند')
    expect(h.getAttribute('aria-expanded')).toBe('false')
    expect(h.classList.contains('has-current')).toBe(true)
  })
})

describe('«مسیرِ کار»', () => {
  it('پیوندِ کم‌رنگِ بالای کارت است، نه یکی از ردیف‌های جابه‌جاشدنی', () => {
    act(() =>
      root.render(
        createElement(ModulePanels, {
          page: 'salesinvoice',
          section: null,
          onSelectSection: noop,
          onNavigate: noop,
          groups: NAV_GROUPS,
          token: 't',
        }),
      ),
    )
    const [ops] = panels()
    const guide = ops.querySelector('.mod-guide')
    expect(guide?.textContent).toBe('فرآیند فروش')
    expect(ops.querySelector('.mod-panel-body')?.firstElementChild).toBe(guide)
    expect(labels(ops)).not.toContain('فرآیند فروش')
  })
})
