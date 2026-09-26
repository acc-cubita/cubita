import { describe, expect, it } from 'vitest'

import type { LegalBookRow } from '../api'
import { entryCount, isBalanced, legalCsv, legalRows, legalStatusText, legalTotals } from './legalBook'

const line = (entry: string, number: number, status: string, code: string, name: string, debit: string, credit: string, extra: Partial<LegalBookRow> = {}): LegalBookRow => ({
  entry_id: entry,
  entry_number: number,
  entry_date: '2026-04-01',
  status,
  voided: false,
  account_code: code,
  account_name: name,
  description: '',
  debit,
  credit,
  ...extra,
})

const BOOK: LegalBookRow[] = [
  line('e1', 1, 'permanent', '1101', 'صندوق', '500', '0'),
  line('e1', 1, 'permanent', '3101', 'سرمایه', '0', '500'),
  line('e2', 2, 'temporary', '5101', 'هزینه‌ی اجاره', '120', '0', { description: 'اجاره‌ی مهر' }),
  line('e2', 2, 'temporary', '1101', 'صندوق', '0', '120'),
  line('e3', 12, 'permanent', '1101', 'صندوق', '80', '0', { voided: true }),
  line('e3', 12, 'permanent', '4101', 'فروش', '0', '80', { voided: true }),
]

describe('legalRows — شماره‌ی ردیف و ردیفِ اولِ سند', () => {
  it('شماره‌ی ردیف پیوسته است و شماره و تاریخِ سند فقط روی ردیفِ اولِ هر سند', () => {
    const rows = legalRows(BOOK, 'all', '')
    expect(rows.map((r) => r.n)).toEqual([1, 2, 3, 4, 5, 6])
    expect(rows.map((r) => r.first)).toEqual([true, false, true, false, true, false])
  })

  it('دفترِ «دائم» از ۱ شماره می‌خورد — دفترِ جداست، نه فیلترِ همان ردیف‌ها', () => {
    const rows = legalRows(BOOK, 'permanent', '')
    expect(rows.map((r) => [r.entry_id, r.n])).toEqual([
      ['e1', 1],
      ['e1', 2],
      ['e3', 3],
      ['e3', 4],
    ])
    expect(legalRows(BOOK, 'temporary', '').map((r) => r.n)).toEqual([1, 2])
  })

  it('جست‌وجو شماره‌ی ردیف را نگه می‌دارد و ردیفِ اولِ سند را روی ردیف‌های دیده‌شده می‌گذارد', () => {
    const rows = legalRows(BOOK, 'all', 'صندوق')
    expect(rows.map((r) => [r.n, r.first])).toEqual([
      [1, true],
      [4, true],
      [5, true],
    ])
  })

  it('رقمِ فارسی، ی/ك عربی و نیم‌فاصله یکی‌اند؛ شرحِ ردیف هم جست‌وجو می‌شود', () => {
    expect(legalRows(BOOK, 'all', '۵۱۰۱').map((r) => r.n)).toEqual([3])
    expect(legalRows(BOOK, 'all', 'هزينه').map((r) => r.n)).toEqual([3])
    expect(legalRows(BOOK, 'all', 'اجاره‌ی مهر').map((r) => r.n)).toEqual([3])
  })

  it('شماره‌ی سند فقط برابر پیدا می‌شود، نه «شاملِ» — «۲» سندِ ۱۲ را نمی‌آورد', () => {
    expect(legalRows(BOOK, 'all', '۲').map((r) => r.entry_id)).toEqual(['e2', 'e2'])
    expect(legalRows(BOOK, 'all', '۱۲').map((r) => r.entry_id)).toEqual(['e3', 'e3'])
  })
})

describe('جمع، توازن، شمارِ سند و CSV', () => {
  it('جمعِ بدهکار و بستانکار و توازن با تحملِ نیم ریال', () => {
    const t = legalTotals(BOOK)
    expect(t).toEqual({ debit: 700, credit: 700 })
    expect(isBalanced(t)).toBe(true)
    expect(isBalanced({ debit: 700.3, credit: 700 })).toBe(true)
    expect(isBalanced({ debit: 701, credit: 700 })).toBe(false)
  })

  it('شمارِ اسناد از ردیف‌ها', () => {
    expect(entryCount(BOOK)).toBe(3)
    expect(entryCount([])).toBe(0)
  })

  it('وضعیت: باطل بر دائم و موقت می‌چربد', () => {
    expect(legalStatusText({ status: 'permanent', voided: true })).toBe('باطل')
    expect(legalStatusText({ status: 'permanent', voided: false })).toBe('دائم')
    expect(legalStatusText({ status: 'temporary', voided: false })).toBe('موقت')
  })

  it('CSV همه‌ی ستون‌ها را روی هر ردیف دارد، با شماره‌ی ردیفِ دفتر', () => {
    const { headers, rows } = legalCsv(legalRows(BOOK, 'permanent', ''), (d) => `j:${d}`)
    expect(headers).toEqual(['ردیف', 'شماره سند', 'تاریخ', 'کد حساب', 'نام حساب', 'شرح', 'بدهکار', 'بستانکار', 'وضعیت'])
    expect(rows[1]).toEqual([2, 1, 'j:2026-04-01', '3101', 'سرمایه', '', 0, 500, 'دائم'])
    expect(rows[2][8]).toBe('باطل')
  })
})
