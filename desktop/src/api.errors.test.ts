import { describe, expect, it } from 'vitest'

import { ApiError, detailText } from './api'

/**
 * `detail`ِ FastAPI دو شکل دارد: متن (HTTPException) و آرایه (۴۲۲). آرایه تا امروز
 * مستقیم به `new Error` می‌رفت و کاربر «[object Object]» می‌دید.
 */
describe('متنِ خوانای خطای سرور', () => {
  it('متن همان است', () => {
    expect(detailText('سند یافت نشد')).toBe('سند یافت نشد')
  })

  it('آرایه‌ی ۴۲۲ → پیام‌ها، بی پیشوندِ «Value error, » و بی تکرار', () => {
    const detail = [
      { loc: ['body'], msg: 'Value error, سند متوازن نیست' },
      { loc: ['body', 'lines', 0], msg: 'Value error, نرخ لازم است' },
      { loc: ['body', 'lines', 1], msg: 'Value error, نرخ لازم است' },
    ]
    expect(detailText(detail)).toBe('سند متوازن نیست؛ نرخ لازم است')
  })

  it('شکلِ ناشناخته → null تا پیامِ پیش‌فرض بیاید', () => {
    expect(detailText({ foo: 1 })).toBeNull()
    expect(detailText([{ nope: true }])).toBeNull()
    expect(detailText(undefined)).toBeNull()
  })

  it('ApiError همان Error است — `err instanceof Error ? err.message` بی‌تغییر کار می‌کند', () => {
    const e = new ApiError('پیام', 422, [])
    expect(e).toBeInstanceOf(Error)
    expect(e.message).toBe('پیام')
    expect(e.status).toBe(422)
  })
})
