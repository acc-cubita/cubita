import { describe, expect, it } from 'vitest'
import CASES from './margin_cases.json'
import {
  effectiveConsumerPrice,
  effectiveUnitCost,
  grossProfit,
  marginPercent,
  markupPercent,
  netPurchasePrice,
  orderAnalysis,
  percentToAmount,
  profitPerPack,
} from './margins'

/**
 * **همان پرونده‌ای که `backend/tests/test_margins.py` می‌خواند.**
 *
 * پرونده این‌جا نشسته و نه کنارِ تست‌های پایتون، چون تایپ‌اسکریپت اجازه‌ی خواندنِ
 * فایل از بیرونِ `src` را نمی‌دهد (نه ایمپورت، نه `node:fs` بی `@types/node`)
 * ولی پایتون هیچ محدودیتی ندارد. یک پرونده می‌ماند؛ فقط جهتِ خواندن عوض شد.
 *
 * `margins.ts` و `app/margins.py` یک منطق را دو بار پیاده کرده‌اند، چون §۲۶
 * محاسبه‌ی زنده می‌خواهد. دو نسخه یعنی دو جا برای واگرایی؛ راهِ بستنش این است
 * که هیچ‌کدام صاحبِ حقیقت نباشد و هر دو از یک پرونده بخوانند. اگر یکی عوض شود
 * و دیگری نه، همین‌جا لو می‌رود.
 */

/** مقایسه‌ای که `null` را می‌فهمد و اعشارِ بلند را تحمل می‌کند. */
function same(got: number | null, expected: number | null): boolean {
  if (expected === null) return got === null
  if (got === null) return false
  return Math.abs(got - expected) < 1e-7
}

describe('خالصِ خرید (§۲۳)', () => {
  for (const c of CASES.net_purchase_price) {
    it(c.name, () => {
      expect(same(netPurchasePrice(c.list_price, c.discount), c.expected)).toBe(true)
    })
  }
})

describe('تخفیفِ درصدی به مبلغ (§۲۴)', () => {
  for (const c of CASES.percent_to_amount) {
    it(c.name, () => {
      expect(same(percentToAmount(c.list_price, c.percent), c.expected)).toBe(true)
    })
  }
})

describe('سودِ ناخالص (§۲۱)', () => {
  for (const c of CASES.gross_profit) {
    it(c.name, () => {
      expect(same(grossProfit(c.consumer_price, c.net_cost), c.expected)).toBe(true)
    })
  }
})

describe('مارک‌آپ (§۲۲)', () => {
  for (const c of CASES.markup_percent) {
    it(c.name, () => {
      expect(same(markupPercent(c.consumer_price, c.net_cost), c.expected)).toBe(true)
    })
  }
})

describe('مارجین (§۲۲)', () => {
  for (const c of CASES.margin_percent) {
    it(c.name, () => {
      expect(same(marginPercent(c.consumer_price, c.net_cost), c.expected)).toBe(true)
    })
  }
})

describe('بهای واقعی با اشانتیون (§۲۵)', () => {
  for (const c of CASES.effective_unit_cost) {
    it(c.name, () => {
      expect(same(effectiveUnitCost(c.total_paid, c.total_received), c.expected)).toBe(true)
    })
  }
})

describe('سودِ هر کارتن (§۲۷)', () => {
  for (const c of CASES.profit_per_pack) {
    it(c.name, () => {
      expect(same(profitPerPack(c.unit_profit, c.units_per_pack), c.expected)).toBe(true)
    })
  }
})

describe('قیمتِ مؤثرِ مصرف‌کننده (§۱۹)', () => {
  for (const c of CASES.effective_consumer_price) {
    it(c.name, () => {
      expect(same(effectiveConsumerPrice(c.batch_price, c.product_price), c.expected)).toBe(true)
    })
  }
})

describe('تحلیلِ سفارش (§۲۶)', () => {
  for (const c of CASES.order_analysis) {
    it(c.name, () => {
      const got = orderAnalysis(c.input)
      for (const [key, expected] of Object.entries(c.expected)) {
        expect(key in got, `کلیدِ «${key}» نیامد`).toBe(true)
        expect(same(got[key], expected as number), `${key}: ${got[key]}`).toBe(true)
      }
    })
  }
})

describe('آنچه قابلِ محاسبه نیست، اصلاً نمی‌آید (§۲۶)', () => {
  it('کلیدِ بی‌داده نه صفر می‌شود نه خط تیره', () => {
    const out = orderAnalysis({ qty: 5, list_price: 1000 })
    expect('potential_gross_profit' in out).toBe(false)
    expect('markup_percent' in out).toBe(false)
    expect('profit_per_pack' in out).toBe(false)
    expect('bonus_quantity' in out).toBe(false)
  })

  it('مارک‌آپ و مارجین یک عدد نیستند', () => {
    expect(markupPercent(450000, 300000)).toBe(50)
    expect(marginPercent(450000, 300000)).toBe(33.3)
  })
})
