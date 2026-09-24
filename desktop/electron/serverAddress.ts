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

// --- جست‌وجوی سرور در شبکه ----------------------------------------------------

export interface NetIface {
  address: string
  family: string | number
  internal: boolean
  netmask?: string
}

/** نشانیِ خصوصیِ IPv4؟ جست‌وجو هرگز روی شبکه‌ی عمومی (VPN به اینترنت، IPِ عمومی) نمی‌رود. */
export function isPrivateIPv4(ip: string): boolean {
  const p = ip.split('.').map(Number)
  if (p.length !== 4 || p.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return false
  return p[0] === 10 || (p[0] === 172 && p[1] >= 16 && p[1] <= 31) || (p[0] === 192 && p[1] === 168)
}

/**
 * نشانی‌هایی که باید پرسیده شوند: همه‌ی ۲۵۴ نشانیِ `/24`ِ هر کارتِ شبکه‌ی خصوصی (بجز خودِ
 * این رایانه، که جداگانه با localhost پرسیده می‌شود). عمداً `/24` و نه ماسکِ واقعی: شبکه‌ی
 * `/16`ِ شرکت یعنی ۶۵ هزار درخواست، و سرورِ حسابداری تقریباً همیشه در همان `/24`ِ کاربران است.
 */
export function candidateHosts(ifaces: NetIface[]): string[] {
  const out = new Set<string>()
  const own = new Set(ifaces.map((i) => i.address))
  for (const i of ifaces) {
    const v4 = i.family === 'IPv4' || i.family === 4
    if (!v4 || i.internal || !isPrivateIPv4(i.address)) continue
    const prefix = i.address.split('.').slice(0, 3).join('.')
    for (let n = 1; n <= 254; n++) {
      const ip = `${prefix}.${n}`
      if (!own.has(ip)) out.add(ip)
    }
  }
  return [...out]
}
