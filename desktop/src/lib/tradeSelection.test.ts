/**
 * انتخابِ چندتاییِ صنف.
 *
 * چیزی که این فایل نگه می‌دارد: «کلِ گروه» در حالتِ **نیمه‌انتخاب** باید گسترش بدهد،
 * نه پاک کند. اگر برعکس شود، پخش‌کننده‌ای که سه صنف از یک گروه را دستی زده و بعد
 * دکمه را می‌زند، کارِ خودش را از دست می‌دهد — و چون ذخیره موفق است، تازه بعداً
 * می‌فهمد.
 */
import { describe, it, expect } from 'vitest'

import { toggleExpanded, toggleGroup, toggleTrade, viewGroups } from './tradeSelection'

describe('toggleTrade', () => {
  it('نبود را می‌گذارد و بود را برمی‌دارد', () => {
    expect(toggleTrade([], 'tools')).toEqual(['tools'])
    expect(toggleTrade(['tools', 'autoparts'], 'tools')).toEqual(['autoparts'])
  })

  it('ترتیبِ بقیه را به‌هم نمی‌زند', () => {
    expect(toggleTrade(['a', 'b', 'c'], 'd')).toEqual(['a', 'b', 'c', 'd'])
  })
})

describe('toggleGroup', () => {
  const group = ['autoparts', 'tools', 'tires']

  it('گروهِ خالی → همه انتخاب می‌شوند', () => {
    expect(toggleGroup([], group)).toEqual(group)
  })

  it('گروهِ کاملاً انتخاب‌شده → همه برداشته می‌شوند، بقیه می‌مانند', () => {
    expect(toggleGroup(['icecream', ...group], group)).toEqual(['icecream'])
  })

  it('نیمه‌انتخاب → گسترش، نه پاک‌کردن', () => {
    expect(toggleGroup(['tools'], group)).toEqual(['tools', 'autoparts', 'tires'])
  })

  it('تکراری نمی‌سازد', () => {
    const got = toggleGroup(['tools', 'tools'], group)
    expect(got.length).toBe(new Set(got).size)
  })
})

describe('viewGroups', () => {
  const m = (label: string, q: string) => label.includes(q)
  const GROUPS = [
    { key: 'auto', label: 'خودرو', trades: [
      { key: 'autoparts', label: 'لوازم یدکی خودرو' },
      { key: 'tires', label: 'لاستیک و رینگ' },
    ] },
    { key: 'food', label: 'خوراکی', trades: [
      { key: 'icecream', label: 'بستنی‌فروشی' },
    ] },
  ]

  it('بدونِ جست‌وجو، همه‌ی گروه‌ها می‌آیند و جمع‌اند', () => {
    const v = viewGroups(GROUPS, [], '', new Set(), m)
    expect(v.map((g) => g.key)).toEqual(['auto', 'food'])
    expect(v.every((g) => !g.open)).toBe(true)
  })

  it('گروهِ بازشده، باز می‌ماند', () => {
    const v = viewGroups(GROUPS, [], '', new Set(['food']), m)
    expect(v.find((g) => g.key === 'food')!.open).toBe(true)
  })

  it('جست‌وجو گروهِ بی‌نتیجه را حذف و گروهِ دارای نتیجه را باز می‌کند', () => {
    const v = viewGroups(GROUPS, [], 'یدک', new Set(), m)
    expect(v.map((g) => g.key)).toEqual(['auto'])
    expect(v[0].open).toBe(true)
    expect(v[0].trades.map((t) => t.key)).toEqual(['autoparts'])
  })

  it('شمارنده از کلِ گروه است، نه از نتایجِ جست‌وجو', () => {
    //: وگرنه کاربرِ وسطِ جست‌وجو فکر می‌کند انتخاب‌هایش پاک شده‌اند.
    const v = viewGroups(GROUPS, ['autoparts', 'tires'], 'یدک', new Set(), m)
    expect(v[0].trades).toHaveLength(1)
    expect([v[0].chosen, v[0].total]).toEqual([2, 2])
  })
})

describe('toggleExpanded', () => {
  it('باز و بسته می‌کند بدونِ دست‌زدن به بقیه', () => {
    const a = toggleExpanded(new Set(['x']), 'y')
    expect([...a].sort()).toEqual(['x', 'y'])
    expect([...toggleExpanded(a, 'x')]).toEqual(['y'])
  })
})
