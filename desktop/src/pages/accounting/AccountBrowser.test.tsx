// @vitest-environment jsdom
/**
 * «مرور حساب‌ها» (UI-02) در DOM — سناریوهای §۳۷ تا §۴۰ و سنجه‌ی چارتِ هزارحسابی (§۲۸).
 *
 * `fetch` با یک مسیریابِ کوچک جایگزین می‌شود؛ پس **آدرس‌های واقعی** هم سنجیده
 * می‌شوند: درخت از `/api/accounting/balance-tree` با همان بازه، گردش از
 * `/api/reports/general-ledger/{id}` با `limit/offset` (صفحه‌بندیِ سمتِ سرور، نه
 * کشیدنِ کلِ دفتر)، و سند از `/api/journal-entries/{id}`.
 *
 * **ارقام از پاسخِ سرور عیناً نمایش داده می‌شوند** — این‌جا همان را می‌سنجیم: عددی
 * که در پاسخِ جعلی برای سرفصل گذاشته شده (عمداً *نه* جمعِ فرزندان) باید همان
 * دیده شود. اگر روزی رابط دوباره خودش جمع بزند، این تست می‌شکند.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { BalanceTreeNode } from '../../api'
import { AccountBrowsePage } from './AccountBrowser'
import { setTenantScope } from '../../lib/tenantScope'

let container: HTMLDivElement
let root: Root
let calls: string[]
let tree: BalanceTreeNode[]

function node(id: string, code: string, name: string, parent: string | null, extra: Partial<BalanceTreeNode> = {}): BalanceTreeNode {
  return {
    account_id: id,
    parent_id: parent,
    account_code: code,
    account_name: name,
    account_type: 'asset',
    nature: 'debit',
    is_group: false,
    is_active: true,
    accepts_tafsili: false,
    depth: 0,
    child_count: 0,
    opening: '0',
    period_debit: '0',
    period_credit: '0',
    closing: '0',
    has_activity: false,
    has_direct_lines: false,
    nature_violation: false,
    ...extra,
  }
}

/** سناریوی بانک (§۳۷). رقمِ «موجودی نقد و بانک» عمداً از سرور است، نه جمعِ فرزندان. */
const bankChart = () => [
  node('a', '1', 'دارایی‌ها', null, { is_group: true, closing: '20000000', child_count: 1 }),
  node('ac', '11', 'دارایی جاری', 'a', { is_group: true, closing: '20000000', child_count: 1 }),
  node('cash', '1102', 'موجودی نقد و بانک', 'ac', { is_group: true, closing: '20000001', child_count: 2 }),
  node('melli', '110201', 'بانک ملی', 'cash', {
    closing: '20000000',
    opening: '250000000',
    period_debit: '3200000000',
    period_credit: '2600000000',
    has_activity: true,
  }),
  node('box', '110202', 'صندوق', 'cash'),
  node('i', '6', 'درآمدها', null, { is_group: true, account_type: 'income', nature: 'credit', closing: '-20000000' }),
  node('sales', '6101', 'فروش', 'i', { account_type: 'income', nature: 'credit', closing: '-20000000' }),
]

const ledger = (accountId: string, offset: number, total = 1) => ({
  account_id: accountId,
  account_code: '110201',
  account_name: 'بانک ملی',
  opening_balance: '0',
  closing_balance: '20000000',
  period_debit: '20000000',
  period_credit: '0',
  total_lines: total,
  offset,
  limit: 100,
  fx_totals: [],
  lines: Array.from({ length: Math.min(100, total - offset) }, (_, i) => ({
    line_id: `l${offset + i}`,
    entry_id: offset + i === 0 ? 'e451' : `e${offset + i}`,
    entry_number: offset + i === 0 ? 451 : 1000 + offset + i,
    entry_date: '2026-03-15',
    entry_status: 'permanent',
    source_type: 'manual',
    account_code: '110201',
    account_name: 'بانک ملی',
    description: 'واریزِ فروش',
    debit: '20000000',
    credit: '0',
    balance: String(20000000 * (offset + i + 1)),
    currency_code: null,
    fx_amount: null,
    fx_rate: null,
    tracking_no: null,
    tracking_date: null,
    cost_center_name: 'شعبه تهران',
  })),
})

const entry451 = {
  id: 'e451',
  number: 451,
  atf_number: 451,
  sub_number: null,
  entry_date: '2026-03-15',
  description: 'فروش نقدی',
  source_type: 'manual',
  source: null,
  status: 'permanent',
  voided_at: null,
  reverses_entry_id: null,
  lines: [
    { id: 'x1', account_id: 'melli', debit: '20000000', credit: '0', description: '' },
    { id: 'x2', account_id: 'sales', debit: '0', credit: '20000000', description: '' },
  ],
}

function respond(url: string): unknown {
  const u = new URL(url)
  if (u.pathname === '/api/accounting/balance-tree') return tree
  const gl = u.pathname.match(/^\/api\/reports\/general-ledger\/(.+)$/)
  if (gl) return ledger(gl[1], Number(u.searchParams.get('offset') ?? 0), gl[1] === 'melli' ? 150 : gl[1] === 'box' ? 0 : 1)
  if (u.pathname === '/api/journal-entries/e451') return entry451
  return []
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  calls = []
  tree = bankChart()
  sessionStorage.clear()
  //: وضعیت به‌ازای کسب‌وکار ذخیره می‌شود؛ بی کسب‌وکار چیزی نه خوانده می‌شود نه نوشته.
  setTenantScope('t1')
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      return { ok: true, status: 200, json: async () => respond(url) }
    }),
  )
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => setTimeout(() => cb(0), 0))
  Element.prototype.scrollIntoView = () => {}
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
const rowIds = () => [...document.querySelectorAll('[role="treeitem"]')].map((el) => el.id.replace('ab-node-', ''))
const selectedId = () => $('[role="treeitem"][aria-selected="true"]')?.id.replace('ab-node-', '') ?? null

function key(el: Element, k: string) {
  act(() => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }))
  })
}

async function mount() {
  act(() => root.render(createElement(AccountBrowsePage, { token: 't' })))
  await wait()
  await wait()
}

function typeSearch(text: string) {
  const input = $<HTMLInputElement>('.ab-search input')!
  const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
  act(() => {
    setValue.call(input, text)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  return input
}

describe('مرور حساب — سناریوی بانک (§۳۷)', () => {
  it('درخت با ریشه‌های باز و ارقامِ سرور', async () => {
    await mount()
    expect(rowIds()).toEqual(['a', 'ac', 'i', 'sales'])
    //: فقط یک درخواستِ درخت — گردشِ هیچ حسابی پیش از انتخاب خوانده نمی‌شود.
    expect(calls.filter((c) => c.includes('general-ledger'))).toEqual([])
    expect(calls.find((c) => c.includes('/api/accounting/balance-tree'))).toContain('date_from=')
    expect($('#ab-node-i .ab-bal')!.textContent).toContain('بس')
  })

  it('کیبورد: ← باز، ↓ حرکت، Enter گردش، Enter سند، Esc برگشت — زمینه می‌ماند', async () => {
    await mount()
    const treeEl = $('[role="tree"]')!
    key(treeEl, 'ArrowDown') // دارایی‌ها
    key(treeEl, 'ArrowDown') // دارایی جاری
    expect(selectedId()).toBe('ac')
    key(treeEl, 'ArrowLeft') // باز
    key(treeEl, 'ArrowLeft') // اولین فرزند
    expect(selectedId()).toBe('cash')
    //: رقمِ سرفصل همان است که سرور داد (۲۰٬۰۰۰٬۰۰۱) — نه جمعِ فرزندان در مرورگر.
    expect($('#ab-node-cash .ab-bal')!.textContent).toContain((20000001).toLocaleString('fa-IR'))
    key(treeEl, 'ArrowLeft')
    key(treeEl, 'ArrowLeft')
    expect(selectedId()).toBe('melli')

    // خلاصه‌ی حساب: فقط ارقامِ سرور
    const metrics = $('.ab-metrics')!.textContent!
    expect(metrics).toContain((250000000).toLocaleString('fa-IR'))
    expect(metrics).toContain((3200000000).toLocaleString('fa-IR'))
    expect(metrics).toContain((2600000000).toLocaleString('fa-IR'))

    key(treeEl, 'Enter')
    await wait(250)
    const ledgerCall = calls.find((c) => c.includes('/api/reports/general-ledger/melli'))!
    expect(ledgerCall).toContain('limit=100')
    expect(ledgerCall).toContain('offset=0')
    const ledgerEl = $('.ab-ledger-scroll')!
    expect(document.activeElement).toBe(ledgerEl)
    expect($('.ab-ledger-table')!.textContent).toContain('شعبه تهران')

    key(ledgerEl, 'Enter') // سند ۴۵۱
    await wait()
    expect(calls.some((c) => c.endsWith('/api/journal-entries/e451'))).toBe(true)
    expect(document.querySelector('.drawer-panel')!.textContent).toContain((451).toLocaleString('fa-IR'))

    // Esc فقط کشو را می‌بندد؛ فوکوس به گردش برمی‌گردد و درخت دست نخورده.
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      ledgerEl.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })
    await wait()
    expect(document.querySelector('.drawer-panel')).toBeNull()
    expect(selectedId()).toBe('melli')
    expect(rowIds()).toContain('melli')

    // Esc دوم: از گردش به درخت.
    key($('.ab-ledger-scroll')!, 'Escape')
    await wait()
    expect(document.activeElement).toBe($('[role="tree"]'))
  })

  it('صفحه‌بندیِ گردش سمتِ سرور: PageDown صفحه‌ی بعد را از سرور می‌خواهد', async () => {
    await mount()
    act(() => $('#ab-node-a')!.click())
    // مستقیم با جست‌وجو به بانک ملی
    const input = typeSearch('بانک ملی')
    key(input, 'Enter')
    await wait(250)
    key($('.ab-ledger-scroll')!, 'PageDown')
    await wait(250)
    expect(calls.some((c) => c.includes('general-ledger/melli') && c.includes('offset=100'))).toBe(true)
    expect($('.ab-pager')!.textContent).toContain((150).toLocaleString('fa-IR'))
  })
})

describe('فوکوس', () => {
  it('Enter روی حسابِ بی‌گردش، فوکوسِ حسابِ بعدی را از درخت نمی‌دزدد', async () => {
    await mount()
    typeSearch('صندوق')
    key($('.ab-search input')!, 'Enter')
    await wait()
    const treeEl = $('[role="tree"]')!
    key(treeEl, 'Enter') // صندوق: گردشی ندارد
    await wait(250)
    expect($('.ab-ledger')!.textContent).toContain('گردشی ندارد')
    expect(document.activeElement).toBe(treeEl)
    key(treeEl, 'ArrowUp') // بانک ملی — گردش دارد
    await wait(250)
    expect(selectedId()).toBe('melli')
    expect($('.ab-ledger-scroll')).not.toBeNull()
    expect(document.activeElement).toBe(treeEl)
  })
})

describe('جست‌وجو (§۳۹)', () => {
  it('«بانک ملی» → نتیجه با مسیر → Enter → نمایش در درخت', async () => {
    await mount()
    expect(rowIds()).not.toContain('melli')
    const input = typeSearch('بانک ملی')
    const hit = $('.ab-hit')!
    expect(hit.textContent).toContain('بانک ملی')
    expect($('.ab-hit-path')!.textContent).toBe('دارایی‌ها / دارایی جاری / موجودی نقد و بانک')
    key(input, 'Enter')
    await wait()
    expect(rowIds()).toContain('melli')
    expect(selectedId()).toBe('melli')
    expect($('.ab-trail')!.textContent).toContain('موجودی نقد و بانک')
  })

  it('Esc در جست‌وجو فوکوس را به درخت برمی‌گرداند — نه به هیچ‌جا', async () => {
    await mount()
    const input = typeSearch('بانک')
    input.focus()
    key(input, 'Escape')
    expect($('.ab-hit')).toBeNull()
    expect(document.activeElement).toBe($('[role="tree"]'))
  })

  it('Enter روی نتیجه، فوکوس را هم‌زمان به درخت می‌برد (بی‌انتظارِ فریم)', async () => {
    await mount()
    const input = typeSearch('بانک ملی')
    input.focus()
    key(input, 'Enter')
    expect(document.activeElement).toBe($('[role="tree"]'))
  })

  it('ارقامِ فارسی در کد', async () => {
    await mount()
    typeSearch('۱۱۰۲۰۲')
    expect($('.ab-hit')!.textContent).toContain('صندوق')
  })
})

describe('برگشت به همان نقطه (§۴۰)', () => {
  it('رفتن به صفحه‌ی دیگر و برگشتن: حساب، گره‌های باز، بازه و صفحه‌ی گردش می‌مانند', async () => {
    await mount()
    typeSearch('بانک ملی')
    key($('.ab-search input')!, 'Enter')
    await wait(250)
    key($('.ab-ledger-scroll')!, 'PageDown')
    await wait(250)
    act(() => ($('.cc-presets button:nth-of-type(3)') as HTMLButtonElement).click()) // «این فصل»
    await wait()

    act(() => root.unmount())
    root = createRoot(container)
    calls = []
    await mount()
    await wait(250)

    expect(selectedId()).toBe('melli')
    expect(rowIds()).toEqual(expect.arrayContaining(['a', 'ac', 'cash', 'melli']))
    expect($('.cc-presets button.is-active')!.textContent).toBe('این فصل')
    expect(calls.some((c) => c.includes('general-ledger/melli') && c.includes('offset=0'))).toBe(false)
  })

  it('بعد از تعویضِ کسب‌وکار، وضعیتِ کسب‌وکارِ قبلی برنمی‌گردد', async () => {
    //: تعویضِ کسب‌وکار فقط صفحه را دوباره بار می‌کند و `sessionStorage` می‌ماند. با کلیدِ
    //: سراسری، حساب و فیلترهای کسب‌وکارِ قبلی روی این یکی می‌نشستند.
    await mount()
    typeSearch('بانک ملی')
    key($('.ab-search input')!, 'Enter')
    await wait(250)
    expect(selectedId()).toBe('melli')

    act(() => root.unmount())
    setTenantScope('t2')
    root = createRoot(container)
    await mount()
    await wait(250)

    expect(selectedId()).not.toBe('melli')
    expect(rowIds()).not.toContain('melli')

    //: و برگشت به کسب‌وکارِ اول، وضعیتِ خودش را پس می‌دهد.
    act(() => root.unmount())
    setTenantScope('t1')
    root = createRoot(container)
    await mount()
    await wait(250)
    expect(selectedId()).toBe('melli')
  })
})

describe('بازه‌ی تاریخ (§۳۸)', () => {
  it('عوض‌کردنِ بازه درخت و گردش را با هم دوباره از سرور می‌خواهد', async () => {
    await mount()
    typeSearch('بانک ملی')
    key($('.ab-search input')!, 'Enter')
    await wait(250)
    calls = []
    act(() => ($('.cc-presets button:nth-of-type(1)') as HTMLButtonElement).click()) // «از ابتدا»
    await wait(250)
    const treeCall = calls.find((c) => c.includes('balance-tree'))
    const ledgerCall = calls.find((c) => c.includes('general-ledger/melli'))
    expect(treeCall).toBeDefined()
    expect(treeCall).not.toContain('date_from')
    expect(ledgerCall).toBeDefined()
    expect(ledgerCall).not.toContain('date_from')
  })
})

describe('حساب‌های غیرفعال و هشدار', () => {
  it('غیرفعال دیده می‌شود با نشان؛ هشدارِ ماهیت روی برگ', async () => {
    tree = [
      ...bankChart(),
      node('old', '110203', 'بانک قدیمی', 'cash', { is_active: false }),
      node('od', '110204', 'اضافه‌برداشت', 'cash', { closing: '-5', nature_violation: true }),
    ]
    await mount()
    typeSearch('بانک قدیمی')
    key($('.ab-search input')!, 'Enter')
    await wait()
    expect($('#ab-node-old')!.textContent).toContain('غیرفعال')
    expect($('#ab-node-od')!.textContent).toContain('هشدار ماهیت')
  })
})

describe('چارتِ ۱۰۰۰ حسابی (§۲۸)', () => {
  it('سوارشدن، بازکردنِ همه، و حرکت با ↓', async () => {
    //: ۱۰ کل + ۱۰۰ معین + ۹۰۰ تفصیل = ۱۰۱۰ گره
    const big: BalanceTreeNode[] = []
    for (let g = 0; g < 10; g++) {
      big.push(node(`g${g}`, `${g + 1}`, `گروه ${g}`, null, { is_group: true, closing: '1' }))
      for (let m = 0; m < 10; m++) {
        big.push(node(`m${g}-${m}`, `${g + 1}${m}`, `معین ${g}-${m}`, `g${g}`, { is_group: true, closing: '1' }))
        for (let t = 0; t < 9; t++) {
          big.push(node(`t${g}-${m}-${t}`, `${g + 1}${m}0${t}`, `تفصیل ${g}-${m}-${t}`, `m${g}-${m}`, { closing: String(t) }))
        }
      }
    }
    tree = big
    const openAll = big.filter((n) => n.is_group).map((n) => n.account_id)
    sessionStorage.setItem('cubita.accountBrowser.v1:t1', JSON.stringify({ expanded: openAll }))

    const t0 = performance.now()
    await mount()
    const mountMs = performance.now() - t0
    expect(rowIds().length).toBe(1010)

    const treeEl = $('[role="tree"]')!
    const times: number[] = []
    for (let i = 0; i < 20; i++) {
      const t = performance.now()
      key(treeEl, 'ArrowDown')
      times.push(performance.now() - t)
    }
    expect(selectedId()).toBe(rowIds()[19])
    const t1 = performance.now()
    typeSearch('تفصیل 7-3-5')
    const searchMs = performance.now() - t1
    expect($('.ab-hit')!.textContent).toContain('تفصیل 7-3-5')

    const med = [...times].sort((a, b) => a - b)[10]
    console.log(
      `[perf] ۱۰۱۰ گره: سوارشدن ${mountMs.toFixed(0)}ms · ↓ میانه ${med.toFixed(1)}ms · جست‌وجو ${searchMs.toFixed(1)}ms`,
    )
  })
})
