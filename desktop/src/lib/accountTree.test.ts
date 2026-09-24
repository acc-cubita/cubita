/**
 * منطقِ خالصِ «مرور حساب‌ها» — درخت، ردیف‌های پیدا، جست‌وجو و کیبوردِ RTL.
 *
 * هیچ عددِ مالی این‌جا سنجیده نمی‌شود چون هیچ عددی این‌جا ساخته نمی‌شود: ارقام از
 * سرور می‌آیند (`backend/tests/test_account_browser.py` قیدِ «والد = جمعِ فرزندان» را
 * همان‌جا قفل می‌کند). این فایل فقط *ساختار* و *ترجمه‌ی علامت به جهت* را می‌سنجد.
 */
import { describe, expect, it } from 'vitest'

import type { BalanceTreeNode } from '../api'
import {
  buildTreeIndex,
  ledgerRaw,
  normalizeSearch,
  pathOf,
  revealIn,
  searchAccounts,
  sideOf,
  treeKey,
  visibleRows,
} from './accountTree'

function node(id: string, code: string, name: string, parent: string | null, extra: Partial<BalanceTreeNode> = {}): BalanceTreeNode {
  return {
    account_id: id,
    parent_id: parent,
    account_code: code,
    account_name: name,
    account_type: 'asset',
    nature: 'debit',
    is_group: false,
    is_active: true,
    accepts_tafsili: false,
    depth: 0,
    child_count: 0,
    opening: '0',
    period_debit: '0',
    period_credit: '0',
    closing: '0',
    has_activity: false,
    has_direct_lines: false,
    nature_violation: false,
    ...extra,
  }
}

/** سناریوی بانک: دارایی / دارایی جاری / موجودی نقد و بانک / {بانک ملی، صندوق}. */
const chart = [
  node('a', '1', 'دارایی‌ها', null, { is_group: true, closing: '20000000', has_activity: true }),
  node('ac', '11', 'دارایی جاری', 'a', { is_group: true, closing: '20000000', has_activity: true }),
  node('cash', '1102', 'موجودی نقد و بانک', 'ac', { is_group: true, closing: '20000000', has_activity: true }),
  node('melli', '110201', 'بانک ملی', 'cash', { closing: '20000000', has_activity: true }),
  node('box', '110202', 'صندوق', 'cash'),
  node('old', '110203', 'بانک قدیمی', 'cash', { is_active: false }),
  node('i', '6', 'درآمدها', null, { is_group: true, account_type: 'income', closing: '-20000000', has_activity: true }),
  node('sales', '6101', 'فروش', 'i', { account_type: 'income', closing: '-20000000', has_activity: true }),
]

describe('درخت', () => {
  const index = buildTreeIndex(chart)

  it('ریشه‌ها و فرزندان به ترتیبِ کد', () => {
    expect(index.roots.map((r) => r.account_code)).toEqual(['1', '6'])
    expect(index.children.get('cash')!.map((r) => r.account_code)).toEqual(['110201', '110202', '110203'])
  })

  it('باز کردنِ سبک: فقط فرزندانِ گره‌های باز پیموده می‌شوند', () => {
    expect(visibleRows(index, new Set()).map((r) => r.node.account_id)).toEqual(['a', 'i'])
    const open = visibleRows(index, new Set(['a']))
    expect(open.map((r) => r.node.account_id)).toEqual(['a', 'ac', 'i'])
    expect(open[1].level).toBe(1)
    expect(open[1].expandable).toBe(true)
  })

  it('فیلترِ «فقط دارای گردش» و «مخفی‌کردنِ صفر»', () => {
    const all = new Set(['a', 'ac', 'cash', 'i'])
    const ids = (f: object) => visibleRows(index, all, f).map((r) => r.node.account_id)
    expect(ids({})).toContain('box')
    expect(ids({ activeOnly: true })).not.toContain('box')
    expect(ids({ hideZero: true })).not.toContain('old')
    expect(ids({ hideZero: true })).toContain('melli')
  })

  it('حسابِ غیرفعال پنهان نمی‌شود — فقط نشان می‌خورد', () => {
    const rows = visibleRows(index, new Set(['a', 'ac', 'cash']))
    expect(rows.find((r) => r.node.account_id === 'old')?.node.is_active).toBe(false)
  })

  it('مسیرِ کامل و «نمایش در درخت»', () => {
    expect(pathOf(index, 'melli').map((n) => n.account_name)).toEqual([
      'دارایی‌ها',
      'دارایی جاری',
      'موجودی نقد و بانک',
      'بانک ملی',
    ])
    const expanded = revealIn(index, new Set(), 'melli')
    expect([...expanded].sort()).toEqual(['a', 'ac', 'cash'])
    expect(visibleRows(index, expanded).some((r) => r.node.account_id === 'melli')).toBe(true)
  })

  it('داده‌ی خراب: والدِ ناموجود ریشه می‌شود و حلقه قفل نمی‌کند', () => {
    const broken = buildTreeIndex([
      node('x', '9', 'یتیم', 'missing'),
      node('p', '8', 'حلقه ۱', 'q'),
      node('q', '81', 'حلقه ۲', 'p'),
    ])
    expect(broken.roots.map((r) => r.account_id)).toEqual(['x'])
    expect(pathOf(broken, 'p').length).toBe(2)
  })
})

describe('جست‌وجو', () => {
  const index = buildTreeIndex(chart)

  it('«بانک ملی» را با مسیرش پیدا می‌کند', () => {
    const hits = searchAccounts(index, 'بانک ملی')
    expect(hits[0].node.account_id).toBe('melli')
    expect(hits[0].path.map((p) => p.account_name).slice(0, -1)).toEqual([
      'دارایی‌ها',
      'دارایی جاری',
      'موجودی نقد و بانک',
    ])
  })

  it('ی و ک عربی، ارقامِ فارسی و ترتیبِ کلمه‌ها', () => {
    expect(normalizeSearch('بانك ملي ۱۱۰')).toBe('بانک ملی 110')
    expect(searchAccounts(index, 'بانك ملي')[0].node.account_id).toBe('melli')
    expect(searchAccounts(index, 'ملی بانک')[0].node.account_id).toBe('melli')
    expect(searchAccounts(index, '۱۱۰۲۰۱')[0].node.account_id).toBe('melli')
  })

  it('کدِ دقیق و پیشوندِ کد پیش از تطبیقِ نام', () => {
    const hits = searchAccounts(index, '1102')
    expect(hits[0].node.account_id).toBe('cash')
    expect(hits.slice(1).map((h) => h.node.account_id)).toEqual(['melli', 'box', 'old'])
  })

  it('حسابِ غیرفعال هم پیدا می‌شود — داده‌ی تاریخی‌اش دیدنی است', () => {
    expect(searchAccounts(index, 'قدیمی')[0].node.account_id).toBe('old')
  })

  it('عبارتِ خالی هیچ نتیجه‌ای نمی‌دهد', () => {
    expect(searchAccounts(index, '   ')).toEqual([])
  })
})

describe('جهتِ مانده', () => {
  it('خام (بد − بس) → مقدار و جهت', () => {
    expect(sideOf(850)).toEqual({ amount: 850, side: 'debit' })
    expect(sideOf(-120)).toEqual({ amount: 120, side: 'credit' })
    expect(sideOf(0)).toEqual({ amount: 0, side: null })
  })

  it('مانده‌ی دفتر بر اساسِ نوعِ حساب علامت دارد — همان `_signed_balance`', () => {
    //: درآمد: مثبت یعنی بستانکار.
    expect(sideOf(ledgerRaw(20, 'income')).side).toBe('credit')
    expect(sideOf(ledgerRaw(-5, 'liability')).side).toBe('debit')
    expect(sideOf(ledgerRaw(20, 'asset')).side).toBe('debit')
    expect(sideOf(ledgerRaw(20, 'expense')).side).toBe('debit')
  })
})

describe('کیبوردِ درخت (راست‌به‌چپ)', () => {
  const index = buildTreeIndex(chart)

  it('↑ ↓ Home End', () => {
    const rows = visibleRows(index, new Set(['a']))
    expect(treeKey('ArrowDown', rows, 'a', new Set(['a']))).toEqual({ kind: 'focus', id: 'ac' })
    expect(treeKey('ArrowUp', rows, 'ac', new Set(['a']))).toEqual({ kind: 'focus', id: 'a' })
    expect(treeKey('ArrowUp', rows, 'a', new Set(['a']))).toEqual({ kind: 'focus', id: 'a' })
    expect(treeKey('End', rows, 'a', new Set(['a']))).toEqual({ kind: 'focus', id: 'i' })
    expect(treeKey('ArrowDown', rows, null, new Set(['a']))).toEqual({ kind: 'focus', id: 'a' })
  })

  it('← باز می‌کند و بعد به اولین فرزند می‌رود', () => {
    const closed = visibleRows(index, new Set())
    expect(treeKey('ArrowLeft', closed, 'a', new Set())).toEqual({ kind: 'expand', id: 'a' })
    const open = visibleRows(index, new Set(['a']))
    expect(treeKey('ArrowLeft', open, 'a', new Set(['a']))).toEqual({ kind: 'focus', id: 'ac' })
  })

  it('→ می‌بندد؛ روی بسته یا برگ به والد می‌رود', () => {
    const exp = new Set(['a', 'ac', 'cash'])
    const rows = visibleRows(index, exp)
    expect(treeKey('ArrowRight', rows, 'cash', exp)).toEqual({ kind: 'collapse', id: 'cash' })
    expect(treeKey('ArrowRight', rows, 'melli', exp)).toEqual({ kind: 'focus', id: 'cash' })
    expect(treeKey('ArrowLeft', rows, 'melli', exp)).toEqual({ kind: 'none' })
  })

  it('Enter وارد گردش می‌شود؛ Escape یک سطح بالا', () => {
    const exp = new Set(['a', 'ac', 'cash'])
    const rows = visibleRows(index, exp)
    expect(treeKey('Enter', rows, 'melli', exp)).toEqual({ kind: 'open', id: 'melli' })
    expect(treeKey('Escape', rows, 'melli', exp)).toEqual({ kind: 'focus', id: 'cash' })
    expect(treeKey('Escape', rows, 'a', exp)).toEqual({ kind: 'none' })
  })
})
