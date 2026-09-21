/**
 * نگهداریِ توکنِ ستاد.
 *
 * نسخه‌ی ساده‌شده‌ی `desktop/src/lib/session.ts`: اپِ ستاد فقط در مرورگر اجرا
 * می‌شود، پس شاخه‌ی Electron ندارد.
 *
 * **کلید عمداً با اپِ مشتری فرق دارد.** در production دو مبدأ جدا هستند و
 * localStorage خودبه‌خود جداست، ولی روی `localhost` هر دو اپ یک مبدأ دارند و با
 * کلیدِ مشترک توکنِ همدیگر را بازنویسی می‌کردند — یعنی توسعه‌دهنده هر بار از یکی
 * بیرون می‌افتاد و علتش پیدا نبود.
 */
const KEY = 'cubita.admin.token'

export function loadStoredToken(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function storeToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(KEY, token)
    else localStorage.removeItem(KEY)
  } catch {
    /* حالتِ ناشناس یا مسدودبودنِ ذخیره‌سازی: نشست فقط تا رفرش می‌ماند. */
  }
}
