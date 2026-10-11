import { describe, expect, it } from 'vitest'
import ExcelJS from 'exceljs'
import type { JournalEntryRecord } from '../api'
import { createJournalWorkbook, excelAmount } from './journalWorkbook'

const entry = (amount: string): JournalEntryRecord => ({
  id: 'e1', number: 7, atf_number: 19, sub_number: 'الف', entry_date: '2026-09-29',
  description: 'اصلاح موجودی', source_type: 'manual', source: null, created_by_name: 'مریم احمدی',
  status: 'permanent', voided_at: null, reverses_entry_id: null,
  lines: [
    { id: 'l1', account_id: 'a', account_code: '1101', account_name: 'صندوق', debit: amount, credit: '0', description: 'نقد' },
    { id: 'l2', account_id: 'b', debit: '0', credit: amount, description: 'طرف حساب', analytic_id: 'x' },
  ],
})
const options = {
  period: '۱۴۰۵/۰۷/۰۱ تا ۱۴۰۵/۰۷/۳۰', filters: 'وضعیت: دائم',
  sourceLabel: () => 'دستی', accounts: new Map([['b', { code: '4101', name: 'درآمد' }]]),
  analytics: new Map([['x', 'پروژه تهران']]), centers: new Map<string, string>(),
}

describe('خروجی واقعی اکسل اسناد', () => {
  it('دو برگهٔ راست‌به‌چپ، ردیف‌های سند، قالب چاپ و مبلغ عددی می‌سازد', async () => {
    const book = createJournalWorkbook([entry('12345123')], options)
    const binary = await book.xlsx.writeBuffer()
    const read = new ExcelJS.Workbook()
    await read.xlsx.load(binary)
    const summary = read.getWorksheet('خلاصه اسناد')!
    const detail = read.getWorksheet('ردیف‌های اسناد')!
    expect(summary.views[0].rightToLeft).toBe(true)
    expect(summary.views[0].state).toBe('frozen')
    expect(summary.getCell('A1').value).toContain('کوبیتا')
    expect(summary.getCell('A7').value).toBe('شماره سند')
    expect(summary.getCell('J8').value).toBe(12345123)
    expect(summary.getCell('J8').numFmt).toContain('#,##0')
    expect(summary.getCell('J9').value).toBe(12345123)
    expect(summary.autoFilter).toBeTruthy()
    expect(summary.pageSetup.printTitlesRow).toBe('1:7')
    expect(detail.getCell('F9').value).toBe('درآمد')
    expect(detail.getCell('H9').value).toBe('پروژه تهران')
    expect(detail.getCell('J8').value).toBe(12345123)
    expect(detail.getCell('K9').value).toBe(12345123)
  })

  it('مبالغ فراتر از دقت ۱۵ رقم Excel را به متنِ دقیق تبدیل می‌کند', () => {
    expect(excelAmount('123456789012345678')).toBe('123456789012345678')
    expect(excelAmount('1.1234567890123456')).toBe('1.1234567890123456')
    expect(excelAmount('120000')).toBe(120000)
    const book = createJournalWorkbook([entry('123456789012345678')], options)
    expect(book.getWorksheet('خلاصه اسناد')!.getCell('J8').value).toBe('123456789012345678')
  })
})
