import type { JournalEntryLine } from '../api'
import { formatErrorDates, toFaDigits } from './jalali'

/** «دستی» نوعِ منشأ است، نه نامِ فرد؛ نام از هویت ذخیره‌شدهٔ خود سند می‌آید. */
export function manualCreatorText(entry: { source_type: string; created_by_name?: string | null }): string | null {
  if (entry.source_type !== 'manual') return null
  return `ثبت‌کننده: ${entry.created_by_name?.trim() || 'نام در دسترس نیست'}`
}

// فقط نمایش: Decimal سرور را به Number تبدیل نمی‌کنیم؛ ریال ۱۸رقمی و ارز با
// چهار رقم اعشار نباید در نمای سند گرد شوند یا توازنِ کاذب بسازند.
const SCALE = 10_000n

function parseAmount(value: string): bigint | null {
  if (!/^-?\d+(?:\.\d{1,4})?$/.test(value)) return null
  const negative = value.startsWith('-')
  const [whole, fraction = ''] = (negative ? value.slice(1) : value).split('.')
  const amount = BigInt(whole) * SCALE + BigInt(fraction.padEnd(4, '0'))
  return negative ? -amount : amount
}

function formatAmount(value: bigint): string {
  const absolute = value < 0n ? -value : value
  const whole = (absolute / SCALE).toLocaleString('fa-IR')
  const fraction = (absolute % SCALE).toString().padStart(4, '0').replace(/0+$/, '')
  const formatted = fraction ? `${whole}٫${toFaDigits(fraction)}` : whole
  return value < 0n ? `−${formatted}` : formatted
}

export function entryAmount(value: string | null | undefined, zeroAsDash = false): string {
  const amount = value == null ? null : parseAmount(value)
  return amount == null || (zeroAsDash && amount === 0n) ? '—' : formatAmount(amount)
}

export function entryTotals(lines: JournalEntryLine[]) {
  let debit = 0n
  let credit = 0n
  for (const line of lines) {
    const d = parseAmount(line.debit)
    const c = parseAmount(line.credit)
    if (d == null || c == null || d < 0n || c < 0n) {
      return { debit: '—', credit: '—', difference: '—', state: 'unknown' as const }
    }
    debit += d
    credit += c
  }
  const difference = debit >= credit ? debit - credit : credit - debit
  return {
    debit: formatAmount(debit),
    credit: formatAmount(credit),
    difference: formatAmount(difference),
    state: debit === 0n && credit === 0n ? 'empty' as const
      : difference === 0n ? 'balanced' as const : 'unbalanced' as const,
  }
}

export function entryAccountName(line: JournalEntryLine, names?: Map<string, string>): string {
  return line.account_name?.trim() || names?.get(line.account_id)?.trim() || 'نام حساب در دسترس نیست'
}

export function entryErrorText(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  if (/failed to fetch|fetch failed|networkerror|network request failed|ECONNREFUSED|ETIMEDOUT|timeout/i.test(message)) {
    return 'ارتباط با سرور برقرار نشد؛ اتصال شبکه و روشن‌بودن سرور را بررسی کنید و «تلاش دوباره» را بزنید.'
  }
  if (error instanceof SyntaxError) return 'پاسخ سرور برای نمایش سند خوانا نیست؛ دوباره تلاش کنید.'
  return formatErrorDates(message || 'دریافت سند انجام نشد؛ دوباره تلاش کنید.')
}
