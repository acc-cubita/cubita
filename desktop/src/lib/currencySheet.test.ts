/**
 * منطقِ برگه‌های «ارزها» و «نرخ برابری»: ترتیبِ زمانیِ نرخ‌ها، درصدِ تغییر، آخرین نرخ، اعتبار و پیش‌نویس.
 */
import { describe, expect, it } from 'vitest'

import type { ExchangeRate } from '../api'
import {
  blankCurrency,
  blankRate,
  currencyIsBlank,
  currencyProblem,
  editedRate,
  latestRates,
  parseCurrencyDraft,
  pendingCount,
  rateChanges,
  rateIsBlank,
  rateProblem,
  sortRates,
  takenCodes,
  withTrailingBlank,
} from './currencySheet'

const rate = (id: string, code: string, date: string, v: number): ExchangeRate => ({ id, currency_code: code, rate_date: date, rate: String(v) })

describe('نرخ‌ها — ترتیب، تغییر، آخرین', () => {
  const rows = [rate('c', 'USD', '2026-09-03', 630000), rate('a', 'USD', '2026-09-01', 600000), rate('b', 'EUR', '2026-09-01', 700000), rate('d', 'EUR', '2026-09-02', 693000)]

  it('ترتیبِ زمانی (قدیمی بالا)، هم‌روزها به کد', () => {
    expect(sortRates(rows).map((r) => r.id)).toEqual(['b', 'a', 'd', 'c'])
  })

  it('درصدِ تغییر نسبت به نرخِ قبلیِ همان ارز؛ اولینِ هر ارز null', () => {
    const ch = rateChanges(sortRates(rows))
    expect(ch.get('a')).toBeNull()
    expect(ch.get('b')).toBeNull()
    expect(ch.get('c')).toBeCloseTo(5, 6)
    expect(ch.get('d')).toBeCloseTo(-1, 6)
  })

  it('آخرین نرخِ هر ارز', () => {
    const l = latestRates(rows)
    expect(l.get('USD')!.id).toBe('c')
    expect(l.get('EUR')!.id).toBe('d')
  })
})

describe('اعتبار', () => {
  it('ارزِ تازه: کد و نام لازم، کدِ تکراری نه (بی‌توجه به بزرگ/کوچکی)', () => {
    const taken = new Set(['USD'])
    expect(currencyProblem({ ...blankCurrency('k') }, taken)).toBe('کد و نامِ ارز را وارد کنید.')
    expect(currencyProblem({ ...blankCurrency('k'), name: 'یورو' }, taken)).toBe('کدِ ارز را وارد کنید.')
    expect(currencyProblem({ ...blankCurrency('k'), code: 'usd', name: 'دلار' }, taken)).toBe('ارزِ USD از قبل هست.')
    expect(currencyProblem({ ...blankCurrency('k'), code: 'eur', name: 'یورو' }, taken)).toBeNull()
  })

  it('کدهای گرفته: ثبت‌شده‌ها و تازه‌های دیگر، نه خودِ همین ردیف', () => {
    const t = takenCodes([{ id: '1', code: 'USD', name: 'دلار', symbol: '$' }], [{ ...blankCurrency('a'), code: 'EUR' }, { ...blankCurrency('b'), code: 'AED' }], 'b')
    expect([...t].sort()).toEqual(['EUR', 'USD'])
  })

  it('نرخ: ارز، تاریخ و عددِ مثبت', () => {
    expect(rateProblem({ currency_code: '', rate_date: '2026-09-01', rate: '5' })).toBe('ارز را انتخاب کنید.')
    expect(rateProblem({ currency_code: 'USD', rate_date: '', rate: '5' })).toBe('تاریخ را انتخاب کنید.')
    expect(rateProblem({ currency_code: 'USD', rate_date: '2026-09-01', rate: '0' })).toBe('نرخ باید بزرگ‌تر از صفر باشد.')
    expect(rateProblem({ currency_code: 'USD', rate_date: '2026-09-01', rate: '612000' })).toBeNull()
  })

  it('ویرایشِ نرخِ ثبت‌شده فقط اگر واقعاً عوض شده', () => {
    const r = rate('a', 'USD', '2026-09-01', 600000)
    expect(editedRate(r, undefined)).toBeNull()
    expect(editedRate(r, '')).toBeNull()
    expect(editedRate(r, '600000')).toBeNull()
    expect(editedRate(r, '610000')).toBe('610000')
  })
})

describe('ردیفِ خالیِ ته، شمارش و پیش‌نویس', () => {
  it('تاریخِ پیش‌فرض محتوا نیست؛ همیشه یک خالیِ ته', () => {
    expect(rateIsBlank(blankRate('k', '2026-09-25'))).toBe(true)
    const out = withTrailingBlank([{ ...blankRate('a', 'x'), currency_code: 'USD' }], rateIsBlank, () => blankRate('n', 'x'))
    expect(out.map((r) => r.key)).toEqual(['a', 'n'])
    expect(withTrailingBlank([blankCurrency('a'), blankCurrency('b')], currencyIsBlank, () => blankCurrency('z')).map((c) => c.key)).toEqual(['a'])
  })

  it('شمارشِ تغییرهای ذخیره‌نشده', () => {
    const rates = [rate('a', 'USD', '2026-09-01', 600000)]
    const d = {
      currencies: [{ ...blankCurrency('c1'), code: 'EUR' }, blankCurrency('c2')],
      rates: [{ ...blankRate('r1', '2026-09-25'), rate: '5' }, blankRate('r2', '2026-09-25')],
      edits: { a: '610000', gone: '1' },
    }
    expect(pendingCount(d, rates)).toEqual({ fresh: 2, edited: 1 })
  })

  it('پیش‌نویسِ خراب یعنی هیچ؛ ردیفِ بدشکل کنار می‌رود', () => {
    expect(parseCurrencyDraft(null)).toBeNull()
    expect(parseCurrencyDraft('{')).toBeNull()
    expect(parseCurrencyDraft(JSON.stringify({ currencies: [{ key: 1 }], rates: [], edits: null }))).toEqual({ currencies: [], rates: [], edits: {} })
  })
})
