import { describe, expect, it } from 'vitest'

import { matchRank, textMatches } from './faText'

describe('matchRank — ترتیبِ نتیجه‌های جست‌وجو', () => {
  it('کدِ حساب که با عبارت شروع می‌شود اول است، کدی که فقط وسطش دارد آخر', () => {
    expect(matchRank('1101 — بانک ملی', '11')).toBe(0)
    expect(matchRank('2110 — حساب‌های پرداختنی', '11')).toBe(2)
  })

  it('ابتدای نامِ حساب رتبه‌ی دوم است — «بان» بانک را پیش از «سایر بانکی‌ها»ی میانه می‌آورد', () => {
    expect(matchRank('1101 — بانک ملی', 'بان')).toBe(1)
    expect(matchRank('1190 — سایر دریافتنی‌ها', 'افت')).toBe(2)
  })

  it('رقمِ فارسی همان رقمِ لاتین است (کاربر روی چیدمانِ فارسی تایپ می‌کند)', () => {
    expect(matchRank('1101 — بانک ملی', '۱۱')).toBe(0)
    expect(textMatches('1101 — بانک ملی', '۱۱۰۱')).toBe(true)
  })

  it('مرتب‌سازی با رتبه، پایدار داخلِ هر رتبه', () => {
    const labels = ['2110 — پرداختنی', '1101 — بانک ملی', '3110 — سرمایه', '1102 — بانک ملت']
    const ranked = labels
      .filter((l) => textMatches(l, '11'))
      .map((l, i) => ({ l, i, r: matchRank(l, '11') }))
      .sort((a, b) => a.r - b.r || a.i - b.i)
      .map((x) => x.l)
    expect(ranked).toEqual(['1101 — بانک ملی', '1102 — بانک ملت', '2110 — پرداختنی', '3110 — سرمایه'])
  })
})
