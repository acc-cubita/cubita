import { describe, expect, it } from 'vitest'

import { mergeMenu, titledCount } from './moduleMenu'

const DEF = new Set(['تعریف‌ها'])
const isDef = (t: string) => DEF.has(t)

describe('منوی یک‌فهرستیِ ماژول', () => {
  it('دفتر به دسته‌ی هم‌نامِ کارش می‌پیوندد؛ درونِ دسته اول کارها، بعد دفترها', () => {
    const out = mergeMenu(
      [
        { title: 'کار روزانه', items: ['فاکتور فروش'] },
        { title: 'تعریف‌ها', items: ['نوع فروش'] },
      ],
      [
        { title: 'کار روزانه', items: ['فاکتورهای فروش'] },
        { title: 'تعریف‌ها', items: ['انواع فروش'] },
      ],
      isDef,
    )
    expect(out).toEqual([
      { title: 'کار روزانه', ops: ['فاکتور فروش'], lists: ['فاکتورهای فروش'] },
      { title: 'تعریف‌ها', ops: ['نوع فروش'], lists: ['انواع فروش'] },
    ])
  })

  it('دسته‌ی فقط-دفتر پیش از تعریف‌ها می‌نشیند — تعریف‌ها همیشه ته', () => {
    const out = mergeMenu(
      [
        { title: 'رسید و حواله', items: ['رسید'] },
        { title: 'تعریف‌ها', items: ['کالاها'] },
      ],
      [{ title: 'موجودی', items: ['کاردکس'] }],
      isDef,
    )
    expect(out.map((c) => c.title)).toEqual(['رسید و حواله', 'موجودی', 'تعریف‌ها'])
  })

  it('بی تعریف، دسته‌ی فقط-دفتر ته می‌آید', () => {
    const out = mergeMenu([{ title: 'گزارش', items: ['گزارش‌ساز'] }], [{ title: 'دیگر', items: ['x'] }], isDef)
    expect(out.map((c) => c.title)).toEqual(['گزارش', 'دیگر'])
  })

  it('دفترِ بی‌دسته ته می‌آید و از دسته‌ی بی‌عنوانِ بالا جداست', () => {
    const out = mergeMenu(
      [{ title: null, items: ['پیمان', 'متمم'] }],
      [{ title: null, items: ['پیمان‌ها'] }],
      isDef,
    )
    expect(out).toEqual([
      { title: null, ops: ['پیمان', 'متمم'], lists: [] },
      { title: null, ops: [], lists: ['پیمان‌ها'], trailing: true },
    ])
    expect(titledCount(out)).toBe(0)
  })

  it('دسته‌ی خالی (همه‌ی ردیف‌ها برای این کسب‌وکار پنهان) نمی‌آید', () => {
    const out = mergeMenu([{ title: 'الف', items: [] }], [], isDef)
    expect(out).toEqual([])
  })
})
