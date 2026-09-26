import type { Cartable, EntrySummary } from '../api'
import { normalizeSearch } from './accountTree'

/**
 * منطقِ خالصِ «کارتابل اسناد موقت» — صفِ اسنادِ موقتی که باید بازبینی و دائم شوند.
 *
 * سه راهِ دائم‌کردن همان سه تصمیمِ واقعی‌اند و هر کدام بدنه‌ی خودش را دارد: سندهای **انتخابی** (شناسه‌ها)، **یک منشأ**
 * در بازه («همه‌ی فاکتورهای فروشِ این ماه درست‌اند») و **کلِ بازه** (بستنِ ماه). سرور فقط ۲۰۰ سندِ اول را می‌فرستد؛
 * شمارِ کامل در `total_count` است و رابط باید بریدگی را بگوید.
 */

export type FinalizeBody = { date_from?: string; date_to?: string; entry_ids?: string[]; source_type?: string }

/** شماره، عطف، فرعی، شرح و حساب‌ها؛ رقمِ فارسی، ی/ك عربی و نیم‌فاصله یکی‌اند. شماره‌ی سند برابر پیدا می‌شود. */
export function filterCartable(
  entries: readonly EntrySummary[],
  source: string | null,
  query: string,
): EntrySummary[] {
  const q = normalizeSearch(query)
  return entries.filter((e) => {
    if (source && e.source_type !== source) return false
    if (!q) return true
    if (e.number != null && String(e.number) === q) return true
    if (e.atf_number != null && String(e.atf_number) === q) return true
    return [e.sub_number ?? '', e.description, ...e.accounts].some((t) => normalizeSearch(t).includes(q))
  })
}

/** جمعِ سندهای انتخاب‌شده — نوارِ پایین. */
export function pickedTotals(entries: readonly EntrySummary[], picked: ReadonlySet<string>): { count: number; total: number } {
  return entries.reduce(
    (t, e) => (picked.has(e.id) ? { count: t.count + 1, total: t.total + Number(e.total || 0) } : t),
    { count: 0, total: 0 },
  )
}

/** سرور همه را نفرستاده؟ (سقفِ ۲۰۰ سند) */
export const isTruncated = (data: Pick<Cartable, 'total_count' | 'entries'>): boolean => data.total_count > data.entries.length

/** بدنه‌ی «دائم‌کردنِ یک منشأ» یا «کلِ بازه» — منشأ خالی یعنی کلِ بازه. */
export function scopeBody(range: { from?: string; to?: string }, source: string | null): FinalizeBody {
  return { date_from: range.from, date_to: range.to, ...(source ? { source_type: source } : {}) }
}
