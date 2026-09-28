import { fetchFiscalYears, type FiscalYearRecord } from '../api'
import { formatJalali } from './jalali'

type JournalFiscalYear = Pick<FiscalYearRecord, 'title' | 'start_date' | 'end_date' | 'status'>

export function journalDateProblem(date: string, years: JournalFiscalYear[]): string | null {
  const parsed = new Date(`${date}T00:00:00Z`)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) {
    return 'تاریخ سند معتبر نیست؛ تاریخ را از تقویم انتخاب کنید.'
  }
  // همان قراردادِ سرور: دفترِ قدیمی که هیچ سال مالی ندارد هنوز اجازهٔ ثبت دارد.
  if (years.length === 0) return null
  const year = years.find((item) => item.start_date <= date && date <= item.end_date)
  if (!year) {
    return `تاریخ سند ${formatJalali(date)} در هیچ سال مالی تعریف‌شده‌ای نیست. تاریخ را اصلاح کنید یا از مدیر بخواهید در «تنظیمات ← سال مالی» بازهٔ مربوط را تعریف کند؛ سند هنوز وارد صف نشده است.`
  }
  if (year.status === 'closed') {
    return `سال مالی «${year.title}» برای تاریخ ${formatJalali(date)} بسته است. تاریخ را بررسی کنید و با مدیر هماهنگ کنید؛ سند هنوز وارد صف نشده است.`
  }
  return null
}

export function isOfflineRequestError(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  if (error.name === 'TimeoutError' || error.name === 'AbortError') return true
  return error instanceof TypeError && /failed to fetch|fetch failed|networkerror|network request failed|load failed/i.test(error.message)
}

/** آفلاین اجازهٔ صف دارد، اما پاسخِ صریحِ خطای سرور با «قطعی شبکه» اشتباه گرفته نمی‌شود. */
export async function checkJournalDate(token: string, date: string): Promise<'online' | 'offline'> {
  const invalid = journalDateProblem(date, [])
  if (invalid) throw new Error(invalid)
  let years: FiscalYearRecord[]
  try {
    years = await fetchFiscalYears(token, AbortSignal.timeout(5000))
  } catch (error) {
    if (isOfflineRequestError(error)) return 'offline'
    throw error
  }
  if (!Array.isArray(years) || years.some((year) => !year || typeof year.title !== 'string'
    || typeof year.start_date !== 'string' || typeof year.end_date !== 'string'
    || (year.status !== 'open' && year.status !== 'closed'))) {
    throw new Error('پاسخ سال مالی از سرور معتبر نیست؛ با مدیر هماهنگ کنید و دوباره ثبت سند را بزنید. پیش‌نویس حفظ شده است.')
  }
  const problem = journalDateProblem(date, years)
  if (problem) throw new Error(problem)
  return 'online'
}
