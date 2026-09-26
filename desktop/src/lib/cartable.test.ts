import { describe, expect, it } from 'vitest'

import type { EntrySummary } from '../api'
import { filterCartable, isTruncated, pickedTotals, scopeBody } from './cartable'

const entry = (id: string, number: number, source: string, description: string, total: string, accounts: string[] = []): EntrySummary => ({
  id,
  number,
  atf_number: number + 100,
  sub_number: null,
  entry_date: '2026-09-01',
  description,
  source_type: source,
  status: 'temporary',
  voided_at: null,
  total,
  line_count: 2,
  accounts,
})

const ENTRIES = [
  entry('e1', 1, 'sales_invoice', 'فروشِ نقدی', '500', ['صندوق', 'فروش']),
  entry('e2', 12, 'manual', 'هزينه‌ی اجاره', '300', ['اجاره']),
  entry('e3', 21, 'sales_invoice', 'فروش اقساطی', '700', ['دریافتنی']),
]

describe('کارتابل — منطقِ برگه', () => {
  it('منشأ و جست‌وجو؛ شماره‌ی سند برابر پیدا می‌شود نه «شاملِ»', () => {
    expect(filterCartable(ENTRIES, 'sales_invoice', '').map((e) => e.id)).toEqual(['e1', 'e3'])
    expect(filterCartable(ENTRIES, null, '۱').map((e) => e.id)).toEqual(['e1'])
    expect(filterCartable(ENTRIES, null, 'هزینه اجاره').map((e) => e.id)).toEqual([])
    expect(filterCartable(ENTRIES, null, 'هزينه').map((e) => e.id)).toEqual(['e2'])
    expect(filterCartable(ENTRIES, null, 'دریافتنی').map((e) => e.id)).toEqual(['e3'])
    //: عطف هم برابر پیدا می‌شود.
    expect(filterCartable(ENTRIES, null, '112').map((e) => e.id)).toEqual(['e2'])
  })

  it('جمعِ انتخاب', () => {
    expect(pickedTotals(ENTRIES, new Set(['e1', 'e3']))).toEqual({ count: 2, total: 1200 })
    expect(pickedTotals(ENTRIES, new Set())).toEqual({ count: 0, total: 0 })
  })

  it('بریدگیِ سرور و بدنه‌ی دائم‌کردنِ منشأ یا کلِ بازه', () => {
    expect(isTruncated({ total_count: 250, entries: ENTRIES })).toBe(true)
    expect(isTruncated({ total_count: 3, entries: ENTRIES })).toBe(false)
    expect(scopeBody({ from: '2026-09-01', to: '2026-09-30' }, 'manual')).toEqual({
      date_from: '2026-09-01',
      date_to: '2026-09-30',
      source_type: 'manual',
    })
    expect(scopeBody({}, null)).toEqual({ date_from: undefined, date_to: undefined })
  })
})
