import { describe, expect, it } from 'vitest'

import { EMPTY_SELECTION, clickRow } from './rowSelection'

const order = ['a', 'b', 'c', 'd', 'e']
const plain = { shift: false, ctrl: false }
const keys = (s: { keys: ReadonlySet<string> }) => [...s.keys].sort()

describe('clickRow — انتخابِ ردیف مثلِ اکسل', () => {
  it('کلیک فقط همین ردیف؛ کلیکِ دوباره برش می‌دارد', () => {
    const s = clickRow(EMPTY_SELECTION, order, 'b', plain)
    expect(keys(s)).toEqual(['b'])
    expect(clickRow(s, order, 'b', plain)).toBe(EMPTY_SELECTION)
    expect(keys(clickRow(s, order, 'd', plain))).toEqual(['d'])
  })

  it('Ctrl+کلیک افزودن و برداشتن', () => {
    let s = clickRow(EMPTY_SELECTION, order, 'a', plain)
    s = clickRow(s, order, 'c', { shift: false, ctrl: true })
    expect(keys(s)).toEqual(['a', 'c'])
    s = clickRow(s, order, 'a', { shift: false, ctrl: true })
    expect(keys(s)).toEqual(['c'])
  })

  it('Shift+کلیک بازه از لنگر، در هر دو جهت', () => {
    const s = clickRow(EMPTY_SELECTION, order, 'b', plain)
    expect(keys(clickRow(s, order, 'd', { shift: true, ctrl: false }))).toEqual(['b', 'c', 'd'])
    const up = clickRow(clickRow(EMPTY_SELECTION, order, 'd', plain), order, 'a', { shift: true, ctrl: false })
    expect(keys(up)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('Ctrl+Shift بازه را به انتخابِ قبلی می‌افزاید', () => {
    let s = clickRow(EMPTY_SELECTION, order, 'a', plain)
    s = clickRow(s, order, 'd', { shift: false, ctrl: true })
    s = clickRow(s, order, 'e', { shift: true, ctrl: true })
    expect(keys(s)).toEqual(['a', 'd', 'e'])
  })

  it('Shift بی لنگر مثلِ کلیکِ ساده است', () => {
    expect(keys(clickRow(EMPTY_SELECTION, order, 'c', { shift: true, ctrl: false }))).toEqual(['c'])
  })
})
