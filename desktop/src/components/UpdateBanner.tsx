import { useEffect, useState } from 'react'
import type { UpdateStatus } from '../lib/updateStatus'
import { toFaDigits } from '../lib/jalali'

/**
 * نوار اطلاع‌رسانی به‌روزرسانی — فقط در اپ دسکتاپ.
 *
 * **چرا فقط وقتی دانلود تمام شده نشان داده می‌شود:** «در حال بررسی» و «در حال
 * دانلود» برای کاربر خبر نیستند، مزاحمت‌اند. چیزی که واقعاً به تصمیم او مربوط است
 * این است که نسخه‌ی تازه آماده است و می‌تواند هر وقت خواست اعمالش کند.
 *
 * **چرا دکمه‌ی «بعداً» هست و بستن اجباری نیست:** این نرم‌افزار حسابداری است. بستن
 * برنامه وسط ثبت فاکتور یعنی از دست رفتن کار کاربر. به‌روزرسانی در خروج طبیعی
 * برنامه خودش نصب می‌شود؛ این دکمه فقط راه میان‌بر است.
 */
export function UpdateBanner() {
  const [status, setStatus] = useState<UpdateStatus>({ state: 'none' })
  const [dismissed, setDismissed] = useState<string | null>(null)

  useEffect(() => {
    const api = window.cubitaUpdate
    if (!api) return
    let active = true
    let received = false
    const stop = api.onStatus((next) => { received = true; if (active) setStatus(next) })
    api.status().then((next) => { if (active && !received) setStatus(next) }).catch(() => {})
    return () => { active = false; stop() }
  }, [])

  if (status.state !== 'ready' || dismissed === status.version) return null

  return (
    <div className="update-banner" role="status">
      <span>
        نسخه‌ی {toFaDigits(status.version)} آماده‌ی نصب است. با بستن برنامه خودکار اعمال می‌شود.
      </span>
      <span className="update-banner__actions">
        <button type="button" onClick={() => {
          if (window.confirm('کارهای در حال انجام را ذخیره کنید. برنامه برای نصب آپدیت بسته و دوباره باز می‌شود. ادامه می‌دهید؟')) void window.cubitaUpdate?.installNow()
        }}>
          نصب و راه‌اندازی مجدد
        </button>
        <button type="button" className="update-banner__later" onClick={() => setDismissed(status.version)}>
          بعداً
        </button>
      </span>
    </div>
  )
}
