import type { Currency, ExchangeRate } from '../api'

/**
 * منطقِ خالصِ برگه‌های «ارزها» و «نرخ برابری» — ویرایشِ درجا به سبکِ اکسل با ذخیره‌ی یک‌جا (همان الگوی
 * برگه‌ی «تفصیلی سایر»، `analyticsSheet.ts`).
 *
 * سرور ارز را فقط می‌سازد و حذف می‌کند (ویرایش ندارد)، و نرخ را «ثبت یا جایگزین» می‌کند (ارز + تاریخ کلیدِ
 * یکتاست؛ حذف ندارد). پس در برگه: ارزِ ثبت‌شده فقط‌خواندنی است، در نرخِ ثبت‌شده فقط خودِ نرخ عوض می‌شود، و
 * زیرِ هر برگه یک ردیفِ خالی برای تازه‌ها. بی DOM و بی React، تا مستقیم تست شود.
 */
export type FreshCurrency = { key: string; code: string; name: string; symbol: string }
export type FreshRate = { key: string; currency_code: string; rate_date: string; rate: string }
export interface CurrencyDraft {
  currencies: FreshCurrency[]
  rates: FreshRate[]
  /** نرخِ تازه‌ی نرخ‌های ثبت‌شده، به شناسه. */
  edits: Record<string, string>
}

export const blankCurrency = (key: string): FreshCurrency => ({ key, code: '', name: '', symbol: '' })
export const blankRate = (key: string, date: string): FreshRate => ({ key, currency_code: '', rate_date: date, rate: '' })
export const currencyIsBlank = (c: FreshCurrency) => !c.code.trim() && !c.name.trim() && !c.symbol.trim()
//: تاریخِ ردیفِ تازه پیش‌فرضِ «امروز» را دارد — محتوا نیست.
export const rateIsBlank = (r: FreshRate) => !r.currency_code && !r.rate.trim()

/** ردیف‌های تازه با دقیقاً یک ردیفِ خالیِ ته (خالیِ وسط دست نمی‌خورد). */
export function withTrailingBlank<T>(rows: readonly T[], isBlank: (r: T) => boolean, make: () => T): T[] {
  const out = [...rows]
  while (out.length >= 2 && isBlank(out[out.length - 1]) && isBlank(out[out.length - 2])) out.pop()
  if (out.length === 0 || !isBlank(out[out.length - 1])) out.push(make())
  return out
}

/** نرخ‌ها به ترتیبِ زمان، مثلِ دفتر: قدیمی بالا، تازه پایین — کنارِ ردیفِ خالیِ ثبتِ نرخِ امروز. */
export function sortRates(rates: readonly ExchangeRate[]): ExchangeRate[] {
  return [...rates].sort((a, b) => a.rate_date.localeCompare(b.rate_date) || a.currency_code.localeCompare(b.currency_code))
}

/** درصدِ تغییرِ هر نرخ نسبت به نرخِ قبلیِ همان ارز؛ اولینِ هر ارز `null`. ورودی مرتب به زمان. */
export function rateChanges(sorted: readonly ExchangeRate[]): Map<string, number | null> {
  const prev = new Map<string, number>()
  const out = new Map<string, number | null>()
  for (const r of sorted) {
    const v = Number(r.rate)
    const p = prev.get(r.currency_code)
    out.set(r.id, p && p > 0 ? ((v - p) / p) * 100 : null)
    prev.set(r.currency_code, v)
  }
  return out
}

/** آخرین نرخِ هر ارز (بیشترین تاریخ). */
export function latestRates(rates: readonly ExchangeRate[]): Map<string, ExchangeRate> {
  const out = new Map<string, ExchangeRate>()
  for (const r of rates) {
    const cur = out.get(r.currency_code)
    if (!cur || r.rate_date > cur.rate_date) out.set(r.currency_code, r)
  }
  return out
}

/** خطای ارزِ تازه پیش از ارسال: کد و نام لازم‌اند، و کد تکراری نباشد (در ثبت‌شده‌ها یا همین برگه). */
export function currencyProblem(c: FreshCurrency, taken: ReadonlySet<string>): string | null {
  const code = c.code.trim().toUpperCase()
  if (!code && !c.name.trim()) return 'کد و نامِ ارز را وارد کنید.'
  if (!code) return 'کدِ ارز را وارد کنید.'
  if (!c.name.trim()) return 'نامِ ارز را وارد کنید.'
  if (taken.has(code)) return `ارزِ ${code} از قبل هست.`
  return null
}

/** خطای نرخِ تازه پیش از ارسال: ارز، تاریخ و نرخِ بزرگ‌تر از صفر. */
export function rateProblem(r: Pick<FreshRate, 'currency_code' | 'rate_date' | 'rate'>): string | null {
  if (!r.currency_code) return 'ارز را انتخاب کنید.'
  if (!r.rate_date) return 'تاریخ را انتخاب کنید.'
  if (!(Number(r.rate) > 0)) return 'نرخ باید بزرگ‌تر از صفر باشد.'
  return null
}

/** نرخِ ویرایش‌شده‌ی یک نرخِ ثبت‌شده — فقط اگر واقعاً عوض شده باشد؛ وگرنه `null`. */
export function editedRate(orig: ExchangeRate, edit: string | undefined): string | null {
  if (edit === undefined || edit.trim() === '') return null
  return Number(edit) === Number(orig.rate) ? null : edit
}

export function pendingCount(d: CurrencyDraft, rates: readonly ExchangeRate[]): { fresh: number; edited: number } {
  const byId = new Map(rates.map((r) => [r.id, r]))
  let edited = 0
  for (const [id, v] of Object.entries(d.edits)) {
    const r = byId.get(id)
    if (r && editedRate(r, v) !== null) edited++
  }
  const fresh = d.currencies.filter((c) => !currencyIsBlank(c)).length + d.rates.filter((r) => !rateIsBlank(r)).length
  return { fresh, edited }
}

/** کدهای ارزِ گرفته‌شده (ثبت‌شده‌ها + تازه‌های دیگرِ همین برگه) — برای «تکراری» پیش از ارسال. */
export function takenCodes(saved: readonly Currency[], fresh: readonly FreshCurrency[], except: string): Set<string> {
  const out = new Set(saved.map((c) => c.code.toUpperCase()))
  for (const f of fresh) if (f.key !== except && f.code.trim()) out.add(f.code.trim().toUpperCase())
  return out
}

/** پیش‌نویسِ خوانده‌شده از ذخیره‌ی نشست — هر شکلِ خرابی یعنی «هیچ». */
export function parseCurrencyDraft(raw: string | null): CurrencyDraft | null {
  if (!raw) return null
  try {
    const d = JSON.parse(raw) as CurrencyDraft
    if (!d || typeof d !== 'object' || !Array.isArray(d.currencies) || !Array.isArray(d.rates)) return null
    const str = (o: object, keys: string[]) => keys.every((k) => typeof (o as Record<string, unknown>)[k] === 'string')
    return {
      currencies: d.currencies.filter((c) => c && str(c, ['key', 'code', 'name', 'symbol'])),
      rates: d.rates.filter((r) => r && str(r, ['key', 'currency_code', 'rate_date', 'rate'])),
      edits: d.edits && typeof d.edits === 'object' ? d.edits : {},
    }
  } catch {
    return null
  }
}
