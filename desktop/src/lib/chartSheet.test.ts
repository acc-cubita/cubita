import { describe, expect, it } from 'vitest'

import type { ChartAccount } from '../api'
import {
  NEW_TRAITS,
  buildTree,
  codeOwners,
  createBody,
  matchingIds,
  nextFreeCode,
  parseDraft,
  patchOf,
  pendingCount,
  problemOf,
  sheetRows,
  visibleNodes,
  type Draft,
  type FreshAccount,
  type Node,
} from './chartSheet'

const acc = (id: string, code: string, name: string, parent: string | null, group = false, extra: Partial<ChartAccount> = {}) =>
  ({
    id,
    code,
    name,
    name2: '',
    type: 'asset',
    nature: null,
    effective_nature: 'debit',
    is_group: group,
    is_active: true,
    parent_id: parent,
    system_role: null,
    nature_control: false,
    is_fx: false,
    fx_revaluable: false,
    accepts_tafsili: false,
    has_tracking: false,
    in_management_reports: true,
    ...extra,
  }) as ChartAccount

//: ۱ دارایی‌ها ← ۱۱ جاری ← ۱۱۰۱ صندوق، ۱۱۰۲ بانک؛ ۱ ← ۱۲ ثابت ← ۱۲۰۱ ساختمان (غیرفعال)؛ ۲ بدهی‌ها.
const CHART = [
  acc('r1', '1', 'دارایی‌ها', null, true),
  acc('g1', '11', 'دارایی‌های جاری', 'r1', true),
  acc('l1', '1101', 'صندوق', 'g1'),
  acc('l2', '1102', 'بانک ملی', 'g1'),
  acc('g2', '12', 'دارایی‌های ثابت', 'r1', true),
  acc('l3', '1201', 'ساختمان', 'g2', false, { is_active: false }),
  acc('r2', '2', 'بدهی‌ها', null, true, { type: 'liability' }),
]
const tree = () => buildTree(CHART, new Map([['l1', 100], ['l2', 50], ['r2', -30]]))
const codes = (rows: { kind: string; key: string }[], byKey: Map<string, string>) => rows.map((r) => byKey.get(r.key) ?? r.key)
const open = { collapsed: new Set<string>(), visible: null, type: '', showInactive: true, flat: false }
const fresh = (key: string, parentId: string | null, over: Partial<FreshAccount> = {}): FreshAccount => ({
  key,
  parentId,
  code: '',
  name: '',
  name2: '',
  nature: '',
  isGroup: false,
  type: 'expense',
  traits: NEW_TRAITS,
  ...over,
})

describe('buildTree', () => {
  it('orders by code, sets depth and full path, and rolls balances up', () => {
    const roots = tree()
    expect(roots.map((r) => r.code)).toEqual(['1', '2'])
    const g1 = roots[0].children[0]
    expect(g1.depth).toBe(1)
    expect(g1.children[1].fullName).toBe('دارایی‌ها › دارایی‌های جاری › بانک ملی')
    expect(g1.balance).toBe(150)
    expect(roots[0].balance).toBe(150)
  })
})

describe('visibleNodes / matchingIds', () => {
  it('collapsed groups hide their subtree; search and flat open everything', () => {
    const roots = tree()
    const ids = (ns: Node[]) => ns.map((n) => n.code)
    expect(ids(visibleNodes(roots, { ...open, collapsed: new Set(['g1', 'g2']) }))).toEqual(['1', '11', '12', '2'])
    expect(ids(visibleNodes(roots, { ...open, collapsed: new Set(['g1']), flat: true }))).toHaveLength(7)
    const hits = matchingIds(roots, 'بانك') //: کافِ عربی همان کافِ فارسی است.
    expect(ids(visibleNodes(roots, { ...open, collapsed: new Set(['r1', 'g1']), visible: hits }))).toEqual(['1', '11', '1102'])
  })
  it('type filter and hiding inactive leaves (groups stay)', () => {
    const roots = tree()
    expect(visibleNodes(roots, { ...open, type: 'liability' }).map((n) => n.code)).toEqual(['2'])
    expect(visibleNodes(roots, { ...open, showInactive: false }).map((n) => n.code)).not.toContain('1201')
  })
})

describe('sheetRows', () => {
  it('a new account sits at the end of its parent subtree; root ones at the end', () => {
    const roots = tree()
    const nodes = visibleNodes(roots, open)
    const byId = new Map<string, Node>()
    const index = (list: Node[]) => list.forEach((n) => (byId.set(n.id, n), index(n.children)))
    index(roots)
    const draft: Draft = { edits: {}, fresh: [fresh('n1', 'g1'), fresh('n2', null), fresh('n3', 'r1')] }
    const rows = sheetRows(nodes, draft, byId)
    const label = new Map(CHART.map((a) => [a.id, a.code]))
    expect(codes(rows, label)).toEqual(['1', '11', '1101', '1102', 'n1', '12', '1201', 'n3', '2', 'n2'])
    expect(rows.find((r) => r.key === 'n1')).toMatchObject({ kind: 'new', depth: 2 })
  })
  it('edits overlay the saved values', () => {
    const roots = tree()
    const rows = sheetRows(visibleNodes(roots, open), { edits: { l1: { name: 'صندوقِ مرکزی' } }, fresh: [] }, new Map())
    expect(rows.find((r) => r.key === 'l1')!.values.name).toBe('صندوقِ مرکزی')
  })
})

describe('patchOf', () => {
  const cash = CHART[2]
  it('splits the code (own endpoint) from the other fields, trimmed', () => {
    expect(patchOf(cash, { code: ' 1109 ', name: 'صندوق ' })).toEqual({ fields: null, code: '1109' })
    expect(patchOf(cash, { nature: 'credit', is_active: false })).toEqual({
      fields: { nature: 'credit', is_active: false },
      code: null,
    })
  })
  it('back to the original means nothing to save; empty nature is null', () => {
    expect(patchOf(cash, { code: '1101', name: 'صندوق' })).toBeNull()
    expect(patchOf({ ...cash, nature: 'debit' }, { nature: '' })).toEqual({ fields: { nature: null }, code: null })
  })
})

describe('problemOf / codeOwners', () => {
  it('code and name are required; a code is unique across saved and new rows', () => {
    const draft: Draft = { edits: { l2: { code: '1101' } }, fresh: [fresh('n1', 'g1', { code: '1102', name: 'تنخواه' })] }
    const owners = codeOwners(CHART, draft)
    expect(problemOf({ code: '', name: 'x' }, 'n1', owners)).toBe('کد را وارد کنید.')
    //: بانک کدِ صندوق را گرفته؛ صاحبِ اول صندوق است.
    expect(problemOf({ code: '1101', name: 'بانک ملی' }, 'l2', owners)).toBe('کدِ «1101» تکراری است.')
    //: کدِ ۱۱۰۲ حالا آزاد است (بانک عوضش کرد) و مالِ ردیفِ تازه است.
    expect(problemOf({ code: '1102', name: 'تنخواه' }, 'n1', owners)).toBeNull()
  })
})

describe('pendingCount / createBody / parseDraft', () => {
  it('counts real edits and new rows', () => {
    const draft: Draft = { edits: { l1: { name: 'صندوق' }, l2: { name: 'بانک' } }, fresh: [fresh('n1', 'g1')] }
    expect(pendingCount(draft, CHART)).toEqual({ fresh: 1, edited: 1 })
  })
  it('type comes from the parent; only roots use their own', () => {
    const f = fresh('n1', 'g1', { code: '1103', name: 'تنخواه', isGroup: true })
    expect(createBody(f, CHART[1])).toMatchObject({ type: 'asset', parent_id: 'g1', is_group: true, nature: null })
    expect(createBody(fresh('n2', null, { code: '6', name: 'هزینه‌ها' }), undefined)).toMatchObject({ type: 'expense', parent_id: null })
  })
  it('a broken draft is nothing; bad rows are dropped', () => {
    expect(parseDraft('{')).toBeNull()
    expect(parseDraft(JSON.stringify({ edits: null, fresh: [] }))).toBeNull()
    const d = parseDraft(JSON.stringify({ edits: {}, fresh: [fresh('ok', null), { key: 'bad' }] }))
    expect(d!.fresh.map((f) => f.key)).toEqual(['ok'])
  })
})

describe('nextFreeCode', () => {
  it('skips codes already taken by saved or unsaved rows; leaves non-numeric codes alone', () => {
    const owners = new Map([['1103', 'n1'], ['1104', 'l9']])
    expect(nextFreeCode('1103', owners)).toBe('1105')
    expect(nextFreeCode('0103', new Map([['0103', 'x']]))).toBe('0104')
    expect(nextFreeCode('11-03', owners)).toBe('11-03')
    expect(nextFreeCode('1106', owners)).toBe('1106')
  })
})
