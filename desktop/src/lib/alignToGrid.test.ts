/**
 * نگاشتِ ستون‌های گرید به پنج خانه‌ی سربرگ و نوارِ پایینِ سند — «جمع بدهکار» باید دقیقاً زیرِ ستونِ
 * بدهکار بنشیند، هر ستونی هم که میانشان بیاید یا برود.
 */
import { describe, expect, it } from 'vitest'

import { SLOT_COUNT, slotWidths } from './alignToGrid'

const col = (id: string, w: number) => ({ id, w })

describe('slotWidths — خانه‌های هم‌خط با گرید', () => {
  it('گریدِ ساده: ردیف+حساب، شرح، بدهکار، بستانکار، آیکون‌ها', () => {
    const cols = [col('num', 44), col('account', 300), col('description', 120), col('debit', 160), col('credit', 150), col('actions', 104)]
    expect(slotWidths(cols)).toEqual([344, 120, 160, 150, 104])
  })

  it('ستون‌های میانی (ارز، تفصیلی، مرکز) به خانه‌ی اول، پیگیری به خانه‌ی آخر', () => {
    const cols = [
      col('num', 44),
      col('account', 250),
      col('fx', 90),
      col('tafsili', 110),
      col('costCenter', 120),
      col('description', 100),
      col('debit', 140),
      col('credit', 140),
      col('trackingNo', 80),
      col('trackingDate', 80),
      col('actions', 104),
    ]
    const s = slotWidths(cols)
    expect(s).toHaveLength(SLOT_COUNT)
    expect(s[0]).toBe(44 + 250 + 90 + 110 + 120)
    expect(s[2]).toBe(140)
    expect(s[4]).toBe(80 + 80 + 104)
    //: جمعِ خانه‌ها همان عرضِ جدول است — هیچ ستونی جا نمی‌ماند.
    expect(s.reduce((a, b) => a + b, 0)).toBe(cols.reduce((a, c) => a + c.w, 0))
  })
})
