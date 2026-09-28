import { describe, expect, it } from 'vitest'

import {
  blankFresh,
  cellChanged,
  isBlank,
  matches,
  omit,
  parseDraft,
  patchOf,
  pendingCount,
  problemOf,
  withTrailingBlank,
  type DefSpec,
} from './defSheet'

//: شکلِ برگه‌ی صندوق: متن، شناسه، ارزِ پیش‌فرض، عدد و وضعیت.
const SPEC: DefSpec = {
  text: ['name', 'analytic_id', 'currency_code', 'blocked'],
  bools: ['is_active'],
  numeric: ['blocked'],
  defaults: { currency_code: 'IRR' },
  required: [{ field: 'name', label: 'عنوان' }],
  search: ['name'],
}
let n = 0
const key = () => `k${++n}`

describe('ردیفِ خالی', () => {
  it('ردیفی که فقط پیش‌فرض دارد خالی است', () => {
    const r = blankFresh(SPEC, 'a')
    expect(r).toEqual({ key: 'a', name: '', analytic_id: '', currency_code: 'IRR', blocked: '' })
    expect(isBlank(SPEC, r)).toBe(true)
    expect(isBlank(SPEC, { ...r, currency_code: 'USD' })).toBe(false)
  })

  it('ته برگه همیشه دقیقاً یک ردیفِ خالی — خالی‌های وسط دست نمی‌خورند', () => {
    const filled = { ...blankFresh(SPEC, 'x'), name: 'صندوق' }
    expect(withTrailingBlank(SPEC, [], key)).toHaveLength(1)
    const out = withTrailingBlank(SPEC, [blankFresh(SPEC, 'm'), filled], key)
    expect(out.map((r) => isBlank(SPEC, r))).toEqual([true, false, true])
    const trimmed = withTrailingBlank(SPEC, [filled, blankFresh(SPEC, 'b1'), blankFresh(SPEC, 'b2')], key)
    expect(trimmed).toHaveLength(2)
  })
})

describe('تغییر', () => {
  const orig = { name: 'صندوق', analytic_id: '', currency_code: 'IRR', blocked: '0.00', is_active: true }

  it('فقط فیلدِ واقعاً عوض‌شده، با trim؛ عددِ هم‌ارز تغییر نیست', () => {
    expect(patchOf(SPEC, orig, { name: ' صندوق ', blocked: '0' })).toBeNull()
    expect(patchOf(SPEC, orig, { name: 'صندوق شعبه ', blocked: '1500' })).toEqual({ name: 'صندوق شعبه', blocked: '1500' })
    expect(patchOf(SPEC, orig, { is_active: false })).toEqual({ is_active: false })
    expect(patchOf(SPEC, orig, undefined)).toBeNull()
  })

  it('ته‌رنگِ خانه همان قاعده را دارد', () => {
    expect(cellChanged(SPEC, 'blocked', orig, { ...orig, blocked: '0' })).toBe(false)
    expect(cellChanged(SPEC, 'name', orig, { ...orig, name: 'دیگر' })).toBe(true)
    expect(cellChanged(SPEC, 'is_active', orig, { ...orig, is_active: false })).toBe(true)
  })

  it('شمارشِ نوار: ردیفِ تازه‌ی پُر و ثبت‌شده‌ی واقعاً عوض‌شده', () => {
    const saved = new Map([['1', orig]])
    const draft = {
      edits: { '1': { name: 'صندوق' }, ghost: { name: 'x' } },
      fresh: [{ ...blankFresh(SPEC, 'a'), name: 'تازه' }, blankFresh(SPEC, 'b')],
    }
    expect(pendingCount(SPEC, draft, saved)).toEqual({ fresh: 1, edited: 0 })
    expect(pendingCount(SPEC, { ...draft, edits: { '1': { name: 'دیگر' } } }, saved)).toEqual({ fresh: 1, edited: 1 })
  })
})

describe('سنجش و جست‌وجو', () => {
  it('فیلدِ لازمِ خالی پیش از ارسال گفته می‌شود', () => {
    expect(problemOf(SPEC, { name: '  ' })).toBe('عنوان را وارد کنید.')
    expect(problemOf(SPEC, { name: 'صندوق' })).toBeNull()
    const two: DefSpec = { ...SPEC, required: [{ field: 'a', label: 'الف' }, { field: 'b', label: 'ب' }] }
    expect(problemOf(two, {})).toBe('الف و ب را وارد کنید.')
  })

  it('جست‌وجو با ی/ک عربی و رقمِ فارسی', () => {
    expect(matches(SPEC, { name: 'صندوق کيش ۲' }, 'کیش 2')).toBe(true)
    expect(matches(SPEC, { name: 'صندوق' }, 'بانک')).toBe(false)
    expect(matches(SPEC, { name: 'هرچه' }, '  ')).toBe(true)
  })
})

describe('پیش‌نویس', () => {
  it('شکلِ خراب یعنی هیچ؛ ردیفِ ناقص کنار می‌رود', () => {
    expect(parseDraft(SPEC, null)).toBeNull()
    expect(parseDraft(SPEC, '{bad')).toBeNull()
    expect(parseDraft(SPEC, JSON.stringify({ edits: [], fresh: [] }))).toBeNull()
    const ok = parseDraft(
      SPEC,
      JSON.stringify({ edits: { '1': { name: 'x' } }, fresh: [blankFresh(SPEC, 'a'), { key: 'b', name: 'ناقص' }] }),
    )
    expect(ok?.fresh.map((f) => f.key)).toEqual(['a'])
    expect(ok?.edits).toEqual({ '1': { name: 'x' } })
  })

  it('omit', () => {
    expect(omit({ a: 1, b: 2, c: 3 }, ['a', 'c'])).toEqual({ b: 2 })
  })
})
