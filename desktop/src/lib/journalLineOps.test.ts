import { describe, expect, it } from 'vitest'

import type { JournalDraftLine } from './journalEntryDraft'
import { copyPreviousInto, duplicateAt, remainingOf, removeAt, sumSide } from './journalLineOps'

const line = (p: Partial<JournalDraftLine> = {}): JournalDraftLine => ({
  accountId: '',
  debit: '',
  credit: '',
  fxAmount: '',
  trackingNo: '',
  trackingDate: '',
  analyticId: '',
  description: '',
  ...p,
})

describe('تکرارِ ردیف', () => {
  const rows = [
    line({ accountId: 'a1', debit: '1000', description: 'اجاره', analyticId: 'x' }),
    line({ accountId: 'a2', credit: '1000' }),
  ]

  it('رونوشت را **بلافاصله بعد از خودش** می‌گذارد، نه ته جدول', () => {
    const out = duplicateAt(rows, 0)
    expect(out).toHaveLength(3)
    expect(out[1].accountId).toBe('a1')
    expect(out[2].accountId).toBe('a2')
  })

  it('مبلغ را هم کپی می‌کند — تفاوتِ عمدی با «کپی از ردیف قبل»', () => {
    expect(duplicateAt(rows, 0)[1].debit).toBe('1000')
  })

  it('تفصیلی و شرح را هم می‌آورد', () => {
    const copy = duplicateAt(rows, 0)[1]
    expect(copy.analyticId).toBe('x')
    expect(copy.description).toBe('اجاره')
  })

  it('آرایه‌ی ورودی را تغییر نمی‌دهد', () => {
    duplicateAt(rows, 0)
    expect(rows).toHaveLength(2)
  })

  it('شاخصِ نامعتبر آرایه را دست‌نخورده برمی‌گرداند', () => {
    expect(duplicateAt(rows, 9)).toBe(rows)
  })
})

describe('کپی از ردیف قبل', () => {
  const rows = [
    line({ accountId: 'a1', analyticId: 'x', description: 'اجاره', debit: '5000' }),
    line({ accountId: '', credit: '' }),
  ]

  it('حساب، تفصیلی و شرح را می‌آورد', () => {
    const out = copyPreviousInto(rows, 1)
    expect(out[1].accountId).toBe('a1')
    expect(out[1].analyticId).toBe('x')
    expect(out[1].description).toBe('اجاره')
  })

  it('**مبلغ را نمی‌آورد** — عددِ جامانده بی‌صدا در سند می‌ماند', () => {
    expect(copyPreviousInto(rows, 1)[1].debit).toBe('')
    expect(copyPreviousInto(rows, 1)[1].credit).toBe('')
  })

  it('روی ردیفِ اول بی‌اثر است', () => {
    expect(copyPreviousInto(rows, 0)).toBe(rows)
  })

  it('ردیف‌های دیگر را دست نمی‌زند', () => {
    expect(copyPreviousInto(rows, 1)[0]).toEqual(rows[0])
  })
})

describe('حذف ردیف', () => {
  it('حذف می‌کند وقتی بیش از دو ردیف هست', () => {
    const rows = [line(), line(), line()]
    expect(removeAt(rows, 1)).toHaveLength(2)
  })

  it('کفِ دو ردیف را نگه می‌دارد — سندِ تک‌ردیفی معنا ندارد', () => {
    const rows = [line(), line()]
    expect(removeAt(rows, 0)).toBe(rows)
  })
})

describe('جمعِ هر طرف', () => {
  it('رشته‌ی خالی و نامعتبر صفر است', () => {
    const rows = [line({ debit: '100' }), line({ debit: '' }), line({ debit: 'خط' })]
    expect(sumSide(rows, 'debit')).toBe(100)
  })
})

describe('مبلغِ باقی‌مانده', () => {
  it('کمبودِ بستانکار را بستانکار می‌خواهد', () => {
    expect(remainingOf(20_000_000, 0)).toEqual({ amount: 20_000_000, side: 'credit' })
  })

  it('کمبودِ بدهکار را بدهکار می‌خواهد', () => {
    expect(remainingOf(0, 5_000)).toEqual({ amount: 5_000, side: 'debit' })
  })

  it('سندِ متوازن پیشنهادی ندارد', () => {
    expect(remainingOf(1000, 1000)).toBeNull()
  })

  it('سندِ خالی هم پیشنهادی ندارد', () => {
    expect(remainingOf(0, 0)).toBeNull()
  })

  it('سناریوی واقعیِ درخواست: بانک ۲۰٬۰۰۰٬۰۰۰ بدهکار → ردیف دوم همان را بستانکار می‌خواهد', () => {
    const rows = [line({ accountId: 'bank', debit: '20000000' }), line({ accountId: 'party' })]
    const r = remainingOf(sumSide(rows, 'debit'), sumSide(rows, 'credit'))
    expect(r).toEqual({ amount: 20_000_000, side: 'credit' })
  })
})
