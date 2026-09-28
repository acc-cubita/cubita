export type UpdateStatus =
  | { state: 'idle' | 'checking' | 'verifying' | 'none' }
  | { state: 'available' | 'ready'; version: string }
  | { state: 'downloading'; percent: number }
  | { state: 'error'; message: string }

export function updateProblem(error: unknown, enterprise: boolean): string {
  const message = error instanceof Error ? error.message : String(error)
  if (/[\u0600-\u06ff]/.test(message)) return message
  if (/404|latest\.yml|ERR_UPDATER_CHANNEL_FILE_NOT_FOUND/i.test(message)) {
    return enterprise
      ? 'نصاب این نسخه هنوز روی سرور شرکت آماده نیست؛ مدیر باید در «سرور و مجوز» آپدیت سرور را آماده کند.'
      : 'فایل به‌روزرسانی هنوز آماده نیست؛ بعداً دوباره بررسی کنید.'
  }
  if (/sha512|checksum|digest/i.test(message)) return 'فایل دانلودشده کامل یا معتبر نیست؛ نصب انجام نشد. دوباره بررسی کنید.'
  return enterprise
    ? 'دریافت آپدیت از سرور شرکت انجام نشد؛ اتصال شبکه و نشانی سرور را بررسی کنید و دوباره تلاش کنید.'
    : 'بررسی به‌روزرسانی انجام نشد؛ اتصال را بررسی کنید و دوباره تلاش کنید.'
}
