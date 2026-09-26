/**
 * «نام کاربری را به خاطر بسپار» در صفحه‌ی ورود.
 *
 * فقط **ایمیل** نگه داشته می‌شود، هرگز رمز — آن هم فقط وقتی کاربر خودش تیک زده. ورودِ موفق با تیکِ برداشته ایمیلِ ذخیره‌شده
 * را پاک می‌کند، پس کسی که روی سیستمِ مشترک کار می‌کند با یک ورودِ بی‌تیک ردش را برمی‌دارد.
 *
 * هم در Electron و هم در مرورگر `localStorage` است (برخلافِ توکن در `session.ts`، ایمیل رازی نیست که به دیتابیسِ محلیِ
 * برنامه نیاز داشته باشد). در کوبیتا سازمانی کلید نشانیِ سرور را هم دارد: یک رایانه ممکن است به سرورِ شرکت‌های مختلف وصل
 * شود و ایمیلِ یکی نباید در فرمِ دیگری بنشیند.
 */
const PREFIX = 'cubita.login.email'

const keyOf = (scope?: string | null): string => (scope ? `${PREFIX}@${scope}` : PREFIX)

/** ایمیلِ به‌خاطرسپرده برای این دامنه؛ اگر نیست یا `localStorage` در دسترس نیست، `null`. */
export function loadRememberedEmail(scope?: string | null): string | null {
  try {
    const v = localStorage.getItem(keyOf(scope))
    return v && v.trim() ? v : null
  } catch {
    return null
  }
}

/** بعد از ورودِ موفق: با تیک ایمیل ذخیره می‌شود، بی‌تیک پاک. */
export function rememberEmail(scope: string | null | undefined, email: string, remember: boolean): void {
  try {
    const clean = email.trim()
    if (remember && clean) localStorage.setItem(keyOf(scope), clean)
    else localStorage.removeItem(keyOf(scope))
  } catch {
    /* localStorage ممکن است در دسترس نباشد؛ ورود بی‌آن هم کار می‌کند */
  }
}
