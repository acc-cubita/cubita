import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api'
import { checkJournalDate, isOfflineRequestError, journalDateProblem } from './journalDateValidation'

const OPEN = { title: '۱۴۰۵', start_date: '2026-03-21', end_date: '2027-03-20', status: 'open' as const }
afterEach(() => vi.unstubAllGlobals())

describe('تاریخ سند و سال مالی: همان قراردادِ سرور', () => {
  it.each(['2026-03-21', '2027-03-20', '2026-09-28'])('مرز و روز %s داخل بازهٔ باز پذیرفته است', (date) => {
    expect(journalDateProblem(date, [OPEN])).toBeNull()
  })
  it('بدون هیچ سال مالی رفتارِ دفترِ قدیمی حفظ می‌شود', () => {
    expect(journalDateProblem('2026-09-28', [])).toBeNull()
  })
  it.each(['', '۱۴۰۵/۰۷/۰۶', '2026-02-30', '2026-99-28', '2026-9-28'])('تاریخ نامعتبر %s حتی آفلاین رد می‌شود', (date) => {
    expect(journalDateProblem(date, [])).toContain('از تقویم')
  })
  it('فاصلهٔ بین دو سال پذیرفته نیست', () => {
    expect(journalDateProblem('2026-09-28', [
      { ...OPEN, end_date: '2026-09-20' }, { ...OPEN, start_date: '2026-10-01' },
    ])).toContain('هنوز وارد صف نشده')
  })
  it('سال بسته رد می‌شود و فعال‌نبودنِ سال باز مانع نیست', () => {
    expect(journalDateProblem('2026-09-28', [{ ...OPEN, status: 'closed' }])).toContain('بسته است')
    expect(journalDateProblem('2026-09-28', [OPEN])).toBeNull()
  })
  it('پاسخ واقعیِ سال‌های تعریف‌شده بررسی می‌شود، با توکن و مهلت کوتاه', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([OPEN])))
    vi.stubGlobal('fetch', fetchMock)
    await expect(checkJournalDate('token', '2026-09-28')).resolves.toBe('online')
    expect(fetchMock.mock.calls[0][0]).toContain('/api/fiscal-years')
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer token')
    expect(fetchMock.mock.calls[0][1].signal).toBeDefined()
  })
  it('قطعی شبکه اجازهٔ کار آفلاین دارد', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(checkJournalDate('t', '2026-09-28')).resolves.toBe('offline')
    expect(isOfflineRequestError(new DOMException('وقت تمام شد', 'TimeoutError'))).toBe(true)
    expect(isOfflineRequestError(new TypeError('اشکال برنامه'))).toBe(false)
  })
  it.each([401, 403, 500])('پاسخ %i قطعی شبکه نیست و نباید سند وارد صف شود', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"دریافت سال مالی مجاز نیست"}', { status })))
    await expect(checkJournalDate('t', '2026-09-28')).rejects.toMatchObject({ status })
    expect(isOfflineRequestError(new ApiError('fetch failed', status, null))).toBe(false)
  })
  it('تاریخ خارج از بازه پیش از صف رد می‌شود', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([OPEN]))))
    await expect(checkJournalDate('t', '2027-03-21')).rejects.toThrow('هنوز وارد صف نشده')
  })
  it.each([null, {}, [{ ...OPEN, status: 'unknown' }]])('پاسخِ خرابِ سال مالی قطعیِ شبکه یا دفترِ بدون سال حساب نمی‌شود: %j', async (body) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body))))
    await expect(checkJournalDate('t', '2026-09-28')).rejects.toThrow('پاسخ سال مالی')
  })
})
