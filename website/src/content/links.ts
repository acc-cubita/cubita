// ورودِ ترایال روی prod متمرکز است: acc.cubita.ir با ?signup مستقیم روی صفحه‌ی ثبت‌نام
// باز می‌شود. (قبلاً به demo.cubita.ir می‌رفت که دیتابیسِ جدا داشت و ورود را خراب می‌کرد.)
export const TRIAL_URL = 'https://acc.cubita.ir/?signup'
export const APP_URL = 'https://acc.cubita.ir'
// لینکِ پایدارِ دانلودِ نسخه‌ی دسکتاپِ ویندوز (فایلِ سرور روی هر انتشار به‌روز می‌شود).
export const DOWNLOAD_URL = 'https://acc.cubita.ir/updates/Cubita-Setup.exe'
// همان الگو برای اپ اندروید: cubita-latest.apk روی هر انتشار به آخرین نسخه اشاره می‌کند.
export const ANDROID_APK_URL = 'https://acc.cubita.ir/updates/android/cubita-latest.apk'
// نشانیِ شماره‌دار نمی‌گذارد کشِ مرورگر نصابِ قدیمی را برای نصب تازه برگرداند.
export const ENTERPRISE_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/enterprise/Cubita-Enterprise-Setup-1.9.21.exe'
export const ENTERPRISE_LEGACY_X86_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/enterprise/legacy/Cubita-Enterprise-Legacy-x86-Setup-1.9.21.exe'
export const ENTERPRISE_LEGACY_X64_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/enterprise/legacy/Cubita-Enterprise-Legacy-x64-Setup-1.9.21.exe'
// نسخهٔ قدیمی۸٫۱ با خطای bootstrap جای خود را به بستهٔ اصلاح‌شدهٔ همان معماری می‌دهد.
export const ENTERPRISE_WINDOWS81_DOWNLOAD_URL = ENTERPRISE_LEGACY_X64_DOWNLOAD_URL
