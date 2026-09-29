import { formatErrorDates } from './jalali'

/** صف‌های قدیمی هم متنِ خامِ HTTP را دارند؛ فقط نمایش را عوض می‌کنیم، نه ردیف یا payload را. */
export function outboxErrorText(raw: string): string {
  let message = raw.trim().replace(/^Error invoking remote method '[^']+':\s*(?:Error:\s*)?/, '')
  try {
    const body: unknown = JSON.parse(message)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : body
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail)) {
      const messages = detail.flatMap((item: unknown) => {
        if (!item || typeof item !== 'object' || !('msg' in item) || typeof item.msg !== 'string') return []
        const text = item.msg.replace(/^Value error, /, '')
        const loc = 'loc' in item && Array.isArray(item.loc) ? item.loc : []
        const line = loc.indexOf('lines')
        return [line >= 0 && typeof loc[line + 1] === 'number'
          ? `ردیف ${(loc[line + 1] + 1).toLocaleString('fa-IR')}: ${text}`
          : text]
      })
      message = [...new Set(messages)].join('؛ ')
    } else message = ''
  } catch {
    // خطای شبکه و پیام‌های قدیمی متنِ ساده‌اند، نه JSON.
  }
  if (/failed to fetch|fetch failed|networkerror|network request failed|ECONNREFUSED|ETIMEDOUT|EHOSTUNREACH|ENOTFOUND|timed? ?out|timeout/i.test(message)) {
    return 'ارتباط با سرور برقرار نشد؛ اتصال شبکه و روشن‌بودن سرور را بررسی کنید و دوباره «هم‌گام‌سازی» را بزنید.'
  }
  if (!message || /^\s*</.test(message)) {
    return 'سرور پاسخ خطای خوانا نداد؛ اتصال و وضعیت سرور را بررسی کنید و دوباره «هم‌گام‌سازی» را بزنید.'
  }
  message = formatErrorDates(message.replace(/^(?:Error|TypeError):\s*/, ''))
  if (/در هیچ سال مالی|سال مالی تعریف‌شده/.test(message)) {
    message += ' — مدیر از «تنظیمات ← سال مالی» بازهٔ این تاریخ را بررسی کند. سند در صف حفظ شده؛ دوباره ثبتش نکنید.'
  } else if (/سال مالی.*بسته/.test(message)) {
    message += ' — برای بررسی سال مالی با مدیر هماهنگ کنید. سند در صف حفظ شده؛ دوباره ثبتش نکنید.'
  }
  return message
}
