// ورودِ ترایال روی prod متمرکز است: acc.cubita.ir با ?signup مستقیم روی صفحه‌ی ثبت‌نام
// باز می‌شود. (قبلاً به demo.cubita.ir می‌رفت که دیتابیسِ جدا داشت و ورود را خراب می‌کرد.)
export const TRIAL_URL = 'https://acc.cubita.ir/?signup'
export const APP_URL = 'https://acc.cubita.ir'
// لینکِ پایدارِ دانلودِ نسخه‌ی دسکتاپِ ویندوز (فایلِ سرور روی هر انتشار به‌روز می‌شود).
export const DOWNLOAD_URL = 'https://acc.cubita.ir/updates/Cubita-Setup.exe'
// همان الگو برای اپ اندروید: cubita-latest.apk روی هر انتشار به آخرین نسخه اشاره می‌کند.
export const ANDROID_APK_URL = 'https://acc.cubita.ir/updates/android/cubita-latest.apk'
// نصابِ «کوبیتا سازمانی» (سرور و کلاینتِ شبکه‌ی داخلی) — نامِ پایدارِ کانالِ امضاشده‌ی سازمانی.
export const ENTERPRISE_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/enterprise/Cubita-Enterprise-Setup.exe'
// Published separately with explicit target-OS QA status; never use the modern update feed.
const windows81Url = import.meta.env.VITE_ENTERPRISE_WINDOWS81_DOWNLOAD_URL?.trim() ?? 'https://acc.cubita.ir/updates/enterprise/windows81/Cubita-Enterprise-Windows81-Setup-1.9.16.exe'
export const ENTERPRISE_WINDOWS81_DOWNLOAD_URL = /^https:\/\//.test(windows81Url) ? windows81Url : null
export const ENTERPRISE_LEGACY_X86_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/enterprise/legacy/Cubita-Enterprise-Legacy-x86-Setup-1.9.17.exe'
export const ENTERPRISE_LEGACY_X64_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/enterprise/legacy/Cubita-Enterprise-Legacy-x64-Setup-1.9.17.exe'
