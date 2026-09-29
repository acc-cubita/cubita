// @vitest-environment jsdom
/**
 * جابه‌جاییِ منوهای کارت‌های «عملیات» و «فهرست» — فلشِ بالا/پایین روی هر ردیف و Alt+↑/↓.
 *
 * * ترتیب روی دستگاه می‌ماند (بعد از سوارشدنِ دوباره هم).
 * * منو یک فهرست است (بی تیترِ «عملیات»/«فهرست»)؛ درونِ هر دسته اول کارها، بعد دفترها، و جابه‌جاییِ یک
 *   کار از مرزِ دفترها رد نمی‌شود.
 * * با صفحه‌کلید، فوکوس روی همان منو می‌ماند.
 * * «ترتیبِ پیش‌فرض» فقط وقتی ترتیب عوض شده پیدا می‌شود و برش می‌گرداند.
 * * دسته‌ها آکاردئون‌اند: پیش‌فرض همه بسته، و باز کردنِ یکی بقیه را می‌بندد — پس هر تست دسته‌ای را که
 *   لازم دارد اول باز می‌کند (`openCat`).
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ModulePanels } from './ModulePanels'
import { resetOpenCategories } from '../lib/menuAccordion'
import { NAV_GROUPS, type PageKey } from '../lib/navModel'

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  resetOpenCategories()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const noop = () => {}
function render(page: PageKey = 'journalentry') {
  act(() =>
    root.render(
      createElement(ModulePanels, {
        page,
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
const head = (title: string) =>
  [...panels()[0].querySelectorAll<HTMLButtonElement>('.mod-section-label')].find(
    (b) => b.querySelector('.mod-section-title')?.textContent === title,
  )!
const openCat = (title: string) => act(() => head(title).click())

describe('جابه‌جاییِ منوهای عملیات و فهرست', () => {
  it('فلشِ پایین منو را یک خانه پایین می‌برد و ترتیب بعد از سوارشدنِ دوباره می‌ماند', () => {
    render()
    openCat('ثبت سند')
    const [ops] = panels()
    const before = labels(ops)
    expect(before.length).toBeGreaterThan(2)
    //: اولی بالا نمی‌رود، آخرین کار پایین نمی‌رود.
    expect(arrow(ops, before[0]!, 'بالا').disabled).toBe(true)
    expect(arrow(ops, 'اسناد تکرارشونده', 'پایین').disabled).toBe(true)

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
    openCat('ثبت سند')
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
    openCat('ثبت سند')
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
    openCat('ثبت سند')
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
    //: تیترِ «ثبت سند» (باز) درست پیش از «سند حسابداری» است.
    openCat('ثبت سند')
    const first = panels()[0].querySelector('.mod-section-label')!
    expect(first.nextElementSibling?.textContent).toContain('سند حسابداری')
  })

  it('جابه‌جایی فقط درونِ دسته: منوی اولِ دسته بالا نمی‌رود و آخرش پایین', () => {
    render()
    openCat('ثبت سند')
    const [ops] = panels()
    expect(arrow(ops, 'سند حسابداری', 'بالا').disabled).toBe(true)
    expect(arrow(ops, 'اسناد تکرارشونده', 'پایین').disabled).toBe(true)
    act(() => arrow(ops, 'مانده اول دوره', 'بالا').click())
    const after = labels(panels()[0])
    expect(after.indexOf('مانده اول دوره')).toBeLessThan(after.indexOf('سند حسابداری'))
    //: دسته‌ی بعدی سرِ جایش است.
    openCat('بازبینی اسناد')
    expect(labels(panels()[0])[0]).toBe('کارتابل اسناد موقت')
  })
})

describe('دسته‌ی بازوبسته — آکاردئون، پیش‌فرض همه بسته (۱۴۰۵/۰۷/۰۶)', () => {
  const expanded = (title: string) => head(title).getAttribute('aria-expanded')

  it('پیش‌فرض همه‌ی دسته‌ها بسته‌اند و هر کدام تعدادِ ردیف‌هایش را می‌گوید', () => {
    render()
    const all = [...panels()[0].querySelectorAll('.mod-section-label')]
    expect(all.length).toBeGreaterThan(1)
    expect(all.every((h) => h.getAttribute('aria-expanded') === 'false')).toBe(true)
    expect(labels(panels()[0])).toEqual([])
    //: «ساختار و تعریف‌ها»: شش کار و دفترِ «مراکز هزینه».
    expect(head('ساختار و تعریف‌ها').querySelector('.mod-section-count')?.textContent).toBe((7).toLocaleString('fa-IR'))
  })

  it('باز کردنِ یک دسته دسته‌ی بازِ قبلی را می‌بندد؛ ضربه‌ی دوباره خودش را می‌بندد', () => {
    render()
    openCat('ثبت سند')
    expect(labels(panels()[0])).toContain('سند حسابداری')
    openCat('پایان دوره')
    expect(expanded('ثبت سند')).toBe('false')
    expect(expanded('پایان دوره')).toBe('true')
    expect(labels(panels()[0])).not.toContain('سند حسابداری')
    expect(labels(panels()[0])).toContain('عملیات پایان سال')
    openCat('پایان دوره')
    expect(labels(panels()[0])).toEqual([])
  })

  it('دسته‌ی باز با رفتن به صفحه‌ی دیگر و سوارشدنِ دوباره می‌ماند، ولی ترجیحِ دائمی ذخیره نمی‌شود', () => {
    render()
    openCat('ساختار و تعریف‌ها')
    render('acctchart')
    expect(expanded('ساختار و تعریف‌ها')).toBe('true')
    remount()
    expect(labels(panels()[0])).toContain('درختواره حساب‌ها')
    expect(localStorage.getItem('cubita.modulePanels.categories')).toBeNull()
    //: اجرای تازه‌ی برنامه = همه بسته.
    resetOpenCategories()
    remount()
    expect(expanded('ساختار و تعریف‌ها')).toBe('false')
  })

  it('هر ماژول دسته‌ی بازِ خودش را دارد', () => {
    render()
    openCat('ثبت سند')
    render('salesinvoice')
    expect([...panels()[0].querySelectorAll('.mod-section-label')].every((h) => h.getAttribute('aria-expanded') === 'false')).toBe(true)
    render('journalentry')
    expect(expanded('ثبت سند')).toBe('true')
  })

  it('دسته‌ی بسته‌ای که صفحه‌ی فعال در آن است نشان می‌گیرد — پیش‌فرض و بعد از بستن', () => {
    render('acctchart')
    expect(expanded('ساختار و تعریف‌ها')).toBe('false')
    expect(head('ساختار و تعریف‌ها').classList.contains('has-current')).toBe(true)
    expect(head('ثبت سند').classList.contains('has-current')).toBe(false)
    openCat('ساختار و تعریف‌ها')
    expect(head('ساختار و تعریف‌ها').classList.contains('has-current')).toBe(false)
    openCat('ساختار و تعریف‌ها')
    expect(head('ساختار و تعریف‌ها').classList.contains('has-current')).toBe(true)
  })
})

describe('«مسیرِ کار»', () => {
  it('پیوندِ کم‌رنگِ بالای کارت است، نه یکی از ردیف‌های جابه‌جاشدنی', () => {
    render('salesinvoice')
    const [ops] = panels()
    const guide = ops.querySelector('.mod-guide')
    expect(guide?.textContent).toBe('فرآیند فروش')
    expect(ops.querySelector('.mod-panel-body')?.firstElementChild).toBe(guide)
    expect(labels(ops)).not.toContain('فرآیند فروش')
  })
})
