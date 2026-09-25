/**
 * فیلترهای سرستونِ «اسناد حسابداری» باید به **سرور** برسند — نه روی ۳۰۰ سندِ بارشده اعمال شوند.
 * این‌جا فقط نام‌های پارامتر سنجیده می‌شود؛ معنای هرکدام را `test_journal_list_filters.py` قفل کرده.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchJournalEntriesFiltered } from './api'

let urls: string[] = []

beforeEach(() => {
  urls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      urls.push(String(url))
      return { ok: true, status: 200, json: async () => ({ items: [], next_cursor: null }) } as unknown as Response
    }),
  )
})
afterEach(() => vi.unstubAllGlobals())

const qs = () => new URL(urls[0], 'http://x').searchParams

describe('fetchJournalEntriesFiltered — فیلترهای ستونی', () => {
  it('شماره (بازه‌ی یک‌عددی)، عطف، فرعی، شرح و منشأ', async () => {
    await fetchJournalEntriesFiltered('t', { entryFrom: 151, entryTo: 151, atf: 149, sub: 'PR-7', desc: 'اجاره', sourceType: 'manual' })
    const p = qs()
    expect(p.get('entry_from')).toBe('151')
    expect(p.get('entry_to')).toBe('151')
    expect(p.get('atf')).toBe('149')
    expect(p.get('sub')).toBe('PR-7')
    expect(p.get('desc')).toBe('اجاره')
    expect(p.get('source_type')).toBe('manual')
  })

  it('فیلترِ خالی پارامتر نمی‌فرستد', async () => {
    await fetchJournalEntriesFiltered('t', { sub: '', desc: '' })
    const p = qs()
    for (const k of ['entry_from', 'entry_to', 'atf', 'sub', 'desc']) expect(p.has(k)).toBe(false)
  })
})
