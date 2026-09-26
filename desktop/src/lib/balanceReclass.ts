import type { ReclassBody, ReclassItem, ReclassPreview, ReclassSource } from '../api'
import { normalizeSearch } from './accountTree'

/**
 * منطقِ خالصِ «انتقال مانده به حساب دیگر».
 *
 * برگه فهرستِ مبدأهاست (هر ترکیبِ حساب و تفصیلیِ مانده‌دار)؛ انتخابِ ردیف یعنی «این مانده منتقل شود». جهت و مبلغِ
 * سند از پیش‌نمایشِ سرور است (`reclass_preview` — جهت از خودِ مانده، نه از فرض)؛ این‌جا فقط کلید، جست‌وجو، بدنه‌ی
 * درخواست و جمعِ خطِ مقصد.
 */

/** کلیدِ ترکیبی، چون یک حساب می‌تواند با چند تفصیلی مانده داشته باشد. */
export const sourceKey = (r: { account_id: string; analytic_id: string | null }): string =>
  `${r.account_id}|${r.analytic_id ?? ''}`

/** کد و نامِ حساب و تفصیلی؛ رقمِ فارسی، ی/ك عربی و نیم‌فاصله یکی‌اند. */
export function filterSources(
  sources: readonly ReclassSource[],
  query: string,
  onlyPicked: boolean,
  picked: ReadonlySet<string>,
): ReclassSource[] {
  const q = normalizeSearch(query)
  return sources.filter(
    (s) =>
      (!onlyPicked || picked.has(sourceKey(s))) &&
      (!q ||
        [s.account_code, s.account_name, s.analytic_code ?? '', s.analytic_name ?? ''].some((t) =>
          normalizeSearch(t).includes(q),
        )),
  )
}

/** بدنه‌ی پیش‌نمایش و صدور — مبدأها به‌ترتیبِ فهرست، نه ترتیبِ کلیک، تا دو پیش‌نمایشِ یک انتخاب یکی باشند. */
export function reclassBody(
  sources: readonly ReclassSource[],
  picked: ReadonlySet<string>,
  opts: { asOf: string; destAccountId: string; destAnalyticId: string; description: string },
): ReclassBody {
  return {
    as_of: opts.asOf,
    sources: sources
      .filter((s) => picked.has(sourceKey(s)))
      .map((s) => ({ account_id: s.account_id, analytic_id: s.analytic_id })),
    dest_account_id: opts.destAccountId,
    dest_analytic_id: opts.destAnalyticId || null,
    description: opts.description,
  }
}

/** ردیف‌های پیش‌نمایش به کلیدِ مبدأ — خانه‌های بدهکار و بستانکارِ هر ردیفِ انتخاب‌شده از همین پر می‌شوند. */
export const itemsByKey = (preview: ReclassPreview | null): Map<string, ReclassItem> =>
  new Map((preview?.items ?? []).map((i) => [sourceKey(i), i]))

/** خطِ مقصد در سند یک ردیف به‌ازای هر مبدأ است؛ برگه جمعشان را در یک ردیف نشان می‌دهد. */
export function destTotals(preview: ReclassPreview): { debit: number; credit: number } {
  return preview.items.reduce(
    (t, i) => ({ debit: t.debit + Number(i.dest_debit || 0), credit: t.credit + Number(i.dest_credit || 0) }),
    { debit: 0, credit: 0 },
  )
}

/** جمعِ مانده‌ی ردیف‌های انتخاب‌شده (مثبت = بدهکار) — نوارِ انتخاب. */
export const pickedBalance = (sources: readonly ReclassSource[], picked: ReadonlySet<string>): number =>
  sources.reduce((s, r) => s + (picked.has(sourceKey(r)) ? Number(r.balance || 0) : 0), 0)
