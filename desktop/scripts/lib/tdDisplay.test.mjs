import { describe, expect, it } from 'vitest'

import { tdClassesIn, tdDisplayFindings } from './tdDisplay.mjs'

describe('کلاس‌های روی <td>', () => {
  it('کلاسِ ساده را می‌گیرد', () => {
    expect([...tdClassesIn('<td className="jg-actions">x</td>')]).toContain('jg-actions')
  })

  it('چند کلاس را جدا می‌کند', () => {
    const s = tdClassesIn('<td className="ef-col-min jg-actions card-actions" />')
    expect([...s].sort()).toEqual(['card-actions', 'ef-col-min', 'jg-actions'])
  })

  it('هر دو شاخه‌ی یک شرط را می‌گیرد — هر کدام ممکن است روی سلول بنشیند', () => {
    const s = tdClassesIn("<td className={bad ? 'is-bad' : 'is-ok'} />")
    expect([...s].sort()).toEqual(['is-bad', 'is-ok'])
  })

  it('کلاسِ عنصرهای دیگر را نمی‌گیرد', () => {
    const s = tdClassesIn('<div className="wrap"><td className="cell" /></div>')
    expect(s.has('cell')).toBe(true)
    expect(s.has('wrap')).toBe(false)
  })

  it('`>` داخلِ attribute سرِ تگ را زود نمی‌بندد', () => {
    const s = tdClassesIn('<td className={n > 0 ? "pos" : "neg"} data-x="1" />')
    expect(s.has('pos')).toBe(true)
    expect(s.has('neg')).toBe(true)
  })
})

describe('display چیدمانی روی سلولِ جدول', () => {
  const td = new Set(['jg-actions', 'card-actions'])

  it('**باگِ واقعیِ #۱۶۹** را می‌گیرد', () => {
    const hits = tdDisplayFindings('.jg-actions { display: flex; gap: 2px; }', td)
    expect(hits).toHaveLength(1)
    expect(hits[0]).toMatchObject({ cls: 'jg-actions', value: 'flex', line: 1 })
  })

  it('grid هم همان اثر را دارد', () => {
    expect(tdDisplayFindings('.jg-actions { display: grid }', td)).toHaveLength(1)
  })

  it('رفعِ درست — فاعل، فرزندِ داخلی است نه خودِ سلول', () => {
    expect(tdDisplayFindings('.jg-actions .row-actions { display: flex }', td)).toEqual([])
  })

  it('`td.card-actions > *` هم فاعلش سلول نیست', () => {
    expect(tdDisplayFindings('td.card-actions > * { display: flex }', td)).toEqual([])
  })

  it('داخلِ @media نادیده گرفته می‌شود — آنجا جدول دیگر جدول نیست', () => {
    const css = '@media (max-width: 760px) {\n  td.card-actions { display: flex }\n}'
    expect(tdDisplayFindings(css, td)).toEqual([])
  })

  it('displayهای بی‌خطر رد می‌شوند', () => {
    expect(tdDisplayFindings('.jg-actions { display: none }', td)).toEqual([])
    expect(tdDisplayFindings('.jg-actions { display: table-cell }', td)).toEqual([])
  })

  it('خاصیت‌های دیگر کاری ندارند', () => {
    expect(tdDisplayFindings('.jg-actions { text-align: end; gap: 2px }', td)).toEqual([])
  })

  it('کلاسی که روی هیچ `<td>` نیست، آزاد است', () => {
    expect(tdDisplayFindings('.toolbar { display: flex }', td)).toEqual([])
  })

  it('انتخابگرِ چندتایی: یکی از آن‌ها کافی است', () => {
    const hits = tdDisplayFindings('.toolbar,\n.jg-actions { display: flex }', td)
    expect(hits).toHaveLength(1)
    expect(hits[0].cls).toBe('jg-actions')
  })

  it('کامنت گمراهش نمی‌کند', () => {
    const css = '/* .jg-actions { display: flex } */\n.jg-actions { text-align: end }'
    expect(tdDisplayFindings(css, td)).toEqual([])
  })

  it('شماره‌ی خط به خطِ انتخابگر اشاره می‌کند، نه به `display`', () => {
    const css = 'a { color: red }\n\n.jg-actions {\n  gap: 2px;\n  display: flex;\n}'
    expect(tdDisplayFindings(css, td)[0].line).toBe(3)
  })
})
