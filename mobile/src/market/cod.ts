/**
 * نقدِ هنگامِ تحویل (COD).
 *
 * **مسئله‌ی طراحی:** بک‌اند `cash_percent` می‌گیرد (۰..۱۰۰) و خودش مبلغ را حساب
 * می‌کند. ولی مأمورِ حملی که سرِ درِ مغازه ایستاده **مبلغ** در دستش است، نه درصد.
 * واداشتنش به محاسبه‌ی ذهنیِ درصد یعنی دعوت به خطا — و خطا اینجا یعنی سندِ
 * خزانه‌ی غلط در دو کسب‌وکار.
 *
 * پس اپ مبلغ می‌گیرد و درصد را می‌سازد. برای اینکه این تبدیل پول را جابه‌جا
 * نکند، `cashAmountFor` **بازتابِ دقیقِ محاسبه‌ی بک‌اند** است
 * (`services/marketplace.py::deliver_order`) و تست رفت‌وبرگشت را می‌سنجد.
 */

/** درصد را با دقتی می‌سازد که بک‌اند دوباره به همان مبلغِ ریالی برسد. */
const PRECISION = 10

/**
 * بازتابِ محاسبه‌ی بک‌اند: `min(round(total × pct ÷ ۱۰۰), total)` با گِردکردنِ
 * نیم‌به‌بالا. اگر این با بک‌اند واگرا شود، عددی که مأمورِ حمل روی صفحه دید با
 * عددی که در دفتر نشست فرق می‌کند.
 */
export function cashAmountFor(percent: number, total: number): number {
  if (!Number.isFinite(percent) || !Number.isFinite(total) || total <= 0) return 0
  const pct = Math.min(Math.max(percent, 0), 100)
  return Math.min(Math.round((total * pct) / 100), total)
}

/**
 * مبلغِ دریافتی → درصد، برای فرستادن به بک‌اند.
 *
 * مبلغ به بازه‌ی [۰، کلِ سفارش] بریده می‌شود: بیشتر از کلِ سفارش را بک‌اند هم
 * قبول نمی‌کند و بهتر است کاربر همان‌جا ببیند چه چیزی ثبت می‌شود.
 */
export function cashPercentFor(amount: number, total: number): string {
  if (!Number.isFinite(amount) || !Number.isFinite(total) || total <= 0) return '0'
  const clamped = Math.min(Math.max(amount, 0), total)
  if (clamped === 0) return '0'
  if (clamped === total) return '100'
  return trimZeros(((clamped / total) * 100).toFixed(PRECISION))
}

function trimZeros(s: string): string {
  return s.includes('.') ? s.replace(/0+$/, '').replace(/\.$/, '') : s
}
