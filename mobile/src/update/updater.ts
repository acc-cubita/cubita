// اطلاع‌رسانیِ نسخه‌ی تازه‌ی اپ اندروید.
//
// **چرا دیگر APK دانلود و نصب نمی‌کند:** نسخه‌ی پیشین این ماژول فایلِ APK را از
// سرورِ خودمان می‌گرفت و با `REQUEST_INSTALL_PACKAGES` نصبش می‌کرد. کافه‌بازار این
// دسترسی را رد می‌کند — و درست هم می‌گوید: اپی که خودش را از بیرونِ فروشگاه
// به‌روز کند، بازبینیِ فروشگاه را دور می‌زند.
//
// حالا اپ فقط *می‌فهمد* که نسخه‌ی تازه‌ای هست و کاربر را به صفحه‌ی خودش در بازار
// می‌فرستد. نه دسترسیِ نصب لازم است، نه دانلودی انجام می‌شود، نه فایلی روی دستگاه
// نوشته می‌شود — یعنی چیزی نمی‌ماند که فروشگاه به آن ایراد بگیرد.
//
// فیدِ `latest.json` سرِ جایش می‌ماند چون هنوز همان کارِ «تازه‌تر هست یا نه» را
// می‌کند و برای دستگاه‌هایی که بازار ندارند تنها راهِ فهمیدن است.

import { Linking, Platform } from 'react-native'
import * as Application from 'expo-application'

// فیدِ آپدیت روی همان سرورِ اصلی سرو می‌شود (کنارِ به‌روزرسانیِ دسکتاپ). قابلِ override با
// EXPO_PUBLIC_UPDATE_BASE_URL برای تستِ محلی.
const DEFAULT_UPDATE_BASE = 'https://acc.cubita.ir/updates/android'
const UPDATE_BASE = (process.env.EXPO_PUBLIC_UPDATE_BASE_URL?.trim() || DEFAULT_UPDATE_BASE).replace(/\/+$/, '')
export const MANIFEST_URL = `${UPDATE_BASE}/latest.json`

/** شناسه‌ی بسته در بازار — همان `applicationId` در build.gradle. */
const PACKAGE_ID = 'ir.cubita.app'
/** دیپ‌لینکِ اپِ بازار؛ اگر نصب باشد مستقیم صفحه‌ی برنامه باز می‌شود. */
const BAZAAR_DEEPLINK = `bazaar://details?id=${PACKAGE_ID}`
/** اگر اپِ بازار نبود، همان صفحه روی وب. */
const BAZAAR_WEB = `https://cafebazaar.ir/app/${PACKAGE_ID}`

export interface UpdateManifest {
  versionCode: number
  versionName: string
  notes?: string
  mandatory?: boolean
}

/** versionCodeِ نسخه‌ی نصب‌شده (روی اندروید یک عددِ صحیحِ یکنواخت است). */
export function installedVersionCode(): number {
  const raw = Application.nativeBuildVersion // اندروید: versionCode به‌شکلِ رشته
  const n = raw ? parseInt(raw, 10) : NaN
  return Number.isFinite(n) ? n : 0
}

/** versionNameِ نمایشیِ نسخه‌ی نصب‌شده (مثلِ «۱.۶.۰»). */
export function installedVersionName(): string {
  return Application.nativeApplicationVersion ?? '—'
}

/** مانیفستِ آخرین نسخه را می‌گیرد (با cache-busting تا کشِ میانی نسخه‌ی کهنه ندهد). */
export async function fetchManifest(): Promise<UpdateManifest> {
  const res = await fetch(`${MANIFEST_URL}?t=${Date.now()}`, { headers: { 'Cache-Control': 'no-cache' } })
  if (!res.ok) throw new Error(`manifest ${res.status}`)
  const j = (await res.json()) as Partial<UpdateManifest>
  if (typeof j.versionCode !== 'number') throw new Error('مانیفستِ آپدیت نامعتبر است')
  return {
    versionCode: j.versionCode,
    versionName: typeof j.versionName === 'string' ? j.versionName : String(j.versionCode),
    notes: typeof j.notes === 'string' ? j.notes : undefined,
    mandatory: Boolean(j.mandatory),
  }
}

/** آیا نسخه‌ی مانیفست از نسخه‌ی نصب‌شده تازه‌تر است؟ (فقط اندرویدِ بسته‌بندی‌شده) */
export function hasUpdate(m: UpdateManifest): boolean {
  return Platform.OS === 'android' && m.versionCode > installedVersionCode()
}

/** صفحه‌ی برنامه در بازار را باز می‌کند؛ اگر اپِ بازار نبود، نسخه‌ی وبش.
 *
 *  `canOpenURL` برای طرحِ `bazaar` بدونِ اعلانِ `<queries>` در مانیفست همیشه false
 *  می‌دهد (اندروید ۱۱+)، پس آن اعلان کنارِ همین کد لازم است. */
export async function openStorePage(): Promise<void> {
  try {
    if (await Linking.canOpenURL(BAZAAR_DEEPLINK)) {
      await Linking.openURL(BAZAAR_DEEPLINK)
      return
    }
  } catch {
    // به وب برمی‌گردیم
  }
  await Linking.openURL(BAZAAR_WEB)
}
