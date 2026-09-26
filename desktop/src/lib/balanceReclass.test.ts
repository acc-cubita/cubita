import { describe, expect, it } from 'vitest'

import type { ReclassPreview, ReclassSource } from '../api'
import { destTotals, filterSources, itemsByKey, pickedBalance, reclassBody, sourceKey } from './balanceReclass'

const src = (account: string, code: string, name: string, balance: string, analytic?: [string, string, string]): ReclassSource => ({
  account_id: account,
  account_code: code,
  account_name: name,
  analytic_id: analytic?.[0] ?? null,
  analytic_code: analytic?.[1] ?? null,
  analytic_name: analytic?.[2] ?? null,
  balance,
  system_role: null,
})

const SOURCES = [
  src('a1', '1104', 'حساب‌های دریافتنی', '2000', ['t1', 'C1', 'شرکت آلفا']),
  src('a1', '1104', 'حساب‌های دریافتنی', '-500', ['t2', 'C2', 'شرکت بتا']),
  src('a2', '2101', 'حساب‌های پرداختنی', '-900'),
]

describe('انتقال مانده — منطقِ برگه', () => {
  it('کلید حساب و تفصیلی است — یک حساب با دو تفصیلی دو مبدأ است', () => {
    expect(SOURCES.map(sourceKey)).toEqual(['a1|t1', 'a1|t2', 'a2|'])
  })

  it('جست‌وجو روی کد و نامِ حساب و تفصیلی؛ «انتخاب‌شده‌ها» فقط انتخاب‌ها', () => {
    const none = new Set<string>()
    expect(filterSources(SOURCES, 'بتا', false, none).map(sourceKey)).toEqual(['a1|t2'])
    expect(filterSources(SOURCES, '۲۱۰۱', false, none).map(sourceKey)).toEqual(['a2|'])
    expect(filterSources(SOURCES, 'C1', false, none).map(sourceKey)).toEqual(['a1|t1'])
    expect(filterSources(SOURCES, '', true, new Set(['a2|'])).map(sourceKey)).toEqual(['a2|'])
  })

  it('بدنه به‌ترتیبِ فهرست است نه ترتیبِ کلیک؛ تفصیلیِ خالیِ مقصد null', () => {
    const body = reclassBody(SOURCES, new Set(['a2|', 'a1|t1']), { asOf: '2026-09-26', destAccountId: 'd', destAnalyticId: '', description: 'x' })
    expect(body).toEqual({
      as_of: '2026-09-26',
      sources: [
        { account_id: 'a1', analytic_id: 't1' },
        { account_id: 'a2', analytic_id: null },
      ],
      dest_account_id: 'd',
      dest_analytic_id: null,
      description: 'x',
    })
  })

  it('ردیف‌های پیش‌نمایش به کلیدِ مبدأ و جمعِ خطِ مقصد', () => {
    const preview = {
      items: [
        { account_id: 'a1', analytic_id: 't1', source_debit: '0', source_credit: '2000', dest_debit: '2000', dest_credit: '0' },
        { account_id: 'a2', analytic_id: null, source_debit: '900', source_credit: '0', dest_debit: '0', dest_credit: '900' },
      ],
    } as unknown as ReclassPreview
    expect([...itemsByKey(preview).keys()]).toEqual(['a1|t1', 'a2|'])
    expect(itemsByKey(null).size).toBe(0)
    expect(destTotals(preview)).toEqual({ debit: 2000, credit: 900 })
  })

  it('جمعِ مانده‌ی انتخاب با علامت (مثبت بدهکار)', () => {
    expect(pickedBalance(SOURCES, new Set(['a1|t1', 'a2|']))).toBe(1100)
    expect(pickedBalance(SOURCES, new Set())).toBe(0)
  })
})
