// @vitest-environment jsdom
/**
 * صفحه‌ی «گزارش‌ها» با تمِ اکسلی — گریدِ صورت‌های مالی، نشانِ توازن، باز شدنِ دفترِ حساب، و پارامترهایی که خودشان
 * گزارش را می‌آورند (بی دکمه‌ی «نمایش»).
 *
 * `fetch` با مسیریابِ کوچکی جایگزین می‌شود؛ ارقام از پاسخِ جعلیِ سرورند و جمعِ هر بخش `total_*`ِ همان پاسخ.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Reports } from './Reports'

let container: HTMLDivElement
let root: Root
let calls: string[]
let totalAssets: string

const acc = (id: string, name: string, balance: number) => ({
  account_id: id,
  account_code: id,
  account_name: name,
  balance: String(balance),
})

function respond(url: string): unknown {
  const u = new URL(url)
  switch (u.pathname) {
    case '/api/reports/income-statement':
      return {
        date_from: null,
        date_to: null,
        income: [acc('4101', 'فروش', 900)],
        expenses: [acc('6101', 'حقوق', 300)],
        total_income: '900',
        total_expenses: '300',
        net_profit: '600',
      }
    case '/api/reports/balance-sheet':
      return {
        as_of: '2026-09-26',
        assets: [acc('1101', 'صندوق', 700), acc('1102', 'بانک', -100)],
        liabilities: [acc('2101', 'پرداختنی', 200)],
        equity: [acc('3101', 'سرمایه', 250)],
        total_assets: totalAssets,
        total_liabilities: '200',
        total_equity: '250',
        current_period_profit: '150',
      }
    case '/api/items':
      return { items: [{ id: 'it1', sku: 'CAM-1', name: 'دوربین', is_service: false }], next_cursor: null }
    case '/api/reports/kardex/it1':
      return {
        item_id: 'it1',
        item_sku: 'CAM-1',
        item_name: 'دوربین',
        unit: 'عدد',
        opening_qty: '0',
        opening_value: '0',
        total_in: '0',
        total_out: '0',
        closing_qty: '0',
        closing_value: '0',
        lines: [],
      }
    case '/api/reports/general-ledger/4101':
      return { account_id: '4101', opening_balance: '0', closing_balance: '0', lines: [], fx_totals: [] }
    default:
      return []
  }
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  calls = []
  totalAssets = '600'
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      return { ok: true, status: 200, json: async () => respond(url) }
    }),
  )
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => setTimeout(() => cb(0), 0))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

const wait = (ms = 0) => act(() => new Promise<void>((r) => setTimeout(r, ms)))
const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel)
const $$ = (sel: string) => [...document.querySelectorAll<HTMLElement>(sel)]
const text = (el: Element | null | undefined) => el?.textContent?.replace(/\s+/g, ' ').trim() ?? ''
const tab = (label: string) => $$('.rp-tab').find((b) => b.textContent === label)!
const click = (el: Element) => act(() => el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })))

async function mount() {
  act(() => root.render(createElement(Reports, { token: 't' })))
  await wait()
  await wait()
}

describe('گزارش‌ها — تمِ اکسلی', () => {
  it('دوازده گزارش در دسته‌های کاتالوگ، و سود و زیان یک برگه با بخش، جمعِ بخش و سودِ خالص در پانویس', async () => {
    await mount()
    expect($$('.rp-group .jh-label').map((l) => l.textContent)).toEqual([
      'صورت‌های مالی',
      'اشخاص و فروش',
      'انبار',
      'مالیات',
    ])
    expect($$('.rp-tab')).toHaveLength(12)
    expect($$('.rp-statement tbody tr.rp-sec').map(text)).toEqual(['درآمدها', 'هزینه‌ها'])
    expect($$('.rp-statement tbody tr.rp-sub').map(text)).toEqual(['جمعِ درآمدها۹۰۰', 'جمعِ هزینه‌ها۳۰۰'])
    expect(text($('.rp-statement tfoot'))).toBe('سود خالص۶۰۰')
  })

  it('کلیک روی قلمِ حساب دفترش را با همان بازه باز می‌کند', async () => {
    await mount()
    const line = $$('.rp-statement tbody tr.acc-row--clickable').find((tr) => text(tr).includes('فروش'))!
    click(line)
    await wait()
    expect($('.drawer-panel')).not.toBeNull()
    expect(calls.some((c) => c.includes('/api/reports/general-ledger/4101'))).toBe(true)
  })

  it('ترازنامه: گزارشِ لحظه‌ای «به تاریخ» می‌گیرد نه بازه؛ منفی در پرانتز؛ نشانِ توازن', async () => {
    await mount()
    click(tab('ترازنامه'))
    await wait()
    await wait()
    expect(text($('.rp-row--asof .jh-label'))).toBe('به تاریخ')
    expect($('.rh-row--range')).toBeNull()
    expect(text($$('.rp-statement tbody tr').find((tr) => text(tr).includes('بانک'))!.querySelector('.rp-neg'))).toBe('(۱۰۰)')
    expect(text($('.rp-statement tfoot'))).toContain('تراز است')
  })

  it('ترازنامه‌ی نامتوازن اختلافش را می‌گوید', async () => {
    totalAssets = '610'
    await mount()
    click(tab('ترازنامه'))
    await wait()
    await wait()
    expect(text($('.rp-statement tfoot .xl-check--off'))).toContain('نامتوازن — اختلاف ۱۰')
  })

  it('کاردکس: انتخابِ کالا خودش گزارش را می‌آورد', async () => {
    await mount()
    click(tab('کاردکس کالا'))
    await wait()
    await wait()
    expect(text($('.rp-body'))).toContain('یک کالا در سربرگ انتخاب کنید')
    const select = $<HTMLSelectElement>('.rp-row--param select')!
    act(() => {
      select.value = 'it1'
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    await wait()
    await wait()
    expect(calls.some((c) => c.includes('/api/reports/kardex/it1'))).toBe(true)
  })
})
