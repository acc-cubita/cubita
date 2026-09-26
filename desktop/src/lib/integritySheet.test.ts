import { describe, expect, it } from 'vitest'

import type { IntegrityCheck, IntegrityRow } from '../api'
import { checkTone, integrityCsv, integritySummary, sheetRows, splitLabel, targetsOf } from './integritySheet'

const row = (label: string, extra: Partial<IntegrityRow> = {}): IntegrityRow => ({
  label,
  detail: '',
  debit: '0',
  credit: '0',
  difference: '0',
  ...extra,
})
const check = (key: string, severity: 'error' | 'warning', rows: IntegrityRow[], extra: Partial<IntegrityCheck> = {}): IntegrityCheck => ({
  key,
  title: `بررسیِ ${key}`,
  description: '',
  severity,
  ok: rows.length === 0,
  count: rows.length,
  rows,
  truncated: false,
  ...extra,
})

const CHECKS: IntegrityCheck[] = [
  check('unbalanced', 'error', [row('سند ۱۲', { entry_id: 'e12', debit: '100', credit: '90', difference: '10' }), row('سند ۱۳', { entry_id: 'e13' })]),
  check('leaves', 'error', []),
  check('empty', 'warning', [row('سند ۲', { entry_id: 'e2' })], { count: 60, truncated: true }),
  check('stale', 'warning', []),
]

describe('وضعیت و خلاصه', () => {
  it('سالم فقط بی‌یافته؛ وگرنه شدتِ خودِ بررسی', () => {
    expect(CHECKS.map(checkTone)).toEqual(['error', 'ok', 'warning', 'ok'])
  })

  it('خلاصه از شمارِ کاملِ سرور، نه ردیف‌های بریده', () => {
    expect(integritySummary(CHECKS)).toEqual({ errors: 1, warnings: 1, healthy: 2, findings: 62 })
  })
})

describe('ردیف‌های گرید', () => {
  it('سرگروهِ هر بررسی، یافته‌ها زیرش و «بقیه» برای بریده‌شده؛ خطا، بعد هشدار، بعد سالم', () => {
    const rows = sheetRows(CHECKS, { onlyFindings: false, closed: new Set() })
    expect(rows.map((r) => (r.kind === 'check' ? `${r.check.key}:${r.open ? 'open' : 'shut'}` : r.kind))).toEqual([
      'unbalanced:open',
      'finding',
      'finding',
      'empty:open',
      'finding',
      'more',
      'leaves:shut',
      'stale:shut',
    ])
  })

  it('هشدارِ اولِ سرور بعد از خطای آخرش می‌آید؛ هم‌رده‌ها ترتیبِ سرور را نگه می‌دارند', () => {
    const order = [CHECKS[3], CHECKS[2], CHECKS[1], CHECKS[0]]
    expect(sheetRows(order, { onlyFindings: false, closed: new Set(['unbalanced', 'empty']) }).map((r) => r.kind === 'check' && r.check.key)).toEqual([
      'unbalanced',
      'empty',
      'stale',
      'leaves',
    ])
  })

  it('«فقط یافته‌ها» سالم‌ها را برمی‌دارد و بستنِ سرگروه یافته‌هایش را', () => {
    const rows = sheetRows(CHECKS, { onlyFindings: true, closed: new Set(['unbalanced']) })
    expect(rows.map((r) => (r.kind === 'check' ? r.check.key : r.kind))).toEqual(['unbalanced', 'empty', 'finding', 'more'])
  })
})

describe('مقصدِ یافته', () => {
  it('سند، بعد کاردکس، بعد دفترِ حساب — با کد و نام از برچسب', () => {
    expect(targetsOf(row('سند ۱۲', { entry_id: 'e12' }))).toEqual([{ kind: 'entry', id: 'e12' }])
    expect(targetsOf(row('SKU-1 — پیچ — ریز', { item_id: 'i1', account_id: 'a1' }))).toEqual([
      { kind: 'item', id: 'i1', sku: 'SKU-1', name: 'پیچ — ریز' },
      { kind: 'account', id: 'a1', code: 'SKU-1', name: 'پیچ — ریز' },
    ])
    expect(targetsOf(row('فاکتورِ ۵'))).toEqual([])
  })

  it('برچسبِ بی «—» کد و نامِ یکسان می‌دهد', () => {
    expect(splitLabel('1101')).toEqual({ code: '1101', name: '1101' })
  })
})

describe('CSV', () => {
  it('هر یافته یک ردیف، بررسیِ سالم یک ردیفِ «بدونِ یافته»، و باقیِ بریده‌شده گفته می‌شود', () => {
    const { headers, rows } = integrityCsv(CHECKS)
    expect(headers).toEqual(['بررسی', 'شدت', 'مورد', 'توضیح', 'بدهکار', 'بستانکار', 'اختلاف'])
    expect(rows[0]).toEqual(['بررسیِ unbalanced', 'خطا', 'سند ۱۲', '', 100, 90, 10])
    expect(rows[2]).toEqual(['بررسیِ leaves', 'سالم', '', 'بدونِ یافته', '', '', ''])
    expect(rows[3][1]).toBe('هشدار')
    expect(rows[4][3]).toContain('و ۵۹ موردِ دیگر')
    expect(rows).toHaveLength(6)
  })
})
