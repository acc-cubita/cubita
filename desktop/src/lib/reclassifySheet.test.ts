import { describe, expect, it } from 'vitest'

import {
  descendantsOf,
  errorAccountId,
  matches,
  parseDraft,
  pendingParent,
  planReclassify,
  treeRows,
  type Acc,
} from './reclassifySheet'

const acc = (id: string, parent: string | null, type: string, group = false, extra: Partial<Acc> = {}): Acc => ({
  id,
  code: id,
  name: `حساب ${id}`,
  type,
  is_group: group,
  parent_id: parent,
  system_role: null,
  ...extra,
})

//: ۱ دارایی ← ۱۱ (گروه) ← ۱۱۱ و ۱۱۲؛ ۲ بدهی ← ۲۱ (گروه)؛ ۵ هزینه ← ۵۱.
const CHART: Acc[] = [
  acc('1', null, 'asset', true),
  acc('11', '1', 'asset', true),
  acc('111', '11', 'asset'),
  acc('112', '11', 'asset', false, { system_role: 'cash' }),
  acc('2', null, 'liability', true),
  acc('21', '2', 'liability', true),
  acc('5', null, 'expense', true),
  acc('51', '5', 'expense'),
]

describe('treeRows', () => {
  it('orders depth-first by code with depths', () => {
    const rows = treeRows(CHART).map((r) => `${r.acc.id}:${r.depth}`)
    expect(rows).toEqual(['1:0', '11:1', '111:2', '112:2', '2:0', '21:1', '5:0', '51:1'])
  })

  it('treats a missing parent as a root and keeps accounts caught in a broken cycle', () => {
    const rows = treeRows([acc('9', 'gone', 'asset'), acc('a', 'b', 'asset'), acc('b', 'a', 'asset')])
    expect(rows.map((r) => r.acc.id).sort()).toEqual(['9', 'a', 'b'])
  })

  it('sorts sibling codes numerically', () => {
    const rows = treeRows([acc('19', null, 'asset'), acc('110', null, 'asset')])
    expect(rows.map((r) => r.acc.id)).toEqual(['19', '110'])
  })
})

describe('descendantsOf', () => {
  it('lists the whole subtree without the account itself', () => {
    expect([...descendantsOf(CHART, '1')].sort()).toEqual(['11', '111', '112'])
    expect(descendantsOf(CHART, '51').size).toBe(0)
  })
})

describe('pendingParent', () => {
  it('ignores a choice equal to the current parent', () => {
    expect(pendingParent(CHART[2], { '111': '11' })).toBeUndefined()
    expect(pendingParent(CHART[2], {})).toBeUndefined()
    expect(pendingParent(CHART[2], { '111': '' })).toBeNull()
    expect(pendingParent(CHART[2], { '111': '21' })).toBe('21')
  })
})

describe('planReclassify', () => {
  it('takes the destination type and counts it as a type change', () => {
    const plan = planReclassify(CHART, { '111': '21' })
    expect(plan.items).toEqual([{ account_id: '111', parent_id: '21', type: 'liability' }])
    expect([...plan.typeChanged]).toEqual(['111'])
  })

  it('cascades a moved group type to its children, hidden system accounts included', () => {
    const plan = planReclassify(CHART, { '11': '5' })
    expect(plan.items).toEqual([{ account_id: '11', parent_id: '5', type: 'expense' }])
    expect([...plan.typeChanged].sort()).toEqual(['11', '111', '112'])
  })

  it('spares a child moved out of a moving group in the same batch', () => {
    const plan = planReclassify(CHART, { '11': '5', '111': '1' })
    expect(plan.finalType.get('111')).toBe('asset')
    expect(plan.typeChanged.has('111')).toBe(false)
    expect(plan.typeChanged.has('112')).toBe(true)
  })

  it('uses the final type of a destination that itself moves, and sends parents first', () => {
    //: ۵۱ زیرِ ۱۱ می‌رود و ۱۱ خودش زیرِ ۲۱ — ۵۱ باید «بدهی» شود، نه «دارایی».
    const plan = planReclassify(CHART, { '51': '11', '11': '21' })
    expect(plan.items.map((i) => [i.account_id, i.type])).toEqual([
      ['11', 'liability'],
      ['51', 'liability'],
    ])
  })

  it('keeps its own type when moved to the root', () => {
    const plan = planReclassify(CHART, { '51': '' })
    expect(plan.items).toEqual([{ account_id: '51', parent_id: null, type: 'expense' }])
    expect(plan.typeChanged.size).toBe(0)
  })

  it('flags a cycle made inside one batch and sends nothing', () => {
    const plan = planReclassify(CHART, { '11': '21', '2': '11' })
    expect(Object.keys(plan.problems).sort()).toEqual(['11', '2'])
    expect(plan.items).toEqual([])
  })

  it('flags a destination that is not a group or no longer exists', () => {
    const plan = planReclassify(CHART, { '111': '51', '21': 'gone' })
    expect(plan.problems['111']).toContain('سرفصل نیست')
    expect(plan.problems['21']).toContain('دیگر نیست')
    expect(plan.items).toEqual([])
  })

  it('refuses a system account from a stale draft', () => {
    expect(planReclassify(CHART, { '112': '1' }).problems['112']).toContain('نقشِ سیستمی')
  })

  it('drops unknown accounts and no-op choices silently', () => {
    const plan = planReclassify(CHART, { gone: '1', '111': '11' })
    expect(plan.moves.size).toBe(0)
    expect(plan.items).toEqual([])
    expect(plan.problems).toEqual({})
  })
})

describe('parseDraft', () => {
  it('reads a string map and rejects anything else', () => {
    expect(parseDraft('{"a":"b","c":""}')).toEqual({ a: 'b', c: '' })
    expect(parseDraft(null)).toBeNull()
    expect(parseDraft('[]')).toBeNull()
    expect(parseDraft('{"a":1}')).toBeNull()
    expect(parseDraft('{oops')).toBeNull()
  })
})

describe('matches', () => {
  it('finds by code, name or current heading, with Arabic letters', () => {
    const a = { ...CHART[2], name: 'بانک ملي' }
    expect(matches(a, 'بانک‌ها', '111')).toBe(true)
    expect(matches(a, 'بانک‌ها', 'ملی')).toBe(true)
    expect(matches(a, 'موجودی نقد', 'نقد')).toBe(true)
    expect(matches(a, 'موجودی نقد', 'هزینه')).toBe(false)
  })
})

describe('errorAccountId', () => {
  it('maps the first quoted name that is a moved account', () => {
    const moved = [CHART[2], CHART[7]]
    expect(errorAccountId('نوعِ «حساب 51» با نوعِ سرفصلِ «حساب 11» نمی‌خواند', moved)).toBe('51')
    expect(errorAccountId('«حساب 21» سرفصل نیست', moved)).toBeNull()
    expect(errorAccountId('خطای شبکه', moved)).toBeNull()
  })
})
