import { useEffect, useState } from 'react'
import { fetchSubscription, type SubscriptionStatus } from '../api'

/**
 * وضعیت اشتراک بالای هر صفحه — تنها جایی که کاربر می‌فهمد چرا نمی‌تواند سند ثبت کند.
 *
 * **چرا این لازم شد:** سرور از ۰۰۲۲ به بعد نوشتن را بعد از انقضا با ۴۰۲ رد
 * می‌کند، ولی بدون این نوار، آن ۴۰۲ فقط داخل یک فرم و بعد از تلاش برای ثبت دیده
 * می‌شود — کاربر باید حدس بزند چرا. این نوار قبل از رسیدن به آن لحظه خبر می‌دهد.
 *
 * **چرا سه سطح شدت دارد و نه یک پیام یکسان:**
 *   - `expired`/`cancelled` (can_write=false): قرمز، ثابت، هرگز بسته نمی‌شود —
 *     این وضعیتی نیست که کاربر بتواند نادیده بگیرد، چون واقعاً نمی‌تواند ثبت کند.
 *   - `grace` (هنوز can_write=true ولی گذشته از تاریخ): کهربایی، ثابت — هشدار
 *     فوری، ولی هنوز کار می‌کند.
 *   - نزدیک به انقضا (still active, days_left کم): خنثی، در همین نشست قابل
 *     بستن — یادآوری است، نه هشدار.
 *
 * **چرا فقط وقتی token هست رندر می‌شود** (از بیرون کنترل می‌شود): قبل از ورود
 * هیچ مستأجری برای پرسیدن وضعیتش وجود ندارد.
 */
export function SubscriptionBanner({ token }: { token: string }) {
  const [sub, setSub] = useState<SubscriptionStatus | null>(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchSubscription(token)
      .then((s) => {
        if (!cancelled) setSub(s)
      })
      .catch(() => {
        // شکست این درخواست نباید کل صفحه را بشکند؛ خودِ اندپوینت‌های دیگر
        // همچنان ۴۰۲ واقعی را برمی‌گردانند اگر لازم باشد.
      })
    return () => {
      cancelled = true
    }
  }, [token])

  // none: هیچ ردیف اشتراکی نیست — fail-open، چیزی برای گفتن نیست.
  // active بدون should_warn: همه‌چیز عادی، نوار هم نباید باشد.
  if (!sub || sub.status === 'none' || (sub.status === 'active' && !sub.should_warn)) return null

  const severity: 'critical' | 'warning' | 'notice' =
    sub.status === 'expired' || sub.status === 'cancelled'
      ? 'critical'
      : sub.status === 'grace'
        ? 'warning'
        : 'notice'

  if (severity === 'notice' && dismissed) return null

  const message =
    severity === 'critical'
      ? 'اشتراک این کسب‌وکار تمام شده است. دفترها و گزارش‌ها همچنان در دسترس‌اند؛ برای ثبت سند تازه باید تمدید کنید.'
      : severity === 'warning'
        ? `اشتراک منقضی شده و در مهلت ارفاق است. برای جلوگیری از قطع ثبت سند، تمدید کنید.`
        : `اشتراک شما ${sub.days_left} روز دیگر تمام می‌شود.`

  return (
    <div className={`subscription-banner subscription-banner--${severity}`} role="status">
      <span>{message}</span>
      {severity === 'notice' && (
        <button type="button" className="subscription-banner__dismiss" onClick={() => setDismissed(true)}>
          بعداً
        </button>
      )}
    </div>
  )
}
