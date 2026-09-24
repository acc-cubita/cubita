// آدرسِ سرورِ «کوبیتا سازمانی» — منطقِ خالص، بدونِ Electron، تا تست‌پذیر بماند.
//
// کاربرِ حسابدار آدرس را هر جور بنویسد باید کار کند: «acc-server»، «192.168.1.10»،
// «http://acc-server:8420/». خروجی همیشه یک origin است (بدونِ مسیر و اسلشِ پایانی)،
// چون همه‌ی فراخوان‌ها `${base}/api/...` می‌سازند و یک «/» اضافه، مسیرِ `//api` می‌داد.

/** پورتِ پیش‌فرضِ API روی سرورِ سازمانی (ENTERPRISE_PLAN.md). */
export const DEFAULT_SERVER_PORT = 8420

export type NormalizeResult = { ok: true; url: string } | { ok: false; error: string }

export function normalizeServerUrl(input: string): NormalizeResult {
  const raw = input.trim()
  if (!raw) return { ok: false, error: 'نشانیِ سرور را وارد کنید.' }

  const hasScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw)
  let parsed: URL
  try {
    parsed = new URL(hasScheme ? raw : `http://${raw}`)
  } catch {
    return { ok: false, error: 'این نشانی معتبر نیست. نمونه: acc-server یا 192.168.1.10' }
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { ok: false, error: 'نشانی باید با http یا https باشد.' }
  }
  if (!parsed.hostname) return { ok: false, error: 'نامِ رایانه‌ی سرور را وارد کنید.' }
  // نام‌کاربری/رمز در نشانی روی دیسک و در لاگ‌ها می‌ماند — هرگز.
  if (parsed.username || parsed.password) {
    return { ok: false, error: 'نشانیِ سرور نباید نامِ کاربری یا رمز داشته باشد.' }
  }
  // بدونِ پورتِ صریح: پورتِ کوبیتا، نه ۸۰. مگر کاربر خودش https نوشته باشد
  // (پشتِ پراکسیِ شرکت) که پورتِ پیش‌فرضِ همان پروتکل درست است.
  if (!parsed.port && !(hasScheme && parsed.protocol === 'https:')) {
    parsed.port = String(DEFAULT_SERVER_PORT)
  }
  return { ok: true, url: parsed.origin }
}
