/**
 * دامنه‌ی کارتِ «فهرست».
 *
 * قیدی که این فایل نگه می‌دارد: **کارت هرگز به گروه گره نمی‌خورد.** اگر روزی
 * کسی `listsForOps` را به `LIST_MENUS[group]` برگرداند، کاربر دوباره بیست ردیفِ
 * بی‌ربط می‌بیند — همان چیزی که رد شد. ممیزِ ایستا فقط می‌گوید «هر دفتر صاحبی
 * دارد»؛ این‌جا سنجیده می‌شود که صاحبش **همان** است و نه بیشتر.
 */
import { describe, it, expect } from 'vitest'

import { listsForOps, SECTION_LIST_MAP } from './moduleLists'

const labels = (page: Parameters<typeof listsForOps>[0], section: string | null) =>
  listsForOps(page, section).map((x) => x.label)

describe('پیش‌فرض: دامنه‌ی صفحه، نه گروه', () => {
  it('«باشگاه مشتریان» شش دفترِ خودش را می‌دهد، نه فهرستِ فروش را', () => {
    const got = labels('crm', 'loyalty')
    expect(got).toEqual(['سرنخ‌ها', 'پیگیری‌ها', 'بخش‌بندی', 'سطوح باشگاه', 'جوایز', 'تولدها'])
    //: هر دو صفحه در گروهِ «مشتریان و فروش»اند؛ نشتی از آن گروه یعنی بازگشتِ باگ.
    expect(got).not.toContain('فاکتورهای فروش')
  })

  it('«ورود گروهی اشخاص» فقط دو دفترِ صفحه‌ی اشخاص را می‌دهد', () => {
    expect(labels('contacts', 'import')).toEqual(['طرف حساب‌ها', 'سنین مطالبات'])
  })
})

describe('ریزکردن در سطحِ تب', () => {
  it('«حواله انبار» یک دفتر می‌دهد، نه هر هشت دفترِ انبار', () => {
    expect(labels('inventory', 'issues')).toEqual(['فهرست رسیدها و حواله‌های انبار'])
  })

  it('«کالاها» پنج دفترِ کالا را می‌دهد', () => {
    expect(labels('inventory', 'products')).toHaveLength(5)
    expect(labels('inventory', 'products')).toContain('کاردکس کالا')
  })

  it('دو تبِ متفاوتِ یک صفحه دو جوابِ متفاوت می‌دهند — همین «دامنه‌دار» یعنی', () => {
    expect(labels('inventory', 'issues')).not.toEqual(labels('inventory', 'count'))
  })

  it('تعریفِ کوچک دفترِ جدا ندارد؛ جدولش داخلِ خودِ تب است', () => {
    expect(labels('inventory', 'units')).toEqual([])
  })
})

describe('صفحه‌ی بی‌تب، از نگاشتِ صفحه', () => {
  it('«طرف حساب جدید» دو دفتر دارد — فهرست و افرادِ مرتبط', () => {
    expect(labels('contactnew', null)).toEqual(['طرف حساب‌ها', 'افراد مرتبط'])
  })

  it('«فروش اقساطی» الگوی مرجع است: قراردادها و همه‌ی اقساط', () => {
    expect(labels('installments', null)).toEqual(['قراردادهای اقساطی', 'همه اقساط'])
  })

  it('عملیاتی که فقط وضعیت عوض می‌کند دفترِ جدا نمی‌گیرد', () => {
    //: `'state'` در OPS_LIST_MAP — مغایرت بانکی روی داده‌ی موجود کار می‌کند.
    expect(labels('bankreconcile', null)).toEqual([])
  })
})

describe('یکپارچگیِ نگاشت', () => {
  it('هر مقصدِ SECTION_LIST_MAP واقعاً پیدا می‌شود', () => {
    //: `listsForOps` مقصدِ ناشناخته را بی‌صدا حذف می‌کند تا کارت نشکند؛ پس
    //: غلطِ تایپی بدونِ این سنجش دیده نمی‌شود.
    for (const [from, targets] of Object.entries(SECTION_LIST_MAP)) {
      const [page, section] = from.split('/')
      const got = listsForOps(page as Parameters<typeof listsForOps>[0], section)
      expect(got, `${from} → ${targets.join(', ')}`).toHaveLength(targets.length)
    }
  })
})
