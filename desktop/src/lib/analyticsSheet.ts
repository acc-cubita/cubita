import type { AnalyticAccount } from '../api'
import { textMatches } from './faText'

/**
 * منطقِ خالصِ برگه‌ی «تفصیلی سایر» — ویرایشِ درجا به سبکِ اکسل با ذخیره‌ی یک‌جا.
 *
 * برگه از دو جنس ردیف ساخته می‌شود: **ثبت‌شده** (از سرور) که ویرایش‌هایش در `edits` کنار می‌ماند تا
 * «ذخیره» بزند، و **تازه** (`fresh`) که هنوز سرور ندیده. زیرِ برگه همیشه یک ردیفِ خالی هست — همان
 * «ردیفِ تازه»ی جدول‌های داده: تایپ در آن ردیف می‌سازد و ردیفِ خالیِ بعدی خودش می‌آید.
 *
 * این‌جا بی DOM و بی React است تا مستقیم تست شود.
 */
export type Field = 'code' | 'name' | 'group_name' | 'description' | 'is_active'
export type Values = Pick<AnalyticAccount, Field>
export type FreshRow = { key: string; code: string; name: string; group_name: string; description: string }
export interface Draft {
  edits: Record<string, Partial<Values>>
  fresh: FreshRow[]
}

const TEXT: Exclude<Field, 'is_active'>[] = ['code', 'name', 'group_name', 'description']

export const blankFresh = (key: string): FreshRow => ({ key, code: '', name: '', group_name: '', description: '' })
export const isBlank = (r: FreshRow) => TEXT.every((f) => r[f].trim() === '')

/** ترتیبِ برگه: دسته، بعد کد — همان گروه‌بندیِ فهرستِ قبلی، ولی در یک جدول. بی‌دسته‌ها آخر. */
export function sortRows(rows: readonly AnalyticAccount[]): AnalyticAccount[] {
  return [...rows].sort(
    (a, b) =>
      Number(!a.group_name) - Number(!b.group_name) ||
      a.group_name.localeCompare(b.group_name, 'fa') ||
      a.code.localeCompare(b.code, 'fa', { numeric: true }),
  )
}

/** فیلدهایی که واقعاً عوض شده‌اند (متن با trim سنجیده می‌شود). `null` = چیزی برای ذخیره نیست. */
export function patchOf(original: Values, edit: Partial<Values> | undefined): Partial<Values> | null {
  if (!edit) return null
  const out: Partial<Values> = {}
  for (const f of TEXT) {
    const v = edit[f]
    if (v !== undefined && v.trim() !== original[f].trim()) out[f] = v.trim()
  }
  if (edit.is_active !== undefined && edit.is_active !== original.is_active) out.is_active = edit.is_active
  return Object.keys(out).length > 0 ? out : null
}

/** خطای پیش از ارسال — همان دو قاعده‌ی سرور (کد و نام خالی نباشند). */
export function problemOf(v: { code: string; name: string }): string | null {
  if (!v.code.trim() && !v.name.trim()) return 'کد و نام را وارد کنید.'
  if (!v.code.trim()) return 'کد را وارد کنید.'
  if (!v.name.trim()) return 'نام را وارد کنید.'
  return null
}

/** ردیف‌های تازه با یک ردیفِ خالیِ ته — هرگز دو خالیِ پشتِ هم در انتها نمی‌ماند. */
export function withTrailingBlank(fresh: readonly FreshRow[], makeKey: () => string): FreshRow[] {
  const out = [...fresh]
  while (out.length >= 2 && isBlank(out[out.length - 1]) && isBlank(out[out.length - 2])) out.pop()
  if (out.length === 0 || !isBlank(out[out.length - 1])) out.push(blankFresh(makeKey()))
  return out
}

/** جست‌وجوی سریع: کد، نام، دسته یا توضیح (رقم و حروفِ فارسی/عربی یکسان). */
export function matches(r: Values, query: string): boolean {
  const q = query.trim()
  if (!q) return true
  return TEXT.some((f) => textMatches(r[f], q))
}

/** شمارشِ تغییرهای ذخیره‌نشده، برای نوارِ پایین. */
export function pendingCount(draft: Draft, rows: readonly AnalyticAccount[]): { fresh: number; edited: number } {
  const byId = new Map(rows.map((r) => [r.id, r]))
  let edited = 0
  for (const [id, e] of Object.entries(draft.edits)) {
    const r = byId.get(id)
    if (r && patchOf(r, e)) edited++
  }
  return { fresh: draft.fresh.filter((f) => !isBlank(f)).length, edited }
}

/** پیش‌نویسِ خوانده‌شده از ذخیره‌ی نشست — هر شکلِ خرابی یعنی «هیچ». */
export function parseDraft(raw: string | null): Draft | null {
  if (!raw) return null
  try {
    const d = JSON.parse(raw) as Draft
    if (!d || typeof d !== 'object' || typeof d.edits !== 'object' || !Array.isArray(d.fresh)) return null
    const fresh = d.fresh.filter(
      (f): f is FreshRow => Boolean(f) && typeof f.key === 'string' && TEXT.every((k) => typeof f[k] === 'string'),
    )
    return { edits: d.edits ?? {}, fresh }
  } catch {
    return null
  }
}
