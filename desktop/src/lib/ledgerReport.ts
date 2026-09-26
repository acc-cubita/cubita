import type { GeneralLedger, GeneralLedgerLine, JournalEntryRecord } from '../api'

/**
 * منطقِ خالصِ «گزارش دفتر» — ردیف‌های گریدِ روزنامه، ستون‌های اختیاریِ دفترِ حساب، جمعِ انتخاب و CSV.
 *
 * روزنامه **یک گرید** است نه یک کارت به‌ازای هر سند: هر سند یک ردیفِ سرگروه (شماره، تاریخ، شرح، وضعیت) و زیرش
 * ردیف‌هایش. جمعِ بازه همیشه از `/summary`ِ سرور است، نه از ردیف‌های بارگذاری‌شده.
 */

export type DaybookRow =
  | { kind: 'entry'; entry: JournalEntryRecord }
  | { kind: 'line'; entry: JournalEntryRecord; line: JournalEntryRecord['lines'][number]; index: number }

export function daybookRows(entries: readonly JournalEntryRecord[]): DaybookRow[] {
  return entries.flatMap((entry) => [
    { kind: 'entry' as const, entry },
    ...entry.lines.map((line, index) => ({ kind: 'line' as const, entry, line, index })),
  ])
}

/** ستون‌های ارز و پیگیری فقط وقتی ردیفی مقدار دارد — ستونِ همیشه‌خط‌تیره خواندن را سخت می‌کند. */
export function daybookColumns(entries: readonly JournalEntryRecord[]): { fx: boolean; tracking: boolean } {
  const lines = entries.flatMap((e) => e.lines)
  return { fx: lines.some((l) => l.currency_code), tracking: lines.some((l) => l.tracking_no) }
}

export interface LedgerColumns {
  /** در دفترِ کل و تفصیلی ردیف‌ها از حساب‌های مختلف‌اند؛ در معین همه یک حساب‌اند و ستون تکرار است. */
  account: boolean
  fx: boolean
  tracking: boolean
}

export function ledgerColumns(lines: readonly GeneralLedgerLine[], multiAccount: boolean): LedgerColumns {
  return {
    account: multiAccount,
    fx: lines.some((l) => l.currency_code),
    tracking: lines.some((l) => l.tracking_no),
  }
}

/** جمعِ گردشِ دوره: از سرور اگر فرستاده، وگرنه جمعِ ردیف‌ها (دفترِ بی‌صفحه‌بندی همه‌ی ردیف‌ها را دارد). */
export function ledgerPeriod(data: GeneralLedger): { debit: number; credit: number } {
  if (data.period_debit != null && data.period_credit != null)
    return { debit: Number(data.period_debit), credit: Number(data.period_credit) }
  return data.lines.reduce(
    (t, l) => ({ debit: t.debit + Number(l.debit || 0), credit: t.credit + Number(l.credit || 0) }),
    { debit: 0, credit: 0 },
  )
}

/** جمعِ بدهکار و بستانکار و خالصِ ردیف‌های انتخاب‌شده — نوارِ وضعیتِ اکسل. */
export function selectionSums(
  lines: readonly { debit: string; credit: string }[],
): { debit: number; credit: number; net: number } {
  const debit = lines.reduce((s, l) => s + Number(l.debit || 0), 0)
  const credit = lines.reduce((s, l) => s + Number(l.credit || 0), 0)
  return { debit, credit, net: debit - credit }
}

export function ledgerCsv(
  data: GeneralLedger,
  cols: LedgerColumns,
  formatDate: (iso: string) => string,
): { headers: string[]; rows: (string | number)[][] } {
  return {
    headers: [
      'شماره سند',
      'تاریخ',
      ...(cols.account ? ['حساب'] : []),
      'شرح',
      ...(cols.fx ? ['ارز', 'مبلغ ارزی'] : []),
      ...(cols.tracking ? ['شماره پیگیری', 'تاریخ پیگیری'] : []),
      'بدهکار',
      'بستانکار',
      'مانده',
    ],
    rows: [
      ['', '', ...(cols.account ? [''] : []), 'مانده‌ی ابتدای دوره', ...(cols.fx ? ['', ''] : []), ...(cols.tracking ? ['', ''] : []), '', '', Number(data.opening_balance)],
      ...data.lines.map((l) => [
        l.entry_number ?? '',
        formatDate(l.entry_date),
        ...(cols.account ? [`${l.account_code} — ${l.account_name}`] : []),
        l.description,
        ...(cols.fx ? [l.currency_code ?? '', l.fx_amount ? Number(l.fx_amount) : ''] : []),
        ...(cols.tracking ? [l.tracking_no ?? '', l.tracking_date ? formatDate(l.tracking_date) : ''] : []),
        Number(l.debit),
        Number(l.credit),
        Number(l.balance),
      ]),
    ],
  }
}
