// به‌روزرسانیِ درون‌برنامه‌ایِ اپ اندروید — «آپدیترِ APK روی سرورِ خودمان».
//
// **چرا این‌طور و نه Play/EAS:** اپ فعلاً مستقیم (APK) پخش می‌شود و همه‌چیز باید روی
// سرورِ خودمان بماند — دقیقاً همان دلیلی که آپدیتِ دسکتاپ هم از acc.cubita.ir/updates
// می‌آید و نه GitHub: دسترسی از ایران به سرویس‌های بیرونی نامطمئن است. این ماژول یک
// فایلِ ایستای latest.json را می‌خواند، نسخه‌ی نصب‌شده را با آن می‌سنجد، و اگر تازه‌تر
// بود APK را دانلود و از طریقِ نصب‌کننده‌ی سیستمِ اندروید نصب می‌کند.
//
// **چرا نصبِ درجا کار می‌کند:** بیلدِ release با همان کلیدِ ثابت (android/app/debug.keystore)
// امضا می‌شود؛ تا وقتی امضا ثابت بماند اندروید آپدیتِ روی نسخه‌ی قبلی را می‌پذیرد.

import { Platform } from 'react-native'
import * as Application from 'expo-application'
import * as FileSystem from 'expo-file-system/legacy'
import * as IntentLauncher from 'expo-intent-launcher'

// فیدِ آپدیت روی همان سرورِ اصلی سرو می‌شود (کنارِ به‌روزرسانیِ دسکتاپ). قابلِ override با
// EXPO_PUBLIC_UPDATE_BASE_URL برای تستِ محلی.
const DEFAULT_UPDATE_BASE = 'https://acc.cubita.ir/updates/android'
const UPDATE_BASE = (process.env.EXPO_PUBLIC_UPDATE_BASE_URL?.trim() || DEFAULT_UPDATE_BASE).replace(/\/+$/, '')
export const MANIFEST_URL = `${UPDATE_BASE}/latest.json`

export interface UpdateManifest {
  versionCode: number
  versionName: string
  apkUrl: string
  notes?: string
  mandatory?: boolean
}

/** versionCodeِ نسخه‌ی نصب‌شده (روی اندروید یک عددِ صحیحِ یکنواخت است). */
export function installedVersionCode(): number {
  const raw = Application.nativeBuildVersion // اندروید: versionCode به‌شکلِ رشته
  const n = raw ? parseInt(raw, 10) : NaN
  return Number.isFinite(n) ? n : 0
}

/** versionNameِ نمایشیِ نسخه‌ی نصب‌شده (مثلِ «۱.۲.۰»). */
export function installedVersionName(): string {
  return Application.nativeApplicationVersion ?? '—'
}

// apkUrl می‌تواند نسبی (نسبت به پوشه‌ی فید) یا مطلق باشد.
function resolveUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url
  return `${UPDATE_BASE}/${url.replace(/^\/+/, '')}`
}

/** مانیفستِ آخرین نسخه را می‌گیرد (با cache-busting تا کشِ میانی نسخه‌ی کهنه ندهد). */
export async function fetchManifest(): Promise<UpdateManifest> {
  const res = await fetch(`${MANIFEST_URL}?t=${Date.now()}`, { headers: { 'Cache-Control': 'no-cache' } })
  if (!res.ok) throw new Error(`manifest ${res.status}`)
  const j = (await res.json()) as Partial<UpdateManifest>
  if (typeof j.versionCode !== 'number' || typeof j.apkUrl !== 'string') {
    throw new Error('مانیفستِ آپدیت نامعتبر است')
  }
  return {
    versionCode: j.versionCode,
    versionName: typeof j.versionName === 'string' ? j.versionName : String(j.versionCode),
    apkUrl: resolveUrl(j.apkUrl),
    notes: typeof j.notes === 'string' ? j.notes : undefined,
    mandatory: Boolean(j.mandatory),
  }
}

/** آیا نسخه‌ی مانیفست از نسخه‌ی نصب‌شده تازه‌تر است؟ (فقط اندرویدِ بسته‌بندی‌شده) */
export function hasUpdate(m: UpdateManifest): boolean {
  return Platform.OS === 'android' && m.versionCode > installedVersionCode()
}

/** APK را در کشِ اپ دانلود می‌کند و مسیرِ file:// را برمی‌گرداند. */
export async function downloadApk(
  m: UpdateManifest,
  onProgress: (fraction: number) => void,
): Promise<string> {
  const dest = `${FileSystem.cacheDirectory}cubita-${m.versionCode}.apk`
  // اگر از دفعه‌ی قبل نیمه‌کاره مانده باشد پاکش کن تا دانلودِ سالم شود.
  try {
    const info = await FileSystem.getInfoAsync(dest)
    if (info.exists) await FileSystem.deleteAsync(dest, { idempotent: true })
  } catch {
    // اهمیتی ندارد
  }
  const task = FileSystem.createDownloadResumable(m.apkUrl, dest, {}, (p) => {
    if (p.totalBytesExpectedToWrite > 0) {
      onProgress(p.totalBytesWritten / p.totalBytesExpectedToWrite)
    }
  })
  const result = await task.downloadAsync()
  if (!result?.uri) throw new Error('دانلودِ به‌روزرسانی ناتمام ماند')
  return result.uri
}

/** نصبِ APK: سیستم‌عامل صفحه‌ی نصب را باز می‌کند و کاربر «نصب» را می‌زند. */
export async function installApk(fileUri: string): Promise<void> {
  // اندروید ۷+ برای دادنِ فایل به نصب‌کننده به content:// از راهِ FileProvider نیاز دارد
  // (خودِ expo-file-system یک FileProvider تعریف کرده؛ authority = <package>.FileSystemFileProvider).
  const contentUri = await FileSystem.getContentUriAsync(fileUri)
  await IntentLauncher.startActivityAsync('android.intent.action.INSTALL_PACKAGE', {
    data: contentUri,
    flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
  })
}
