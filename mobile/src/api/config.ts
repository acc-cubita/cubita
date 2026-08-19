// آدرسِ بک‌اند.
//
// **پیش‌فرض همیشه سرورِ اصلیِ کوبیتاست** — یعنی اپ به همان حساب‌هایی وصل می‌شود که با
// برنامه (دسکتاپ/وب) روی prod ساخته شده‌اند. اپ نیتیو است، پس CORS بی‌ربط است.
//
// برای اتصال به بک‌اندِ شبکه‌ی داخلی (تست/سرورِ محلی)، آدرس را صریح بده — یا در فایلِ
// `mobile/.env` بگذار، یا هنگامِ اجرا/ساخت:
//   EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8000    (روی همان WiFi)
//   EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000        (امولاتورِ اندروید → localhostِ کامپیوتر)
// Expo متغیرهای `EXPO_PUBLIC_*` را هنگامِ باندل جای‌گذاری می‌کند.

const PROD_BASE_URL = 'https://acc.cubita.ir'

const override = process.env.EXPO_PUBLIC_API_BASE_URL?.trim()

export const API_BASE_URL: string = override ? override.replace(/\/+$/, '') : PROD_BASE_URL
