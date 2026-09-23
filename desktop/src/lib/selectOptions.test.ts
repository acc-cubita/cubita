import { createElement as h } from 'react'
import { describe, expect, it } from 'vitest'

import { flatten, shouldSearch } from './selectOptions'

describe('برچسبِ گزینه', () => {
  it('فرزندِ رشته‌ای همان است', () => {
    expect(flatten([h('option', { key: 'a', value: 'a' }, 'بانک')])[0].label).toBe('بانک')
  })

  it('**فرزندِ چندتکه ویرگول نمی‌گیرد** — الگوی `{code} — {name}`ِ ۵۴ جای برنامه', () => {
    const el = h('option', { key: 'a', value: 'a' }, '1007', ' — ', 'بانک صادرات')
    expect(flatten([el])[0].label).toBe('1007 — بانک صادرات')
  })

  it('عدد هم متن می‌شود', () => {
    expect(flatten([h('option', { key: 'a', value: 'a' }, 1007, ' — ', 'نقد')])[0].label).toBe(
      '1007 — نقد',
    )
  })

  it('عنصرِ تودرتو باز می‌شود، نه [object Object]', () => {
    const el = h('option', { key: 'a', value: 'a' }, h('b', null, '۱۰۰۷'), ' نقد')
    expect(flatten([el])[0].label).toBe('۱۰۰۷ نقد')
  })

  it('فرزندِ تهی برچسبِ خالی می‌دهد، نه «null»', () => {
    expect(flatten([h('option', { key: 'a', value: 'a' }, null)])[0].label).toBe('')
  })

  it('value و disabled دست‌نخورده می‌مانند', () => {
    const el = h('option', { key: 'a', value: 'x1', disabled: true }, 'الف')
    expect(flatten([el])[0]).toEqual({ value: 'x1', label: 'الف', disabled: true })
  })
})

describe('optgroup', () => {
  it('باز می‌شود و برچسب‌های چندتکه‌اش هم درست‌اند', () => {
    const g = h(
      'optgroup',
      { key: 'g', label: 'دارایی' },
      h('option', { key: 'a', value: 'a' }, '10', ' — ', 'نقد'),
      h('option', { key: 'b', value: 'b' }, '11', ' — ', 'بانک'),
    )
    expect(flatten([g]).map((o) => o.label)).toEqual(['10 — نقد', '11 — بانک'])
  })
})

describe('آستانه‌ی جست‌وجو', () => {
  it('فهرستِ کوتاه select بومی می‌ماند', () => {
    expect(shouldSearch(3)).toBe(false)
  })
  it('فهرستِ بلند جست‌وجو می‌گیرد', () => {
    expect(shouldSearch(476)).toBe(true)
  })
  it('multiple و size همیشه بومی می‌مانند', () => {
    expect(shouldSearch(476, { multiple: true })).toBe(false)
    expect(shouldSearch(476, { size: 5 })).toBe(false)
  })
})
