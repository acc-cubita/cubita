/**
 * انتخابِ چندتاییِ صنف.
 *
 * چیزی که این فایل نگه می‌دارد: «کلِ گروه» در حالتِ **نیمه‌انتخاب** باید گسترش بدهد،
 * نه پاک کند. اگر برعکس شود، پخش‌کننده‌ای که سه صنف از یک گروه را دستی زده و بعد
 * دکمه را می‌زند، کارِ خودش را از دست می‌دهد — و چون ذخیره موفق است، تازه بعداً
 * می‌فهمد.
 */
import { describe, it, expect } from 'vitest'

import { toggleGroup, toggleTrade } from './tradeSelection'

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
