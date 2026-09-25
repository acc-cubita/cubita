import { describe, expect, it } from 'vitest'

import { fitScale } from './useFitText'

describe('fitScale — کوچک‌کردنِ عدد به‌جای پهن‌کردنِ خانه', () => {
  it('جا می‌شود: اندازه‌ی کامل', () => {
    expect(fitScale(150, 120)).toBe(1)
    expect(fitScale(150, 150)).toBe(1)
  })

  it('بیشتر از جا: به نسبت کوچک می‌شود، کمی زیرِ نسبتِ دقیق تا لبه بریده نشود', () => {
    const s = fitScale(150, 200)
    expect(s).toBeLessThan(0.75)
    expect(s).toBeGreaterThan(0.72)
    expect(150 / s).toBeGreaterThanOrEqual(150) //: پهنای تازه ≤ جعبه
    expect(200 * s).toBeLessThanOrEqual(150)
  })

  it('کفِ خوانایی: از `min` ریزتر نمی‌شود', () => {
    expect(fitScale(100, 1000)).toBe(0.55)
    expect(fitScale(100, 1000, 0.7)).toBe(0.7)
  })

  it('جعبه‌ی بی‌پهنا (چیده‌نشده / jsdom): اندازه‌ی کامل', () => {
    expect(fitScale(0, 300)).toBe(1)
  })
})
