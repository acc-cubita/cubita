import { describe, expect, it } from 'vitest'

import type { JournalEntryRecord } from '../api'
import { defaultMergeDescription, entryTotal, mergeRows, mergedLines, mergedTotals, pickedDate } from './mergeSheet'

const line = (id: string, debit: number, credit: number) => ({ id, account_id: 'a', debit: String(debit), credit: String(credit), description: id })
const entry = (id: string, number: number, date: string, lines: ReturnType<typeof line>[], voided = false) =>
  ({ id, number, entry_date: date, voided_at: voided ? '2026-09-02' : null, lines }) as unknown as JournalEntryRecord

const E = [
  entry('x13', 13, '2026-09-01', [line('x13-1', 50, 0), line('x13-2', 0, 50)]),
  entry('x12', 12, '2026-09-01', [line('x12-1', 100, 0), line('x12-2', 0, 100)]),
  entry('y20', 20, '2026-09-02', [line('y20-1', 5, 0), line('y20-2', 0, 5)]),
  entry('z30', 30, '2026-09-03', [line('z30-1', 7, 0), line('z30-2', 0, 7)]),
  entry('z31', 31, '2026-09-03', [line('z31-1', 9, 0), line('z31-2', 0, 9)], true),
]

describe('ادغام اسناد — منطقِ برگه', () => {
  it('فقط روزهای دارای دست‌کم دو سندِ ابطال‌نشده؛ تازه‌ترین اول، سندها به‌ترتیبِ شماره', () => {
    expect(mergeRows(E).map((r) => (r.kind === 'day' ? `day:${r.date}:${r.count}` : r.entry.id))).toEqual(['day:2026-09-01:2', 'x12', 'x13'])
  })

  it('ردیف‌های سندِ ادغامی به‌ترتیبِ شماره‌ی سند، مثلِ سرور؛ جمع متوازن', () => {
    const picked = new Set(['x13', 'x12'])
    const lines = mergedLines(E, picked)
    expect(lines.map((l) => [l.entryNumber, l.line.id])).toEqual([
      [12, 'x12-1'],
      [12, 'x12-2'],
      [13, 'x13-1'],
      [13, 'x13-2'],
    ])
    expect(mergedTotals(lines)).toEqual({ debit: 150, credit: 150 })
    expect(pickedDate(E, picked)).toBe('2026-09-01')
    expect(pickedDate(E, new Set())).toBeNull()
  })

  it('مبلغِ سند و شرحِ پیش‌فرضِ سرور', () => {
    expect(entryTotal(E[1])).toBe(100)
    expect(defaultMergeDescription(E, new Set(['x13', 'x12']))).toBe('ادغامِ اسنادِ ۱۲، ۱۳')
    expect(defaultMergeDescription(E, new Set())).toBe('ادغامِ اسناد')
  })
})
