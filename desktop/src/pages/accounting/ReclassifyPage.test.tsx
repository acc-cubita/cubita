// @vitest-environment jsdom
/**
 * «انتقال حساب به سرفصل دیگر» به‌صورتِ برگه‌ی اکسلی.
 *
 * * ردیف‌ها به ترتیبِ درختواره‌اند و حسابِ نقش‌دار ردیف ندارد.
 * * تایپِ کد در خانه‌ی «سرفصلِ تازه» و Enter: خانه ته‌رنگ می‌گیرد، ستونِ «نوع» تغییرِ نوع را نشان می‌دهد و
 *   فوکوس به ردیفِ بعد می‌رود؛ Ctrl+S یک درخواست با نوعِ نهایی می‌فرستد.
 * * حلقه‌ای که دو ردیف با هم می‌سازند همان لحظه قرمز است و چیزی فرستاده نمی‌شود.
 * * انتخابِ چند ردیف و «بردنِ همه زیرِ سرفصلِ…» از نوارِ انتخاب.
 * * ردِ سرور ردیفِ نام‌برده را قرمز می‌کند و جابه‌جایی‌ها می‌مانند؛ پیش‌نویس با برگشتن برمی‌گردد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ReclassifyPage } from './ReclassifyPage'
import { setTenantScope } from '../../lib/tenantScope'

type Row = { id: string; code: string; name: string; type: string; is_group: boolean; parent_id: string | null; system_role: string | null }

let container: HTMLDivElement
let root: Root
let server: Row[]
let calls: unknown[]
let reject: string | null

const acc = (id: string, name: string, parent: string | null, type: string, group = false, role: string | null = null): Row => ({
  id,
  code: id,
  name,
  type,
  is_group: group,
  parent_id: parent,
  system_role: role,
})

function stub() {
  server = [
    acc('5', 'هزینه‌ها', null, 'expense', true),
    acc('51', 'اجاره', '5', 'expense'),
    acc('1', 'دارایی‌ها', null, 'asset', true),
    acc('11', 'موجودی نقد', '1', 'asset', true),
    acc('1101', 'صندوق', '11', 'asset', false, 'cash'),
    acc('1102', 'تنخواه', '11', 'asset'),
    acc('2', 'بدهی‌ها', null, 'liability', true),
    acc('21', 'پرداختنی‌ها', '2', 'liability', true),
  ]
  calls = []
  reject = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (url.pathname === '/api/accounts') return json(server)
      if (url.pathname === '/api/accounting/accounts/reclassify') {
        const body = JSON.parse(String(init?.body))
        calls.push(body)
        if (reject) return json({ detail: reject }, 400)
        for (const it of body.items) server = server.map((r) => (r.id === it.account_id ? { ...r, parent_id: it.parent_id, type: it.type } : r))
        return json({ count: body.items.length, changed: [] })
      }
      return json([])
    }),
  )
}

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  setTenantScope('t1')
  sessionStorage.clear()
  stub()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  setTenantScope(null)
})

const settle = (ms = 0) =>
  act(async () => {
    await new Promise((r) => setTimeout(r, ms))
  })
async function render() {
  await act(async () => {
    root.render(createElement(ReclassifyPage, { token: 't' }))
  })
  await settle()
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.rx-sheet tbody tr')]
const codes = () => rows().map((r) => r.querySelector('td[data-label="کد"]')!.textContent)
const rowOf = (code: string) => rows().find((r) => r.querySelector('td[data-label="کد"]')!.textContent === code)!
const comboOf = (code: string) => rowOf(code).querySelector<HTMLInputElement>('[data-cell] input')!
const kindOf = (code: string) => rowOf(code).querySelector<HTMLElement>('td[data-label="نوع"]')!
const focused = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-cell]')?.dataset.cell
const foot = () => container.querySelector<HTMLElement>('.jf-foot')!
const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!

async function key(el: Element, code: string, init: KeyboardEventInit = {}) {
  await act(async () => {
    el.dispatchEvent(
      new KeyboardEvent('keydown', { key: code.startsWith('Key') ? code.slice(3).toLowerCase() : code, code, bubbles: true, cancelable: true, ...init }),
    )
  })
}
/** تایپ در کادرِ درجا و Enter — همان کاری که حسابدار می‌کند. */
async function pick(el: HTMLInputElement, text: string) {
  act(() => el.focus())
  act(() => {
    setValue.call(el, text)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await key(el, 'Enter')
  //: جلو رفتنِ گرید بعد از `requestAnimationFrame` است.
  await settle(40)
}
async function save() {
  await key(comboOf('51'), 'KeyS', { ctrlKey: true })
  await settle()
  await settle()
}

describe('انتقال حساب به سرفصل دیگر — برگه‌ی اکسلی', () => {
  it('ترتیبِ درختواره، بی حسابِ نقش‌دار؛ نوارِ سبز', async () => {
    await render()
    expect(codes()).toEqual(['1', '11', '1102', '2', '21', '5', '51'])
    expect(comboOf('1102').value).toBe('11 — موجودی نقد')
    expect(comboOf('1').value).toBe('— ریشه (بی‌سرفصل) —')
    expect(foot().className).toContain('jf-foot--ok')
  })

  it('سرفصلِ تازه با تایپ و Enter: ته‌رنگ، تغییرِ نوع، ردیفِ بعد؛ Ctrl+S یک درخواست', async () => {
    await render()
    await pick(comboOf('1102'), '21')
    expect(comboOf('1102').closest('td')!.className).toContain('is-changed')
    expect(rowOf('1102').className).toContain('xl-row--dirty')
    expect(kindOf('1102').textContent).toBe('دارایی ← بدهی')
    expect(focused()).toBe('3-0')
    expect(foot().className).toContain('jf-foot--warn')
    await save()
    expect(calls).toEqual([{ items: [{ account_id: '1102', parent_id: '21', type: 'liability' }] }])
    expect(foot().className).toContain('jf-foot--ok')
    expect(comboOf('1102').value).toBe('21 — پرداختنی‌ها')
    expect(sessionStorage.length).toBe(0)
  })

  it('سرفصلِ جابه‌جاشده زیرمجموعه‌اش را هم‌نوع می‌کند — پیش از ذخیره دیده می‌شود', async () => {
    await render()
    await pick(comboOf('11'), '5')
    expect(kindOf('11').textContent).toBe('دارایی ← هزینه')
    expect(kindOf('1102').textContent).toBe('دارایی ← هزینه')
    //: «تغییرِ نوع» صندوقِ پنهان را هم می‌شمارد (سه حساب)، ولی «n تغییر» فقط یک جابه‌جایی است.
    expect(foot().textContent).toContain('۱ تغییر')
    expect(foot().querySelector('.jb-stat--b')!.textContent).toContain('۳')
  })

  it('حلقه‌ای که دو ردیف با هم می‌سازند قرمز است و چیزی فرستاده نمی‌شود', async () => {
    await render()
    await pick(comboOf('2'), '11')
    await pick(comboOf('1'), '21')
    expect(rowOf('1').className).toContain('xl-row--error')
    expect(rowOf('2').className).toContain('xl-row--error')
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('حلقه')
    expect(foot().className).toContain('jf-foot--err')
    await save()
    expect(calls).toEqual([])
  })

  it('چند ردیف با هم زیرِ یک سرفصل، و Ctrl+Delete برمی‌گرداند', async () => {
    await render()
    await act(async () => rowOf('51').querySelector<HTMLButtonElement>('.xl-rowhead-btn')!.click())
    await act(async () => {
      rowOf('1102').querySelector<HTMLButtonElement>('.xl-rowhead-btn')!.dispatchEvent(new MouseEvent('click', { bubbles: true, ctrlKey: true }))
    })
    const bulk = container.querySelector<HTMLInputElement>('.xl-selbar .rx-bulk input')!
    await pick(bulk, '21')
    expect(comboOf('51').value).toBe('21 — پرداختنی‌ها')
    expect(comboOf('1102').value).toBe('21 — پرداختنی‌ها')
    expect(container.querySelector('.jf-foot')!.textContent).toContain('۲ تغییر')

    await key(comboOf('51'), 'Delete', { ctrlKey: true })
    expect(comboOf('51').value).toBe('5 — هزینه‌ها')
    expect(comboOf('1102').value).toBe('11 — موجودی نقد')
  })

  it('ردِ سرور: ردیفِ نام‌برده قرمز، جابه‌جایی می‌ماند؛ پیش‌نویس با برگشتن برمی‌گردد', async () => {
    await render()
    await pick(comboOf('51'), '11')
    reject = 'نوعِ «اجاره» با نوعِ سرفصلِ «موجودی نقد» نمی‌خواند'
    await save()
    expect(calls).toHaveLength(1)
    expect(rowOf('51').className).toContain('xl-row--error')
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('نمی‌خواند')
    expect(comboOf('51').value).toBe('11 — موجودی نقد')

    act(() => root.unmount())
    root = createRoot(container)
    await render()
    expect(comboOf('51').value).toBe('11 — موجودی نقد')
    expect(foot().textContent).toContain('دفعه‌ی قبل برگشت')
  })

  it('جست‌وجو سرفصلِ فعلی را هم می‌گردد', async () => {
    await render()
    const find = container.querySelector<HTMLInputElement>('.jg-find input')!
    act(() => {
      setValue.call(find, 'موجودی')
      find.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(codes()).toEqual(['11', '1102'])
  })
})
