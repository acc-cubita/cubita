/**
 * اصناف سمتِ کلاینت — منطقِ خالصش.
 *
 * دو قیدی که این فایل نگه می‌دارد:
 *
 * ۱. **گروه‌ها در انتخابگر گم نمی‌شوند.** اصناف داخلِ `<optgroup>` رندر می‌شوند و
 *    `SearchSelect` باید همه‌شان را ببیند. اگر `flatten` گروه را باز نکند، فهرستِ
 *    ~۹۰تایی **بی‌صدا خالی** می‌شود — نه خطا می‌دهد و نه به چشم می‌آید.
 * ۲. **جست‌وجو با تکه‌ی وسطِ نام کار می‌کند.** کاربر «یدک» می‌زند، نه «لوازم».
 */
import { createElement as h } from 'react'
import { describe, it, expect } from 'vitest'

import { flatten } from './selectOptions'
import { textMatches } from './commands'
import { labelOfTrade } from './useTrades'
import type { TradeGroup } from '../api'

//: نمونه‌ای به شکلِ واقعیِ پاسخِ `/api/trades`.
const GROUPS: TradeGroup[] = [
  {
    key: 'food',
    label: 'خوراکی و آشامیدنی',
    trades: [
      { key: 'supermarket', label: 'سوپرمارکت' },
      { key: 'icecream', label: 'بستنی‌فروشی' },
    ],
  },
  {
    key: 'auto_industrial',
    label: 'فنی، خودرو و صنعتی',
    trades: [
      { key: 'autoparts', label: 'لوازم یدکی خودرو' },
      { key: 'tools', label: 'ابزارفروشی' },
    ],
  },
]

/** همان چیزی که صفحه‌ها رندر می‌کنند: یک گزینه‌ی خالی + یک `<optgroup>` به‌ازای هر گروه. */
const options = () => [
  h('option', { key: '', value: '' }, '— انتخاب کنید —'),
  ...GROUPS.map((g) =>
    h(
      'optgroup',
      { key: g.key, label: g.label },
      g.trades.map((t) => h('option', { key: t.key, value: t.key }, t.label)),
    ),
  ),
]

describe('انتخابگرِ صنف', () => {
  it('همه‌ی اصنافِ داخلِ گروه‌ها دیده می‌شوند', () => {
    const got = flatten(options())
    expect(got.map((o) => o.value)).toEqual(['', 'supermarket', 'icecream', 'autoparts', 'tools'])
  })

  it('با ۹ گزینه به بالا، `SearchSelect` جست‌وجو می‌دهد', async () => {
    const { shouldSearch, SEARCH_THRESHOLD } = await import('./selectOptions')
    //: تاکسونومیِ واقعی ~۹۴ صنف دارد، پس همیشه از آستانه بالاتر است.
    expect(shouldSearch(94)).toBe(true)
    expect(SEARCH_THRESHOLD).toBeLessThan(94)
  })
})

describe('جست‌وجوی صنف', () => {
  const labels = GROUPS.flatMap((g) => g.trades.map((t) => t.label))

  it('«یدک» → لوازم یدکی خودرو', () => {
    expect(labels.filter((l) => textMatches(l, 'یدک'))).toEqual(['لوازم یدکی خودرو'])
  })

  it('«بستني» با یای عربی هم پیدا می‌شود', () => {
    expect(labels.filter((l) => textMatches(l, 'بستني'))).toEqual(['بستنی‌فروشی'])
  })
})

describe('برچسبِ صنف', () => {
  it('کلیدِ شناخته‌شده برچسبش را می‌دهد', () => {
    expect(labelOfTrade(GROUPS, 'icecream')).toBe('بستنی‌فروشی')
  })

  it('خالی و نامشخص، رشته‌ی خالی', () => {
    expect(labelOfTrade(GROUPS, null)).toBe('')
    expect(labelOfTrade(GROUPS, undefined)).toBe('')
  })

  it('کلیدِ ناشناخته خودش برمی‌گردد — مثلِ `trade_label` سمتِ سرور', () => {
    //: داده‌ی یک نسخه‌ی جلوتر نباید به رشته‌ی خالی تبدیل شود و گم شود.
    expect(labelOfTrade(GROUPS, 'from_newer_release')).toBe('from_newer_release')
  })
})
