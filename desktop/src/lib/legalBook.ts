import type { LegalBookRow } from '../api'
import { normalizeSearch } from './accountTree'

/**
 * منطقِ خالصِ «دفاتر تجارت الکترونیک» — دفترِ روزنامه‌ی قانونی: یک ردیف به‌ازای هر ردیفِ سند.
 *
 * دو چیز این دفتر را از روزنامه‌ی «گزارش دفتر» جدا می‌کند و هر دو این‌جا تعریف می‌شوند:
 * * **شماره‌ی ردیفِ پیوسته** در کلِ دفترِ انتخاب‌شده (همه، دائم یا موقت). جست‌وجو فقط «پیدا کردن» است و شماره‌ی
 *   ردیف را عوض نمی‌کند؛ عوض‌شدنش یعنی ردیفِ ۱۲ در چاپ و در صفحه دو ردیفِ مختلف باشند.
 * * **شماره و تاریخِ سند فقط روی ردیفِ اولِ هر سند**، مثلِ دفترِ کاغذی — تکرارشان روی هر ردیف چشم را از حساب و مبلغ
 *   دور می‌کرد.
 */

export type LegalScope = 'all' | 'permanent' | 'temporary'

export const LEGAL_SCOPES: { key: LegalScope; label: string; hint: string }[] = [
  { key: 'all', label: 'همه', hint: 'همه‌ی اسناد، از جمله باطل‌شده‌ها و معکوسشان' },
  { key: 'permanent', label: 'دائم', hint: 'فقط اسنادِ دائم — همان چیزی که در دفترِ قانونی می‌نشیند' },
  { key: 'temporary', label: 'موقت', hint: 'اسنادی که هنوز دائم نشده‌اند' },
]

export interface LegalRow extends LegalBookRow {
  /** شماره‌ی ردیفِ دفتر، از ۱ و پیوسته در دفترِ انتخاب‌شده. */
  n: number
  /** اولین ردیفِ سندش در نمای فعلی: شماره و تاریخِ سند فقط این‌جا نوشته می‌شوند و مرزِ سند بالای آن است. */
  first: boolean
}

export const legalStatusText = (r: Pick<LegalBookRow, 'status' | 'voided'>): string =>
  r.voided ? 'باطل' : r.status === 'permanent' ? 'دائم' : 'موقت'

function matches(r: LegalBookRow, q: string): boolean {
  if (r.entry_number != null && String(r.entry_number) === q) return true
  return [r.account_code, r.account_name, r.description].some((t) => normalizeSearch(t).includes(q))
}

/**
 * ردیف‌های گرید: دفترِ دامنه (شماره‌گذاری)، بعد جست‌وجو، بعد نشانِ ردیفِ اولِ هر سند روی همان ردیف‌های دیده‌شده.
 *
 * شماره‌ی سند فقط **برابر** پیدا می‌شود نه «شاملِ»؛ وگرنه «۱» هر سندی را که ۱ در شماره‌اش دارد می‌آورد.
 */
export function legalRows(rows: readonly LegalBookRow[], scope: LegalScope, query: string): LegalRow[] {
  const inBook = scope === 'all' ? rows : rows.filter((r) => r.status === scope)
  const numbered = inBook.map((r, i) => ({ ...r, n: i + 1 }))
  const q = normalizeSearch(query)
  const found = q ? numbered.filter((r) => matches(r, q)) : numbered
  return found.map((r, i) => ({ ...r, first: i === 0 || found[i - 1].entry_id !== r.entry_id }))
}

export function legalTotals(rows: readonly Pick<LegalBookRow, 'debit' | 'credit'>[]): { debit: number; credit: number } {
  return rows.reduce(
    (t, r) => ({ debit: t.debit + Number(r.debit || 0), credit: t.credit + Number(r.credit || 0) }),
    { debit: 0, credit: 0 },
  )
}

/** جمعِ ریالی زیرِ نیم ریال اختلاف تراز است — خطای گردکردنِ جمعِ اعشاری نباید «ناتراز» خوانده شود. */
export const isBalanced = (t: { debit: number; credit: number }): boolean => Math.abs(t.debit - t.credit) < 0.5

export const entryCount = (rows: readonly Pick<LegalBookRow, 'entry_id'>[]): number =>
  new Set(rows.map((r) => r.entry_id)).size

/** خروجیِ CSV: همه‌ی ستون‌ها روی **هر** ردیف (فایل مرتب‌شدنی و فیلترشدنی بماند)، با شماره‌ی ردیفِ دفتر. */
export function legalCsv(
  rows: readonly LegalRow[],
  formatDate: (iso: string) => string,
): { headers: string[]; rows: (string | number)[][] } {
  return {
    headers: ['ردیف', 'شماره سند', 'تاریخ', 'کد حساب', 'نام حساب', 'شرح', 'بدهکار', 'بستانکار', 'وضعیت'],
    rows: rows.map((r) => [
      r.n,
      r.entry_number ?? '',
      formatDate(r.entry_date),
      r.account_code,
      r.account_name,
      r.description,
      Number(r.debit),
      Number(r.credit),
      legalStatusText(r),
    ]),
  }
}
