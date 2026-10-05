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
  qty: string | number
}

const SCALE = 100000000n
export function quantityAtoms(value: string | number): bigint {
  const match = /^(\d+)(?:\.(\d{0,8}))?$/.exec(String(value).trim())
  if (!match) throw new Error('مقدار نامعتبر است؛ حداکثر هشت رقم اعشار مجاز است.')
  return BigInt(match[1]) * SCALE + BigInt((match[2] ?? '').padEnd(8, '0'))
}
export function atomQuantity(value: bigint): string {
  const fraction = (value % SCALE).toString().padStart(8, '0').replace(/0+$/, '')
  return `${value / SCALE}${fraction ? `.${fraction}` : ''}`
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
export function fefoPlan(batches: AllocatableBatch[], qty: string | number): Allocation[] {
  let remaining = quantityAtoms(qty)
  const plan: Allocation[] = []
  for (const batch of fefoOrder(batches)) {
    if (remaining <= 0n) break
    const available = quantityAtoms(batch.sellable_qty || '0')
    const take = available < remaining ? available : remaining
    if (take <= 0n) continue
    plan.push({ batch_id: batch.id, qty: atomQuantity(take) })
    remaining -= take
  }
  return plan
}

export function allocationTotal(allocations: Allocation[]): string {
  return atomQuantity(allocations.reduce((sum, a) => sum + quantityAtoms(a.qty), 0n))
}

export function allocationError(allocations: Allocation[], qty: string | number,
  batches: AllocatableBatch[]): string | null {
  const byId = new Map(batches.map((b) => [b.id, b]))
  const seen = new Set<string>()
  try {
    for (const a of allocations) {
      if (quantityAtoms(a.qty) <= 0n) return 'مقدارِ هر بار باید بزرگ‌تر از صفر باشد.'
      if (seen.has(a.batch_id)) return 'هر بار را فقط یک بار انتخاب کنید.'
      seen.add(a.batch_id)
      const batch = byId.get(a.batch_id)
      if (!batch) return 'یکی از بارهای انتخاب‌شده دیگر در این انبار نیست.'
      if (quantityAtoms(a.qty) > quantityAtoms(batch.sellable_qty))
        return `موجودیِ قابلِ فروشِ بارِ «${batch.batch_number}» کافی نیست.`
    }
    if (quantityAtoms(allocationTotal(allocations)) !== quantityAtoms(qty))
      return 'جمعِ تفکیکِ بارها باید دقیقاً برابرِ مقدارِ ردیف باشد.'
  } catch {
    return 'مقدار نامعتبر است؛ حداکثر هشت رقم اعشار مجاز است.'
  }
  return null
}

export function totalSellable(batches: AllocatableBatch[]): string {
  return atomQuantity(batches.reduce((sum, b) => sum + quantityAtoms(b.sellable_qty || '0'), 0n))
}
