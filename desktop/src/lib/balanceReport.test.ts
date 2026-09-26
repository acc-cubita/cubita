import { describe, expect, it } from 'vitest'

import type { BalanceRow, ChartAccount } from '../api'
import {
  aggregateBalances,
  balanceCheck,
  balanceGroups,
  balanceTotals,
  filterBalances,
  levelOf,
  pairOf,
} from './balanceReport'

const acc = (id: string, parent: string | null, type = 'asset'): ChartAccount =>
  ({ id, code: id, name: `حساب ${id}`, type, parent_id: parent, is_group: false }) as ChartAccount

//: ۱ (گروه) ← ۱۱ (کل) ← ۱۱۱ (معین) ← ۱۱۱۱ و ۱۱۱۲ (تفصیلی)؛ ۱۱ ← ۱۱۲؛ ۲ ← ۲۱ ← ۲۱۱.
const CHART = [
  acc('1', null),
  acc('11', '1'),
  acc('111', '11'),
  acc('1111', '111'),
  acc('1112', '111'),
  acc('112', '11'),
  acc('2', null, 'liability'),
  acc('21', '2', 'liability'),
  acc('211', '21', 'liability'),
]

const row = (id: string, n: Partial<Record<'od' | 'oc' | 'pd' | 'pc' | 'cd' | 'cc', number>>, active = true): BalanceRow => ({
  account_id: id,
  account_code: id,
  account_name: `حساب ${id}`,
  account_type: 'asset',
  parent_id: null,
  opening_debit: String(n.od ?? 0),
  opening_credit: String(n.oc ?? 0),
  period_debit: String(n.pd ?? 0),
  period_credit: String(n.pc ?? 0),
  closing_debit: String(n.cd ?? 0),
  closing_credit: String(n.cc ?? 0),
  balance: '0',
  has_activity: active,
})

describe('balanceGroups', () => {
  it('maps each column format to its pairs in display order', () => {
    expect(balanceGroups(2, false)).toEqual(['closing'])
    expect(balanceGroups(4, false)).toEqual(['period', 'closing'])
    expect(balanceGroups(6, false)).toEqual(['opening', 'period', 'closing'])
    expect(balanceGroups(8, false)).toEqual(['opening', 'period', 'sum', 'closing'])
  })
  it('general ledger sheet shows turnover only, whatever columns were chosen', () => {
    expect(balanceGroups(8, true)).toEqual(['period'])
    expect(balanceGroups(2, true)).toEqual(['period'])
  })
})

describe('pairOf', () => {
  it('sum = opening + period on each side', () => {
    expect(pairOf(row('a', { od: 10, oc: 1, pd: 5, pc: 7 }), 'sum')).toEqual([15, 8])
  })
})

describe('levelOf / aggregateBalances', () => {
  it('counts depth from the root', () => {
    const byId = new Map(CHART.map((a) => [a.id, a]))
    expect(levelOf(byId.get('1')!, byId)).toBe(1)
    expect(levelOf(byId.get('1111')!, byId)).toBe(4)
  })

  it('level 0 returns the leaf rows untouched', () => {
    const src = [row('1111', { pd: 5 })]
    expect(aggregateBalances(src, CHART, 0)).toEqual(src)
  })

  it('rolls leaves up to their «کل» ancestor and nets opening/closing', () => {
    const src = [
      row('1111', { od: 100, pd: 50, pc: 10, cd: 140 }),
      row('1112', { oc: 30, pd: 5, pc: 20, cc: 45 }),
      row('112', { pd: 1, cd: 1 }),
      row('211', { pc: 9, cc: 9 }),
    ]
    const out = aggregateBalances(src, CHART, 2)
    expect(out.map((r) => r.account_code)).toEqual(['11', '21'])
    const kol = out[0]
    //: افتتاحیه ۱۰۰ بد − ۳۰ بس = ۷۰ بد؛ پایان ۱۴۱ بد − ۴۵ بس = ۹۶ بد؛ گردش خالص نمی‌شود.
    expect([kol.opening_debit, kol.opening_credit]).toEqual(['70', '0'])
    expect([kol.period_debit, kol.period_credit]).toEqual(['56', '30'])
    expect([kol.closing_debit, kol.closing_credit]).toEqual(['96', '0'])
    expect(kol.balance).toBe('96')
    expect(out[1].closing_credit).toBe('9')
  })

  it('a heading has activity when any child had it, not only the first', () => {
    const src = [row('1111', {}, false), row('1112', { pd: 3, cd: 3 }, true)]
    expect(aggregateBalances(src, CHART, 3)[0].has_activity).toBe(true)
    expect(aggregateBalances([row('1111', {}, false)], CHART, 3)[0].has_activity).toBe(false)
  })

  it('skips rows whose account is missing from the chart', () => {
    expect(aggregateBalances([row('999', { pd: 1 })], CHART, 2)).toEqual([])
  })
})

describe('filterBalances', () => {
  const rows = [
    row('1101', { cd: 5 }),
    row('1102', { cc: 5 }),
    row('1103', { pd: 5, pc: 5 }),
    row('1104', {}, false),
  ]
  const codes = (list: BalanceRow[]) => list.map((r) => r.account_code)

  it('balance filter keeps the matching side', () => {
    expect(codes(filterBalances(rows, { general: false, filter: 'all' }))).toEqual(['1101', '1102', '1103', '1104'])
    expect(codes(filterBalances(rows, { general: false, filter: 'debit' }))).toEqual(['1101'])
    expect(codes(filterBalances(rows, { general: false, filter: 'credit' }))).toEqual(['1102'])
  })
  it('«zero balance» and «no activity» are different things', () => {
    expect(codes(filterBalances(rows, { general: false, filter: 'zero' }))).toEqual(['1103'])
    expect(codes(filterBalances(rows, { general: false, filter: 'idle' }))).toEqual(['1104'])
  })
  it('general ledger sheet keeps only accounts with turnover and ignores the balance filter', () => {
    expect(codes(filterBalances(rows, { general: true, filter: 'debit' }))).toEqual(['1103'])
  })
  it('search matches a code prefix in Persian digits or a normalized name', () => {
    expect(codes(filterBalances(rows, { general: false, filter: 'all', query: '۱۱۰۲' }))).toEqual(['1102'])
    //: کد با پیشوند جست‌وجو می‌شود، نه هرجای کد (نام‌ها این‌جا خودشان کد دارند، پس جدا).
    const plain = rows.map((r) => ({ ...r, account_name: 'صندوق' }))
    expect(codes(filterBalances(plain, { general: false, filter: 'all', query: '02' }))).toEqual([])
    const named = [{ ...row('1', {}), account_name: 'بانک ملی' }]
    expect(filterBalances(named, { general: false, filter: 'all', query: 'ملي' })).toHaveLength(1)
  })
})

describe('balanceTotals / balanceCheck', () => {
  const rows = [row('a', { od: 10, pd: 4, pc: 1, cd: 13 }), row('b', { oc: 10, pd: 1, pc: 4, cc: 13 })]

  it('sums each shown pair', () => {
    const t = balanceTotals(rows, ['opening', 'period', 'sum', 'closing'])
    expect(t.get('opening')).toEqual([10, 10])
    expect(t.get('period')).toEqual([5, 5])
    expect(t.get('sum')).toEqual([15, 15])
    expect(t.get('closing')).toEqual([13, 13])
    expect(balanceCheck(t, true)).toEqual({ kind: 'ok' })
  })

  it('names every unbalanced pair with its difference, in column order', () => {
    const t = balanceTotals([...rows, row('c', { pd: 7, cd: 7 })], ['opening', 'period', 'closing'])
    expect(balanceCheck(t, true)).toEqual({
      kind: 'off',
      off: [
        { group: 'period', diff: 7 },
        { group: 'closing', diff: 7 },
      ],
    })
  })

  it('does not judge a filtered subset, and ignores float dust', () => {
    const t = balanceTotals([row('a', { cd: 5 })], ['closing'])
    expect(balanceCheck(t, false)).toEqual({ kind: 'partial' })
    const dust = new Map([['period', [0.1 + 0.2, 0.3]]]) as Parameters<typeof balanceCheck>[0]
    expect(balanceCheck(dust, true)).toEqual({ kind: 'ok' })
  })
})
