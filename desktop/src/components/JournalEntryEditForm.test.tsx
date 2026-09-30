// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchAccountsLive, fetchAnalytics, fetchCostCenters, updateJournalEntry, type JournalEntryRecord } from '../api'
import { JournalEntryEditForm } from './JournalEntryEditForm'

vi.mock('../api', () => ({
  fetchAccountsLive: vi.fn(), fetchAnalytics: vi.fn(), fetchCostCenters: vi.fn(), updateJournalEntry: vi.fn(),
}))

const entry: JournalEntryRecord = {
  id: 'entry-1', number: 12, atf_number: 20, sub_number: null, entry_date: '2026-09-29',
  updated_at: '2026-09-29T12:00:00Z', description: 'شرح اول', source_type: 'manual', source: null,
  status: 'permanent', voided_at: null, reverses_entry_id: null,
  lines: [
    { id: 'line-1', account_id: 'cash', account_code: '1101', account_name: 'صندوق', debit: '1000', credit: '0', description: 'بدهکار' },
    { id: 'line-2', account_id: 'income', account_code: '4101', account_name: 'درآمد', debit: '0', credit: '1000', description: 'بستانکار' },
  ],
}

let host: HTMLDivElement, root: Root
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  vi.mocked(fetchAccountsLive).mockResolvedValue([
    { id: 'cash', code: '1101', name: 'صندوق', type: 'asset', is_group: 0, parent_id: null, has_tracking: 0, accepts_tafsili: 0 },
    { id: 'income', code: '4101', name: 'درآمد', type: 'income', is_group: 0, parent_id: null, has_tracking: 0, accepts_tafsili: 0 },
  ])
  vi.mocked(fetchAnalytics).mockResolvedValue([])
  vi.mocked(fetchCostCenters).mockResolvedValue([])
  vi.mocked(updateJournalEntry).mockReset().mockResolvedValue(entry)
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(async () => { await act(() => root.unmount()); host.remove() })

function change(input: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value')!.set!
  setter.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

describe('فرم اصلاح سند ثبت‌شده', () => {
  it('سند دائم را فقط با دلیل ذخیره و شناسهٔ ردیف‌ها را حفظ می‌کند', async () => {
    const saved = vi.fn()
    await act(async () => { root.render(<JournalEntryEditForm token="test" entry={entry} onSaved={saved} onCancel={() => {}} />) })
    const save = [...host.querySelectorAll('button')].find((button) => button.textContent?.includes('ثبت اصلاح و تاریخچه'))!
    expect(save.hasAttribute('disabled')).toBe(true)
    const reason = host.querySelector('textarea')!
    await act(async () => change(reason, 'اصلاح پس از بررسی'))
    expect(save.hasAttribute('disabled')).toBe(false)
    await act(async () => { save.click() })
    expect(updateJournalEntry).toHaveBeenCalledWith('test', 'entry-1', expect.objectContaining({
      status: 'permanent', expected_updated_at: entry.updated_at, reason: 'اصلاح پس از بررسی',
      lines: expect.arrayContaining([expect.objectContaining({ id: 'line-1', account_id: 'cash' })]),
    }))
    expect(saved).toHaveBeenCalledOnce()
  })
})
