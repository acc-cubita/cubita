import type { ClosingPreview, ClosingRow, JournalEntryRecord, OpeningPreview } from '../api'

/**
 * منطقِ خالصِ «صدور سند اختتامیه و افتتاحیه» — پیش‌نمایشِ همان سندی که صادر می‌شود.
 *
 * ردیف‌ها، شرحشان و خطِ توازن («حساب اختتامیه» / «حساب افتتاحیه») همه از سرور است؛ این‌جا فقط کلید، برچسبِ نوع، حالِ
 * نوار و فهرستِ اختتامیه‌های مبنا برای افتتاحیه.
 */

export const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

export const closingRowKey = (r: Pick<ClosingRow, 'account_id' | 'analytic_id' | 'cost_center_id'>): string =>
  `${r.account_id}|${r.analytic_id ?? ''}|${r.cost_center_id ?? ''}`

/**
 * حالِ اختتامیه:
 * * `pnl-open` — درآمد و هزینه هنوز باز است؛ سرور صدور را رد می‌کند، پس صدور بسته می‌ماند؛
 * * `none` — هیچ حسابِ دائمیِ مانده‌داری نیست؛
 * * `ready` — سند آماده است.
 */
export type ClosingState = 'pnl-open' | 'none' | 'ready'

export function closingState(p: Pick<ClosingPreview, 'rows' | 'open_pnl_total'>): ClosingState {
  if (Number(p.open_pnl_total) !== 0) return 'pnl-open'
  return p.rows.length === 0 ? 'none' : 'ready'
}

/**
 * حالِ افتتاحیه:
 * * `repeat` — از همین اختتامیه قبلاً افتتاحیه صادر شده؛ صدورِ دوباره هر مانده را دو برابر می‌کرد و سرور ۴۰۹ می‌دهد؛
 * * `order` — تاریخِ افتتاحیه بعد از اختتامیه نیست (سرور رد می‌کند)؛
 * * `none` — اختتامیه‌ی مبنا ردیفی ندارد؛
 * * `ready` — سند آماده است.
 */
export type OpeningState = 'repeat' | 'order' | 'none' | 'ready'

export function openingState(p: Pick<OpeningPreview, 'rows' | 'existing_opening_number' | 'as_of' | 'source_date'>): OpeningState {
  if (p.existing_opening_number != null) return 'repeat'
  if (p.source_date >= p.as_of) return 'order'
  return p.rows.length === 0 ? 'none' : 'ready'
}

export interface ClosingOption {
  id: string
  date: string
  number: number | null
}

/** اختتامیه‌های مبنا برای افتتاحیه: فقط ابطال‌نشده‌ها، تازه‌ترین اول. */
export function closingOptions(entries: readonly Pick<JournalEntryRecord, 'id' | 'entry_date' | 'number' | 'voided_at' | 'source_type'>[]): ClosingOption[] {
  return entries
    .filter((e) => e.source_type === 'closing_entry' && !e.voided_at)
    .map((e) => ({ id: e.id, date: e.entry_date, number: e.number }))
    .sort((a, b) => (a.date === b.date ? (b.number ?? 0) - (a.number ?? 0) : a.date < b.date ? 1 : -1))
}

/** روزِ بعد از یک تاریخِ ISO — پیش‌فرضِ تاریخِ افتتاحیه، روزِ بعد از اختتامیه‌ی مبنا. */
export function nextDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}
