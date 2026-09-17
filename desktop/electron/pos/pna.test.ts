/**
 * پروتکلِ کارتخوانِ «پرداخت نوین آرین».
 *
 * **چرا این تست از یک تستِ معمولی مهم‌تر است.** قالبِ این پیام از مستندات
 * نیامده — از خروجیِ ابزارِ رسمیِ خودِ PNA (`PCPOS Tester`) استخراج شد: نُه
 * ورودیِ مختلف داده شد، نُه خروجی گرفته شد، و ساختار از تفاوتشان بیرون آمد.
 *
 * یعنی **تنها چیزی که درستیِ این قالب را تضمین می‌کند همین نمونه‌هاست** — و
 * پیامی که از این کد بیرون می‌آید به یک دستگاهِ بانکی می‌رود. اگر روزی کسی
 * `pna.ts` را دست بزند و این‌ها بخوانند، مطمئن است؛ اگر نخوانند، باید همین‌جا
 * قرمز شود نه سرِ صندوق.
 */
import { describe, it, expect } from 'vitest'

import { buildPnaMessage, parsePnaResponse, PNA_HEADER } from './pna.js'

describe('ساختِ پیامِ درخواست — نمونه‌های طلاییِ PCPOS Tester', () => {
  //: هر ردیف: آنچه در فرمِ ابزار گذاشته شد، و رشته‌ای که خودش ساخت.
  it.each([
    ['مبلغ ۱',
     { amount: '1' },
     '@@PNA@@0110001100000200000000011'],

    ['مبلغ ۱۰ — طولِ فیلد با مقدار بزرگ می‌شود',
     { amount: '10' },
     '@@PNA@@01100021000000200000000011'],

    ['مبلغ ۱۰۰۰۰۰',
     { amount: '100000' },
     '@@PNA@@011000610000000000200000000011'],

    ['شماره قبض ۵۵ — فیلدِ پیش از مبلغ هم طول‌دار است',
     { billNumber: '55', amount: '1221' },
     '@@PNA@@011025504122100000200000000011'],

    ['نوع تراکنش: قبض',
     { billNumber: '55', amount: '1221', txKind: 'bill' as const },
     '@@PNA@@011025504122100000201000000011'],

    ['رسید: فقط مشتری',
     { billNumber: '55', amount: '1221', txKind: 'bill' as const, receipt: 'customer' as const },
     '@@PNA@@011025504122100000201000000012'],

    ['ECR نوعِ ۲',
     { ecrType: 2 as const, billNumber: '55', amount: '1221', txKind: 'bill' as const, receipt: 'customer' as const },
     '@@PNA@@012025504122100000201000000012'],

    ['مهلتِ کشیدن کارت ۳۰ ثانیه',
     { ecrType: 2 as const, billNumber: '55', amount: '1221', txKind: 'bill' as const,
       swipeCardTimeout: '30', receipt: 'customer' as const },
     '@@PNA@@01202550412210000020100000230012'],

    ['داده‌ی اضافیِ غیرعددی — تنها نمونه‌ای که ثابت می‌کند مقدار، متنِ خام است',
     { ecrType: 2 as const, billNumber: '55', amount: '1221', txKind: 'bill' as const,
       additionalData: 'ab', swipeCardTimeout: '30', receipt: 'customer' as const },
     '@@PNA@@01202550412210000020102ab000230012'],
  ])('%s', (_name, input, expected) => {
    expect(buildPnaMessage(input)).toBe(expected)
  })
})

describe('مبلغ', () => {
  //: بریدنِ بی‌صدا یا فرستادنِ رشته‌ی بدشکل یعنی دستگاه چیزی می‌گیرد که یا رد
  //: می‌کند یا — بدتر — غلط می‌فهمد. گرفتنش این‌جا ارزان‌تر از فهمیدنش سرِ صندوق است.
  it.each(['1,000', '1000.00', '', 'abc', '۱۲۳', '-5', '1e3'])(
    'مقدارِ نامعتبر «%s» رد می‌شود',
    (bad) => {
      expect(() => buildPnaMessage({ amount: bad })).toThrow()
    },
  )

  it('صفر مجاز است — مبلغِ صفر تصمیمِ کاربر است نه خطای قالب', () => {
    expect(() => buildPnaMessage({ amount: '0' })).not.toThrow()
  })
})

describe('طولِ دو رقمی', () => {
  it('مقدارِ بلندتر از ۹۹ نویسه صریح خطا می‌دهد، نه اینکه بریده شود', () => {
    expect(() => buildPnaMessage({ amount: '1', customerName: 'x'.repeat(100) })).toThrow(/۹۹|99/)
  })

  it('دقیقاً ۹۹ نویسه هنوز مجاز است', () => {
    expect(() => buildPnaMessage({ amount: '1', customerName: 'x'.repeat(99) })).not.toThrow()
  })
})

describe('خواندنِ پاسخ', () => {
  //: **هسته‌ی ایمنیِ این ماژول.** اگر دستگاه کارت را بکشد و پول را بگیرد ولی ما
  //: پاسخ را نفهمیم و «رد شد» بگوییم، کاربر دوباره می‌کشد و مشتری دوبار پول
  //: می‌دهد. پس هیچ پاسخی تا وقتی قالبش شناخته نشده «تأییدشده» خوانده نمی‌شود.
  it('پاسخِ ناشناخته هرگز approved نمی‌شود', () => {
    const r = parsePnaResponse(`${PNA_HEADER}0201OK`)
    expect(r.outcome).toBe('unknown')
  })

  it('پاسخِ خالی هم unknown است، نه رد', () => {
    expect(parsePnaResponse('').outcome).toBe('unknown')
    expect(parsePnaResponse('   ').outcome).toBe('unknown')
  })

  it('پاسخِ بی‌سرآیند unknown است', () => {
    expect(parsePnaResponse('HELLO').outcome).toBe('unknown')
  })

  it('پیامِ هر پاسخِ ناشناخته کاربر را به رسیدِ دستگاه ارجاع می‌دهد', () => {
    //: بدونِ این جمله، کاربر تراکنش را تکرار می‌کند — همان چیزی که نباید بشود.
    expect(parsePnaResponse(`${PNA_HEADER}xyz`).message).toMatch(/رسید/)
  })

  it('پاسخِ خام همیشه برگردانده می‌شود — بدونِ آن، اولین تراکنشِ واقعی هم قالب را لو نمی‌دهد', () => {
    const raw = `${PNA_HEADER}0201OK`
    expect(parsePnaResponse(raw).raw).toBe(raw)
  })

  it('فیلدهای طول‌دار جدا می‌شوند حتی وقتی معنایشان معلوم نیست', () => {
    //: `02`+`OK` و `03`+`123`
    expect(parsePnaResponse(`${PNA_HEADER}02OK03123`).fields).toEqual(['OK', '123'])
  })

  it('پیامِ ناقص نمی‌ترکد — هرچه سالم بود جدا می‌شود', () => {
    //: طول ۰۵ اعلام شده ولی فقط سه نویسه آمده.
    expect(() => parsePnaResponse(`${PNA_HEADER}02OK05ab`)).not.toThrow()
    expect(parsePnaResponse(`${PNA_HEADER}02OK05ab`).fields).toEqual(['OK'])
  })
})
