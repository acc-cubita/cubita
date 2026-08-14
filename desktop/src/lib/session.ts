import { isElectron } from '../platform'

/**
 * ماندگاریِ توکنِ ورود در مرورگر.
 *
 * چرا فقط وب: در Electron توکن را خودِ برنامه (از طریقِ `window.cubita.setAuthToken`)
 * در دیتابیسِ محلی نگه می‌دارد و موتورِ همگام‌سازی از همان می‌خواند؛ آن مسیر دست‌نخورده
 * می‌ماند. اما در وب هیچ‌جا ذخیره نمی‌شد، برای همین با هر «رفرش» جلسه از دست می‌رفت و
 * کاربر به صفحه‌ی ورود پرت می‌شد. اینجا در `localStorage` نگه می‌داریم تا رفرش، جلسه را
 * نبندد و بعدِ باز شدنِ دوباره‌ی برنامه هم کاربر وارد بماند.
 */
const KEY = 'cubita.auth.token'

/** توکنِ ذخیره‌شده را می‌خواند (فقط وب). اگر `localStorage` در دسترس نباشد، `null`. */
export function loadStoredToken(): string | null {
  if (isElectron) return null
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

/** توکن را ذخیره یا (با `null`) پاک می‌کند (فقط وب). */
export function storeToken(token: string | null): void {
  if (isElectron) return
  try {
    if (token) localStorage.setItem(KEY, token)
    else localStorage.removeItem(KEY)
  } catch {
    /* localStorage ممکن است در دسترس نباشد؛ همان جلسه اعمال می‌شود */
  }
}
