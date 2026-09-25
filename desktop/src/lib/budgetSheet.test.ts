/**
 * منطقِ برگه‌ی «بودجه‌بندی»: ماتریسِ حساب × ماه، کارهای ذخیره (upsert/حذف)، خطای ردیفِ تازه، پرکردن و
 * «از سالِ قبل»، و پیش‌نویس.
 */
import { describe, expect, it } from 'vitest'

import type { BudgetLineRecord } from '../api'
import {
  blankFresh,
  budgetYears,
  cellText,
  copyFromYear,
  emptyDraft,
  fillEmptyMonths,
  parseBudgetDraft,
  pendingCount,
  pendingOps,
  rowTotal,
  savedRows,
  sheetProblems,
  withTrailingBlank,
} from './budgetSheet'
import { jalaliToIso } from './jalali'

const line = (id: string, acc: string, code: string, jy: number, jm: number, amount: number, center: string | null = null, notes = ''): BudgetLineRecord => ({
  id,
  account_id: acc,
  account_code: code,
  account_name: `حساب ${code}`,
  account_type: 'expense',
  period_date: jalaliToIso(jy, jm, 1),
  amount: String(amount),
  notes,
  cost_center_id: center,
  cost_center_name: '',
})
const LINES = [
  line('a1', 'rent', '6201', 1405, 1, 500, null, 'قرارداد'),
  line('a2', 'rent', '6201', 1405, 2, 500),
  line('b1', 'salary', '6101', 1405, 1, 900),
  line('c1', 'rent', '6201', 1404, 12, 450),
  line('d1', 'rent', '6201', 1405, 1, 70, 'proj'),
]

describe('ماتریسِ یک سال و یک دامنه', () => {
  it('ردیف به حساب، به ترتیبِ کد؛ سالِ دیگر و مرکزِ دیگر بیرون', () => {
    const rows = savedRows(LINES, 1405, '')
    expect(rows.map((r) => r.code)).toEqual(['6101', '6201'])
    expect(rows[1].cells.slice(0, 3).map((c) => c?.amount ?? null)).toEqual([500, 500, null])
    expect(savedRows(LINES, 1405, 'proj')[0].cells[0]?.amount).toBe(70)
    expect(savedRows(LINES, 1404, '')[0].cells[11]?.amount).toBe(450)
  })

  it('سال‌های انتخاب‌گر: پیرامونِ امسال و هر سالی که بودجه دارد', () => {
    expect(budgetYears(LINES, 1406)).toEqual([1404, 1405, 1406, 1407])
  })
})

describe('کارهای ذخیره', () => {
  const saved = savedRows(LINES, 1405, '')
  const rent = saved.find((r) => r.account_id === 'rent')!

  it('عوض‌شده upsert با یادداشتِ قبلی، خالی‌شده حذف، خانه‌ی تازه upsertِ تازه، بی‌تغییر هیچ', () => {
    const draft = { ...emptyDraft(1405, ''), edits: { rent: { '1': '600', '2': '', '3': '500', '4': '0', '5': '' } } }
    expect(cellText(rent, 0, draft)).toBe('600')
    expect(cellText(rent, 5, draft)).toBe('')
    expect(pendingOps(saved, draft)).toEqual([
      { kind: 'upsert', account_id: 'rent', month: 1, amount: 600, notes: 'قرارداد', isNew: false },
      { kind: 'delete', account_id: 'rent', month: 2, id: 'a2' },
      { kind: 'upsert', account_id: 'rent', month: 3, amount: 500, notes: '', isNew: true },
    ])
    expect(pendingCount(saved, draft)).toEqual({ fresh: 1, edited: 2 })
  })

  it('ردیفِ تازه: هر ماهِ پر یک upsert؛ بی‌حساب یا تکراری نه، و خطایش گفته می‌شود', () => {
    const cells = Array(12).fill('')
    cells[0] = '100'
    cells[5] = '1,200'
    const draft = {
      ...emptyDraft(1405, ''),
      fresh: [
        { key: 'n1', account_id: 'fuel', cells },
        { key: 'n2', account_id: '', cells },
        { key: 'n3', account_id: 'rent', cells },
        blankFresh('n4'),
      ],
    }
    expect(pendingOps(saved, draft)).toEqual([
      { kind: 'upsert', account_id: 'fuel', month: 1, amount: 100, notes: '', isNew: true },
      { kind: 'upsert', account_id: 'fuel', month: 6, amount: 1200, notes: '', isNew: true },
    ])
    expect(sheetProblems(saved, draft, (id) => id)).toEqual({
      n2: 'حساب را انتخاب کنید.',
      n3: '«rent» از قبل در برگه هست — همان ردیف را ویرایش کنید.',
    })
  })
})

describe('کمک‌های برگه', () => {
  it('جمعِ ردیف با ارقامِ فارسی و جداکننده', () => {
    expect(rowTotal(['۱,۰۰۰', '500', ''])).toBe(1500)
  })

  it('تکرار در ماه‌های خالی از اولین مبلغِ پر', () => {
    expect(fillEmptyMonths(['', '50', '', '70'])).toEqual(['50', '50', '50', '70'])
    expect(fillEmptyMonths(['', ''])).toEqual(['', ''])
  })

  it('از سالِ قبل فقط خانه‌های خالی را پر می‌کند؛ حسابِ بی‌ردیف ردیفِ تازه می‌گیرد', () => {
    let n = 0
    const saved = savedRows(LINES, 1405, '')
    const prev = [...LINES, line('e1', 'salary', '6101', 1404, 1, 800), line('e2', 'tax', '6301', 1404, 3, 40)]
    const { draft, filled } = copyFromYear(prev, 1404, saved, emptyDraft(1405, ''), () => `k${++n}`)
    //: حقوقِ فروردین امسال ۹۰۰ دارد، پس دست نمی‌خورد؛ اجاره‌ی اسفند خالی بود و ۴۵۰ می‌گیرد.
    expect(draft.edits).toEqual({ rent: { '12': '450' } })
    expect(draft.fresh[0]).toMatchObject({ account_id: 'tax' })
    expect(draft.fresh[0].cells[2]).toBe('40')
    expect(freshCount(draft.fresh)).toBe(1)
    expect(filled).toBe(2)
  })

  it('همیشه یک ردیفِ خالیِ ته', () => {
    const out = withTrailingBlank([{ ...blankFresh('a'), account_id: 'x' }], () => blankFresh('z'))
    expect(out.map((r) => r.key)).toEqual(['a', 'z'])
  })

  it('پیش‌نویسِ خراب یعنی هیچ؛ ردیفِ بدشکل کنار می‌رود', () => {
    expect(parseBudgetDraft('{')).toBeNull()
    expect(parseBudgetDraft(JSON.stringify({ jy: 1405 }))).toBeNull()
    expect(parseBudgetDraft(JSON.stringify({ jy: 1405, center: '', edits: null, fresh: [{ key: 'a', account_id: '', cells: [] }] }))).toEqual(
      emptyDraft(1405, ''),
    )
  })
})

const freshCount = (rows: { account_id: string }[]) => rows.filter((r) => r.account_id).length
