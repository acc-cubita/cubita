import { describe, expect, it } from 'vitest'
import type { JournalEntryLine } from '../api'
import { entryAccountName, entryAmount, entryErrorText, entryTotals } from './entryPresentation'

const line = (debit: string, credit: string): JournalEntryLine => ({ id: 'l', account_id: 'a', debit, credit, description: '' })

describe('نمای سند بدون گردکردن داده', () => {
  it('ریال ۱۸رقمی و ارز چهاررقم‌اعشار را دقیق نشان می‌دهد', () => {
    expect(entryAmount('999999999999999999')).toBe(999999999999999999n.toLocaleString('fa-IR'))
    expect(entryAmount('1234.5678')).toBe('۱٬۲۳۴٫۵۶۷۸')
    expect(entryAmount('0.0100')).toBe('۰٫۰۱')
    expect(entryAmount('0', true)).toBe('—')
    expect(entryAmount('0')).toBe('۰')
    expect(entryAmount('-12.3456')).toBe('−۱۲٫۳۴۵۶') // مبلغِ ارزی علامت‌دار مجاز است.
  })
  it('جمعِ اعشاری و ارقام بزرگ خطای Number ندارند', () => {
    expect(entryTotals([line('0.1', '0'), line('0.2', '0'), line('0', '0.3')])).toEqual({
      debit: '۰٫۳', credit: '۰٫۳', difference: '۰', state: 'balanced',
    })
    const result = entryTotals([line('999999999999999998', '0'), line('1', '0'), line('0', '999999999999999999')])
    expect(result.state).toBe('balanced')
    expect(result.debit).toBe(entryAmount('999999999999999999'))
  })
  it('اختلاف، مبلغ خالی و دادهٔ نامعتبر توازن کاذب نمی‌سازند', () => {
    expect(entryTotals([line('10', '0'), line('0', '9.9')])).toMatchObject({ state: 'unbalanced', difference: '۰٫۱' })
    expect(entryTotals([]).state).toBe('empty')
    expect(entryTotals([line('0', '0')]).state).toBe('empty')
    expect(entryTotals([line('-1', '0')]).state).toBe('unknown')
    for (const invalid of ['NaN', '', '1.00001', '1e6']) {
      expect(entryTotals([line(invalid, '0')]).state).toBe('unknown')
      expect(entryAmount(invalid)).toBe('—')
    }
  })
  it('نام سرور اولویت دارد؛ چارت قبلی و نبودِ نام صریحاً پشتیبانی می‌شوند', () => {
    const row = line('1', '0'), names = new Map([['a', 'صندوق']])
    expect(entryAccountName({ ...row, account_name: 'بانک' }, names)).toBe('بانک')
    expect(entryAccountName(row, names)).toBe('صندوق')
    expect(entryAccountName({ ...row, account_name: ' ' }, names)).toBe('صندوق')
    expect(entryAccountName(row)).toBe('نام حساب در دسترس نیست')
  })
  it('خطای شبکه و پاسخ ناقص فارسی و خطای تاریخ شمسی است', () => {
    expect(entryErrorText(new TypeError('Failed to fetch'))).toContain('ارتباط با سرور برقرار نشد')
    expect(entryErrorText(new SyntaxError('Unexpected token'))).toContain('پاسخ سرور')
    expect(entryErrorText(new Error('خطا در 2026-09-29'))).toBe('خطا در ۱۴۰۵/۰۷/۰۷')
    expect(entryErrorText(null)).toContain('دریافت سند انجام نشد')
  })
})
