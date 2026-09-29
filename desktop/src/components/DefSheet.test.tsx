// @vitest-environment jsdom
/**
 * «برگه‌ی تعریف» (`DefSheet`) — همان قراردادِ برگه‌های اکسلیِ ویرایشِ درجا، یک‌جا برای هر داده‌ی پایه.
 *
 * * ته برگه همیشه یک ردیفِ خالی؛ تایپ در آن ردیفِ خالیِ بعدی را می‌آورد.
 * * خانه‌ی عوض‌شده ته‌رنگ می‌گیرد؛ «ذخیره» (Ctrl+S) فقط فیلدهای عوض‌شده را می‌فرستد، یکی‌یکی.
 * * ردیفِ ردشده از سرور ورودی‌اش را نگه می‌دارد و دلیلش زیرِ برگه می‌آید؛ بقیه ذخیره می‌شوند.
 * * سنجشِ پیش از ارسال درخواستی نمی‌فرستد. خانه‌ی قفل و حذفِ ناممکن غیرفعال‌اند و دلیلشان در `title`.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { Tag } from 'lucide-react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DefSheet, type DefCol, type DefSheetProps } from './DefSheet'
import type { DefSpec } from '../lib/defSheet'
import { setTenantScope } from '../lib/tenantScope'

type Rec = { id: string; name: string; code: string; is_active: boolean; used: number }

const SPEC: DefSpec = {
  text: ['name', 'code'],
  bools: ['is_active'],
  required: [{ field: 'name', label: 'نام' }],
  search: ['name', 'code'],
}
const COLS: DefCol<Rec>[] = [
  { id: 'name', label: 'نام', kind: 'text', field: 'name', enter: true },
  { id: 'code', label: 'کد', kind: 'text', field: 'code', w: '20%', lock: (r) => (r.used > 0 ? 'کدِ رکوردِ استفاده‌شده عوض نمی‌شود.' : null) },
  { id: 'used', label: 'استفاده', kind: 'ro', numeric: true, w: '12%', ro: (r) => (r ? String(r.used) : '—') },
  { id: 'active', label: 'وضعیت', kind: 'toggle', field: 'is_active', w: '10%' },
]
const ROWS: Rec[] = [
  { id: 'a', name: 'اول', code: 'A1', is_active: true, used: 0 },
  { id: 'b', name: 'دوم', code: 'B1', is_active: true, used: 3 },
]

let container: HTMLDivElement
let root: Root
type CreateFn = (v: Record<string, unknown>) => Promise<void>
type UpdateFn = (r: Rec, p: unknown) => Promise<void>
type RemoveFn = (r: Rec) => Promise<void>
let create: ReturnType<typeof vi.fn<CreateFn>>
let update: ReturnType<typeof vi.fn<UpdateFn>>
let remove: ReturnType<typeof vi.fn<RemoveFn>>
let order: string[]

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  setTenantScope('t1')
  sessionStorage.clear()
  localStorage.clear()
  order = []
  create = vi.fn<CreateFn>(async (v) => {
    order.push(`create:${v.name}`)
    if (v.name === 'تکراری') throw new Error('این نام از قبل هست')
  })
  update = vi.fn<UpdateFn>(async (r) => {
    order.push(`update:${r.id}`)
  })
  remove = vi.fn<RemoveFn>(async () => {})
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  setTenantScope(null)
})

async function render(extra: Partial<DefSheetProps<Rec>> = {}) {
  await act(async () => {
    root.render(
      createElement(DefSheet<Rec>, {
        sheetId: 'test',
        spec: SPEC,
        cols: COLS,
        autoCol: 'name',
        slots: [['num', 'name'], ['code'], ['used'], ['active'], ['actions']],
        rows: ROWS,
        error: null,
        reload: () => {},
        valuesOf: (r) => ({ ...r }),
        create: (v) => create(v),
        update: (r, p) => update(r, p),
        remove: (r) => remove(r),
        removeBlock: (r) => (r.used > 0 ? 'استفاده شده؛ غیرفعالش کنید.' : null),
        labelOf: (v) => String(v.name ?? ''),
        icon: Tag,
        title: 'آزمون',
        tip: '',
        unit: 'مورد',
        newPlaceholder: 'تازه…',
        findPlaceholder: 'جست‌وجو',
        ...extra,
      }),
    )
  })
}
const rows = () => [...container.querySelectorAll<HTMLTableRowElement>('.ds-sheet tbody tr')]
const cell = (row: number, col: number) => container.querySelector<HTMLElement>(`.ds-sheet [data-cell="${row}-${col}"]`)!
const input = (row: number, col: number) => cell(row, col).querySelector<HTMLInputElement>('input')!
const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
function type(el: HTMLInputElement, text: string) {
  act(() => el.focus())
  act(() => {
    setValue.call(el, text)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
async function save() {
  await act(async () => {
    container.querySelector('form')!.dispatchEvent(new KeyboardEvent('keydown', { key: 's', code: 'KeyS', ctrlKey: true, bubbles: true, cancelable: true }))
  })
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
}

describe('برگه‌ی تعریف', () => {
  it('ته برگه یک ردیفِ خالی؛ تایپ در آن ردیفِ خالیِ بعدی را می‌آورد', async () => {
    await render()
    expect(rows()).toHaveLength(3)
    expect(input(2, 0).placeholder).toBe('تازه…')
    type(input(2, 0), 'سوم')
    expect(rows()).toHaveLength(4)
    expect(rows()[2].className).toContain('xl-row--new')
  })

  it('خانه‌ی عوض‌شده ته‌رنگ می‌گیرد و ذخیره فقط همان فیلد را می‌فرستد — ویرایش‌ها پیش از ساخت، یکی‌یکی', async () => {
    await render()
    type(input(0, 0), 'اولِ تازه')
    expect(cell(0, 0).className).toContain('is-changed')
    expect(rows()[0].className).toContain('xl-row--dirty')
    type(input(2, 0), 'سوم')
    type(input(2, 1), 'C1')
    await save()
    expect(update).toHaveBeenCalledWith(ROWS[0], { name: 'اولِ تازه' })
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ name: 'سوم', code: 'C1' }))
    expect(order).toEqual(['update:a', 'create:سوم'])
  })

  it('ردیفِ ردشده ورودی‌اش را نگه می‌دارد و دلیلش زیرِ برگه است؛ بقیه ذخیره می‌شوند', async () => {
    await render()
    type(input(2, 0), 'تکراری')
    type(input(3, 0), 'درست')
    await save()
    expect(create).toHaveBeenCalledTimes(2)
    const bad = rows().find((r) => r.className.includes('xl-row--error'))!
    expect(bad.querySelector('input')!.value).toBe('تکراری')
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('این نام از قبل هست')
  })

  it('سنجشِ پیش از ارسال درخواستی نمی‌فرستد', async () => {
    const check = vi.fn(() => 'کد لازم است.')
    await render({ check })
    type(input(2, 1), 'Z9')
    await save()
    //: نامِ خالی اول گفته می‌شود (فیلدِ لازمِ spec)، و `check` فقط بعد از آن.
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('نام را وارد کنید.')
    type(input(2, 0), 'چهارم')
    await save()
    expect(container.querySelector('.xl-errbar')!.textContent).toContain('کد لازم است.')
    expect(create).not.toHaveBeenCalled()
  })

  it('خانه‌ی قفل و حذفِ ناممکن غیرفعال‌اند و دلیلشان در title', async () => {
    await render()
    expect(input(1, 1).disabled).toBe(true)
    expect(cell(1, 1).title).toBe('کدِ رکوردِ استفاده‌شده عوض نمی‌شود.')
    expect(input(0, 1).disabled).toBe(false)
    const del = rows()[1].querySelector<HTMLButtonElement>('.card-actions button[aria-label="حذف ردیف"]')!
    expect(del.disabled).toBe(true)
    //: دکمه‌ی غیرفعال رویدادِ موس نمی‌گیرد؛ `RowAction` دلیل را روی پوسته‌اش می‌گذارد.
    expect(del.parentElement!.title).toBe('استفاده شده؛ غیرفعالش کنید.')
  })

  it('وضعیت با کلید عوض می‌شود و ردیفِ تازه همیشه «فعال» است', async () => {
    await render()
    const toggle = (row: number) => cell(row, 2).querySelector<HTMLButtonElement>('button')!
    expect(toggle(2).disabled).toBe(true)
    act(() => toggle(0).click())
    expect(toggle(0).getAttribute('aria-pressed')).toBe('false')
    await save()
    expect(update).toHaveBeenCalledWith(ROWS[0], { is_active: false })
  })

  it('پیش‌نویس در نشست می‌ماند و با سوارشدنِ دوباره برمی‌گردد', async () => {
    await render()
    type(input(0, 0), 'پیش‌نویس')
    act(() => root.unmount())
    root = createRoot(container)
    await render()
    expect(input(0, 0).value).toBe('پیش‌نویس')
    expect(container.textContent).toContain('تغییرهای ذخیره‌نشده‌ی دفعه‌ی قبل برگشت')
  })
})
