import { normalizeFa, textMatches } from './faText'
import { tenantKey } from './tenantScope'

/**
 * حافظه‌ی شرح (UI-01 §۲۰) — پیشنهادِ شرح‌های تکراری، بی هیچ «یادگیری».
 *
 * **منبع:** شرح‌های همین سند، و شرح‌هایی که در همین جلسه ثبت شده‌اند. نه سرور و نه
 * `localStorage`: پیشنهاد باید از کارِ همین حالای کاربر بیاید. حافظه‌ی بین‌جلسه‌ای
 * روی دستگاهِ مشترک شرحِ کسِ دیگری را پیشنهاد می‌داد، و §۲۰ خودش حافظه‌ی همان
 * جلسه را کافی دانسته.
 *
 * **فقط پیشنهاد:** هیچ‌چیز خودکار در فیلد نمی‌نشیند؛ انتخاب با کاربر است
 * (`DescriptionInput`).
 *
 * **به‌ازای کسب‌وکار** (`tenantKey`): تعویضِ کسب‌وکار همین تب را دوباره بار می‌کند
 * و `sessionStorage` می‌ماند. با کلیدِ سراسری، شرح‌های کسب‌وکارِ دیگر پیشنهاد می‌شد.
 */

const KEY = 'cubita.journal.descriptions'
//: سقفِ حافظه‌ی جلسه — قدیمی‌ترها بیرون می‌روند.
const CAP = 50
/** بیشترین تعدادِ پیشنهادِ هم‌زمان. */
export const SUGGEST_LIMIT = 6

/** یکتاسازی با متنِ یکسان‌شده (ی/ک، نیم‌فاصله) — اولین نمونه، با همان نگارشِ کاربر، می‌ماند. */
export function dedupe(list: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of list) {
    const s = raw.trim()
    const key = normalizeFa(s)
    if (!key || seen.has(key)) continue
    seen.add(key)
    out.push(s)
  }
  return out
}

/**
 * پیشنهادها برای آنچه کاربر تایپ کرده، حداکثر `limit` تا.
 *
 * آن‌هایی که با همین متن **شروع** می‌شوند اول می‌آیند، بعد آن‌هایی که واژه‌ها را جای
 * دیگری دارند. کادرِ خالی هیچ پیشنهادی نمی‌گیرد — فهرستی که بی‌تایپ باز شود فقط
 * جلوی گرید را می‌گیرد. متنی که دقیقاً همان است که تایپ شده هم پیشنهاد نمی‌شود.
 */
export function suggestDescriptions(pool: string[], query: string, limit = SUGGEST_LIMIT): string[] {
  const q = normalizeFa(query)
  if (!q) return []
  const starts: string[] = []
  const contains: string[] = []
  for (const s of dedupe(pool)) {
    const n = normalizeFa(s)
    if (n === q) continue
    if (n.startsWith(q)) starts.push(s)
    else if (textMatches(s, query)) contains.push(s)
  }
  return [...starts, ...contains].slice(0, limit)
}

/** شرح‌های ثبت‌شده در همین جلسه، تازه‌ترین اول. */
export function sessionDescriptions(): string[] {
  const key = tenantKey(KEY)
  if (!key) return []
  try {
    const raw = sessionStorage.getItem(key)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

/** بعد از ثبتِ موفقِ سند: شرح‌هایش به حافظه‌ی جلسه اضافه می‌شوند. */
export function rememberDescriptions(list: string[]): void {
  const key = tenantKey(KEY)
  const merged = dedupe([...list, ...sessionDescriptions()]).slice(0, CAP)
  if (!key || merged.length === 0) return
  try {
    sessionStorage.setItem(key, JSON.stringify(merged))
  } catch {
    /* ذخیره‌ی جلسه در دسترس نیست — پیشنهادها فقط از همین سند می‌آیند */
  }
}

/**
 * مخزنِ پیشنهادِ یک ردیف: شرح‌های دیگرِ همین سند (نزدیک‌ترین ردیف‌های بالایی اول —
 * همان‌جا که الگو تکرار می‌شود) و بعد حافظه‌ی جلسه.
 */
export function poolFor(descriptions: string[], row: number): string[] {
  const above = descriptions.slice(0, row).reverse()
  const below = descriptions.slice(row + 1)
  return [...above, ...below, ...sessionDescriptions()]
}
