import { describe, expect, it } from 'vitest'

import { formatJalali } from './jalali'

describe('formatJalali', () => {
  it('تاریخِ ساده', () => {
    expect(formatJalali('2027-07-22')).toBe('۱۴۰۶/۰۴/۳۱')
  })

  it('datetimeِ کامل با افست هم همان تاریخ را می‌دهد', () => {
    //: رگرسیونِ واقعی: `split('-')` روی datetime چهار تکه می‌داد و روز NaN
    //: می‌شد، پس ستونِ «انقضا» رشته‌ی خامِ ISO را نشان می‌داد.
    expect(formatJalali('2027-07-22T03:29:23.079449-12:00')).toBe('۱۴۰۶/۰۴/۳۱')
    expect(formatJalali('2027-07-22T03:29:23Z')).toBe('۱۴۰۶/۰۴/۳۱')
  })

  it('خالی خط تیره می‌شود', () => {
    expect(formatJalali(null)).toBe('—')
    expect(formatJalali(undefined)).toBe('—')
    expect(formatJalali('')).toBe('—')
  })

  it('ورودیِ بی‌معنی خودش برمی‌گردد، نه NaN', () => {
    expect(formatJalali('not-a-date')).toBe('not-a-date')
  })
})
