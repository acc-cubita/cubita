import type { LicenseInfo } from '../api'

//: برچسب و لحنِ هر حالتِ مجوزِ کوبیتا سازمانی — مشترکِ صفحه‌ی «مجوز نرم‌افزار» و نوارِ
//: بالای اپ، تا یک حالت در دو جا با دو اسم دیده نشود.
export const LICENSE_MODE_LABEL: Record<LicenseInfo['mode'], string> = {
  trial: 'آزمایشی',
  trial_expired: 'آزمایشیِ تمام‌شده',
  active: 'فعال',
  grace: 'منقضی — در مهلت',
  expired: 'منقضی',
  clock: 'ساعتِ سرور نادرست',
  mismatch: 'مجوزِ رایانه‌ی دیگر',
  invalid: 'نامعتبر',
}

export type LicenseTone = 'ok' | 'warn' | 'err'

//: سقفِ کاربرانِ نسخه‌ی رایگان — آینه‌ی `FREE_SEATS` در `backend/app/services/enterprise_free.py`.
//: فقط برای متنِ پیش از ثبت‌نام است؛ پس از آن سقفِ واقعی از خودِ مجوز (`seats`) خوانده می‌شود.
export const FREE_SEATS = 3

//: «نسخه»ی این نصب، به زبانِ کاربر: رایگان/تجاری از مجوز، و پیش از هر مجوزی آزمایشی.
export function licenseEditionLabel(lic: LicenseInfo): string {
  if (lic.tier === 'free') return `رایگان — تا ${(lic.seats ?? FREE_SEATS).toLocaleString('fa-IR')} کاربر`
  if (lic.tier === 'paid') return 'تجاری'
  return 'آزمایشی — هنوز ثبت‌نام نشده'
}

export function licenseTone(lic: LicenseInfo): LicenseTone {
  if (!lic.writable) return 'err'
  if (lic.mode === 'active' && (lic.days_left == null || lic.days_left > 30)) return 'ok'
  return 'warn'
}

//: نوارِ بالای اپ فقط وقتی دیده می‌شود که کاری از کاربر برمی‌آید: آزمایشی، نزدیکِ
//: انقضا، یا بسته‌بودنِ ثبت. مجوزِ فعالِ دور از انقضا هیچ نواری نمی‌خواهد.
export const licenseNeedsAttention = (lic: LicenseInfo) => licenseTone(lic) !== 'ok'
