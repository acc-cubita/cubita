import { toJalaali, toGregorian, jalaaliMonthLength, isLeapJalaaliYear } from 'jalaali-js'

export const JALALI_MONTH_NAMES = [
  'فروردین',
  'اردیبهشت',
  'خرداد',
  'تیر',
  'مرداد',
  'شهریور',
  'مهر',
  'آبان',
  'آذر',
  'دی',
  'بهمن',
  'اسفند',
]

// هفته‌ی شمسی از شنبه شروع می‌شود
export const JALALI_WEEKDAY_SHORT = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
const pad2 = (n: number) => String(n).padStart(2, '0')

export function toFaDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)])
}

export function isoToJalali(iso: string): { jy: number; jm: number; jd: number } {
  const [gy, gm, gd] = iso.split('-').map(Number)
  return toJalaali(gy, gm, gd)
}

export function jalaliToIso(jy: number, jm: number, jd: number): string {
  const { gy, gm, gd } = toGregorian(jy, jm, jd)
  return `${gy}-${pad2(gm)}-${pad2(gd)}`
}

export function formatJalali(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const { jy, jm, jd } = isoToJalali(iso)
    return toFaDigits(`${jy}/${pad2(jm)}/${pad2(jd)}`)
  } catch {
    return iso
  }
}

export function todayIso(): string {
  const now = new Date()
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`
}

function jalaliWeekdayIndex(jy: number, jm: number, jd: number): number {
  const { gy, gm, gd } = toGregorian(jy, jm, jd)
  const jsDay = new Date(gy, gm - 1, gd).getDay() // 0=یکشنبه ... 6=شنبه (استاندارد جاوااسکریپت)
  return (jsDay + 1) % 7 // 0=شنبه ... 6=جمعه (شروع هفته‌ی شمسی)
}

export function buildJalaliMonthCells(jy: number, jm: number): (number | null)[] {
  const daysInMonth = jalaaliMonthLength(jy, jm)
  const firstWeekday = jalaliWeekdayIndex(jy, jm, 1)
  const cells: (number | null)[] = []
  for (let i = 0; i < firstWeekday; i += 1) cells.push(null)
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

export { jalaaliMonthLength, isLeapJalaaliYear }
