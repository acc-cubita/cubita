import Constants from 'expo-constants'

// آدرسِ بک‌اند — سه لایه‌ی اولویت تا اپ هم روی prod و هم روی «شبکه‌ی داخلی» کار کند،
// بی‌آنکه لازم باشد این فایل دست بخورد:
//
//   ۱) EXPO_PUBLIC_API_BASE_URL — پینِ صریح. برای APKِ داخلی/تست: هنگامِ build ست کن،
//      مثلاً EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8000 یا http://cubita.local:8000
//   ۲) کشفِ خودکارِ LAN در حالتِ توسعه (Expo Go): همان ماشینی که Metro را می‌راند بک‌اند را
//      هم روی :8000 دارد؛ آدرسش از hostUri گرفته می‌شود تا گوشیِ روی همان WiFi وصل شود.
//   ۳) prod: سرورِ اصلیِ کوبیتا (HTTPS). اپ نیتیو است، پس CORS بی‌ربط است.

const PROD_BASE_URL = 'https://acc.cubita.ir'
const DEV_BACKEND_PORT = 8000

function lanBaseUrl(): string | null {
  // hostUri شبیهِ «۱۹۲.۱۶۸.۱.۲۰:۸۰۸۱» است؛ فقط میزبان را می‌خواهیم و پورتِ بک‌اند را می‌گذاریم.
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.expoGoConfig?.debuggerHost ?? null
  const host = hostUri?.split(':')[0]?.trim()
  if (!host) return null
  // امولاتورِ اندروید میزبان را با ۱۰.۰.۲.۲ می‌بیند، نه localhost.
  const target = host === 'localhost' || host === '127.0.0.1' ? '10.0.2.2' : host
  return `http://${target}:${DEV_BACKEND_PORT}`
}

function resolveBaseUrl(): string {
  const override = process.env.EXPO_PUBLIC_API_BASE_URL?.trim()
  if (override) return override.replace(/\/+$/, '')
  if (__DEV__) {
    const lan = lanBaseUrl()
    if (lan) return lan
  }
  return PROD_BASE_URL
}

export const API_BASE_URL: string = resolveBaseUrl()
