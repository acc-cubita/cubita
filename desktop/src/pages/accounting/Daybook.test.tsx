// @vitest-environment jsdom
/**
 * دفتر روزنامه — صفحه‌بندی و جمع از سرور، فیلترهای مشترک، برچسبِ درستِ جست‌وجو.
 *
 * چهار ایرادِ پیشین، هرکدام یک تست:
 *
 * 1. تا ۲۰۰ سند می‌گرفت و بقیه را **بی‌صدا** نمی‌آورد.
 * 2. «جمعِ گردشِ بازه» جمعِ همان سندهای بارگذاری‌شده بود، نه کلِ بازه.
 * 3. نوارِ فیلتر (وضعیت، مرکز هزینه، شماره‌ی سند، …) اصلاً به روزنامه نمی‌رسید.
 * 4. جست‌وجو برچسبِ «نام یا کدِ حساب» داشت ولی سرور روی شماره و شرحِ سند می‌گردد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LedgerReportPage } from './ReportPages'

let container: HTMLDivElement
let root: Root
let fetchMock: ReturnType<typeof vi.fn>

const entry = (id: string, number: number, amount: number) => ({
  id,
  number,
  atf_number: number,
  sub_number: null,
  entry_date: '2026-09-01',
  description: `سندِ ${number}`,
  source_type: 'manual',
  source: null,
  status: 'temporary',
  finalized_at: null,
  voided_at: null,
  reverses_entry_id: null,
  lines: [
    { id: `${id}-d`, account_id: 'a1', debit: String(amount), credit: '0', description: '' },
    { id: `${id}-c`, account_id: 'a2', debit: '0', credit: String(amount), description: '' },
  ],
})

//: جمعِ سرور عمداً با جمعِ ردیف‌های بارگذاری‌شده فرق دارد: اگر صفحه جمع را خودش
//: می‌ساخت، ۳۰۰ می‌دید، نه ۹۹۹٬۰۰۰.
const SUMMARY = { entry_count: 3, line_count: 6, total_debit: '999000.000', total_credit: '999000.000' }
const FIRST = { items: [entry('e1', 1, 100), entry('e2', 2, 200)], next_cursor: 'c1' }
const SECOND = { items: [entry('e3', 3, 300)], next_cursor: null }

type Routes = { summary?: () => Response; page?: (url: URL) => Response }

function stub(routes: Routes = {}) {
  fetchMock = vi.fn(async (input: string) => {
    const url = new URL(input, 'http://x')
    if (url.pathname === '/api/journal-entries/summary') {
      return routes.summary ? routes.summary() : new Response(JSON.stringify(SUMMARY), { status: 200 })
    }
    if (url.pathname === '/api/journal-entries') {
      if (routes.page) return routes.page(url)
      const body = url.searchParams.get('cursor') === 'c1' ? SECOND : FIRST
      return new Response(JSON.stringify(body), { status: 200 })
    }
    if (url.pathname === '/api/cost-centers') {
      return new Response(JSON.stringify([{ id: 'cc1', name: 'مرکزِ تهران', code: 'T1' }]), { status: 200 })
    }
    return new Response('[]', { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function render() {
  await act(async () => {
    root.render(createElement(LedgerReportPage, { token: 't' }))
  })
}

const calls = (path: string) =>
  fetchMock.mock.calls
    .map((c) => new URL(String(c[0]), 'http://x'))
    .filter((u) => u.pathname === path)

const text = () => container.textContent ?? ''
/** خانه‌ی جمعِ پانویسِ گریدِ روزنامه — «جمعِ بازه» از سرور. */
const footCell = (label: string) => container.querySelector(`.lr-daybook tfoot td[data-label="${label}"]`)?.textContent ?? ''
const footLabel = () => container.querySelector('.lr-daybook tfoot .card-title')?.textContent ?? ''
const moreButton = () =>
  [...container.querySelectorAll('button')].find((b) => b.textContent?.includes('سندِ بعدی'))

function fieldByLabel(label: string): HTMLInputElement {
  //: خانه‌های سربرگِ اکسلی: «از/تا شماره سند» یک خانه است و هر کادر نامش را در `aria-label` دارد.
  const host = [...container.querySelectorAll('label')].find((l) => l.textContent?.includes(label))
  const input = container.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`) ?? host?.querySelector('input')
  if (!input) throw new Error(`فیلدِ «${label}» پیدا نشد`)
  return input
}

async function type(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  await act(async () => {
    setter?.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('دفتر روزنامه', () => {
  it('جمع از سرور می‌آید، نه از سندهای بارگذاری‌شده', async () => {
    stub()
    await render()
    expect(footCell('جمعِ بدهکار')).toBe((999000).toLocaleString('fa-IR'))
    expect(footCell('جمعِ بستانکار')).toBe((999000).toLocaleString('fa-IR'))
    expect(footLabel()).toContain(`همه‌ی ${(3).toLocaleString('fa-IR')} سند`)
    expect(footLabel()).toContain('تراز است')
    expect(text()).toContain(`نمایشِ ${(2).toLocaleString('fa-IR')} از ${(3).toLocaleString('fa-IR')} سند`)
  })

  it('صفحه‌ی بعد با کرسرِ سرور می‌آید و به همان فهرست اضافه می‌شود', async () => {
    stub()
    await render()
    const first = calls('/api/journal-entries')
    expect(first).toHaveLength(1)
    expect(first[0].searchParams.get('limit')).toBe('50')

    await act(async () => moreButton()?.click())

    const pages = calls('/api/journal-entries')
    expect(pages).toHaveLength(2)
    expect(pages[1].searchParams.get('cursor')).toBe('c1')
    expect(text()).toContain('سندِ 3')
    expect(text()).toContain(`نمایشِ ${(3).toLocaleString('fa-IR')} از ${(3).toLocaleString('fa-IR')} سند`)
    //: کرسرِ بعدی نیست؛ دکمه نباید بماند.
    expect(moreButton()).toBeUndefined()
  })

  it('برگشت به فیلترِ قبلی صفحه‌های بارگذاری‌شده‌ی قدیمی را زنده نمی‌کند', async () => {
    //: مرورگرِ واقعی این را گرفت: «سندهای بعدی» ← فیلترِ دیگر ← برگشت. کلیدِ دامنه همان
    //: می‌شد و صفحه‌ی دومِ قدیمی کنارِ صفحه‌ی اولِ دامنه‌ی قبلی می‌نشست: سندِ تکراری.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    stub({
      page: (url) => {
        if (url.searchParams.get('entry_from') === '120') {
          return new Response(JSON.stringify({ items: [entry('e3', 3, 300)], next_cursor: null }), { status: 200 })
        }
        const body = url.searchParams.get('cursor') === 'c1' ? SECOND : FIRST
        return new Response(JSON.stringify(body), { status: 200 })
      },
    })
    await render()
    await act(async () => moreButton()?.click())
    expect(text()).toContain(`نمایشِ ${(3).toLocaleString('fa-IR')} از`)

    const from = fieldByLabel('از شماره سند')
    await type(from, '120')
    await type(from, '')

    const duplicates = consoleError.mock.calls.filter((c) => String(c[0]).includes('same key'))
    consoleError.mockRestore()
    expect(duplicates).toEqual([])
    //: از صفحه‌ی اول شروع می‌شود، با دکمه‌ی «سندهای بعدی»، نه با صفحه‌ی دومِ کهنه.
    expect(text()).toContain(`نمایشِ ${(2).toLocaleString('fa-IR')} از ${(3).toLocaleString('fa-IR')} سند`)
    expect(moreButton()).toBeDefined()
  })

  it('فهرست و جمع با یک دامنه می‌روند', async () => {
    stub()
    await render()
    const page = calls('/api/journal-entries')[0]
    const summary = calls('/api/journal-entries/summary')[0]
    page.searchParams.delete('limit')
    expect(summary.searchParams.toString()).toBe(page.searchParams.toString())
    //: بازه‌ی پیش‌فرضِ صفحه («این ماه») به هر دو می‌رسد.
    expect(summary.searchParams.get('date_from')).toBeTruthy()
  })

  it('فیلترِ شماره‌ی سند به فهرست و جمعِ روزنامه می‌رسد', async () => {
    stub()
    await render()
    await type(fieldByLabel('از شماره سند'), '120')

    const page = calls('/api/journal-entries').at(-1)
    const summary = calls('/api/journal-entries/summary').at(-1)
    expect(page?.searchParams.get('entry_from')).toBe('120')
    expect(summary?.searchParams.get('entry_from')).toBe('120')
  })

  it('با فیلترِ مرکز هزینه، جمع و برچسبش می‌گویند فقط ردیف‌های منطبق', async () => {
    stub()
    await render()
    expect(footLabel()).toContain('همه‌ی')
    const center = [...container.querySelectorAll('label')]
      .find((l) => l.textContent?.includes('مرکز هزینه'))
      ?.querySelector('select')
    if (!center) throw new Error('انتخابگرِ مرکز هزینه پیدا نشد')
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set
    await act(async () => {
      setter?.call(center, 'cc1')
      center.dispatchEvent(new Event('change', { bubbles: true }))
    })

    expect(calls('/api/journal-entries/summary').at(-1)?.searchParams.get('cost_center_id')).toBe('cc1')
    expect(calls('/api/journal-entries').at(-1)?.searchParams.get('cost_center_id')).toBe('cc1')
    //: جمعِ ردیف‌های منطبق بخشی از هر سند است: برچسب همین را می‌گوید و توازن سنجیده نمی‌شود.
    expect(footLabel()).toContain('ردیف‌های منطبق')
    expect(footLabel()).not.toContain('همه‌ی')
    expect(footLabel()).not.toContain('تراز است')
  })

  it('جست‌وجو برچسبِ درست دارد: سند، نه حساب', async () => {
    stub()
    await render()
    const search = container.querySelector('input[type="search"]')
    expect(search?.getAttribute('aria-label')).toBe('جست‌وجوی سند')
    expect(search?.getAttribute('placeholder')).toBe('شماره یا شرحِ سند')
  })

  it('نتیجه‌ی خالی پیامِ خالی می‌دهد، نه خطا', async () => {
    stub({
      summary: () =>
        new Response(JSON.stringify({ entry_count: 0, line_count: 0, total_debit: '0', total_credit: '0' }), {
          status: 200,
        }),
      page: () => new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }),
    })
    await render()
    expect(text()).toContain('در بازه و فیلترِ انتخاب‌شده سندی یافت نشد.')
    expect(moreButton()).toBeUndefined()
  })

  it('خطای سرور در همان کارت نشان داده می‌شود و صفحه را نمی‌اندازد', async () => {
    stub({
      summary: () => new Response('{}', { status: 500 }),
      page: () => new Response('{}', { status: 500 }),
    })
    await render()
    expect(text()).toContain('دریافت اطلاعات ناموفق بود (500)')
    expect(text()).toContain('جمعِ دفتر نیامد')
    //: سربرگ و انتخابِ دفتر سرِ جایشان‌اند.
    expect([...container.querySelectorAll('[aria-label="دفتر"] button')].map((b) => b.textContent)).toContain('معین')
  })
})
