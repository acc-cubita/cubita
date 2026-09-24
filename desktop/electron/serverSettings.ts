import { app } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import { normalizeServerUrl } from './serverAddress.js'

// نسخه‌ی این بیلد و نشانیِ سروری که کلاینت به آن وصل می‌شود.
//
// نسخه‌ی ابری نشانیِ ثابتِ acc.cubita.ir را دارد. نسخه‌ی سازمانی نشانی را از کاربر
// می‌گیرد (جادوگرِ «اتصال به سرور») و در userData نگه می‌دارد — همان الگوی
// backup-settings.json. appIdِ نسخه‌ی سازمانی جداست، پس این فایل هرگز با نصبِ ابریِ
// کنارش قاطی نمی‌شود.

declare const __CUBITA_EDITION__: string

export type Edition = 'cloud' | 'enterprise'

export const EDITION: Edition = __CUBITA_EDITION__ === 'enterprise' ? 'enterprise' : 'cloud'

const CLOUD_URL = 'https://acc.cubita.ir'
const DEV_URL = 'http://localhost:8000'

interface ServerSettings {
  url: string
}

function settingsPath(): string {
  return path.join(app.getPath('userData'), 'server-settings.json')
}

function readSaved(): string | null {
  try {
    const raw = JSON.parse(fs.readFileSync(settingsPath(), 'utf8')) as Partial<ServerSettings>
    if (typeof raw.url !== 'string') return null
    const n = normalizeServerUrl(raw.url)
    return n.ok ? n.url : null
  } catch {
    // نبودن/خرابیِ فایل یعنی هنوز وصل نشده — جادوگر دوباره می‌پرسد.
    return null
  }
}

/**
 * نشانیِ سرور، یا `null` وقتی نسخه‌ی سازمانی هنوز به سروری وصل نشده.
 *
 * `CUBITA_API_URL` در هر دو نسخه مقدم است — برای توسعه و عیب‌یابی.
 */
export function currentServerUrl(): string | null {
  if (process.env.CUBITA_API_URL) return process.env.CUBITA_API_URL
  if (EDITION === 'enterprise') return readSaved()
  return app.isPackaged ? CLOUD_URL : DEV_URL
}

export function saveServerUrl(input: string): { ok: true; url: string } | { ok: false; error: string } {
  if (EDITION !== 'enterprise') return { ok: false, error: 'نشانیِ سرور فقط در کوبیتا سازمانی تنظیم‌شدنی است.' }
  const n = normalizeServerUrl(input)
  if (!n.ok) return n
  fs.writeFileSync(settingsPath(), JSON.stringify({ url: n.url } satisfies ServerSettings, null, 2), 'utf8')
  return n
}

export type ServerProbe =
  | { ok: true; url: string }
  | { ok: false; url?: string; error: string }

/**
 * آزمایشِ اتصال — در main، نه رندرر، تا پیش از هر تنظیمِ CORS هم جواب بدهد.
 *
 * فقط «جواب داد» کافی نیست: باید سرورِ **کوبیتا سازمانی** باشد. کلاینتی که به
 * acc.cubita.ir یا هر وب‌سرورِ دیگری روی آن پورت وصل شود، بعداً خطاهای گیج‌کننده می‌دهد.
 */
export async function probeServer(input: string): Promise<ServerProbe> {
  const n = normalizeServerUrl(input)
  if (!n.ok) return n
  let res: Response
  try {
    res = await fetch(`${n.url}/api/health`, { signal: AbortSignal.timeout(5000) })
  } catch {
    return {
      ok: false,
      url: n.url,
      error:
        'به این نشانی دسترسی نیست. روشن‌بودنِ رایانه‌ی سرور، یکی‌بودنِ شبکه، و بازبودنِ ' +
        'فایروالِ ویندوز روی سرور را بررسی کنید.',
    }
  }
  let body: { status?: string; edition?: string } = {}
  try {
    body = (await res.json()) as typeof body
  } catch {
    // پاسخِ غیرِ JSON یعنی چیزِ دیگری روی این پورت است.
  }
  if (!res.ok || body.status !== 'ok') {
    return { ok: false, url: n.url, error: 'این نشانی جواب داد ولی سرورِ کوبیتا نیست.' }
  }
  if (body.edition !== 'enterprise') {
    return { ok: false, url: n.url, error: 'این سرورِ کوبیتا سازمانی نیست.' }
  }
  return { ok: true, url: n.url }
}
