/**
 * گزارشِ کرش — خودمیزبان.
 *
 * **چرا خودمیزبان و نه Sentry:** حسابِ Sentry برای یک شرکتِ ایرانی قابلِ تعلیق است،
 * و آن‌وقت گزارشِ کرش *بی‌صدا* قطع می‌شود — دقیقاً همان حالتی که این ماژول برای فرار
 * از آن نوشته شده. ضمناً stack trace و breadcrumbِ یک اپِ حسابداری نباید روی سرورِ
 * ثالث بنشیند.
 *
 * **سه قاعده‌ی سختِ این فایل:**
 *
 * ۱. **هرگز throw نمی‌کند.** گزارشگری که خودش خطا بدهد، بدتر از نداشتنش است — چون
 *    درست همان لحظه‌ای می‌شکند که اپ از قبل در حالِ شکستن است. هر مسیرِ اینجا
 *    try/catch دارد و در بدترین حالت بی‌صدا رد می‌شود.
 *
 * ۲. **آفلاین را تحمل می‌کند.** کرش معمولاً وقتی می‌افتد که شبکه هم خوب نیست.
 *    گزارش اول روی دیسک می‌نشیند، بعد تلاش برای ارسال می‌شود. اگر نرفت، سرِ اجرای
 *    بعدیِ اپ دوباره تلاش می‌شود.
 *
 * ۳. **سقف دارد.** صف روی {@link MAX_QUEUE} گزارش بسته می‌شود. یک حلقه‌ی خطا
 *    می‌تواند هزاران گزارش بسازد؛ بدونِ سقف، حافظه‌ی گوشیِ کاربر پر می‌شود.
 */
import { Platform } from 'react-native'
import * as Application from 'expo-application'
import * as Device from 'expo-device'
import { File, Paths } from 'expo-file-system'

import { API_BASE_URL } from '../api/config'

/** بیشترین گزارشی که روی دیسک نگه داشته می‌شود. قدیمی‌ترها اول دور ریخته می‌شوند. */
const MAX_QUEUE = 50

/** طولِ بیشینه‌ی stack — گزارشِ چندمگابایتی نه به درد می‌خورد نه ارسال می‌شود. */
const MAX_STACK = 8_000

/** پوشه‌ی document (نه cache) — سیستم نباید موقعِ کمبودِ فضا گزارش‌ها را پاک کند. */
const queueFile = (): File => new File(Paths.document, 'crash-queue.json')

export interface CrashReport {
  /** شناسه‌ی محلی — تا ارسالِ دوباره‌ی یک گزارش، رکوردِ تکراری نسازد. */
  id: string
  at: string
  fatal: boolean
  name: string
  message: string
  stack: string | null
  /** کجای اپ بود (نامِ صفحه). اختیاری چون خطا ممکن است بیرونِ ناوبری بیفتد. */
  screen: string | null
  app_version: string | null
  platform: string
  os_version: string | null
  device: string | null
}

// ── وضعیتِ درون‌حافظه‌ای ────────────────────────────────────────────────────

let currentScreen: string | null = null
let flushing = false

/** ناوبری این را ست می‌کند تا گزارش بگوید کاربر کجا بود. */
export function setCurrentScreen(name: string | null): void {
  currentScreen = name
}

// ── صفِ روی دیسک ───────────────────────────────────────────────────────────

async function readQueue(): Promise<CrashReport[]> {
  try {
    const f = queueFile()
    if (!f.exists) return []
    const parsed: unknown = JSON.parse(await f.text())
    return Array.isArray(parsed) ? (parsed as CrashReport[]) : []
  } catch {
    // فایلِ خراب یا غیرقابلِ خواندن: صفر گزارش، نه یک throw.
    return []
  }
}

async function writeQueue(reports: CrashReport[]): Promise<void> {
  try {
    const f = queueFile()
    if (!f.exists) f.create({ intermediates: true })
    f.write(JSON.stringify(reports))
  } catch {
    // اگر دیسک پر است یا اجازه نداریم، گزارش را از دست می‌دهیم — ولی اپ نمی‌شکند.
  }
}

// ── ساختِ گزارش ────────────────────────────────────────────────────────────

function trim(s: string | undefined | null, max: number): string | null {
  if (!s) return null
  return s.length > max ? `${s.slice(0, max)}\n…(بریده شد)` : s
}

function build(error: unknown, fatal: boolean): CrashReport {
  const err = error instanceof Error ? error : new Error(String(error))
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    at: new Date().toISOString(),
    fatal,
    name: err.name || 'Error',
    message: trim(err.message, 500) ?? 'بدونِ پیام',
    stack: trim(err.stack, MAX_STACK),
    screen: currentScreen,
    app_version: Application.nativeApplicationVersion ?? null,
    platform: Platform.OS,
    os_version: Device.osVersion ?? null,
    device: Device.modelName ?? null,
  }
}

// ── ارسال ──────────────────────────────────────────────────────────────────

/**
 * تلاش برای فرستادنِ یک دسته گزارش.
 *
 * عمداً `fetch` خام است نه کلاینتِ `api/client.ts`: آن کلاینت روی ۴۰۱ رفرش و خروج
 * را تریگر می‌کند، و یک گزارشِ کرش هرگز نباید کاربر را از حساب بیرون بیندازد.
 * ضمناً کرش ممکن است پیش از ورود بیفتد، جایی که اصلاً توکنی نیست.
 */
async function send(reports: CrashReport[]): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/client-errors`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reports }),
    })
    // ۴۰۴ یعنی اندپوینت هنوز روی سرور نیست (نسخه‌ی قدیمیِ بک‌اند). گزارش را نگه
    // می‌داریم تا بعد از استقرارِ بک‌اند خودش برود — نه اینکه دور ریخته شود.
    return res.ok
  } catch {
    return false
  }
}

/** هر چه در صف هست را می‌فرستد. اگر نرفت، سرِ اجرای بعدی دوباره تلاش می‌شود. */
export async function flush(): Promise<void> {
  if (flushing) return
  flushing = true
  try {
    const queue = await readQueue()
    if (queue.length === 0) return
    if (await send(queue)) {
      await writeQueue([])
    }
  } catch {
    // هیچ. گزارشگر نباید صدا داشته باشد.
  } finally {
    flushing = false
  }
}

/**
 * یک خطا را ثبت می‌کند: اول روی دیسک، بعد تلاش برای ارسال.
 *
 * ترتیب مهم است. اگر اول ارسال می‌کردیم و اپ وسطش می‌مرد (که برای خطای fatal
 * محتمل است)، گزارش برای همیشه از بین می‌رفت.
 */
export async function report(error: unknown, fatal = false): Promise<void> {
  try {
    const queue = await readQueue()
    queue.push(build(error, fatal))
    // سقف: قدیمی‌ترها اول می‌روند — تازه‌ترین خطاها معمولاً مرتبط‌ترند.
    await writeQueue(queue.slice(-MAX_QUEUE))
  } catch {
    return
  }
  void flush()
}

// ── نصبِ گیرنده‌ی سراسری ────────────────────────────────────────────────────

/**
 * خطاهای بیرونِ درختِ React را می‌گیرد — چیزی که `ErrorBoundary` نمی‌بیند:
 * خطای داخلِ callback، تایمر، و promiseِ رهاشده.
 *
 * گیرنده‌ی قبلی صدا زده می‌شود تا رفتارِ پیش‌فرضِ React Native (صفحه‌ی قرمزِ
 * توسعه، بستنِ اپ در production) دست‌نخورده بماند.
 */
export function installGlobalHandler(): void {
  try {
    const g = globalThis as unknown as {
      ErrorUtils?: {
        getGlobalHandler: () => (e: unknown, isFatal?: boolean) => void
        setGlobalHandler: (h: (e: unknown, isFatal?: boolean) => void) => void
      }
    }
    if (!g.ErrorUtils) return
    const previous = g.ErrorUtils.getGlobalHandler()
    g.ErrorUtils.setGlobalHandler((error, isFatal) => {
      void report(error, Boolean(isFatal))
      previous?.(error, isFatal)
    })
  } catch {
    // اگر ErrorUtils نبود (تستِ node، وبِ Expo)، بی‌صدا رد شو.
  }
}
