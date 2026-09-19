/**
 * `SearchSelect` — منطقِ خالصش.
 *
 * دو قیدی که این فایل نگه می‌دارد:
 *
 * ۱. **فهرستِ کوتاه `<select>`ِ بومی می‌ماند.** اگر روزی آستانه برداشته شود،
 *    «وضعیت: همه / باز / بسته» هم کادرِ جست‌وجو می‌گیرد و روی موبایل چرخِ
 *    بومیِ سیستم را از دست می‌دهیم.
 * ۲. **خواندنِ `<option>`ها نباید بشکند.** این کامپوننت جایگزینِ درجای
 *    `<select>` است؛ اگر `flatten` یک شکلِ فرزند را نفهمد، آن فهرست بی‌صدا
 *    خالی می‌شود — نه خطا می‌دهد، نه دیده می‌شود.
 *
 * رندرِ واقعی این‌جا سنجیده نمی‌شود: محیطِ vitest این پروژه `node` است و DOM
 * ندارد. آن بخش دستی دیده می‌شود.
 */
import { createElement as h } from 'react'
import { describe, it, expect } from 'vitest'

import { flatten, shouldSearch, SEARCH_THRESHOLD } from '../lib/selectOptions'
import { textMatches } from '../lib/commands'

const opt = (value: string, label: string, disabled?: boolean) =>
  h('option', { key: value, value, disabled }, label)

describe('آستانه', () => {
  it('فهرستِ کوتاه جست‌وجو نمی‌گیرد', () => {
    expect(shouldSearch(3)).toBe(false)
    expect(shouldSearch(SEARCH_THRESHOLD - 1)).toBe(false)
  })

  it('از آستانه به بالا می‌گیرد', () => {
    expect(shouldSearch(SEARCH_THRESHOLD)).toBe(true)
    expect(shouldSearch(393)).toBe(true)
  })

  it('`multiple` و `size` همیشه بومی می‌مانند — رفتارشان چیزِ دیگری است', () => {
    expect(shouldSearch(100, { multiple: true })).toBe(false)
    expect(shouldSearch(100, { size: 5 })).toBe(false)
  })
})

describe('خواندنِ گزینه‌ها', () => {
  it('`<option>`های ساده', () => {
    const got = flatten([opt('a', 'عدد'), opt('b', 'کارتن')])
    expect(got).toEqual([
      { value: 'a', label: 'عدد', disabled: undefined },
      { value: 'b', label: 'کارتن', disabled: undefined },
    ])
  })

  it('`<optgroup>` باز می‌شود — وگرنه آن فهرست‌ها خالی دیده می‌شدند', () => {
    const got = flatten([h('optgroup', { key: 'g', label: 'وزن' }, [opt('1', 'گرم'), opt('2', 'کیلوگرم')])])
    expect(got.map((o) => o.label)).toEqual(['گرم', 'کیلوگرم'])
  })

  it('گزینه‌ی غیرفعال نشانه‌اش را نگه می‌دارد', () => {
    expect(flatten([opt('x', 'قدیمی', true)])[0].disabled).toBe(true)
  })

  it('گزینه‌ی بی‌`value` رشته‌ی خالی می‌شود — همان کاری که `<select>` می‌کند', () => {
    expect(flatten([h('option', { key: 'e' }, '— انتخاب کنید —')])[0].value).toBe('')
  })

  it('چیزی که `<option>` نیست نادیده گرفته می‌شود', () => {
    expect(flatten(['متن', null, undefined, false, opt('a', 'عدد')])).toHaveLength(1)
  })
})

describe('جست‌وجو روی واحدهای واقعی', () => {
  //: همان چیزی که کاربر خواست: «کا» بزند، «کارتن» بیاید.
  const units = ['عدد', 'کارتن', 'کاشی', 'کابل', 'کیلوگرم', 'متر مربع', 'بسته', 'پالت']

  it('«کا» هر چیزی را که «کا» دارد می‌آورد', () => {
    expect(units.filter((u) => textMatches(u, 'کا'))).toEqual(['کارتن', 'کاشی', 'کابل'])
  })

  it('«كارتن» با کافِ عربی هم پیدا می‌شود', () => {
    expect(units.filter((u) => textMatches(u, 'كارتن'))).toEqual(['کارتن'])
  })

  it('«متر مربع» با نیم‌فاصله هم پیدا می‌شود', () => {
    expect(units.filter((u) => textMatches(u, 'متر‌مربع'))).toEqual(['متر مربع'])
  })
})
