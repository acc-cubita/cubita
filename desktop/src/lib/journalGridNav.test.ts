import { describe, expect, it } from 'vitest'

import {
  firstInRow,
  lastInRow,
  onEnter,
  onShiftEnter,
  onVertical,
  stepInRow,
  type ColId,
  type GridShape,
} from './journalGridNav'

/** گریدِ معمولی: حساب، شرح، بدهکار، بستانکار. */
const plain: GridShape = { cols: ['account', 'description', 'debit', 'credit'], rowCount: 2 }
const all = () => true

/** گریدی که ستونِ تفصیلی دارد ولی فقط ردیفِ ۰ حسابش تفصیلی می‌خواهد. */
const withTafsili: GridShape = {
  cols: ['account', 'tafsili', 'description', 'debit', 'credit'],
  rowCount: 3,
}
const tafsiliOnlyRow0 = (row: number, col: ColId) => (col === 'tafsili' ? row === 0 : true)

describe('حرکت در همان ردیف', () => {
  it('جلو و عقب می‌رود', () => {
    expect(stepInRow(plain, { row: 0, col: 0 }, 1, all)).toEqual({ row: 0, col: 1 })
    expect(stepInRow(plain, { row: 0, col: 2 }, -1, all)).toEqual({ row: 0, col: 1 })
  })

  it('در لبه null می‌دهد — تصمیمِ ردیفِ بعد مالِ این تابع نیست', () => {
    expect(stepInRow(plain, { row: 0, col: 3 }, 1, all)).toBeNull()
    expect(stepInRow(plain, { row: 0, col: 0 }, -1, all)).toBeNull()
  })

  it('از سلولِ غیرفعال می‌پرد', () => {
    //: ردیفِ ۱ تفصیلی ندارد، پس از حساب باید مستقیم به شرح برود.
    expect(stepInRow(withTafsili, { row: 1, col: 0 }, 1, tafsiliOnlyRow0)).toEqual({ row: 1, col: 2 })
    //: ولی ردیفِ ۰ دارد.
    expect(stepInRow(withTafsili, { row: 0, col: 0 }, 1, tafsiliOnlyRow0)).toEqual({ row: 0, col: 1 })
  })
})

describe('Enter', () => {
  it('به سلولِ بعدی می‌رود', () => {
    expect(onEnter(plain, { row: 0, col: 0 }, all)).toEqual({
      kind: 'move',
      to: { row: 0, col: 1 },
    })
  })

  it('در آخرین ستون به اولین ستونِ ردیفِ بعد می‌رود', () => {
    expect(onEnter(plain, { row: 0, col: 3 }, all)).toEqual({
      kind: 'move',
      to: { row: 1, col: 0 },
    })
  })

  it('در آخرین سلولِ آخرین ردیف، ردیفِ تازه می‌خواهد', () => {
    expect(onEnter(plain, { row: 1, col: 3 }, all)).toEqual({ kind: 'appendRow' })
  })

  it('ستونِ غیرفعال را در ردیفِ بعد هم رد می‌کند', () => {
    //: از آخرِ ردیفِ ۰ به ردیفِ ۱ — که تفصیلی ندارد؛ سرِ ردیف باید حساب باشد.
    const move = onEnter(withTafsili, { row: 0, col: 4 }, tafsiliOnlyRow0)
    expect(move).toEqual({ kind: 'move', to: { row: 1, col: 0 } })
  })
})

describe('Shift+Enter', () => {
  it('عقب می‌رود', () => {
    expect(onShiftEnter(plain, { row: 1, col: 2 }, all)).toEqual({
      kind: 'move',
      to: { row: 1, col: 1 },
    })
  })

  it('از سرِ ردیف به تهِ ردیفِ قبل می‌رود', () => {
    expect(onShiftEnter(plain, { row: 1, col: 0 }, all)).toEqual({
      kind: 'move',
      to: { row: 0, col: 3 },
    })
  })

  it('در ردیفِ اول ردیف نمی‌سازد — بالا رفتن هرگز داده اضافه نمی‌کند', () => {
    expect(onShiftEnter(plain, { row: 0, col: 0 }, all)).toEqual({ kind: 'none' })
  })
})

describe('پیکانِ بالا/پایین', () => {
  it('همان ستون، ردیفِ مجاور', () => {
    expect(onVertical(plain, { row: 0, col: 2 }, 1, all)).toEqual({
      kind: 'move',
      to: { row: 1, col: 2 },
    })
    expect(onVertical(plain, { row: 1, col: 2 }, -1, all)).toEqual({
      kind: 'move',
      to: { row: 0, col: 2 },
    })
  })

  it('در لبه‌ی گرید هیچ — و هرگز ردیف نمی‌سازد', () => {
    expect(onVertical(plain, { row: 0, col: 0 }, -1, all)).toEqual({ kind: 'none' })
    expect(onVertical(plain, { row: 1, col: 0 }, 1, all)).toEqual({ kind: 'none' })
  })

  it('اگر سلولِ هم‌ستون غیرفعال باشد، نزدیک‌ترین فعال را می‌گیرد — حرکت بی‌اثر نمی‌ماند', () => {
    //: از تفصیلیِ ردیفِ ۰ به پایین؛ ردیفِ ۱ تفصیلی ندارد.
    const move = onVertical(withTafsili, { row: 0, col: 1 }, 1, tafsiliOnlyRow0)
    expect(move).toEqual({ kind: 'move', to: { row: 1, col: 2 } })
  })
})

describe('سر و تهِ ردیف', () => {
  it('اولین و آخرینِ فعال را می‌دهد', () => {
    expect(firstInRow(plain, 0, all)).toEqual({ row: 0, col: 0 })
    expect(lastInRow(plain, 0, all)).toEqual({ row: 0, col: 3 })
  })

  it('ردیفِ بی‌سلولِ فعال null می‌دهد', () => {
    expect(firstInRow(plain, 0, () => false)).toBeNull()
  })
})

describe('سندِ ۳۰۰ ردیفی', () => {
  //: هدف صحت است نه سرعت — ولی اگر ناوبری با شمارِ ردیف بزرگ بشکند، سندِ بزرگ
  //: غیرقابلِ استفاده می‌شود و هیچ تستِ دیگری نمی‌گیردش.
  const big: GridShape = { cols: plain.cols, rowCount: 300 }

  it('از تهِ ردیفِ ۲۹۸ به سرِ ۲۹۹ می‌رود', () => {
    expect(onEnter(big, { row: 298, col: 3 }, all)).toEqual({
      kind: 'move',
      to: { row: 299, col: 0 },
    })
  })

  it('تهِ آخرین ردیف ردیفِ ۳۰۱ام را می‌خواهد', () => {
    expect(onEnter(big, { row: 299, col: 3 }, all)).toEqual({ kind: 'appendRow' })
  })
})
