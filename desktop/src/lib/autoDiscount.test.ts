/**
 * قاعده‌ی تخفیفِ خودکارِ فاکتور.
 *
 * این قاعده **مبلغِ فاکتور را عوض می‌کند**، پس هر تغییری در آن باید عمدی باشد.
 * مهم‌ترین موردِ این فایل «نرخِ صفر ⇒ رفتارِ دیروز» است: تا پیش از وصل‌شدنِ
 * `Contact.discount_rate`، تنها منبع سطحِ باشگاه بود. مشتری‌هایی که نرخِ
 * اختصاصی ندارند نباید هیچ تفاوتی ببینند.
 */
import { describe, it, expect } from 'vitest'

import { pickAutoDiscount } from './autoDiscount'

const CM = { tierName: 'طلایی', tierAuto: true }

describe('کدام منبع برنده می‌شود', () => {
  it('سطح بیشتر است → سطح', () => {
    expect(pickAutoDiscount({ ownPct: 5, tierPct: 10, ...CM })).toEqual({ pct: 10, source: 'tier' })
  })

  it('نرخِ طرف‌حساب بیشتر است → طرف‌حساب', () => {
    expect(pickAutoDiscount({ ownPct: 15, tierPct: 10, ...CM })).toEqual({ pct: 15, source: 'contact' })
  })

  it('مساوی → سطح، چون نامش پیامِ گویاتری می‌دهد', () => {
    expect(pickAutoDiscount({ ownPct: 10, tierPct: 10, ...CM })).toEqual({ pct: 10, source: 'tier' })
  })
})

describe('پیش‌فرض = رفتارِ دیروز', () => {
  //: **مهم‌ترین تستِ این فایل.** پیش از وصل‌شدنِ نرخِ طرف‌حساب، تنها منبع سطح
  //: بود. اگر این بشکند یعنی مشتری‌هایی که نرخ ندارند تخفیفشان عوض شده — و
  //: هیچ خطایی هم جایی ثبت نمی‌شود.
  it('نرخِ طرف‌حساب صفر → دقیقاً همان سطحِ باشگاه', () => {
    expect(pickAutoDiscount({ ownPct: 0, tierPct: 10, ...CM })).toEqual({ pct: 10, source: 'tier' })
  })

  it('هیچ‌کدام → هیچ تخفیفی', () => {
    expect(pickAutoDiscount({ ownPct: 0, tierPct: 0, tierName: '', tierAuto: true }))
      .toEqual({ pct: 0, source: null })
  })
})

describe('گیتِ «پیشنهادِ خودکارِ سطح»', () => {
  //: آن تنظیم درباره‌ی باشگاه است، نه نرخی که کاربر دستی روی طرف‌حساب گذاشته.
  it('خاموش باشد، نرخِ طرف‌حساب همچنان اعمال می‌شود', () => {
    expect(pickAutoDiscount({ ownPct: 5, tierPct: 10, tierName: 'طلایی', tierAuto: false }))
      .toEqual({ pct: 5, source: 'contact' })
  })

  it('خاموش و نرخِ طرف‌حساب صفر → هیچ، حتی اگر سطح درصد داشته باشد', () => {
    expect(pickAutoDiscount({ ownPct: 0, tierPct: 10, tierName: 'طلایی', tierAuto: false }))
      .toEqual({ pct: 0, source: null })
  })
})

describe('سطحِ بی‌نام', () => {
  it('درصد دارد ولی نام ندارد → به‌نامِ طرف‌حساب نسبت داده می‌شود', () => {
    //: بدونِ نام، پیامِ «🎖️ سطحِ …» با نامِ خالی رندر می‌شد — دروغِ کوچکی که
    //: کاربر نمی‌فهمد از کجاست.
    expect(pickAutoDiscount({ ownPct: 0, tierPct: 10, tierName: '', tierAuto: true }))
      .toEqual({ pct: 10, source: 'contact' })
  })
})

describe('مقادیرِ مرزی', () => {
  it('درصدِ اعشاری حفظ می‌شود', () => {
    expect(pickAutoDiscount({ ownPct: 2.5, tierPct: 0, tierName: '', tierAuto: true }).pct).toBe(2.5)
  })

  it('درصدِ منفی تخفیف نمی‌سازد', () => {
    //: نباید ممکن باشد (قیدِ دیتابیس ۰..۱۰۰ است)، ولی اگر داده‌ی خراب رسید،
    //: نتیجه «بدونِ تخفیف» باشد نه یک عددِ منفی روی فاکتور.
    expect(pickAutoDiscount({ ownPct: -5, tierPct: -1, tierName: '', tierAuto: true }))
      .toEqual({ pct: 0, source: null })
  })

  it('۱۰۰ درصد مجاز است — فاکتورِ رایگان تصمیمِ کاربر است', () => {
    expect(pickAutoDiscount({ ownPct: 100, tierPct: 0, tierName: '', tierAuto: true }).pct).toBe(100)
  })
})
