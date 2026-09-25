import { describe, expect, it } from 'vitest'

import { applyOrder, moveInOrder } from './menuOrder'

const id = (s: string) => s

describe('applyOrder', () => {
  it('بی ترتیبِ ذخیره‌شده: همان پیش‌فرض', () => {
    expect(applyOrder(['a', 'b', 'c'], id)).toEqual(['a', 'b', 'c'])
    expect(applyOrder(['a', 'b', 'c'], id, [])).toEqual(['a', 'b', 'c'])
  })

  it('ترتیبِ ذخیره‌شده اعمال می‌شود', () => {
    expect(applyOrder(['a', 'b', 'c'], id, ['c', 'a', 'b'])).toEqual(['c', 'a', 'b'])
  })

  it('منوی تازه (در ذخیره نیست) ته فهرست می‌نشیند، به ترتیبِ پیش‌فرضِ خودش — ناپدید نمی‌شود', () => {
    expect(applyOrder(['a', 'new1', 'b', 'new2'], id, ['b', 'a'])).toEqual(['b', 'a', 'new1', 'new2'])
  })

  it('کلیدِ ذخیره‌شده‌ای که الان دیده نمی‌شود نادیده گرفته می‌شود', () => {
    expect(applyOrder(['a', 'b'], id, ['gone', 'b', 'a'])).toEqual(['b', 'a'])
  })
})

describe('moveInOrder', () => {
  it('بالا و پایین', () => {
    expect(moveInOrder(['a', 'b', 'c'], undefined, 'b', -1)).toEqual(['b', 'a', 'c'])
    expect(moveInOrder(['a', 'b', 'c'], undefined, 'b', 1)).toEqual(['a', 'c', 'b'])
  })

  it('لبه‌ها: اولی بالا نمی‌رود، آخری پایین نمی‌رود', () => {
    expect(moveInOrder(['a', 'b'], undefined, 'a', -1)).toBeNull()
    expect(moveInOrder(['a', 'b'], undefined, 'b', 1)).toBeNull()
    expect(moveInOrder(['a', 'b'], undefined, 'x', 1)).toBeNull()
  })

  it('کلیدهای ذخیره‌شده‌ی پنهان (ماژولِ خاموش) با جابه‌جایی پاک نمی‌شوند', () => {
    //: روی صفحه (ترتیبِ ذخیره‌شده اعمال‌شده): b, a — «hidden» الان دیده نمی‌شود.
    expect(moveInOrder(['b', 'a'], ['b', 'hidden', 'a'], 'a', -1)).toEqual(['a', 'b', 'hidden'])
  })
})
