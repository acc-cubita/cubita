// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchJournalEntry, type JournalEntryRecord } from '../api'
import { JournalEntryDrawer } from './JournalEntryDrawer'
vi.mock('../api', () => ({ fetchJournalEntry: vi.fn() }))
const fetchEntry = vi.mocked(fetchJournalEntry)
const sample = (id: string): JournalEntryRecord => ({ id, number: id === 'a' ? 1 : 2,
  entry_date: '2026-09-29', atf_number: 9, sub_number: null, description: `شرح ${id}`,
  source_type: 'manual', source: null, status: 'temporary', voided_at: null, reverses_entry_id: null, lines: [] })
let host: HTMLDivElement, opener: HTMLButtonElement, root: Root
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  fetchEntry.mockReset()
  host = document.createElement('div'); opener = document.createElement('button')
  document.body.append(opener, host); opener.focus(); root = createRoot(host)
})
afterEach(async () => { await act(() => root.unmount()); host.remove(); opener.remove() })
const flush = () => act(async () => { await Promise.resolve() })

describe('کشوی سند', () => {
  it('درخواست دیررس سند قبلی و دادهٔ مانده هنگام تعویض را نشان نمی‌دهد', async () => {
    let resolveA!: (entry: JournalEntryRecord) => void, resolveB!: (entry: JournalEntryRecord) => void
    fetchEntry.mockImplementation((_token, id) => new Promise((resolve) => { if (id === 'a') resolveA = resolve; else resolveB = resolve }))
    const render = (id: string) => act(async () => { root.render(<JournalEntryDrawer token="test" entryId={id} onClose={() => {}} />) })
    await render('a'); await render('b')
    await act(async () => { resolveA(sample('a')) })
    expect(document.body.textContent).not.toContain('شرح a')
    expect(document.querySelector('[role="status"]')).not.toBeNull()
    await act(async () => { resolveB(sample('b')) })
    expect(document.body.textContent).toContain('شرح b')
    await render('a')
    expect(document.body.textContent).not.toContain('شرح b')
  })
  it('خطا به شمسی، تلاش مجدد و aria-busy کار می‌کنند', async () => {
    fetchEntry.mockRejectedValueOnce(new Error('خطای دریافت در 2026-09-29')).mockResolvedValueOnce(sample('a'))
    await act(async () => { root.render(<JournalEntryDrawer token="test" entryId="a" onClose={() => {}} />) }); await flush()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('۱۴۰۵/۰۷/۰۷')
    const retry = [...document.querySelectorAll('button')].find((button) => button.textContent?.includes('تلاش دوباره'))!
    await act(async () => { retry.click() }); await flush()
    expect(fetchEntry).toHaveBeenCalledTimes(2)
    expect(document.activeElement?.getAttribute('aria-label')).toBe('بستن جزئیات سند')
    expect(document.querySelector('[role="alert"]')).toBeNull()
    expect(document.querySelector('[aria-busy="false"]')).not.toBeNull()
  })
  it('نام دسترس‌پذیر، محصورکردن فوکوس و Escape فقط همین کشو را می‌بندند', async () => {
    fetchEntry.mockResolvedValue(sample('a'))
    const close = vi.fn(), parentEscape = vi.fn()
    window.addEventListener('keydown', parentEscape)
    try {
      await act(async () => { root.render(<JournalEntryDrawer token="test" entryId="a" onClose={close} />) }); await flush()
      const dialog = document.querySelector('[role="dialog"]')!
      expect(document.getElementById(dialog.getAttribute('aria-labelledby')!)?.textContent).toBe('جزئیات سند حسابداری')
      expect(document.activeElement?.getAttribute('aria-label')).toBe('بستن جزئیات سند')
      await act(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })))
      expect(dialog.contains(document.activeElement)).toBe(true)
      parentEscape.mockClear()
      await act(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })))
      expect(close).toHaveBeenCalledOnce(); expect(parentEscape).not.toHaveBeenCalled()
      await act(() => root.render(null)); expect(document.activeElement).toBe(opener)
    } finally { window.removeEventListener('keydown', parentEscape) }
  })
})
