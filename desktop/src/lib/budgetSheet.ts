import type { BudgetLineRecord } from '../api'
import { toNumber } from './csv'
import { isoToJalali } from './jalali'

/**
 * منطقِ خالصِ برگه‌ی «بودجه‌بندی» — ماتریسِ اکسلیِ حساب × دوازده ماهِ یک سالِ شمسی، برای کلِ کسب‌وکار یا
 * یک مرکزِ هزینه. بی DOM و بی React، تا مستقیم تست شود (همان الگوی `analyticsSheet.ts`).
 *
 * سرور هر خانه را یک ردیفِ بودجه می‌داند (حساب، اولِ ماه، مرکز) و `POST` روی همان ترکیب **upsert** است.
 * پس ذخیره‌ی برگه یعنی: خانه‌ای که عدد گرفت یا عوض شد → `POST`؛ خانه‌ای که خالی شد → `DELETE`ِ همان
 * ردیف. یادداشتِ ردیف (که ماتریس نشانش نمی‌دهد) در upsert همان که بود برمی‌گردد تا گم نشود.
 */
export const MONTHS = 12

export interface BudgetCell {
  id: string
  amount: number
  notes: string
}
export interface SavedRow {
  account_id: string
  code: string
  name: string
  /** دوازده خانه، فروردین تا اسفند. */
  cells: (BudgetCell | null)[]
}
export type FreshRow = { key: string; account_id: string; cells: string[] }
export interface BudgetDraft {
  /** دامنه‌ی پیش‌نویس — سال و مرکز. پیش‌نویسِ دامنه‌ی دیگر به این برگه نمی‌آید. */
  jy: number
  center: string
  /** ویرایشِ خانه‌های ردیف‌های ثبت‌شده: حساب → شماره‌ی ماه (۱ تا ۱۲) → متنِ خامِ کادر. */
  edits: Record<string, Record<string, string>>
  fresh: FreshRow[]
}

export const blankFresh = (key: string): FreshRow => ({ key, account_id: '', cells: Array(MONTHS).fill('') })
export const freshIsBlank = (r: FreshRow) => !r.account_id && r.cells.every((c) => !c.trim())
export const emptyDraft = (jy: number, center: string): BudgetDraft => ({ jy, center, edits: {}, fresh: [] })

/** ردیف‌های تازه با دقیقاً یک ردیفِ خالیِ ته (خالیِ وسط دست نمی‌خورد). */
export function withTrailingBlank(rows: readonly FreshRow[], make: () => FreshRow): FreshRow[] {
  const out = [...rows]
  while (out.length >= 2 && freshIsBlank(out[out.length - 1]) && freshIsBlank(out[out.length - 2])) out.pop()
  if (out.length === 0 || !freshIsBlank(out[out.length - 1])) out.push(make())
  return out
}

const inScope = (l: BudgetLineRecord, center: string) => (l.cost_center_id ?? '') === center

/**
 * ردیف‌های ثبت‌شده‌ی یک سال و یک دامنه، به ترتیبِ کدِ حساب. تاریخِ هر ردیف اولِ ماهِ شمسی است؛ اگر دو ردیف
 * به یک ماه بیفتند (ناممکن در این رابط، ممکن از راهِ دیگر)، اولی خانه را می‌گیرد.
 */
export function savedRows(lines: readonly BudgetLineRecord[], jy: number, center: string): SavedRow[] {
  const byAccount = new Map<string, SavedRow>()
  for (const l of lines) {
    if (!inScope(l, center)) continue
    const j = isoToJalali(l.period_date)
    if (j.jy !== jy) continue
    let row = byAccount.get(l.account_id)
    if (!row) {
      row = { account_id: l.account_id, code: l.account_code, name: l.account_name, cells: Array(MONTHS).fill(null) }
      byAccount.set(l.account_id, row)
    }
    if (!row.cells[j.jm - 1]) row.cells[j.jm - 1] = { id: l.id, amount: Number(l.amount), notes: l.notes }
  }
  return [...byAccount.values()].sort((a, b) => a.code.localeCompare(b.code, 'en', { numeric: true }))
}

/** سال‌هایی که بودجه دارند — برای انتخاب‌گرِ سال، کنارِ سال‌های پیرامونِ امسال. */
export function budgetYears(lines: readonly BudgetLineRecord[], around: number): number[] {
  const years = new Set([around - 1, around, around + 1])
  for (const l of lines) years.add(isoToJalali(l.period_date).jy)
  return [...years].sort((a, b) => a - b)
}

const amountText = (c: BudgetCell | null) => (c ? String(c.amount) : '')

/** متنِ فعلیِ یک خانه‌ی ردیفِ ثبت‌شده — ویرایش اگر هست، وگرنه مبلغِ ذخیره‌شده. `m` از ۰. */
export function cellText(row: SavedRow, m: number, draft: BudgetDraft): string {
  return draft.edits[row.account_id]?.[String(m + 1)] ?? amountText(row.cells[m])
}

/** آیا متنِ کادر با خانه‌ی ذخیره‌شده فرق دارد؟ خالی و «۰»ِ خانه‌ی بی‌ردیف یکی‌اند؛ خالی روی ردیفِ موجود یعنی حذف. */
export function cellChanged(orig: BudgetCell | null, raw: string): boolean {
  if (!raw.trim()) return orig !== null
  return orig === null ? toNumber(raw) !== 0 : toNumber(raw) !== orig.amount
}

export const rowTotal = (texts: readonly string[]) => texts.reduce((s, t) => s + toNumber(t), 0)

export type BudgetOp =
  | { kind: 'upsert'; account_id: string; month: number; amount: number; notes: string; isNew: boolean }
  | { kind: 'delete'; account_id: string; month: number; id: string }

/**
 * کارهای ذخیره به ترتیبِ برگه. `month` از ۱. ردیفِ تازه‌ی بی‌حساب یا تکراری این‌جا نمی‌آید — خطایش را
 * `sheetProblems` می‌گوید.
 */
export function pendingOps(saved: readonly SavedRow[], draft: BudgetDraft): BudgetOp[] {
  const ops: BudgetOp[] = []
  for (const row of saved) {
    const e = draft.edits[row.account_id]
    if (!e) continue
    for (let m = 0; m < MONTHS; m++) {
      const raw = e[String(m + 1)]
      if (raw === undefined) continue
      const orig = row.cells[m]
      if (!cellChanged(orig, raw)) continue
      if (!raw.trim()) ops.push({ kind: 'delete', account_id: row.account_id, month: m + 1, id: orig!.id })
      else ops.push({ kind: 'upsert', account_id: row.account_id, month: m + 1, amount: toNumber(raw), notes: orig?.notes ?? '', isNew: orig === null })
    }
  }
  const taken = new Set(saved.map((r) => r.account_id))
  for (const f of draft.fresh) {
    if (!f.account_id || taken.has(f.account_id)) continue
    taken.add(f.account_id)
    f.cells.forEach((raw, m) => {
      if (toNumber(raw) !== 0) ops.push({ kind: 'upsert', account_id: f.account_id, month: m + 1, amount: toNumber(raw), notes: '', isNew: true })
    })
  }
  return ops
}

/** شمارِ خانه‌های تازه و ویرایش/حذف‌شده — برای نوارِ پایین. */
export function pendingCount(saved: readonly SavedRow[], draft: BudgetDraft): { fresh: number; edited: number } {
  const ops = pendingOps(saved, draft)
  const fresh = ops.filter((o) => o.kind === 'upsert' && o.isNew).length
  return { fresh, edited: ops.length - fresh }
}

/** خطای ردیف‌های تازه پیش از ارسال، به کلیدِ ردیف: مبلغ بی‌حساب، یا حسابی که از قبل در برگه هست. */
export function sheetProblems(saved: readonly SavedRow[], draft: BudgetDraft, labelOf: (id: string) => string): Record<string, string> {
  const out: Record<string, string> = {}
  const taken = new Set(saved.map((r) => r.account_id))
  for (const f of draft.fresh) {
    if (freshIsBlank(f)) continue
    if (!f.account_id) out[f.key] = 'حساب را انتخاب کنید.'
    else if (taken.has(f.account_id)) out[f.key] = `«${labelOf(f.account_id)}» از قبل در برگه هست — همان ردیف را ویرایش کنید.`
    else taken.add(f.account_id)
  }
  return out
}

/** «تکرار در ماه‌های خالی»: هر ماهِ خالی اولین مبلغِ پرِ همان ردیف را می‌گیرد. ماهِ پر دست نمی‌خورد. */
export function fillEmptyMonths(texts: readonly string[]): string[] {
  const first = texts.find((t) => t.trim())
  return first === undefined ? [...texts] : texts.map((t) => (t.trim() ? t : first))
}

/**
 * «از سالِ قبل»: بودجه‌ی سالِ `fromJy` (همان دامنه) در خانه‌های **خالیِ** برگه‌ی فعلی می‌نشیند — ویرایش برای
 * ردیف‌های موجود، ردیفِ تازه برای حساب‌هایی که امسال ردیف ندارند. چیزی ذخیره نمی‌شود تا کاربر ببیند و بزند.
 */
export function copyFromYear(
  lines: readonly BudgetLineRecord[],
  fromJy: number,
  saved: readonly SavedRow[],
  draft: BudgetDraft,
  makeKey: () => string,
): { draft: BudgetDraft; filled: number } {
  const source = savedRows(lines, fromJy, draft.center)
  const edits: BudgetDraft['edits'] = { ...draft.edits }
  let fresh = draft.fresh.filter((f) => !freshIsBlank(f))
  const byAccount = new Map(saved.map((r) => [r.account_id, r]))
  let filled = 0
  for (const src of source) {
    const row = byAccount.get(src.account_id)
    if (row) {
      const e = { ...edits[row.account_id] }
      src.cells.forEach((c, m) => {
        if (c && !cellText(row, m, { ...draft, edits }).trim()) {
          e[String(m + 1)] = String(c.amount)
          filled++
        }
      })
      if (Object.keys(e).length) edits[row.account_id] = e
      continue
    }
    const existing = fresh.find((f) => f.account_id === src.account_id)
    const cells = existing ? [...existing.cells] : Array<string>(MONTHS).fill('')
    src.cells.forEach((c, m) => {
      if (c && !cells[m].trim()) {
        cells[m] = String(c.amount)
        filled++
      }
    })
    fresh = existing
      ? fresh.map((f) => (f === existing ? { ...f, cells } : f))
      : [...fresh, { key: makeKey(), account_id: src.account_id, cells }]
  }
  return { draft: { ...draft, edits, fresh: withTrailingBlank(fresh, () => blankFresh(makeKey())) }, filled }
}

/** پیش‌نویسِ خوانده‌شده از ذخیره‌ی نشست — هر شکلِ خرابی یعنی «هیچ». */
export function parseBudgetDraft(raw: string | null): BudgetDraft | null {
  if (!raw) return null
  try {
    const d = JSON.parse(raw) as BudgetDraft
    if (!d || typeof d !== 'object' || typeof d.jy !== 'number' || typeof d.center !== 'string') return null
    const edits = d.edits && typeof d.edits === 'object' ? d.edits : {}
    const fresh = Array.isArray(d.fresh)
      ? d.fresh.filter(
          (f) =>
            f &&
            typeof f.key === 'string' &&
            typeof f.account_id === 'string' &&
            Array.isArray(f.cells) &&
            f.cells.length === MONTHS &&
            f.cells.every((c) => typeof c === 'string'),
        )
      : []
    return { jy: d.jy, center: d.center, edits, fresh }
  } catch {
    return null
  }
}
