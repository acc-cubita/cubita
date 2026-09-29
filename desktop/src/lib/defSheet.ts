import { textMatches } from './faText'

/**
 * منطقِ خالصِ «برگه‌ی تعریف» — ویرایشِ درجا به سبکِ اکسل با ذخیره‌ی یک‌جا، برای هر داده‌ی پایه‌ای که ردیف‌به‌ردیف
 * ساخته و ویرایش می‌شود (صندوق، حسابِ بانکی، کارتخوان، دسته‌چک، …).
 *
 * همان قراردادِ `analyticsSheet.ts`، فقط با فیلدهایی که هر برگه خودش اعلام می‌کند (`DefSpec`): ردیفِ **ثبت‌شده**
 * ویرایش‌هایش را در `edits` کنار نگه می‌دارد تا «ذخیره» بزند، ردیفِ **تازه** (`fresh`) هنوز سرور ندیده، و ته برگه
 * همیشه دقیقاً یک ردیفِ خالی هست. همه‌ی مقدارهای ویرایشی این‌جا **رشته**اند (شناسه‌ی خالی، تاریخِ خالی و عدد هم) —
 * تبدیل به بدنه‌ی API کارِ پیکربندیِ هر برگه است، نه این‌جا.
 *
 * بی DOM و بی React است تا مستقیم تست شود.
 */
//: مقدارهای ویرایشی رشته یا بولی‌اند؛ بقیه‌ی فیلدهای رکورد (کدِ تفصیلی، نامِ حساب، شمارش‌ها) هم کنارشان می‌مانند
//: تا جست‌وجو و برچسبِ ردیف از همان بخوانند. `str()` تهی و عدد را یکسان می‌خواند.
export type DefValues = Record<string, unknown>
export type FreshRow = { key: string } & Record<string, string>
export interface DefDraft {
  edits: Record<string, Partial<DefValues>>
  fresh: FreshRow[]
}

export interface DefSpec {
  /** فیلدهای رشته‌ایِ ویرایشی (متن، شناسه، تاریخ، عدد) — ردیفِ تازه همین‌ها را دارد. */
  text: readonly string[]
  /** فیلدهای بولیِ ویرایشی (مثلِ `is_active`) — فقط روی ردیفِ ثبت‌شده؛ ردیفِ تازه پیش‌فرضِ سرور را می‌گیرد. */
  bools?: readonly string[]
  /** فیلدهای عددی: `"0.00"` و `"0"` یکی‌اند و «تغییر» شمرده نمی‌شوند. */
  numeric?: readonly string[]
  /** مقدارِ پیش‌فرضِ ردیفِ تازه (مثلاً ارزِ `IRR`). ردیفی که فقط پیش‌فرض دارد «خالی» است. */
  defaults?: Readonly<Record<string, string>>
  /** فیلدهای لازم، به ترتیبِ پیام: «X را وارد کنید». */
  required?: readonly { field: string; label: string }[]
  /** فیلدهایی که جست‌وجوی برگه در آن‌ها می‌گردد. */
  search: readonly string[]
}

const str = (v: unknown) => (v === undefined || v === null ? '' : String(v))

export function blankFresh(spec: DefSpec, key: string): FreshRow {
  const row: FreshRow = { key } as FreshRow
  for (const f of spec.text) row[f] = spec.defaults?.[f] ?? ''
  return row
}

export function isBlank(spec: DefSpec, row: FreshRow): boolean {
  return spec.text.every((f) => str(row[f]).trim() === (spec.defaults?.[f] ?? '').trim())
}

/** ردیف‌های تازه با یک ردیفِ خالیِ ته — هرگز دو خالیِ پشتِ هم در انتها نمی‌ماند. خالی‌های وسط دست نمی‌خورند. */
export function withTrailingBlank(spec: DefSpec, fresh: readonly FreshRow[], makeKey: () => string): FreshRow[] {
  const out = [...fresh]
  while (out.length >= 2 && isBlank(spec, out[out.length - 1]) && isBlank(spec, out[out.length - 2])) out.pop()
  if (out.length === 0 || !isBlank(spec, out[out.length - 1])) out.push(blankFresh(spec, makeKey()))
  return out
}

/** یکی بودنِ دو مقدارِ یک فیلد، به زبانِ کاربر: فاصله‌ی دو سر مهم نیست و عددِ `"0.00"` همان `"0"` است. */
function same(spec: DefSpec, field: string, a: unknown, b: unknown): boolean {
  const x = str(a).trim()
  const y = str(b).trim()
  if (spec.numeric?.includes(field)) return (Number(x) || 0) === (Number(y) || 0)
  return x === y
}

/** فیلدهایی که واقعاً عوض شده‌اند (رشته‌ها trim شده). `null` = چیزی برای ذخیره نیست. */
export function patchOf(spec: DefSpec, original: DefValues, edit: Partial<DefValues> | undefined): Partial<DefValues> | null {
  if (!edit) return null
  const out: Partial<DefValues> = {}
  for (const f of spec.text) {
    const v = edit[f]
    if (v !== undefined && !same(spec, f, v, original[f])) out[f] = str(v).trim()
  }
  for (const f of spec.bools ?? []) {
    const v = edit[f]
    if (v !== undefined && Boolean(v) !== Boolean(original[f])) out[f] = Boolean(v)
  }
  return Object.keys(out).length > 0 ? out : null
}

/** آیا این خانه‌ی ثبت‌شده با نسخه‌ی سرور فرق دارد؟ (برای ته‌رنگِ `is-changed`.) */
export function cellChanged(spec: DefSpec, field: string, original: DefValues, current: DefValues): boolean {
  if (spec.bools?.includes(field)) return Boolean(original[field]) !== Boolean(current[field])
  return !same(spec, field, current[field], original[field])
}

/** خطای پیش از ارسال — اولین فیلدِ لازمِ خالی. */
export function problemOf(spec: DefSpec, values: DefValues): string | null {
  const missing = (spec.required ?? []).filter((r) => str(values[r.field]).trim() === '')
  if (missing.length === 0) return null
  return `${missing.map((m) => m.label).join(' و ')} را وارد کنید.`
}

/** جست‌وجوی سریع در فیلدهای `search` (رقم و حروفِ فارسی/عربی یکسان). */
export function matches(spec: DefSpec, values: DefValues, query: string): boolean {
  const q = query.trim()
  if (!q) return true
  return spec.search.some((f) => textMatches(str(values[f]), q))
}

/** شمارشِ تغییرهای ذخیره‌نشده، برای نوارِ پایین. */
export function pendingCount(
  spec: DefSpec,
  draft: DefDraft,
  saved: ReadonlyMap<string, DefValues>,
): { fresh: number; edited: number } {
  let edited = 0
  for (const [id, e] of Object.entries(draft.edits)) {
    const r = saved.get(id)
    if (r && patchOf(spec, r, e)) edited++
  }
  return { fresh: draft.fresh.filter((f) => !isBlank(spec, f)).length, edited }
}

/** پیش‌نویسِ خوانده‌شده از ذخیره‌ی نشست — هر شکلِ خرابی یعنی «هیچ»؛ ردیفِ ناقص کنار می‌رود. */
export function parseDraft(spec: DefSpec, raw: string | null): DefDraft | null {
  if (!raw) return null
  try {
    const d = JSON.parse(raw) as DefDraft
    if (!d || typeof d !== 'object' || !d.edits || typeof d.edits !== 'object' || Array.isArray(d.edits) || !Array.isArray(d.fresh)) {
      return null
    }
    const fresh = d.fresh.filter(
      (f): f is FreshRow => Boolean(f) && typeof f.key === 'string' && spec.text.every((k) => typeof f[k] === 'string'),
    )
    return { edits: d.edits, fresh }
  } catch {
    return null
  }
}

/** یک‌کلید را از نگاشت بردار — کمکیِ ذخیره و حذف. */
export function omit<T>(o: Record<string, T>, keys: readonly string[]): Record<string, T> {
  const out = { ...o }
  for (const k of keys) delete out[k]
  return out
}
