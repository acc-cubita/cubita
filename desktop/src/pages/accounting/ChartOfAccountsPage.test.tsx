// @vitest-environment jsdom
/**
 * «درختواره حساب‌ها» — برگه‌ی ویرایشِ درجا روی درخت (تمِ اکسلی).
 *
 * همان چیزهایی که درختواره‌ی قبلی تضمین می‌کرد، این‌بار در برگه:
 * * «حساب تازه» (جای «سرفصل جدید»): کدِ پیشنهادی از سرور؛ نوع از مادر؛ فقط ریشه نوعِ دستی می‌گیرد.
 * * «نمای تخت» (جای «فهرست حساب‌ها»): همه‌ی حساب‌ها بی‌جمع‌شدن.
 * و آنچه برگه اضافه کرده: ویرایشِ درجا با ذخیره‌ی یک‌جا (نام با `PATCH /accounts/{id}`، کد با `…/code`)،
 * سنجشِ کدِ تکراری پیش از ارسال، و برگرداندنِ ردیف با Ctrl+Delete.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NavSectionContext } from '../../components/navContext'
import { setTenantScope } from '../../lib/tenantScope'
import { ChartOfAccountsPage } from './ChartOfAccountsPage'

let container: HTMLDivElement
let root: Root
let writes: { method: string; path: string; body: Record<string, unknown> }[]

const account = (id: string, code: string, name: string, parent: string | null, isGroup: boolean) => ({
  id,
  code,
  name,
  name2: '',
  type: 'asset',
  nature: null,
  effective_nature: 'debit',
  is_group: isGroup,
  is_active: true,
  statement_type: 'balance_sheet',
  parent_id: parent,
  system_role: null,
  nature_control: false,
  is_fx: false,
  fx_revaluable: false,
  accepts_tafsili: false,
  has_tracking: false,
  in_management_reports: true,
})

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  sessionStorage.clear()
  setTenantScope('t1')
  writes = []
  const accounts = [
    account('r1', '1', 'دارایی‌ها', null, true),
    account('g1', '11', 'دارایی‌های جاری', 'r1', true),
    account('l1', '1101', 'صندوق', 'g1', false),
  ]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (init?.method && init.method !== 'GET') {
        const body = JSON.parse(String(init.body ?? '{}'))
        writes.push({ method: init.method, path: url.pathname, body })
        return json({ id: 'new', ...body }, init.method === 'POST' ? 201 : 200)
      }
      if (url.pathname === '/api/accounts') return json(accounts)
      if (url.pathname === '/api/accounts/next-code')
        return json(url.searchParams.get('parent_id') ? { code: '1102', level: 'معین', digits: 2 } : { code: '6', level: 'گروه', digits: 1 })
      return json([])
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
  vi.unstubAllGlobals()
})

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
async function render(section: string | null = null) {
  await act(async () => {
    root.render(
      createElement(
        NavSectionContext.Provider,
        { value: { activePage: 'acctchart', section, setSection: vi.fn() } },
        createElement(ChartOfAccountsPage, { token: 't' }),
      ),
    )
  })
  await settle()
  await settle()
  await settle()
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.ca-sheet tbody tr')]
const codes = () => rows().map((tr) => tr.querySelector<HTMLInputElement>('td[data-cell$="-0"] input')?.value)
const rowOf = (code: string) => rows().find((tr) => tr.querySelector<HTMLInputElement>('td[data-cell$="-0"] input')?.value === code)!
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!

function change(el: HTMLInputElement | HTMLSelectElement, value: string) {
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  act(() => {
    Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value)
    el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
  })
}
async function save() {
  await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
  await settle()
  await settle()
}

describe('درختواره — درخت و نمای تخت', () => {
  it('درخت از اول جمع است؛ بازکردنِ سرفصل زیرشاخه را نشان می‌دهد؛ نمای تخت همه را', async () => {
    await render()
    expect(codes()).toEqual(['1'])
    act(() => rowOf('1').querySelector<HTMLButtonElement>('.ca-toggle')!.click())
    expect(codes()).toEqual(['1', '11'])
    act(() => button('تخت').click())
    expect(codes()).toEqual(['1', '11', '1101'])
    expect(container.querySelector('.ca-sheet .ca-toggle')).toBeNull()
  })

  it('از فهرستِ قدیمیِ «فهرست حساب‌ها» مستقیم در نمای تخت باز می‌شود', async () => {
    await render('flat')
    expect(codes()).toEqual(['1', '11', '1101'])
  })
})

describe('درختواره — حسابِ تازه', () => {
  it('از منوی قدیمیِ «سرفصل جدید»: ردیفِ ریشه با کدِ پیشنهادی و نوعِ دستی', async () => {
    await render('new')
    const fresh = container.querySelector<HTMLTableRowElement>('.ca-sheet tr.xl-row--new')!
    expect(fresh.querySelector<HTMLInputElement>('td[data-cell$="-0"] input')!.value).toBe('6')
    const type = fresh.querySelector<HTMLSelectElement>('select[aria-label="نوعِ سرفصلِ ریشه"]')!
    change(type, 'expense')
    change(fresh.querySelector<HTMLInputElement>('td[data-cell$="-1"] input')!, 'هزینه‌ها')
    await save()
    expect(writes).toEqual([
      expect.objectContaining({
        method: 'POST',
        path: '/api/accounts',
        body: expect.objectContaining({ code: '6', name: 'هزینه‌ها', type: 'expense', parent_id: null }),
      }),
    ])
  })

  it('«+»ِ یک سرفصل: زیرِ همان سرفصل، نوع از مادر و کدِ بعدیِ همان سرفصل', async () => {
    await render('flat')
    act(() => rowOf('11').querySelector<HTMLButtonElement>('.jg-actions button')!.click())
    await settle()
    const fresh = container.querySelector<HTMLTableRowElement>('.ca-sheet tr.xl-row--new')!
    //: ته زیرشاخه‌ی «۱۱»، بعد از «۱۱۰۱».
    expect(codes()).toEqual(['1', '11', '1101', '1102'])
    expect(fresh.querySelector('select[aria-label="نوعِ سرفصلِ ریشه"]')).toBeNull()
    change(fresh.querySelector<HTMLInputElement>('td[data-cell$="-1"] input')!, 'بانک')
    await save()
    expect(writes[0]).toMatchObject({
      method: 'POST',
      body: { code: '1102', name: 'بانک', type: 'asset', parent_id: 'g1', is_group: false, in_management_reports: true },
    })
  })
})

describe('درختواره — ویرایشِ درجا', () => {
  it('نام و کد یک‌جا ذخیره می‌شوند: نام با PATCH، کد با مسیرِ جدای کد', async () => {
    await render('flat')
    const cash = rowOf('1101')
    change(cash.querySelector<HTMLInputElement>('td[data-cell$="-1"] input')!, 'صندوقِ مرکزی')
    change(cash.querySelector<HTMLInputElement>('td[data-cell$="-0"] input')!, '1109')
    expect(rowOf('1109').className).toContain('xl-row--dirty')
    expect(container.querySelector('.jf-foot')?.textContent).toContain('۱ تغییر')
    await save()
    expect(writes).toEqual([
      { method: 'PATCH', path: '/api/accounts/l1', body: { name: 'صندوقِ مرکزی' } },
      { method: 'PATCH', path: '/api/accounts/l1/code', body: { code: '1109' } },
    ])
  })

  it('کدِ تکراری پیش از ارسال گرفته می‌شود و دلیلش زیرِ برگه می‌آید', async () => {
    await render('flat')
    change(rowOf('1101').querySelector<HTMLInputElement>('td[data-cell$="-0"] input')!, '11')
    await save()
    expect(writes).toEqual([])
    expect(container.querySelector('.xl-errbar')?.textContent).toContain('کدِ «11» تکراری است.')
  })

  it('Ctrl+Delete تغییرِ ردیف را برمی‌گرداند', async () => {
    await render('flat')
    const input = rowOf('1101').querySelector<HTMLInputElement>('td[data-cell$="-1"] input')!
    change(input, 'صندوقِ مرکزی')
    act(() => {
      input.focus()
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', code: 'Delete', ctrlKey: true, bubbles: true, cancelable: true }))
    })
    expect(rowOf('1101').querySelector<HTMLInputElement>('td[data-cell$="-1"] input')!.value).toBe('صندوق')
    expect(rowOf('1101').className).not.toContain('xl-row--dirty')
  })

  it('ماهیت فقط روی حسابِ قابلِ ثبت ویرایش می‌شود', async () => {
    await render('flat')
    expect(rowOf('11').querySelector('td[data-cell$="-3"] select')).toBeNull()
    const nature = rowOf('1101').querySelector<HTMLSelectElement>('td[data-cell$="-3"] select')!
    change(nature, 'credit')
    await save()
    expect(writes).toEqual([{ method: 'PATCH', path: '/api/accounts/l1', body: { nature: 'credit' } }])
  })
})
