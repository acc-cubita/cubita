// @vitest-environment jsdom
/**
 * درختواره تنها خانه‌ی حساب‌هاست (بازچینیِ ۱۴۰۵/۰۷/۰۳) — دو کارِ دو صفحه‌ی حذف‌شده این‌جاست:
 *
 * * «حساب تازه» (جای «سرفصل جدید»): سرفصلِ مادر از فهرست، نوع از مادر، کدِ پیشنهادی از سرور؛ فقط ریشه
 *   نوعِ دستی می‌گیرد.
 * * «نمای تخت» (جای «فهرست حساب‌ها»): همه‌ی حساب‌ها بی‌تورفتگی و بی‌جمع‌شدن.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AccountTreePanel } from './AccountTreePanel'

let container: HTMLDivElement
let root: Root
let posts: { path: string; body: Record<string, unknown> }[]

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
  posts = []
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
      if (init?.method === 'POST') {
        posts.push({ path: url.pathname, body: JSON.parse(String(init.body)) })
        return json({ id: 'new', ...JSON.parse(String(init.body)) }, 201)
      }
      if (url.pathname === '/api/accounts') return json(accounts)
      if (url.pathname === '/api/accounts/next-code')
        return json(url.searchParams.get('parent_id') ? { code: '1102', level: 'معین', digits: 2 } : { code: '6', level: 'گروه', digits: 1 })
      return json([])
    }),
  )
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
async function render(props: { startAdding?: boolean; startFlat?: boolean } = {}) {
  await act(async () => {
    root.render(createElement(AccountTreePanel, { token: 't', ...props }))
  })
  await settle()
  await settle()
}
const addRow = () => container.querySelector<HTMLFormElement>('.tree-add')
const rowNames = () =>
  [...container.querySelectorAll('.tree-table tbody tr:not(.tree-add-row) .tree-cell')].map(
    (c) => c.querySelector('.chart-group-name, .entity-name')?.textContent,
  )
const button = (text: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.includes(text))!

function change(el: HTMLInputElement | HTMLSelectElement, value: string) {
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  act(() => {
    Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value)
    el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
  })
}

describe('«حساب تازه» درونِ درختواره', () => {
  it('از منوی قدیمیِ «سرفصل جدید» باز می‌آید: ریشه با کدِ پیشنهادی و نوعِ دستی', async () => {
    await render({ startAdding: true })
    const form = addRow()!
    const [parent, type] = [...form.querySelectorAll('select')]
    expect(parent.value).toBe('')
    expect(type.title).toBe('نوعِ حساب')
    expect(form.querySelector<HTMLInputElement>('input[placeholder="کد"]')!.value).toBe('6')
  })

  it('با انتخابِ سرفصلِ مادر، نوع از مادر و کدِ بعدیِ همان سرفصل؛ ثبت زیرِ همان مادر', async () => {
    await render()
    expect(addRow()).toBeNull()
    await act(async () => button('حساب تازه').click())
    await settle()
    const form = addRow()!
    change(form.querySelector('select')!, 'g1')
    await settle()
    //: زیرِ سرفصل، نوعِ دستی نیست — از مادر می‌آید.
    expect([...form.querySelectorAll('select')].some((s) => s.title === 'نوعِ حساب')).toBe(false)
    expect(form.querySelector<HTMLInputElement>('input[placeholder="کد"]')!.value).toBe('1102')
    change(form.querySelector<HTMLInputElement>('input[placeholder="نام حساب"]')!, 'بانک')
    await act(async () => form.requestSubmit())
    await settle()
    expect(posts).toHaveLength(1)
    expect(posts[0]).toMatchObject({ path: '/api/accounts', body: { code: '1102', name: 'بانک', parent_id: 'g1', type: 'asset' } })
    expect(addRow()).toBeNull()
  })
})

describe('«نمای تخت» درونِ درختواره', () => {
  it('درخت از اول جمع است؛ نمای تخت همه را بی‌تورفتگی نشان می‌دهد و برمی‌گردد', async () => {
    await render()
    expect(rowNames()).toEqual(['دارایی‌ها'])
    await act(async () => button('نمای تخت').click())
    expect(rowNames()).toEqual(['دارایی‌ها', 'دارایی‌های جاری', 'صندوق'])
    const cells = [...container.querySelectorAll<HTMLElement>('.tree-table tbody .tree-cell')]
    expect(cells.every((c) => !c.style.paddingInlineStart || c.style.paddingInlineStart === '0px')).toBe(true)
    await act(async () => button('نمای درختی').click())
    expect(rowNames()).toEqual(['دارایی‌ها'])
  })

  it('از فهرستِ قدیمیِ «فهرست حساب‌ها» مستقیم در نمای تخت باز می‌شود', async () => {
    await render({ startFlat: true })
    expect(rowNames()).toHaveLength(3)
  })
})
