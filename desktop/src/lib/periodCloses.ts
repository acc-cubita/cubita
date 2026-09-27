import type { FiscalPeriodCloseRecord } from '../api'

/**
 * منطقِ خالصِ «دوره‌های بسته‌شده».
 *
 * هر قفل بازه‌ای را می‌بندد که از **روزِ بعد از قفلِ قبلی** شروع می‌شود (اولی از ابتدای دفتر) — همان قاعده‌ی
 * `pnl_close_preview`ِ سرور. آخرین قفل مرزِ ثبتِ سند است: هیچ سندی تا آن تاریخ ثبت یا اصلاح نمی‌شود.
 */

export interface CloseRow extends FiscalPeriodCloseRecord {
  /** شروعِ بازه‌ی این قفل: روزِ بعد از قفلِ قبلی، یا `null` یعنی ابتدای دفتر. */
  from: string | null
  /** آخرین قفل — مرزِ ثبتِ سند. */
  latest: boolean
}

const nextDay = (iso: string): string => {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

/** ردیف‌ها تازه‌ترین اول، هر کدام با شروعِ بازه‌اش. */
export function closeRows(records: readonly FiscalPeriodCloseRecord[]): CloseRow[] {
  const asc = [...records].sort((a, b) => (a.closing_date < b.closing_date ? -1 : a.closing_date > b.closing_date ? 1 : 0))
  return asc
    .map((r, i) => ({ ...r, from: i === 0 ? null : nextDay(asc[i - 1].closing_date), latest: i === asc.length - 1 }))
    .reverse()
}

/** جمعِ سود/زیانِ خالصِ همه‌ی دوره‌ها (مثبت = سود). */
export const profitTotal = (records: readonly Pick<FiscalPeriodCloseRecord, 'net_profit'>[]): number =>
  records.reduce((s, r) => s + Number(r.net_profit || 0), 0)
