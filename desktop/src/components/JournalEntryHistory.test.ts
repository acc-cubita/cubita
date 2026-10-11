import { describe, expect, it } from 'vitest'
import { journalEditChanges } from '../lib/journalEditChanges'

describe('تفاوت‌های تاریخچهٔ سند', () => {
  it('فیلد سند، تغییر مبلغ، افزودن و حذف ردیف را جداگانه نشان می‌دهد', () => {
    const changes = journalEditChanges({
      id: 'h1', at: '2026-09-29T10:00:00Z', actor_email: 'accountant@example.test', summary: 'اصلاح',
      changes: {
        description: { from: 'قبل', to: 'بعد' },
        lines: { from: [
          { id: 'a', seq: 1, account_id: '1', account_name: 'صندوق', debit: '100', credit: '0' },
          { id: 'b', seq: 2, account_id: '2', debit: '0', credit: '100' },
        ], to: [
          { id: 'a', seq: 1, account_id: '1', account_name: 'صندوق', debit: '200', credit: '0' },
          { id: 'c', seq: 2, account_id: '3', account_name: 'بانک', debit: '0', credit: '200' },
        ] },
      },
    })
    expect(changes).toContainEqual({ label: 'شرح سند', before: 'قبل', after: 'بعد' })
    expect(changes).toContainEqual({ label: 'ردیف ۱ / بدهکار', before: '۱۰۰', after: '۲۰۰' })
    expect(changes.some((change) => change.after === 'حذف شد')).toBe(true)
    expect(changes.some((change) => change.after.includes('بانک'))).toBe(true)
  })

  it('مبالغ ۱۸ رقمی را در تاریخچه بدون گردشدن نشان می‌دهد', () => {
    const changes = journalEditChanges({
      id: 'h2', at: '2026-09-29T10:00:00Z', actor_email: 'accountant@example.test', summary: 'اصلاح',
      changes: { lines: { from: [{ id: 'a', debit: '123456789012345678' }], to: [{ id: 'a', debit: '123456789012345679' }] } },
    })
    expect(changes[0]).toEqual({ label: 'ردیف ۱ / بدهکار', before: '۱۲۳٬۴۵۶٬۷۸۹٬۰۱۲٬۳۴۵٬۶۷۸', after: '۱۲۳٬۴۵۶٬۷۸۹٬۰۱۲٬۳۴۵٬۶۷۹' })
  })
})
