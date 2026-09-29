// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CubitaBridge, JournalOutboxEdit } from '../electron.d'
import { useJournalEntryDraft, type JournalEntryDraft } from './journalEntryDraft'

vi.mock('../platform', () => ({ isElectron: true, isEnterprise: false }))

const accounts = [
  { id: 'a', code: '1101', name: 'بانک', type: 'asset', is_group: 0, parent_id: null },
  { id: 'b', code: '2101', name: 'سرمایه', type: 'liability', is_group: 0, parent_id: null },
]
const lines = [{ accountId: 'a', debit: '100', credit: '' }, { accountId: 'b', debit: '', credit: '100' }]
const OPEN = { title: '۱۴۰۵', start_date: '2026-03-21', end_date: '2027-03-20', status: 'open' }
let years: unknown[]
let fiscalFailure: Error | null
let fiscalResponse: (() => Promise<Response>) | null
let draft: JournalEntryDraft
let container: HTMLDivElement
let root: Root
const queue = vi.fn()
const onQueued = vi.fn()

let editing: JournalOutboxEdit | undefined
const saved = vi.fn()
const onEdited = vi.fn()
function Harness() { draft = useJournalEntryDraft({ token: 't', accounts, onQueued, editing, onEdited }); return null }
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  queue.mockReset().mockResolvedValue('local-id')
  onQueued.mockReset()
  editing = undefined; saved.mockReset().mockResolvedValue({ state: 'synced', message: 'اصلاح شد' }); onEdited.mockReset()
  window.cubita = { queueJournalEntry: queue, saveJournalEdit: saved } as unknown as CubitaBridge
  years = [OPEN]
  fiscalFailure = null
  fiscalResponse = null
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const path = new URL(url).pathname
    if (path === '/api/fiscal-years') {
      if (fiscalFailure) throw fiscalFailure
      if (fiscalResponse) return fiscalResponse()
      return new Response(JSON.stringify(years))
    }
    return new Response(JSON.stringify(path === '/api/accounts/tafsili-mode' ? { mode: 'optional' } : []))
  }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  Reflect.deleteProperty(window, 'cubita')
  vi.unstubAllGlobals()
})
async function render() {
  await act(async () => { root.render(<Harness />) })
  // دسکتاپ عمداً پیش‌نویس را از localStorage نمی‌خواند؛ ورودی از setterهای واقعیِ فرم می‌آید.
  act(() => {
    draft.setDescription('سند آزمایشی')
    draft.setEntryDate('2026-09-28')
    lines.forEach((line, index) => draft.updateLine(index, line))
  })
}
async function submit() { let result = false; await act(async () => { result = await draft.submit() }); return result }

describe('ثبتِ دسکتاپ: سال مالی پیش از صف و پیش‌نویسِ محفوظ', () => {
  it('ویرایش اطلاعات اصلی را بارگذاری و همان شناسه را ذخیره می‌کند، نه queueJournalEntry', async () => {
    editing = { local_id: 'original', lease: 'lease', payload: JSON.stringify({ entry_date: '2025-07-08', description: 'قبلی', sub_number: 'A', lines: [
      { account_id: 'a', debit: 100, credit: 0, description: 'ردیف اول' }, { account_id: 'b', debit: 0, credit: 100 },
    ] }) }
    await act(async () => root.render(<Harness />))
    expect(draft.entryDate).toBe('2025-07-08'); expect(draft.description).toBe('قبلی'); expect(draft.lines[0].description).toBe('ردیف اول')
    expect(await submit()).toBe(false); expect(saved).not.toHaveBeenCalled(); expect(draft.message?.text).toContain('نسخه قبلی سند در صف حفظ شده')
    act(() => { draft.setEntryDate('2026-09-28'); draft.setDescription('اصلاح') })
    expect(await submit()).toBe(true)
    expect(saved).toHaveBeenCalledExactlyOnceWith('original', 'lease', expect.objectContaining({ entry_date: '2026-09-28', description: 'اصلاح', sub_number: 'A' }))
    expect(queue).not.toHaveBeenCalled(); expect(onEdited).toHaveBeenCalledOnce()
  })
  it('تاریخ معتبر یک‌بار وارد صف می‌شود و ورودی پاک می‌شود', async () => {
    await render()
    expect(await submit()).toBe(true)
    expect(queue).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ entry_date: '2026-09-28', description: 'سند آزمایشی' }))
    expect(draft.description).toBe('')
    expect(onQueued).toHaveBeenCalledOnce()
  })
  it('تاریخ خارج از سال مالی نه وارد صف می‌شود، نه پیش‌نویس را پاک می‌کند', async () => {
    years = [{ ...OPEN, end_date: '2026-03-22' }]
    await render()
    const originalLines = structuredClone(draft.lines)
    expect(await submit()).toBe(false)
    expect(queue).not.toHaveBeenCalled()
    expect(draft.description).toBe('سند آزمایشی')
    expect(draft.lines).toEqual(originalLines)
    expect(draft.entryDate).toBe('2026-09-28')
    expect(draft.message?.text).toContain('۱۴۰۵/۰۷/۰۶')
    expect(onQueued).not.toHaveBeenCalled()
  })
  it('سال بسته هم پیش از صف رد می‌شود', async () => {
    years = [{ ...OPEN, status: 'closed' }]
    await render()
    expect(await submit()).toBe(false)
    expect(queue).not.toHaveBeenCalled()
    expect(draft.message?.text).toContain('بسته است')
  })
  it('قطعی واقعی شبکه کارِ آفلاین را حفظ می‌کند و بررسیِ معوق را می‌گوید', async () => {
    fiscalFailure = new TypeError('Failed to fetch')
    await render()
    expect(await submit()).toBe(true)
    expect(queue).toHaveBeenCalledOnce()
    expect(draft.message?.text).toContain('هنگام «هم‌گام‌سازی» بررسی می‌شود')
  })
  it.each([401, 403, 500])('پاسخ %i آفلاین حساب نمی‌شود و پیش‌نویس می‌ماند', async (status) => {
    fiscalResponse = async () => new Response('{"detail":"دریافت سال مالی ناموفق است"}', { status })
    await render()
    expect(await submit()).toBe(false)
    expect(queue).not.toHaveBeenCalled()
    expect(draft.description).toBe('سند آزمایشی')
    expect(draft.message?.text).toBe('دریافت سال مالی ناموفق است')
  })
  it('دو Ctrl+S در انتظارِ سال مالی فقط یک سند صف می‌کند', async () => {
    let resolve!: (response: Response) => void
    fiscalResponse = () => new Promise<Response>((done) => { resolve = done })
    await render()
    await act(async () => {
      const first = draft.submit()
      const second = draft.submit()
      resolve(new Response(JSON.stringify([OPEN])))
      expect(await first).toBe(true)
      expect(await second).toBe(false)
    })
    expect(queue).toHaveBeenCalledOnce()
  })
})
