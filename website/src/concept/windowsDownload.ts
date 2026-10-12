import { ENTERPRISE_DOWNLOAD_URL, ENTERPRISE_WINDOWS81_DOWNLOAD_URL } from '../content/links'

export type WindowsVersion = '' | '7' | '8' | '8.1' | '10-11'
export type WindowsBits = '' | '32' | '64'
export type WindowsSuggestion = { version: WindowsVersion; bits: WindowsBits }
export type WindowsHints = { platform?: string; architecture?: string; bitness?: string; wow64?: boolean }

export function suggestWindows(userAgent: string, hints?: WindowsHints): WindowsSuggestion {
  if (!/Windows NT/i.test(userAgent)) return { version: '', bits: '' }
  const nt = /Windows NT (\d+\.\d+)/i.exec(userAgent)?.[1]
  const version: WindowsVersion = nt === '6.1' ? '7' : nt === '6.2' ? '8' : nt === '6.3' ? '8.1' : nt === '10.0' ? '10-11' : ''
  // A 32-bit browser can run on 64-bit Windows; absence of Win64 is not proof of 32-bit OS.
  let bits: WindowsBits = /Win64|WOW64|x64/i.test(userAgent) ? '64' : ''
  if (hints?.platform === 'Windows') {
    if (hints.architecture === 'arm') return { version, bits: '' }
    if (hints.wow64 === true || hints.bitness === '64') bits = '64'
    else if (hints.architecture === 'x86' && hints.bitness === '32' && hints.wow64 === false) bits = '32'
  }
  if (/ARM|aarch64/i.test(userAgent)) bits = ''
  return { version, bits }
}

export function windowsPackage(version: WindowsVersion, bits: WindowsBits) {
  if (!version || !bits) return { href: null, message: 'نسخهٔ ویندوز و معماری سیستم را انتخاب کنید.' }
  if (bits === '32') return { href: null, message: 'نصاب سازمانی ۳۲ بیتی هنوز آماده و منتشر نشده است. فایل ۶۴ بیتی روی ویندوز ۳۲ بیتی نصب نمی‌شود.' }
  if (version === '7' || version === '8') return { href: null, message: 'نصاب کامل سرور و کلاینت برای این ویندوز هنوز آماده و منتشر نشده است.' }
  if (version === '8.1') return { href: ENTERPRISE_WINDOWS81_DOWNLOAD_URL, message: 'نسخهٔ سازگار ۱٫۹٫۱۶ — سرور و کلاینت. آزمون نصب و اجرای واقعی روی ویندوز ۸٫۱ هنوز تکمیل نشده است.' }
  return { href: ENTERPRISE_DOWNLOAD_URL, message: 'نسخهٔ اصلی — سرور و کلاینت، برای ویندوز ۱۰ و ۱۱ نسخهٔ ۶۴ بیتی.' }
}
