import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { OutboxEntry } from '../electron.d'
import { OutboxList } from './OutboxList'

const pending: OutboxEntry = { local_id: 'l', payload: '{}', synced: 0, server_id: null, server_number: null, created_at: '2026-09-28', sync_error: '{"detail":"تاریخ 2026-09-28 در هیچ سال مالی تعریف‌شده‌ای نیست"}' }
describe('نمایش صف بدون تغییر داده', () => {
  it('ویرایش فقط برای سند ارسال‌نشده است و تاریخ/شرح آن مشخص است', () => {
    const payload = '{"entry_date":"2026-09-28","description":"سند مشخص"}'
    const html = renderToStaticMarkup(<OutboxList entries={[{ ...pending, payload }, { ...pending, payload, local_id: 'sent', synced: 1 }]} emptyHint="خالی" onEdit={() => {}} />)
    expect(html.match(/ویرایش سند/g)).toHaveLength(1); expect(html).toContain('سند مشخص'); expect(html).toContain('۱۴۰۵/۰۷/۰۶')
  })
  it('خطای ردیفِ قدیمی JSON نیست و تاریخ جلالی و اقدام دارد', () => {
    const rendered = renderToStaticMarkup(<OutboxList entries={[pending]} emptyHint="سندی در صف نیست." />)
    expect(rendered).toContain('۱۴۰۵/۰۷/۰۶')
    expect(rendered).toContain('تنظیمات ← سال مالی')
    expect(rendered).not.toContain('detail')
    expect(pending.sync_error).toContain('2026-09-28')
  })
  it('شمارهٔ رسمی فارسی می‌شود و وضعیتِ همگام‌شده حفظ است', () => {
    expect(renderToStaticMarkup(<OutboxList entries={[{ ...pending, synced: 1, server_number: 12, sync_error: null }]} emptyHint="خالی" />)).toContain('۱۲')
  })
})
