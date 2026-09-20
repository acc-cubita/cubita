/**
 * سودِ فروشگاه: خالصِ خرید، سودِ ناخالص، مارک‌آپ و مارجین (§۲۱ تا §۲۷).
 *
 * **دوقلوی `backend/app/margins.py` است، و عمداً.** §۲۶ می‌خواهد وقتی فروشگاه
 * تعداد را عوض می‌کند اعداد **زنده** عوض شوند؛ درخواست به سرور به‌ازای هر کلید
 * یعنی تأخیر و بار.
 *
 * دو نسخه یعنی دو جا برای واگرایی — و راهِ بستنش یک **پرونده‌ی نمونه‌ی مشترک**
 * است: `backend/tests/fixtures/margin_cases.json`. هر دو طرف همان را می‌خوانند
 * و همان جواب‌ها را می‌سنجند. هیچ‌کدام صاحبِ حقیقت نیست؛ پرونده هست.
 *
 * **قاعده‌ی گِردکردن:** درصدها با یک رقمِ اعشار و «نیم به بالا». این انتخاب لازم
 * است چون پایتون `Decimal` دارد و این‌جا `float64`؛ مبلغِ ریالِ صحیح در هر دو
 * دقیق است ولی **درصد** در رقم‌های آخر فرق می‌کند. پس آنچه سنجیده می‌شود عددِ
 * *نمایشی* است، نه خامِ محاسبه.
 */

const num = (v: number | string | null | undefined): number => {
  const n = Number(v ?? 0)
  return Number.isFinite(n) ? n : 0
}

/** یک رقمِ اعشار، «نیم به بالا» — همان قاعده‌ی سمتِ پایتون. */
const roundPercent = (v: number): number => Math.round(v * 10 + Number.EPSILON) / 10

/** مبلغِ ریالِ صحیح، «نیم به بالا». */
const roundMoney = (v: number): number => Math.round(v + Number.EPSILON)

/**
 * قیمتِ واقعیِ خریدِ فروشگاه پس از تخفیف (§۲۳).
 *
 * **تخفیف همیشه مبلغ است، نه درصد.** ردیفِ فاکتور در این مخزن تخفیف را مبلغ
 * ذخیره می‌کند؛ §۲۴ درصد را هم می‌خواهد، ولی درصد یک **ویجتِ ورودی** است که
 * پیش از ارسال به مبلغ تبدیل می‌شود.
 */
export function netPurchasePrice(listPrice: number | string, discount: number | string = 0): number {
  return Math.max(num(listPrice) - num(discount), 0)
}

/** تبدیلِ تخفیفِ درصدی به مبلغ (§۲۴) — برای ویجتِ ورودی، پیش از ذخیره. */
export function percentToAmount(listPrice: number | string, percent: number | string): number {
  const pct = num(percent)
  if (pct <= 0) return 0
  return roundMoney((num(listPrice) * pct) / 100)
}

/**
 * بهای واقعیِ هر واحد وقتی اشانتیون گرفته‌ای (§۲۵).
 *
 * `null` وقتی چیزی دریافت نشده: تقسیم بر صفر جواب ندارد و صفر برگرداندن یعنی
 * ادعای «رایگان بود».
 */
export function effectiveUnitCost(
  totalPaid: number | string,
  totalReceived: number | string,
): number | null {
  const received = num(totalReceived)
  if (received <= 0) return null
  return num(totalPaid) / received
}

/** سودِ ناخالصِ هر واحد (§۲۱) — **محاسبه می‌شود، دستی وارد نمی‌شود.** */
export function grossProfit(consumerPrice: number | string, netCost: number | string): number {
  return num(consumerPrice) - num(netCost)
}

/** سود نسبت به **بهای خرید** (§۲۲). `null` وقتی بهای خرید صفر است. */
export function markupPercent(
  consumerPrice: number | string,
  netCost: number | string,
): number | null {
  const cost = num(netCost)
  if (cost <= 0) return null
  return roundPercent((grossProfit(consumerPrice, cost) / cost) * 100)
}

/**
 * سود نسبت به **قیمتِ فروش** (§۲۲). `null` وقتی قیمتِ فروش صفر است.
 *
 * مارک‌آپ و مارجین دو عددِ متفاوت‌اند: ۱۵۰ روی ۳۰۰ یعنی مارک‌آپِ ۵۰٪ ولی
 * مارجینِ ۳۳٫۳٪. یکی‌گرفتنشان اشتباهِ رایجی است که فروشنده را گمراه می‌کند.
 */
export function marginPercent(
  consumerPrice: number | string,
  netCost: number | string,
): number | null {
  const price = num(consumerPrice)
  if (price <= 0) return null
  return roundPercent((grossProfit(price, netCost) / price) * 100)
}

/**
 * سودِ هر کارتن (§۲۷) — از نسبتِ تبدیلِ **ثابتِ** خودِ کالا.
 *
 * `null` وقتی نسبت تعریف نشده. حدس‌زدنش یعنی عددی که کاربر باور می‌کند و ما از
 * خودمان درآورده‌ایم.
 */
export function profitPerPack(
  unitProfit: number | string,
  unitsPerPack: number | string | null | undefined,
): number | null {
  const perPack = num(unitsPerPack)
  if (perPack <= 0) return null
  return num(unitProfit) * perPack
}

/**
 * §۱۹ — قیمتِ بار بر قیمتِ کالا می‌چربد: `effective = batch ?? product`.
 *
 * هر بار می‌تواند قیمتِ چاپیِ خودش را داشته باشد؛ قیمتِ کالا فقط پیش‌فرض است.
 * `null` یعنی هیچ‌کدام اعلام نشده — و §۳۰ می‌گوید چنین فیلدی اصلاً نباید نمایش
 * داده شود، نه اینکه صفر نشان داده شود.
 */
export function effectiveConsumerPrice(
  batchPrice: number | string | null | undefined,
  productPrice: number | string | null | undefined,
): number | null {
  if (batchPrice !== null && batchPrice !== undefined) return num(batchPrice)
  if (productPrice !== null && productPrice !== undefined) return num(productPrice)
  return null
}

export interface OrderAnalysisInput {
  qty: number | string
  list_price: number | string
  discount?: number | string
  consumer_price?: number | string | null
  units_per_pack?: number | string | null
  bonus_qty?: number | string
}

/**
 * تحلیلِ زنده‌ی سودِ یک سفارش (§۲۶).
 *
 * **فقط چیزی را برمی‌گرداند که واقعاً قابلِ محاسبه است.** §۲۶ صریح است که این
 * اطلاعات فقط وقتی نمایش داده شوند که داده‌ی لازم باشد؛ پس کلیدهایی که
 * ورودی‌شان نیست اصلاً در خروجی نمی‌آیند — نه با صفر، نه با خط تیره.
 */
export function orderAnalysis(input: OrderAnalysisInput): Record<string, number> {
  const quantity = num(input.qty)
  let netUnit = netPurchasePrice(input.list_price, input.discount ?? 0)
  const bonus = num(input.bonus_qty)
  const received = quantity + bonus

  const out: Record<string, number> = {
    order_quantity: quantity,
    net_purchase_amount: netUnit * quantity,
  }

  if (bonus > 0) {
    out.bonus_quantity = bonus
    const eff = effectiveUnitCost(netUnit * quantity, received)
    if (eff !== null) {
      out.effective_unit_cost = eff
      netUnit = eff // سودِ واقعی با بهای واقعی حساب می‌شود، نه با فیِ لیست
    }
  }

  const consumer = input.consumer_price
  if (consumer === null || consumer === undefined) return out

  const price = num(consumer)
  out.potential_revenue = price * received
  out.potential_gross_profit = grossProfit(price, netUnit) * received
  const markup = markupPercent(price, netUnit)
  if (markup !== null) out.markup_percent = markup
  const margin = marginPercent(price, netUnit)
  if (margin !== null) out.margin_percent = margin
  const perPack = profitPerPack(grossProfit(price, netUnit), input.units_per_pack)
  if (perPack !== null) out.profit_per_pack = perPack
  return out
}
