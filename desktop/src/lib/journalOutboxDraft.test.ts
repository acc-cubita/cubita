import { describe, expect, it } from 'vitest'
import { mergeQueuedJournalPayload, parseQueuedJournalDraft } from './journalOutboxDraft'

const original = {
  entry_date: '2026-09-28', description: 'سند قدیمی', status: 'temporary', sub_number: 'A', analytic_id: 'person', extra: 'preserved',
  lines: [
    { account_id: 'a', debit: '9007199254740993', credit: '0', description: 'اول', cost_center_id: 'branch', tracking_no: 'T', custom: 'line one' },
    { account_id: 'b', debit: '0', credit: '9007199254740993', description: 'دوم', custom: 'line two' },
  ],
}
describe('بارگذاری و ذخیره همان سند صف', () => {
  it('تاریخ، ردیف‌ها، ابعاد و دقت مقدار اصلی را بارگذاری می‌کند', () => {
    const draft = parseQueuedJournalDraft(JSON.stringify(original))
    expect(draft.entryDate).toBe('2026-09-28')
    expect(draft.lines[0]).toMatchObject({ originIndex: 0, debit: '9007199254740993', costCenterId: 'branch', trackingNo: 'T' })
  })
  it('تغییر تاریخ، جابه‌جایی ردیف و پاک‌کردن ابعاد، metadata ردیف درست را حفظ می‌کند', () => {
    const draft = parseQueuedJournalDraft(JSON.stringify(original))
    const lines = [...draft.lines].reverse()
    const merged = mergeQueuedJournalPayload(original, { entry_date: '2026-09-29', lines: [
      { account_id: 'b', debit: 0, credit: Number(lines[0].credit) }, { account_id: 'a', debit: Number(lines[1].debit), credit: 0 },
    ] }, lines) as typeof original
    expect(merged.entry_date).toBe('2026-09-29'); expect(merged.extra).toBe('preserved')
    expect(merged.lines[0]).toMatchObject({ custom: 'line two', credit: '9007199254740993' })
    expect(merged.lines[1]).toMatchObject({ custom: 'line one', tracking_no: null, cost_center_id: null, debit: '9007199254740993' })
  })
  it('اعداد متفاوتی که در Number برابرند بی‌صدا برابر محسوب نمی‌شوند', () => {
    const draft = parseQueuedJournalDraft(JSON.stringify(original)); draft.lines[0].debit = '9007199254740992'
    const changed = mergeQueuedJournalPayload(original, { lines: [{ debit: 9007199254740992, credit: 0 }, { debit: 0, credit: 9007199254740992 }] }, draft.lines)
    expect((changed.lines as Record<string, unknown>[])[0].debit).toBe('9007199254740992')
  })
  it('JSON خراب و فرم چندارزی را رد می‌کند، نه تبدیل به فرم خالی', () => {
    expect(() => parseQueuedJournalDraft('{broken')).toThrow(/صف/)
    expect(() => parseQueuedJournalDraft(JSON.stringify({ ...original, lines: original.lines.map((line, index) => ({ ...line, currency_code: index ? 'EUR' : 'USD', fx_rate: 10 })) }))).toThrow(/چند ارز/)
  })
})
