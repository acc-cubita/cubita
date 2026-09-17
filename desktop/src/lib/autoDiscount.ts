/**
 * انتخابِ تخفیفِ خودکارِ فاکتور از بینِ دو منبع.
 *
 * **چرا تابعِ جدا و نه چند خط داخلِ افکت.** این قاعده مبلغِ فاکتور را عوض
 * می‌کند. تا وقتی داخلِ `useEffect` بود، آزمودنش یعنی رندرکردنِ کلِ فرم و
 * تقلبِ شبکه — که کسی انجامش نمی‌داد، و در عمل هم ندادیم: قاعده یک بار بیرونِ
 * پروژه با اسکریپت سنجیده شد و بعد رها ماند.
 *
 * حالا تابعِ خالص است و `autoDiscount.test.ts` گاردش می‌کند.
 */

export type AutoDiscountSource = 'tier' | 'contact'

export interface AutoDiscountInput {
  /** نرخِ تخفیفِ خودِ طرف‌حساب (درصد). */
  ownPct: number
  /** درصدِ تخفیفِ سطحِ باشگاه. */
  tierPct: number
  /** نامِ سطح — برای پیامِ زیرِ انتخابگر. */
  tierName: string
  /** آیا «پیشنهادِ خودکارِ تخفیفِ سطح» در تنظیماتِ باشگاه روشن است. */
  tierAuto: boolean
}

export interface AutoDiscountChoice {
  /** درصدی که روی فاکتور می‌نشیند. صفر یعنی هیچ تخفیفی اعمال نمی‌شود. */
  pct: number
  /** از کجا آمد — یا `null` وقتی چیزی اعمال نشده. */
  source: AutoDiscountSource | null
}

/**
 * **قاعده: هرکدام بیشتر باشد.** به نفعِ مشتری — سطحِ باشگاه یک کفِ تضمین‌شده
 * می‌شود که نرخِ اختصاصی از آن کم نمی‌کند.
 *
 * **گیتِ `tierAuto` فقط روی سمتِ سطح است.** آن تنظیم درباره‌ی پیشنهادِ خودکارِ
 * *باشگاه* است؛ نرخی که کاربر دستی روی یک طرف‌حساب گذاشته داده‌ی عمدیِ خودِ
 * اوست و به آن سوییچ ربطی ندارد.
 */
export function pickAutoDiscount({ ownPct, tierPct, tierName, tierAuto }: AutoDiscountInput): AutoDiscountChoice {
  const tier = tierAuto ? tierPct : 0
  const name = tierAuto ? tierName : ''
  const pct = Math.max(ownPct, tier)
  if (pct <= 0) return { pct: 0, source: null }
  //: مساوی که باشند سطح برنده است — نامِ سطح پیامِ گویاتری از نامِ طرف‌حساب می‌دهد.
  return { pct, source: name && tier >= ownPct ? 'tier' : 'contact' }
}
