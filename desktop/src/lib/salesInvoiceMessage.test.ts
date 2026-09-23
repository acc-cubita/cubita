import { describe, expect, it } from 'vitest'

import { salesInvoiceSavedMessage } from './salesInvoiceMessage'

/**
 * پیامِ پس از ثبتِ فاکتور همان را می‌گوید که سرور کرد — در هر دو سیاستِ صدور.
 * پیامِ پیشین همیشه «از فهرست صادر کنید» بود، حتی در سیاستِ پیش‌فرضِ «خودکار» که
 * سند و خروج را از قبل زده بود.
 */
describe('پیامِ ثبتِ فاکتور فروش', () => {
  it('سیاستِ «خودکار» (پیش‌فرض): هر دو صادر شدند — کاری نمانده', () => {
    const m = salesInvoiceSavedMessage({ accounting_status: 'posted', fulfillment_status: 'fully_issued' })
    expect(m).toBe('فاکتور ثبت شد؛ سندِ حسابداری و خروجِ انبار هم خودکار صادر شدند.')
    expect(m).not.toContain('از فهرست')
  })

  it('سیاستِ «دومرحله‌ای»: هر دو مانده‌اند — همان راهنمای پیشین', () => {
    expect(salesInvoiceSavedMessage({ accounting_status: 'unposted', fulfillment_status: 'not_issued' })).toBe(
      'فاکتور ثبت شد؛ سندِ حسابداری و خروجِ انبار را از فهرستِ فاکتورها صادر کنید.',
    )
  })

  it('فاکتورِ خدماتی: خروجِ انبار ندارد', () => {
    expect(salesInvoiceSavedMessage({ accounting_status: 'posted', fulfillment_status: 'not_applicable' })).toBe(
      'فاکتور ثبت شد و سندِ حسابداری‌اش هم صادر شد.',
    )
    expect(salesInvoiceSavedMessage({ accounting_status: 'unposted', fulfillment_status: 'not_applicable' })).toBe(
      'فاکتور ثبت شد؛ سندِ حسابداری را از فهرستِ فاکتورها صادر کنید.',
    )
  })

  it('فقط آنچه واقعاً مانده گفته می‌شود', () => {
    expect(salesInvoiceSavedMessage({ accounting_status: 'posted', fulfillment_status: 'partially_issued' })).toBe(
      'فاکتور ثبت شد؛ خروجِ انبار را از فهرستِ فاکتورها صادر کنید.',
    )
  })
})
