/**
 * اولین فیلدِ الزامیِ خالی را فوکوس می‌کند و پیامش را برمی‌گرداند؛ اگر همه پر بودند null.
 *
 * دکمه‌ی ثبت عمداً خاموش نمی‌شود: دکمه‌ی خاموش نمی‌گوید چه چیزی کم است. ثبت پیام
 * می‌دهد و مکان‌نما را روی همان فیلد می‌برد.
 */
export function firstMissing(checks: [filled: unknown, id: string, message: string][]): string | null {
  for (const [filled, id, message] of checks) {
    if (typeof filled === 'string' ? filled.trim() === '' : !filled) {
      document.getElementById(id)?.focus()
      return message
    }
  }
  return null
}
