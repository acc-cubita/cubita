import { describe, expect, it } from 'vitest'

import { closingOptions, closingRowKey, closingState, nextDay, openingState } from './yearEnd'

describe('اختتامیه و افتتاحیه — منطقِ برگه', () => {
  it('کلیدِ ردیف حساب و هر دو بُعد را دارد', () => {
    expect(closingRowKey({ account_id: 'a', analytic_id: 't', cost_center_id: null })).toBe('a|t|')
  })

  it('اختتامیه: سود و زیانِ باز بر همه‌چیز مقدم است؛ بعد بی‌ردیف؛ بعد آماده', () => {
    expect(closingState({ rows: [], open_pnl_total: '5' })).toBe('pnl-open')
    expect(closingState({ rows: [{} as never], open_pnl_total: '5' })).toBe('pnl-open')
    expect(closingState({ rows: [], open_pnl_total: '0' })).toBe('none')
    expect(closingState({ rows: [{} as never], open_pnl_total: '0' })).toBe('ready')
  })

  it('افتتاحیه: تکراری، بعد ترتیبِ تاریخ، بعد بی‌ردیف، بعد آماده', () => {
    const base = { rows: [{} as never], existing_opening_number: null, as_of: '2027-03-21', source_date: '2027-03-20' }
    expect(openingState(base)).toBe('ready')
    expect(openingState({ ...base, existing_opening_number: 12 })).toBe('repeat')
    expect(openingState({ ...base, as_of: '2027-03-20' })).toBe('order')
    expect(openingState({ ...base, rows: [] })).toBe('none')
  })

  it('اختتامیه‌های مبنا: فقط ابطال‌نشده‌ی «اختتامیه»، تازه‌ترین اول', () => {
    const e = (id: string, date: string, number: number, extra: object = {}) => ({
      id,
      entry_date: date,
      number,
      voided_at: null as string | null,
      source_type: 'closing_entry',
      ...extra,
    })
    expect(
      closingOptions([
        e('a', '2025-03-20', 10),
        e('b', '2026-03-20', 90),
        e('c', '2026-03-20', 95, { voided_at: '2026-03-21' }),
        e('d', '2026-03-20', 91, { source_type: 'manual' }),
      ]).map((o) => o.id),
    ).toEqual(['b', 'a'])
  })

  it('روزِ بعد، از مرزِ ماه و سال', () => {
    expect(nextDay('2026-03-20')).toBe('2026-03-21')
    expect(nextDay('2026-12-31')).toBe('2027-01-01')
  })
})
