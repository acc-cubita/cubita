import { describe, expect, it } from 'vitest'

import type { JournalDraftLine } from './journalEntryDraft'
import {
  copyPreviousInto,
  duplicateAt,
  faRows,
  findLines,
  isPostedLine,
  postedRowNumbers,
  remainingOf,
  removeAt,
  removeRows,
  rowsMissingTafsili,
  rowsWithoutAccount,
  rowsWithoutAmount,
  serverLineErrors,
  sumSide,
} from './journalLineOps'

const line = (p: Partial<JournalDraftLine> = {}): JournalDraftLine => ({
  accountId: '',
  debit: '',
  credit: '',
  fxAmount: '',
  trackingNo: '',
  trackingDate: '',
  analyticId: '',
  description: '',
  ...p,
})

describe('تکرارِ ردیف', () => {
  const rows = [
    line({ accountId: 'a1', debit: '1000', description: 'اجاره', analyticId: 'x' }),
    line({ accountId: 'a2', credit: '1000' }),
  ]

  it('رونوشت را **بلافاصله بعد از خودش** می‌گذارد، نه ته جدول', () => {
    const out = duplicateAt(rows, 0)
    expect(out).toHaveLength(3)
    expect(out[1].accountId).toBe('a1')
    expect(out[2].accountId).toBe('a2')
  })

  it('مبلغ را هم کپی می‌کند — تفاوتِ عمدی با «کپی از ردیف قبل»', () => {
    expect(duplicateAt(rows, 0)[1].debit).toBe('1000')
  })

  it('تفصیلی و شرح را هم می‌آورد', () => {
    const copy = duplicateAt(rows, 0)[1]
    expect(copy.analyticId).toBe('x')
    expect(copy.description).toBe('اجاره')
  })

  it('آرایه‌ی ورودی را تغییر نمی‌دهد', () => {
    duplicateAt(rows, 0)
    expect(rows).toHaveLength(2)
  })

  it('شاخصِ نامعتبر آرایه را دست‌نخورده برمی‌گرداند', () => {
    expect(duplicateAt(rows, 9)).toBe(rows)
  })
})

describe('کپی از ردیف قبل', () => {
  const rows = [
    line({ accountId: 'a1', analyticId: 'x', description: 'اجاره', debit: '5000' }),
    line({ accountId: '', credit: '' }),
  ]

  it('حساب، تفصیلی و شرح را می‌آورد', () => {
    const out = copyPreviousInto(rows, 1)
    expect(out[1].accountId).toBe('a1')
    expect(out[1].analyticId).toBe('x')
    expect(out[1].description).toBe('اجاره')
  })

  it('**مبلغ را نمی‌آورد** — عددِ جامانده بی‌صدا در سند می‌ماند', () => {
    expect(copyPreviousInto(rows, 1)[1].debit).toBe('')
    expect(copyPreviousInto(rows, 1)[1].credit).toBe('')
  })

  it('روی ردیفِ اول بی‌اثر است', () => {
    expect(copyPreviousInto(rows, 0)).toBe(rows)
  })

  it('ردیف‌های دیگر را دست نمی‌زند', () => {
    expect(copyPreviousInto(rows, 1)[0]).toEqual(rows[0])
  })
})

describe('حذف ردیف', () => {
  it('حذف می‌کند وقتی بیش از دو ردیف هست', () => {
    const rows = [line(), line(), line()]
    expect(removeAt(rows, 1)).toHaveLength(2)
  })

  it('کفِ دو ردیف را نگه می‌دارد — سندِ تک‌ردیفی معنا ندارد', () => {
    const rows = [line(), line()]
    expect(removeAt(rows, 0)).toBe(rows)
  })
})

describe('جمعِ هر طرف', () => {
  it('رشته‌ی خالی و نامعتبر صفر است', () => {
    const rows = [line({ debit: '100' }), line({ debit: '' }), line({ debit: 'خط' })]
    expect(sumSide(rows, 'debit')).toBe(100)
  })
})

describe('مبلغِ باقی‌مانده', () => {
  it('کمبودِ بستانکار را بستانکار می‌خواهد', () => {
    expect(remainingOf(20_000_000, 0)).toEqual({ amount: 20_000_000, side: 'credit' })
  })

  it('کمبودِ بدهکار را بدهکار می‌خواهد', () => {
    expect(remainingOf(0, 5_000)).toEqual({ amount: 5_000, side: 'debit' })
  })

  it('سندِ متوازن پیشنهادی ندارد', () => {
    expect(remainingOf(1000, 1000)).toBeNull()
  })

  it('سندِ خالی هم پیشنهادی ندارد', () => {
    expect(remainingOf(0, 0)).toBeNull()
  })

  it('سناریوی واقعیِ درخواست: بانک ۲۰٬۰۰۰٬۰۰۰ بدهکار → ردیف دوم همان را بستانکار می‌خواهد', () => {
    const rows = [line({ accountId: 'bank', debit: '20000000' }), line({ accountId: 'party' })]
    const r = remainingOf(sumSide(rows, 'debit'), sumSide(rows, 'credit'))
    expect(r).toEqual({ amount: 20_000_000, side: 'credit' })
  })
})

describe('شماره‌ی ردیف در خطا = شماره‌ی گرید', () => {
  //: سناریوی گزارش‌شده: پُر، خالی، نامعتبر. پیش از رفع، شمارش روی ردیف‌های پُر بود
  //: و پیام «ردیف ۲» می‌گفت برای ردیفی که کاربر کنارش «۳» می‌بیند.
  const TAFSILI = new Set(['needs-tafsili'])
  const rows = [
    line({ accountId: 'bank', debit: '5000' }),
    line(),
    line({ accountId: 'needs-tafsili', credit: '5000' }),
  ]

  it('ردیفِ خالیِ وسط شماره‌ها را جابه‌جا نمی‌کند — «ردیف ۳»', () => {
    expect(rowsMissingTafsili(rows, TAFSILI, '')).toEqual([3])
  })

  it('تفصیلیِ خودِ ردیف یا سربرگ کافی است', () => {
    expect(rowsMissingTafsili([rows[0], rows[1], { ...rows[2], analyticId: 't1' }], TAFSILI, '')).toEqual([])
    expect(rowsMissingTafsili(rows, TAFSILI, 'header-t')).toEqual([])
  })

  it('ردیفِ بی‌مبلغ فرستاده نمی‌شود، پس خطا هم نمی‌گیرد', () => {
    expect(rowsMissingTafsili([line({ accountId: 'needs-tafsili' })], TAFSILI, '')).toEqual([])
  })

  it('نگاشتِ payload ← گرید: ردیفِ دومِ فرستاده‌شده، ردیفِ سومِ گرید است', () => {
    expect(postedRowNumbers(rows)).toEqual([1, 3])
    expect(rows.filter(isPostedLine)).toHaveLength(2)
  })

  it('متنِ شماره‌ها فارسی و خوانا', () => {
    expect(faRows([3])).toBe('۳')
    expect(faRows([3, 5])).toBe('۳ و ۵')
    expect(faRows([3, 5, 17])).toBe('۳، ۵ و ۱۷')
  })
})

describe('ردیفِ نیمه‌کاره بی‌صدا حذف نمی‌شود', () => {
  const rows = [
    line({ accountId: 'bank', debit: '100' }),
    line(), // خالیِ واقعی — خطا نیست
    line({ debit: '50' }), // مبلغ بی حساب
    line({ accountId: 'cust' }), // حساب بی مبلغ
    line({ accountId: 'cust', credit: '100' }),
  ]
  it('مبلغ بی حساب → ردیفِ ۳ (شماره‌ی گرید)', () => {
    expect(rowsWithoutAccount(rows)).toEqual([3])
  })
  it('حساب بی مبلغ → ردیفِ ۴؛ ردیفِ کاملاً خالی هیچ‌کدام نیست', () => {
    expect(rowsWithoutAmount(rows)).toEqual([4])
  })
})

describe('خطای ۴۲۲ِ سرور ← شماره‌ی گرید', () => {
  //: ردیفِ ۲ِ گرید خالی است، پس ردیفِ دومِ payload ردیفِ ۳ِ گرید است.
  const posted = postedRowNumbers([
    line({ accountId: 'bank', debit: '100' }),
    line(),
    line({ accountId: 'cust', credit: '100' }),
  ])

  it('جایگاهِ payload به ردیفِ گرید برمی‌گردد و «Value error, » برداشته می‌شود', () => {
    const detail = [{ loc: ['body', 'lines', 1, 'fx_rate'], msg: 'Value error, نرخِ ارز باید بزرگ‌تر از صفر باشد' }]
    expect(serverLineErrors(detail, posted)).toBe('ردیفِ ۳: نرخِ ارز باید بزرگ‌تر از صفر باشد')
  })

  it('پیامِ انگلیسیِ پایدانتیک → نامِ فارسیِ فیلد', () => {
    const detail = [{ loc: ['body', 'lines', 0, 'tracking_no'], msg: 'String should have at most 50 characters' }]
    expect(serverLineErrors(detail, posted)).toBe('ردیفِ ۱: مقدارِ «شماره پیگیری» نامعتبر است')
  })

  it('چند ردیف، به ترتیبِ گرید', () => {
    const detail = [
      { loc: ['body', 'lines', 1, 'fx_amount'], msg: 'Value error, مبلغ ارزی لازم است' },
      { loc: ['body', 'lines', 0, 'fx_rate'], msg: 'Value error, نرخ لازم است' },
    ]
    expect(serverLineErrors(detail, posted)).toBe('ردیفِ ۱: نرخ لازم است — ردیفِ ۳: مبلغ ارزی لازم است')
  })

  it('خطای سطحِ سند یا متنِ ساده، ردیفی نیست → null', () => {
    expect(serverLineErrors([{ loc: ['body'], msg: 'Value error, سند متوازن نیست' }], posted)).toBeNull()
    expect(serverLineErrors('سند یافت نشد', posted)).toBeNull()
  })

  it('خطای ۴۰۰ با اندیسِ ساختاری و متنِ قدیمی، ردیفِ واقعیِ گرید را نشان می‌دهد', () => {
    const tagged = [{ index: 1, field: 'tracking_no', message: 'این حساب پیگیری نمی‌پذیرد.' }]
    expect(serverLineErrors('پیگیری مجاز نیست', posted, tagged)).toBe('ردیفِ ۳: این حساب پیگیری نمی‌پذیرد.')
    expect(serverLineErrors('پیگیری مجاز نیست', posted, [{ index: 2, field: 'tracking_no', message: 'نامعتبر' }])).toBeNull()
  })
})

describe('کپی از ردیفِ قبل — مرکزِ هزینه هم (§۱۸)', () => {
  it('حساب، تفصیلی، مرکز و شرح می‌آیند؛ مبلغ نه', () => {
    const rows = [line({ accountId: 'a1', analyticId: 't', costCenterId: 'cc1', description: 'اجاره', debit: '900' }), line()]
    expect(copyPreviousInto(rows, 1)[1]).toMatchObject({ accountId: 'a1', analyticId: 't', costCenterId: 'cc1', description: 'اجاره', debit: '' })
  })
})

describe('حذفِ دسته‌ایِ ردیف‌های انتخاب‌شده', () => {
  const blank = () => line()
  it('ردیف‌های انتخاب‌شده می‌روند، بقیه به ترتیب می‌مانند', () => {
    const ls = [line({ description: 'a' }), line({ description: 'b' }), line({ description: 'c' }), line({ description: 'd' })]
    expect(removeRows(ls, [1, 3], blank).map((l) => l.description)).toEqual(['a', 'c'])
  })
  it('کفِ دو ردیف: همه که انتخاب شده‌اند، دو ردیفِ خالی می‌ماند — نه «حذف نمی‌شود»', () => {
    const ls = [line({ accountId: 'x', debit: '5' }), line({ accountId: 'y', credit: '5' })]
    const out = removeRows(ls, [0, 1], blank)
    expect(out).toHaveLength(2)
    expect(out.every((l) => !l.accountId && !l.debit && !l.credit)).toBe(true)
  })
})

describe('findLines — جست‌وجوی سریع در ردیف‌ها', () => {
  const labels = new Map([
    ['bank', '1101 — بانک ملی'],
    ['cust', '1301 — طرف حساب'],
  ])
  const ls = [
    line({ accountId: 'bank', debit: '2500000' }),
    line({ accountId: 'cust', credit: '2500000', description: 'بابت اجاره' }),
    line({ accountId: 'cust', debit: '750' }),
  ]
  it('عبارتِ خالی یعنی جست‌وجویی نیست (`null`)، نه «هیچ پیدا نشد»', () => {
    expect(findLines(ls, '  ', labels)).toBeNull()
  })
  it('کد یا نامِ حساب', () => {
    expect(findLines(ls, '1101', labels)).toEqual([0])
    expect(findLines(ls, 'طرف', labels)).toEqual([1, 2])
  })
  it('شرحِ ردیف', () => {
    expect(findLines(ls, 'اجاره', labels)).toEqual([1])
  })
  it('مبلغ با رقمِ فارسی و جداکننده‌ی هزارگان', () => {
    expect(findLines(ls, '۲٬۵۰۰٬۰۰۰', labels)).toEqual([0, 1])
    expect(findLines(ls, '750', labels)).toEqual([2])
  })
  it('هیچ: آرایه‌ی خالی', () => {
    expect(findLines(ls, 'ناموجود', labels)).toEqual([])
  })
})
