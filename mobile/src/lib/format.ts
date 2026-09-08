/**
 * قالبِ عدد و تاریخ — یک جا.
 *
 * **چرا متمرکز شد:** `todayIso` در دو صفحه کپی شده بود و `normalizeAmount` در
 * یکی. هر کپی یک فرصتِ واگرایی است: کافی است یکی ارقامِ عربی‌ـهندی (٠١٢…، که
 * صفحه‌کلیدهای فارسیِ اندروید هم تولید می‌کنند) را بشناسد و دیگری نه — آن‌وقت
 * همان کاربر در یک صفحه عدد ثبت می‌کند و در صفحه‌ی دیگر «۰» می‌گیرد.
 *
 * تاریخ‌ها با `jalaali-js` — **همان کتابخانه‌ی دسکتاپ**. با پیاده‌سازیِ جداگانه
 * ممکن بود یک سند روی دسکتاپ ۱۴۰۵/۰۶/۱۶ باشد و روی موبایل ۱۴۰۵/۰۶/۱۵.
 * `toLocaleDateString('fa-IR')` هم عمداً استفاده نشد: به ICUِ خودِ گوشی وابسته
 * است و روی دستگاه‌های مختلف یکسان نیست.
 */
import { toJalaali } from 'jalaali-js'

const FA = '۰۱۲۳۴۵۶۷۸۹'
const AR = '٠١٢٣٤٥٦٧٨٩'

const pad2 = (n: number): string => String(n).padStart(2, '0')

/** ارقامِ لاتین → فارسی (برای نمایش). */
export const toFaDigits = (v: string | number): string =>
  String(v).replace(/[0-9]/g, (d) => FA[Number(d)])

/** ارقامِ فارسی و عربی‌ـهندی → لاتین (برای ورودیِ کاربر). */
export const toLatinDigits = (raw: string): string =>
  raw.replace(/[۰-۹٠-٩]/g, (ch) => {
    const i = FA.indexOf(ch)
    return String(i >= 0 ? i : AR.indexOf(ch))
  })

/** تاریخِ امروز YYYY-MM-DD در وقتِ محلی (نه UTC — وگرنه شب‌ها یک روز عقب می‌افتد). */
export function todayIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/** «YYYY-MM-DD» یا ISOِ کامل → «۱۴۰۵/۰۶/۱۶». ورودیِ نامعتبر خودش برمی‌گردد. */
export function faDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [gy, gm, gd] = iso.slice(0, 10).split('-').map(Number)
  if (!gy || !gm || !gd) return String(iso)
  const { jy, jm, jd } = toJalaali(gy, gm, gd)
  return toFaDigits(`${jy}/${pad2(jm)}/${pad2(jd)}`)
}

/** فقط رقمِ صحیح نگه می‌دارد — برای مبلغ (کاربر جداکننده یا رقمِ فارسی می‌زند). */
export const normalizeInt = (raw: string): string =>
  toLatinDigits(raw).replace(/[^0-9]/g, '')

/**
 * عددِ اعشاری برای مقدار/تعداد.
 *
 * تعدادِ انبار همیشه صحیح نیست (۲٫۵ کیلو، ۰٫۷۵ متر) پس برخلافِ مبلغ، ممیز مجاز
 * است — ولی فقط یکی؛ «۱.۲.۳» هرچه بعد از ممیزِ اول بیاید را دور می‌ریزد تا به
 * سرور `NaN` نرسد.
 */
export function normalizeDecimal(raw: string): string {
  const cleaned = toLatinDigits(raw).replace(/[٫،]/g, '.').replace(/[^0-9.]/g, '')
  const [head, ...rest] = cleaned.split('.')
  return rest.length ? `${head}.${rest.join('')}` : head
}

/**
 * متنِ ورودیِ کاربر → عدد.
 *
 * **چرا `Number()` تنها کافی نیست:** فیلدهای مقدار با ارقامِ *فارسی* پر می‌شوند
 * (چون بقیه‌ی صفحه فارسی است)، و `Number('۱۲')` در جاوااسکریپت `NaN` می‌دهد.
 * نتیجه‌اش خطا نیست — محاسبه‌ی مغایرت بی‌صدا از کار می‌افتد و ردیفِ مغایرت‌دار
 * «بدونِ اختلاف» به‌نظر می‌رسد.
 */
export const parseQty = (raw: string): number => Number(normalizeDecimal(raw) || 0)

/** مقدار برای نمایش: تا سه رقمِ اعشار، بدونِ صفرهای بی‌معنیِ انتها، با ارقامِ فارسی. */
export function faQty(v: string | number): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return toFaDigits(String(v))
  return n.toLocaleString('fa-IR', { maximumFractionDigits: 3 })
}
