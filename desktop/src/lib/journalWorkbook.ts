import ExcelJS from 'exceljs'
import type { JournalEntryRecord } from '../api'
import { formatJalali } from './jalali'

const NAVY = '17233F'
const GOLD = 'FBC437'
const PALE = 'F3F5F9'
const INK = '233457'
const GREEN = 'E9F6EE'
const FORMAT = '#,##0;[Red](#,##0);–'

export interface JournalWorkbookOptions {
  period: string
  filters: string
  sourceLabel: (entry: JournalEntryRecord) => string
  accounts: Map<string, { code: string; name: string }>
  analytics: Map<string, string>
  centers: Map<string, string>
}

// Excel فقط ۱۵ رقم معنی‌دار نگه می‌دارد. مبلغِ بزرگ‌تر باید متن باشد تا
// خروجیِ «حرفه‌ای» عدد مالی را بی‌سروصدا گرد نکند.
export function excelAmount(value: string | number | bigint | null | undefined): number | string {
  const raw = String(value ?? '0')
  const number = Number(raw)
  const significantDigits = raw.replace(/^[+-]/, '').replace('.', '').replace(/^0+/, '').length
  return Number.isFinite(number) && significantDigits <= 15 && Math.abs(number) <= 999_999_999_999_999 ? number : raw
}

function baseSheet(book: ExcelJS.Workbook, name: string, columns: { header: string; width: number }[], period: string, filters: string) {
  const sheet = book.addWorksheet(name, {
    views: [{ state: 'frozen', ySplit: 7, rightToLeft: true, showGridLines: false }],
    pageSetup: { paperSize: 9, orientation: 'landscape', fitToPage: true, fitToWidth: 1, fitToHeight: 0,
      margins: { left: 0.25, right: 0.25, top: 0.5, bottom: 0.5, header: 0.2, footer: 0.2 } },
  })
  sheet.columns = columns.map(({ width }) => ({ width }))
  const last = columns.length
  sheet.mergeCells(1, 1, 2, last)
  const title = sheet.getCell(1, 1)
  title.value = `کوبیتا  |  گزارش ${name}`
  title.font = { name: 'Tahoma', size: 17, bold: true, color: { argb: 'FFFFFFFF' } }
  title.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${NAVY}` } }
  title.alignment = { horizontal: 'right', vertical: 'middle', indent: 1 }
  sheet.getRow(1).height = 24
  sheet.getRow(2).height = 20
  sheet.mergeCells(3, 1, 3, last)
  sheet.getCell(3, 1).value = `بازه: ${period}     |     فیلتر: ${filters}`
  sheet.getCell(3, 1).font = { name: 'Tahoma', size: 10, color: { argb: `FF${INK}` } }
  sheet.getCell(3, 1).alignment = { horizontal: 'right', vertical: 'middle' }
  sheet.getRow(3).height = 26
  sheet.mergeCells(4, 1, 4, last)
  sheet.getCell(4, 1).value = 'مبالغ به ریال · مبالغ بیش از ۱۵ رقم برای حفظ دقت به‌صورت متن صادر می‌شوند.'
  sheet.getCell(4, 1).font = { name: 'Tahoma', size: 9, italic: true, color: { argb: 'FF66738D' } }
  sheet.getCell(4, 1).alignment = { horizontal: 'right' }
  sheet.getRow(5).height = 28
  sheet.getRow(6).height = 12
  const header = sheet.getRow(7)
  header.values = columns.map((c) => c.header)
  header.height = 32
  header.eachCell((cell) => {
    cell.font = { name: 'Tahoma', size: 10, bold: true, color: { argb: `FF${NAVY}` } }
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${GOLD}` } }
    cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
    cell.border = { bottom: { style: 'medium', color: { argb: `FF${NAVY}` } } }
  })
  sheet.pageSetup.printTitlesRow = '1:7'
  sheet.headerFooter.oddFooter = '&Rصفحه &P از &N   |   کوبیتا'
  return sheet
}

function bodyRow(row: ExcelJS.Row, index: number, moneyColumns: number[]) {
  row.height = 24
  row.eachCell({ includeEmpty: true }, (cell) => {
    cell.font = { name: 'Tahoma', size: 10, color: { argb: `FF${INK}` } }
    cell.alignment = { horizontal: 'right', vertical: 'middle', wrapText: true }
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${index % 2 ? 'FFFFFF' : PALE}` } }
    cell.border = { bottom: { style: 'hair', color: { argb: 'FFE0E5ED' } } }
  })
  for (const col of moneyColumns) {
    const cell = row.getCell(col)
    cell.numFmt = FORMAT
    cell.alignment = { horizontal: 'left', vertical: 'middle' }
  }
}

/** هر سند در خلاصه یک سطر و هر ردیف واقعی در برگهٔ دوم؛ هیچ صفحه‌ای از فیلتر جا نمی‌ماند. */
export function createJournalWorkbook(entries: JournalEntryRecord[], options: JournalWorkbookOptions): ExcelJS.Workbook {
  const book = new ExcelJS.Workbook()
  book.creator = 'Cubita'
  book.subject = 'گزارش اسناد حسابداری'
  book.created = new Date()
  const summary = baseSheet(book, 'خلاصه اسناد', [
    { header: 'شماره سند', width: 15 }, { header: 'عطف', width: 13 }, { header: 'فرعی', width: 20 },
    { header: 'تاریخ شمسی', width: 17 }, { header: 'شرح سند', width: 38 }, { header: 'منشأ', width: 25 },
    { header: 'ثبت‌کننده', width: 25 }, { header: 'وضعیت', width: 13 }, { header: 'تعداد ردیف', width: 14 },
    { header: 'جمع بدهکار', width: 22 }, { header: 'جمع بستانکار', width: 22 },
  ], options.period, options.filters)
  const detail = baseSheet(book, 'ردیف‌های اسناد', [
    { header: 'شماره سند', width: 15 }, { header: 'عطف', width: 13 }, { header: 'تاریخ شمسی', width: 17 },
    { header: 'ردیف', width: 10 }, { header: 'کد حساب', width: 18 }, { header: 'نام حساب', width: 33 },
    { header: 'شرح ردیف', width: 35 }, { header: 'تفصیلی', width: 25 }, { header: 'مرکز هزینه', width: 25 },
    { header: 'بدهکار', width: 22 }, { header: 'بستانکار', width: 22 }, { header: 'ارز', width: 11 },
    { header: 'مبلغ ارزی', width: 18 }, { header: 'نرخ ارز', width: 18 }, { header: 'شماره پیگیری', width: 20 },
    { header: 'تاریخ پیگیری', width: 17 },
  ], options.period, options.filters)
  let detailIndex = 0
  let sumDebit = 0n, sumCredit = 0n
  for (const [index, entry] of entries.entries()) {
    const debit = entry.lines.reduce((acc, line) => acc + BigInt(line.debit), 0n)
    const credit = entry.lines.reduce((acc, line) => acc + BigInt(line.credit), 0n)
    sumDebit += debit; sumCredit += credit
    const row = summary.addRow([
      entry.number, entry.atf_number, entry.sub_number ?? '', formatJalali(entry.entry_date), entry.description,
      options.sourceLabel(entry), entry.created_by_name?.trim() || 'نام در دسترس نیست',
      entry.voided_at ? 'باطل' : entry.status === 'permanent' ? 'دائم' : 'موقت', entry.lines.length,
      excelAmount(debit), excelAmount(credit),
    ])
    bodyRow(row, index, [10, 11])
    for (const [lineIndex, line] of entry.lines.entries()) {
      const detailed = detail.addRow([
        entry.number, entry.atf_number, formatJalali(entry.entry_date), lineIndex + 1,
        line.account_code ?? options.accounts.get(line.account_id)?.code ?? '',
        line.account_name ?? options.accounts.get(line.account_id)?.name ?? line.account_id,
        line.description || '', line.analytic_name ?? options.analytics.get(line.analytic_id ?? '') ?? '',
        line.cost_center_name ?? options.centers.get(line.cost_center_id ?? '') ?? '',
        excelAmount(line.debit), excelAmount(line.credit), line.currency_code ?? '',
        line.fx_amount == null ? '' : excelAmount(line.fx_amount), line.fx_rate == null ? '' : excelAmount(line.fx_rate),
        line.tracking_no ?? '', line.tracking_date ? formatJalali(line.tracking_date) : '',
      ])
      bodyRow(detailed, detailIndex++, [10, 11, 13, 14])
    }
  }
  for (const [sheet, count, debitCol, creditCol] of [
    [summary, entries.length, 10, 11], [detail, detailIndex, 10, 11],
  ] as const) {
    const last = 7 + count
    if (count) sheet.autoFilter = { from: { row: 7, column: 1 }, to: { row: last, column: sheet.columnCount } }
    const total = sheet.getRow(last + 1)
    total.getCell(1).value = `جمع کل · ${entries.length.toLocaleString('fa-IR')} سند`
    total.getCell(debitCol).value = excelAmount(sumDebit)
    total.getCell(creditCol).value = excelAmount(sumCredit)
    total.height = 29
    total.eachCell({ includeEmpty: true }, (cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${GREEN}` } }
      cell.font = { name: 'Tahoma', bold: true, color: { argb: `FF${NAVY}` } }
      cell.alignment = { vertical: 'middle', horizontal: 'right' }
    })
    total.getCell(debitCol).numFmt = FORMAT
    total.getCell(creditCol).numFmt = FORMAT
    sheet.pageSetup.printArea = `A1:${sheet.getColumn(sheet.columnCount).letter}${last + 1}`
  }
  summary.getCell('A5').value = `تعداد اسناد: ${entries.length.toLocaleString('fa-IR')}    •    تعداد ردیف‌ها: ${detailIndex.toLocaleString('fa-IR')}`
  summary.getCell('A5').font = { name: 'Tahoma', size: 10, bold: true, color: { argb: `FF${NAVY}` } }
  return book
}

export async function downloadJournalWorkbook(filename: string, entries: JournalEntryRecord[], options: JournalWorkbookOptions) {
  const book = createJournalWorkbook(entries, options)
  const buffer = await book.xlsx.writeBuffer()
  const blob = new Blob([buffer as BlobPart], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.xlsx`
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
}
