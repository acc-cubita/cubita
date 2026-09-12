import type { ResolvedPrice } from '../api'

const fa = (n: number | string) => Number(n || 0).toLocaleString('fa-IR')

/**
 * زیرِ فیِ هر ردیف: نرخِ مصوبِ اعلامیه، حدِ مجاز، و اینکه عددِ واردشده از آن
 * بیرون زده یا نه (§۲۹ §۵۹ §۹۱).
 *
 * **چرا لازم است.** گاردِ سیاستِ قیمت سمتِ سرور است — و باید باشد (§۹۶). ولی
 * بدونِ این خط، کاربر تا لحظه‌ی زدنِ «ثبت» نمی‌داند نرخی که نوشته مجاز است یا
 * نه، و خطا وقتی می‌آید که کلِ فاکتور پر شده. حدها هم این‌جا **دوباره حساب
 * نمی‌شوند**: همان `min_price`/`max_price`ی نشان داده می‌شود که سرور اعمال
 * می‌کند، وگرنه دو محاسبه‌ی مستقل دیر یا زود از هم جدا می‌افتند.
 */
export function PriceRuleHint({ rule, entered }: { rule: ResolvedPrice | null | undefined; entered: string }) {
  if (!rule) return null

  const value = Number(entered)
  const low = rule.min_price == null ? null : Number(rule.min_price)
  const high = rule.max_price == null ? null : Number(rule.max_price)
  const outOfBounds =
    Number.isFinite(value) && value > 0 && ((low != null && value < low) || (high != null && value > high))

  const range =
    low == null && high == null
      ? null
      : low != null && high != null && low === high
        ? 'نرخ قفل است'
        : `مجاز: ${low == null ? '—' : fa(low)} تا ${high == null ? '—' : fa(high)}`

  return (
    <span className={`field-hint${outOfBounds ? ' stock-over' : ''}`}>
      نرخِ مصوب {fa(rule.unit_price)}
      {range ? ` — ${range}` : ''}
      {rule.ambiguous ? ' — چند قاعده هم‌زمان می‌خوانند' : ''}
    </span>
  )
}
