/**
 * قالبِ عدد و تاریخ.
 *
 * این‌ها بی‌صدا غلط می‌دهند: یک تاریخِ جلالیِ یک‌روز‌عقب یا یک «۰» به‌جای عددِ
 * واردشده هیچ خطایی نمی‌سازد، فقط دفترِ غلط.
 */
import {
  faDate,
  faQty,
  normalizeDecimal,
  normalizeInt,
  toFaDigits,
  toLatinDigits,
  todayIso,
} from '../format'

describe('ارقام', () => {
  it('لاتین → فارسی', () => {
    expect(toFaDigits('1405/06/16')).toBe('۱۴۰۵/۰۶/۱۶')
  })

  it('فارسی → لاتین', () => {
    expect(toLatinDigits('۱۲۳۴')).toBe('1234')
  })

  it('عربی‌ـهندی هم شناخته می‌شود', () => {
    // صفحه‌کلیدهای فارسیِ اندروید گاهی ٠١٢ می‌دهند نه ۰۱۲. اگر این را نشناسیم،
    // فیلترِ «فقط رقم» کلِ عدد را دور می‌ریزد و کاربر «۰» ثبت می‌کند.
    expect(toLatinDigits('٣٤٥')).toBe('345')
  })
})

describe('تاریخِ جلالی', () => {
  it('نوروز', () => {
    expect(faDate('2026-03-21')).toBe('۱۴۰۵/۰۱/۰۱')
  })

  it('ISOِ کامل هم قبول است (created_at)', () => {
    expect(faDate('2026-09-06T11:30:00Z')).toBe('۱۴۰۵/۰۶/۱۵')
  })

  it('روزِ آخرِ سال', () => {
    expect(faDate('2026-03-20')).toBe('۱۴۰۴/۱۲/۲۹')
  })

  it('خالی یعنی خط تیره، نه «Invalid Date»', () => {
    expect(faDate(null)).toBe('—')
    expect(faDate('')).toBe('—')
  })
})

describe('todayIso', () => {
  it('وقتِ محلی می‌دهد نه UTC', () => {
    // با UTC، کاربرِ ایران بعد از ساعتِ ۳:۳۰ بامداد سندش یک روز عقب ثبت می‌شد.
    const d = new Date()
    const p = (n: number) => String(n).padStart(2, '0')
    expect(todayIso()).toBe(`${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`)
  })
})

describe('پاک‌سازیِ ورودی', () => {
  it('مبلغ: جداکننده و رقمِ فارسی', () => {
    expect(normalizeInt('۱٬۲۰۰٬۰۰۰')).toBe('1200000')
  })

  it('مبلغ: ممیز را هم دور می‌ریزد', () => {
    expect(normalizeInt('12.5')).toBe('125')
  })

  it('مقدار: ممیز مجاز است', () => {
    expect(normalizeDecimal('۲٫۵')).toBe('2.5')
  })

  it('مقدار: فقط یک ممیز — وگرنه سرور NaN می‌گیرد', () => {
    expect(normalizeDecimal('1.2.3')).toBe('1.23')
  })

  it('مقدار: حروف حذف می‌شوند', () => {
    expect(normalizeDecimal('12 کیلو')).toBe('12')
  })
})

describe('نمایشِ مقدار', () => {
  it('صفرهای بی‌معنیِ اعشار نمی‌آیند', () => {
    expect(faQty('12.000')).toBe('۱۲')
  })

  it('اعشارِ واقعی می‌ماند', () => {
    expect(faQty('2.5')).toBe('۲٫۵')
  })
})
