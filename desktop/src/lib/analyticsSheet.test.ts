/**
 * منطقِ برگه‌ی «تفصیلی سایر»: ترتیب، تغییرِ واقعی، اعتبار، ردیفِ خالیِ ته، جست‌وجو و پیش‌نویس.
 */
import { describe, expect, it } from 'vitest'

import type { AnalyticAccount } from '../api'
import {
  blankFresh,
  isBlank,
  matches,
  parseDraft,
  patchOf,
  pendingCount,
  problemOf,
  sortRows,
  withTrailingBlank,
} from './analyticsSheet'

const row = (id: string, code: string, name: string, group_name = '', extra: Partial<AnalyticAccount> = {}): AnalyticAccount => ({
  id,
  code,
  name,
  group_name,
  description: '',
  is_active: true,
  line_count: 0,
  ...extra,
})

describe('sortRows — دسته، بعد کد؛ بی‌دسته‌ها آخر', () => {
  it('کدِ عددی به ترتیبِ عددی', () => {
    const out = sortRows([row('a', '10', 'ده', 'خودرو'), row('b', '2', 'دو', 'خودرو'), row('c', '1', 'بی‌دسته'), row('d', '5', 'پنج', 'پروژه')])
    expect(out.map((r) => r.id)).toEqual(['d', 'b', 'a', 'c'])
  })
})

describe('patchOf — فقط آنچه واقعاً عوض شده', () => {
  const r = row('a', 'A1', 'پژو', 'خودرو')
  it('بی ویرایش یا ویرایشِ بی‌اثر (فقط فاصله) → null', () => {
    expect(patchOf(r, undefined)).toBeNull()
    expect(patchOf(r, { name: ' پژو ' })).toBeNull()
    expect(patchOf(r, { is_active: true })).toBeNull()
  })
  it('فیلدِ عوض‌شده، trim‌شده', () => {
    expect(patchOf(r, { name: ' پژو ۴۰۵ ', code: 'A1' })).toEqual({ name: 'پژو ۴۰۵' })
    expect(patchOf(r, { is_active: false })).toEqual({ is_active: false })
  })
})

describe('problemOf — همان دو قاعده‌ی سرور', () => {
  it('کد و نام لازم‌اند', () => {
    expect(problemOf({ code: '', name: '' })).toBe('کد و نام را وارد کنید.')
    expect(problemOf({ code: ' ', name: 'x' })).toBe('کد را وارد کنید.')
    expect(problemOf({ code: 'x', name: '' })).toBe('نام را وارد کنید.')
    expect(problemOf({ code: 'x', name: 'y' })).toBeNull()
  })
})

describe('withTrailingBlank — همیشه دقیقاً یک ردیفِ خالیِ ته', () => {
  let n = 0
  const key = () => `k${++n}`
  it('بی ردیف یا با ردیفِ پُر → یک خالیِ تازه', () => {
    expect(withTrailingBlank([], key)).toHaveLength(1)
    const out = withTrailingBlank([{ ...blankFresh('x'), code: 'Z' }], key)
    expect(out).toHaveLength(2)
    expect(isBlank(out[1])).toBe(true)
  })
  it('دو خالیِ ته → یکی', () => {
    const out = withTrailingBlank([{ ...blankFresh('x'), code: 'Z' }, blankFresh('y'), blankFresh('z')], key)
    expect(out.map((f) => f.key)).toEqual(['x', 'y'])
  })
  it('خالیِ وسط دست نمی‌خورد (کاربر ممکن است برگردد و پرش کند)', () => {
    const out = withTrailingBlank([blankFresh('a'), { ...blankFresh('b'), name: 'n' }, blankFresh('c')], key)
    expect(out.map((f) => f.key)).toEqual(['a', 'b', 'c'])
  })
})

describe('matches و pendingCount', () => {
  it('جست‌وجو در کد، نام، دسته و توضیح — «ي» عربی هم', () => {
    const r = row('a', 'V-12', 'پیکان', 'خودرو', { description: 'مدلِ ۱۴۰۰' })
    expect(matches(r, 'v-1')).toBe(true)
    expect(matches(r, 'پيكان')).toBe(true)
    expect(matches(r, 'خودر')).toBe(true)
    expect(matches(r, 'قرارداد')).toBe(false)
    expect(matches(r, '  ')).toBe(true)
  })
  it('فقط ویرایشِ واقعی و ردیفِ تازه‌ی نه‌خالی شمرده می‌شوند', () => {
    const rows = [row('a', 'A', 'x'), row('b', 'B', 'y')]
    const draft = {
      edits: { a: { name: 'x' }, b: { name: 'yy' }, gone: { name: 'z' } },
      fresh: [{ ...blankFresh('n1'), code: 'N' }, blankFresh('n2')],
    }
    expect(pendingCount(draft, rows)).toEqual({ fresh: 1, edited: 1 })
  })
})

describe('parseDraft — ذخیره‌ی خراب یعنی هیچ', () => {
  it('شکلِ درست', () => {
    const d = { edits: { a: { name: 'x' } }, fresh: [blankFresh('k')] }
    expect(parseDraft(JSON.stringify(d))).toEqual(d)
  })
  it('خراب یا نامعتبر', () => {
    expect(parseDraft(null)).toBeNull()
    expect(parseDraft('{')).toBeNull()
    expect(parseDraft('[]')).toBeNull()
    expect(parseDraft(JSON.stringify({ edits: {}, fresh: [{ key: 1 }] }))).toEqual({ edits: {}, fresh: [] })
  })
})
