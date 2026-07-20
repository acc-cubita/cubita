import { useEffect, useState } from 'react'

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
type UpdateStatus =
  | { state: 'checking' }
  | { state: 'available'; version: string }
  | { state: 'downloading'; percent: number }
  | { state: 'ready'; version: string }
  | { state: 'none' }
  | { state: 'error'; message: string }

declare global {
  interface Window {
    cubitaUpdate?: {
      status: () => Promise<UpdateStatus>
      installNow: () => Promise<void>
      onStatus: (cb: (status: UpdateStatus) => void) => () => void
    }
  }
}

export function UpdateBanner() {
  const [status, setStatus] = useState<UpdateStatus>({ state: 'none' })
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const api = window.cubitaUpdate
    if (!api) return
    api.status().then(setStatus).catch(() => {})
    return api.onStatus(setStatus)
  }, [])

  if (status.state !== 'ready' || dismissed) return null

  return (
    <div className="update-banner" role="status">
      <span>
        نسخه‌ی {status.version} آماده‌ی نصب است. با بستن برنامه خودکار اعمال می‌شود.
      </span>
      <span className="update-banner__actions">
        <button type="button" onClick={() => window.cubitaUpdate?.installNow()}>
          نصب و راه‌اندازی مجدد
        </button>
        <button type="button" className="update-banner__later" onClick={() => setDismissed(true)}>
          بعداً
        </button>
      </span>
    </div>
  )
}
