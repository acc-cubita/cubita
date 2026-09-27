import { describe, expect, it } from 'vitest'

import { closeRows, profitTotal } from './periodCloses'

const rec = (id: string, date: string, profit: string) => ({ id, closing_date: date, net_profit: profit, notes: '', journal_entry_id: `je-${id}` })

describe('دوره‌های بسته‌شده — منطقِ برگه', () => {
  it('تازه‌ترین اول؛ هر قفل از روزِ بعد از قفلِ قبلی، اولی از ابتدای دفتر؛ آخرین «مرز»', () => {
    const rows = closeRows([rec('b', '2026-06-30', '50'), rec('a', '2026-03-20', '-20'), rec('c', '2026-12-31', '5')])
    expect(rows.map((r) => [r.id, r.from, r.latest])).toEqual([
      ['c', '2026-07-01', true],
      ['b', '2026-03-21', false],
      ['a', null, false],
    ])
  })

  it('جمعِ سود/زیانِ دوره‌ها با علامت', () => {
    expect(profitTotal([rec('a', '2026-01-01', '-20'), rec('b', '2026-02-01', '50')])).toBe(30)
    expect(profitTotal([])).toBe(0)
  })

  it('بی قفل، هیچ ردیف', () => {
    expect(closeRows([])).toEqual([])
  })
})
