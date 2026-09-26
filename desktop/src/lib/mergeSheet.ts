import type { JournalEntryRecord } from '../api'

/**
 * منطقِ خالصِ «ادغام اسناد» — چند سندِ موقتِ دستیِ هم‌تاریخ در یک سند.
 *
 * سرور ردیف‌های اسنادِ انتخابی را **به‌ترتیبِ شماره‌ی سند** پشتِ هم می‌گذارد و چیزی جمع یا حذف نمی‌کند (`merge_entries`)؛
 * پس پیش‌نمایشِ سندِ ادغامی عیناً همین‌جا ساخته می‌شود. ادغام فقط میانِ هم‌تاریخ‌هاست، پس برگه بر اساسِ تاریخ دسته
 * می‌شود و روزهای تک‌سندی نمی‌آیند.
 */

export type MergeRow = { kind: 'day'; date: string; count: number } | { kind: 'entry'; entry: JournalEntryRecord }

/** روزهای دارای دست‌کم دو سندِ ابطال‌نشده، تازه‌ترین اول؛ هر روز یک سرگروه و سندهایش به‌ترتیبِ شماره. */
export function mergeRows(entries: readonly JournalEntryRecord[]): MergeRow[] {
  const byDate = new Map<string, JournalEntryRecord[]>()
  for (const e of entries) {
    if (e.voided_at) continue
    byDate.set(e.entry_date, [...(byDate.get(e.entry_date) ?? []), e])
  }
  return [...byDate.entries()]
    .filter(([, rows]) => rows.length > 1)
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .flatMap(([date, rows]) => [
      { kind: 'day' as const, date, count: rows.length },
      ...[...rows].sort((a, b) => (a.number ?? 0) - (b.number ?? 0)).map((entry) => ({ kind: 'entry' as const, entry })),
    ])
}

export const entryTotal = (e: Pick<JournalEntryRecord, 'lines'>): number =>
  e.lines.reduce((s, l) => s + Number(l.debit || 0), 0)

/** تاریخِ انتخاب — همه‌ی انتخاب‌ها هم‌تاریخ‌اند؛ سندِ روزِ دیگر تا انتخاب پاک نشود قفل است. */
export function pickedDate(entries: readonly JournalEntryRecord[], picked: ReadonlySet<string>): string | null {
  return entries.find((e) => picked.has(e.id))?.entry_date ?? null
}

export interface MergedLine {
  entryNumber: number | null
  line: JournalEntryRecord['lines'][number]
}

/** ردیف‌های سندِ ادغامی، همان ترتیبِ سرور: سندها به‌ترتیبِ شماره و ردیف‌های هر سند پشتِ هم. */
export function mergedLines(entries: readonly JournalEntryRecord[], picked: ReadonlySet<string>): MergedLine[] {
  return entries
    .filter((e) => picked.has(e.id))
    .sort((a, b) => (a.number ?? 0) - (b.number ?? 0))
    .flatMap((e) => e.lines.map((line) => ({ entryNumber: e.number, line })))
}

export function mergedTotals(lines: readonly MergedLine[]): { debit: number; credit: number } {
  return lines.reduce(
    (t, { line }) => ({ debit: t.debit + Number(line.debit || 0), credit: t.credit + Number(line.credit || 0) }),
    { debit: 0, credit: 0 },
  )
}

/** شرحِ پیش‌فرضِ سرور وقتی کاربر چیزی ننویسد: «ادغامِ اسنادِ ۱۲، ۱۳». */
export function defaultMergeDescription(entries: readonly JournalEntryRecord[], picked: ReadonlySet<string>): string {
  const numbers = entries
    .filter((e) => picked.has(e.id))
    .map((e) => e.number ?? 0)
    .sort((a, b) => a - b)
    .map((n) => n.toLocaleString('fa-IR', { useGrouping: false }))
  return numbers.length ? `ادغامِ اسنادِ ${numbers.join('، ')}` : 'ادغامِ اسناد'
}
