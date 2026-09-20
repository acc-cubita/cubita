/**
 * تفکیکِ یک مقدارِ خروج بینِ بارهای ورودی — منطقِ خالص.
 *
 * **چرا این‌جا و نه داخلِ کامپوننت:** محیطِ vitest این پروژه `node` است و DOM
 * ندارد، پس هرچه داخلِ کامپوننت بماند تست‌ناپذیر است. همین قاعده برای
 * `tradeSelection.ts` هم بود.
 *
 * **و چرا اصلاً سمتِ کلاینت حساب می‌شود، وقتی سرور خودش FEFO می‌زند؟** چون این
 * *پیشنهادِ نمایشی* است: کاربر باید پیش از ثبت ببیند از کدام بار چه‌قدر برداشته
 * می‌شود تا بتواند نقضش کند (§۱۱). عددِ نهایی را همیشه سرور می‌سنجد — این‌جا
 * هیچ‌چیز تضمین نمی‌شود، فقط نشان داده می‌شود.
 */

/** فقط آن‌چه برای تفکیک لازم است — نه کلِ رکوردِ بار. */
export interface AllocatableBatch {
  id: string
  batch_number: string
  expiry_date: string | null
  /** مقدارِ واقعاً قابلِ فروش (سرور حساب کرده: انسداد، QC، انقضا و عمرِ مفید). */
  sellable_qty: string
}

export interface Allocation {
  batch_id: string
  qty: number
}

const num = (v: string | number | null | undefined): number => {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

/**
 * ترتیبِ FEFO: نزدیک‌ترین انقضا اول، و بارِ **بدونِ** تاریخ آخر.
 *
 * «نمی‌دانم» نباید جلوی باری بیفتد که تاریخش دارد می‌گذرد — همین قاعده سمتِ
 * سرور هم هست و اگر این دو از هم جدا شوند، پیشنهادِ نمایشی با چیزی که ثبت
 * می‌شود فرق می‌کند.
 */
export function fefoOrder(batches: AllocatableBatch[]): AllocatableBatch[] {
  return [...batches].sort((a, b) => {
    if (!a.expiry_date && !b.expiry_date) return a.batch_number.localeCompare(b.batch_number, 'fa')
    if (!a.expiry_date) return 1
    if (!b.expiry_date) return -1
    return a.expiry_date.localeCompare(b.expiry_date)
  })
}

/** پیشنهادِ پیش‌فرض: از نزدیک‌ترین انقضا بردار تا مقدار تمام شود. */
export function fefoPlan(batches: AllocatableBatch[], qty: number): Allocation[] {
  let remaining = qty
  const plan: Allocation[] = []
  for (const batch of fefoOrder(batches)) {
    if (remaining <= 0) break
    const take = Math.min(num(batch.sellable_qty), remaining)
    if (take <= 0) continue
    plan.push({ batch_id: batch.id, qty: take })
    remaining -= take
  }
  return plan
}

export function allocationTotal(allocations: Allocation[]): number {
  return allocations.reduce((sum, a) => sum + a.qty, 0)
}

/**
 * پیامِ خطای تفکیک، یا `null` اگر درست است.
 *
 * عمداً **همان سه سنجه‌ای** را می‌گوید که سرور می‌سنجد، با همان لحن: جمع باید
 * برابرِ مقدارِ ردیف باشد، هیچ باری بیشتر از موجودی‌اش ندهد، و مقدارِ منفی نباشد.
 * اگر این‌جا چیزی را نگوییم که سرور می‌گوید، کاربر خطا را بعد از «ثبت» می‌بیند.
 */
export function allocationError(
  allocations: Allocation[],
  qty: number,
  batches: AllocatableBatch[],
): string | null {
  const byId = new Map(batches.map((b) => [b.id, b]))
  for (const a of allocations) {
    if (a.qty <= 0) return 'مقدارِ هر بار باید بزرگ‌تر از صفر باشد.'
    const batch = byId.get(a.batch_id)
    if (!batch) return 'یکی از بارهای انتخاب‌شده دیگر در این انبار نیست.'
    if (a.qty > num(batch.sellable_qty)) {
      return `موجودیِ قابلِ فروشِ بارِ «${batch.batch_number}» کافی نیست.`
    }
  }
  const total = allocationTotal(allocations)
  if (total !== qty) {
    return 'جمعِ تفکیکِ بارها باید دقیقاً برابرِ مقدارِ ردیف باشد.'
  }
  return null
}

/** جمعِ قابلِ فروشِ همه‌ی بارها — برای پیامِ «اصلاً این‌قدر نداریم». */
export function totalSellable(batches: AllocatableBatch[]): number {
  return batches.reduce((sum, b) => sum + num(b.sellable_qty), 0)
}
