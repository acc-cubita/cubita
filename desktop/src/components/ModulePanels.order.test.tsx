// @vitest-environment jsdom
/**
 * جابه‌جاییِ منوهای کارت‌های «عملیات» و «فهرست» — فلشِ بالا/پایین روی هر ردیف و Alt+↑/↓.
 *
 * * ترتیب روی دستگاه می‌ماند (بعد از سوارشدنِ دوباره هم).
 * * هر کارت فهرستِ خودش است: جابه‌جایی در «عملیات» به «فهرست» دست نمی‌زند.
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

  it('هر کارت فهرستِ خودش: جابه‌جایی در عملیات به فهرست دست نمی‌زند', () => {
    render()
    const listBefore = labels(panels()[1])
    const opsBefore = labels(panels()[0])
    act(() => arrow(panels()[0], opsBefore[1]!, 'بالا').click())
    expect(labels(panels()[1])).toEqual(listBefore)
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
    const reset = () => panels()[1].querySelector<HTMLButtonElement>('.mod-order-reset')
    const listBefore = labels(panels()[1])
    expect(reset()).toBeNull()
    act(() => arrow(panels()[1], listBefore[0]!, 'پایین').click())
    expect(labels(panels()[1])).not.toEqual(listBefore)
    act(() => reset()!.click())
    expect(labels(panels()[1])).toEqual(listBefore)
    expect(reset()).toBeNull()
  })
})

describe('دسته‌های منوی عملیات', () => {
  it('حسابداری: تیترِ شش دسته به ترتیبِ کار، هرکدام بالای منوهای خودش', () => {
    render()
    const [ops] = panels()
    const heads = [...ops.querySelectorAll('.mod-section-label')].map((e) => e.textContent)
    expect(heads).toEqual(['ساختار و تعریف‌ها', 'ثبت سند', 'بازبینی اسناد', 'اصلاح و تعدیل', 'پایان دوره', 'گزارش و کنترل'])
    //: تیترِ «ثبت سند» درست پیش از «سند حسابداری» است.
    const head = [...ops.querySelectorAll('.mod-section-label')][1]
    expect(head.nextElementSibling?.textContent).toContain('سند حسابداری')
  })

  it('جابه‌جایی فقط درونِ دسته: منوی اولِ دسته بالا نمی‌رود و آخرش پایین', () => {
    render()
    const [ops] = panels()
    expect(arrow(ops, 'سند حسابداری', 'بالا').disabled).toBe(true)
    expect(arrow(ops, 'بودجه‌بندی', 'پایین').disabled).toBe(true)
    act(() => arrow(ops, 'مانده اول دوره', 'بالا').click())
    const after = labels(panels()[0])
    expect(after.indexOf('مانده اول دوره')).toBeLessThan(after.indexOf('سند حسابداری'))
    //: دسته‌ی قبلی سرِ جایش است.
    expect(after.indexOf('بودجه‌بندی')).toBeLessThan(after.indexOf('مانده اول دوره'))
  })
})
