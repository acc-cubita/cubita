import { describe, expect, it } from 'vitest'
import { outboxErrorText } from './outboxError'

describe('خطای خوانای صفِ جدید و قدیمی', () => {
  it('پیام Electron IPC هم قبل از تبدیل تاریخ پاک می‌شود', () => {
    expect(outboxErrorText("Error invoking remote method 'journal:saveEdit': Error: تاریخ 2025-07-08 نادرست است")).toBe('تاریخ ۱۴۰۴/۰۴/۱۷ نادرست است')
  })
  it('detailِ JSON بیرون می‌آید، تاریخ جلالی و راهِ اقدام روشن می‌شود', () => {
    const raw = JSON.stringify({ detail: 'تاریخ 2026-09-28 در هیچ سال مالی تعریف‌شده‌ای نیست؛ ابتدا سال مالی مربوطه را بسازید' })
    const message = outboxErrorText(raw)
    expect(message).toContain('۱۴۰۵/۰۷/۰۶')
    expect(message).toContain('تنظیمات ← سال مالی')
    expect(message).toContain('دوباره ثبتش نکنید')
    expect(message).not.toContain('detail')
    expect(raw).toContain('2026-09-28')
  })

  it('سال بسته از سال تعریف‌نشده جداست', () => {
    expect(outboxErrorText('{"detail":"سال مالی «۱۴۰۵» بسته شده؛ ثبت سند با تاریخ 2026-09-28 مجاز نیست"}')).toContain('با مدیر هماهنگ کنید')
  })

  it('آرایهٔ اعتبارسنجی ردیف و پیام‌ها را نشان می‌دهد', () => {
    expect(outboxErrorText(JSON.stringify({ detail: [
      { loc: ['body', 'lines', 1, 'fx_rate'], msg: 'Value error, نرخ لازم است' },
      { loc: ['body'], msg: 'Value error, سند متوازن نیست' },
    ] }))).toBe('ردیف ۲: نرخ لازم است؛ سند متوازن نیست')
  })

  it.each(['TypeError: Failed to fetch', 'Error: fetch failed', 'connect ECONNREFUSED 192.168.50.1', 'The operation was aborted due to timeout'])('خطای شبکهٔ %s راهنمای فارسی دارد', (raw) => {
    expect(outboxErrorText(raw)).toContain('اتصال شبکه')
  })

  it('متن قدیمی حفظ می‌شود و HTML/JSON ناشناخته به کاربر چاپ نمی‌شود', () => {
    expect(outboxErrorText('سند متوازن نیست')).toBe('سند متوازن نیست')
    expect(outboxErrorText('{"detail":{}}')).toContain('وضعیت سرور')
    expect(outboxErrorText('<html>500</html>')).not.toContain('<html>')
    expect(outboxErrorText('{ناقص')).toBe('{ناقص')
    expect(outboxErrorText('تاریخ 2026-99-28 معتبر نیست')).toContain('2026-99-28')
  })
})
