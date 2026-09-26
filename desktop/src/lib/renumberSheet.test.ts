import { describe, expect, it } from 'vitest'

import { numberSpan, planNumbers, renumberState } from './renumberSheet'

describe('شماره‌گذاری مجدد — منطقِ برگه', () => {
  it('شماره‌ی تازه از نقشه‌ی سرور؛ بی نقشه هیچ', () => {
    const plan = { rows: [{ id: 'a', new_number: 7 }, { id: 'b', new_number: 8 }] } as never
    expect([...planNumbers(plan).entries()]).toEqual([
      ['a', 7],
      ['b', 8],
    ])
    expect(planNumbers(null).size).toBe(0)
  })

  it('حال: شماره‌ی تکراری بر همه‌چیز مقدم است؛ بعد خالی، بی‌تغییر، آماده', () => {
    expect(renumberState({ count: 3, changed_count: 2, first_clash: 5 })).toBe('clash')
    expect(renumberState({ count: 0, changed_count: 0, first_clash: null })).toBe('none')
    expect(renumberState({ count: 3, changed_count: 0, first_clash: null })).toBe('same')
    expect(renumberState({ count: 3, changed_count: 1, first_clash: null })).toBe('ready')
  })

  it('بازه‌ی شماره‌های تازه', () => {
    expect(numberSpan(10, 3)).toEqual([10, 12])
    expect(numberSpan(1, 0)).toBeNull()
  })
})
