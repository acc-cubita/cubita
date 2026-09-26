import type { VatBreakdown, VatReport } from '../api'
import { jalaaliMonthLength, jalaliToIso } from './jalali'

/**
 * منطقِ خالصِ «مالیات بر ارزش افزوده» — بازه‌ی فصل، ردیف‌های برگه‌ی محاسبه و ترکیبِ پایه.
 *
 * برگه‌ی محاسبه مثلِ اظهارنامه است: بخشِ «مالیاتِ فروش» (فروش منهای برگشت) و بخشِ «اعتبارِ خرید» (خرید منهای برگشت)،
 * هر کدام با جمعِ خودش، و «مالیاتِ خالصِ فصل» = جمعِ اول − جمعِ دوم؛ همان فرمولِ `net_vat`ِ سرور
 * (`services/reports.py`). برگشت‌ها **منفی** نشان داده می‌شوند تا هر ستون از بالا به پایین جمع بخورد.
 */

/** بازه‌ی فصلِ شمسی — اظهارنامه فصلی است، نه سه‌ماهه‌ی میلادی. */
export function quarterRange(year: number, quarter: number): { from: string; to: string } {
  const startMonth = (quarter - 1) * 3 + 1
  const endMonth = startMonth + 2
  return {
    from: jalaliToIso(year, startMonth, 1),
    to: jalaliToIso(year, endMonth, jalaaliMonthLength(year, endMonth)),
  }
}

export type VatRow =
  | { kind: 'section'; label: string }
  | { kind: 'line' | 'subtotal'; label: string; net: number; vat: number }

const n = (v: string | number | null | undefined) => Number(v || 0)

export function vatRows(r: VatReport): VatRow[] {
  const salesNet = n(r.sales_net) - n(r.sales_returns_net)
  const salesVat = n(r.output_vat) - n(r.sales_returns_vat)
  const buyNet = n(r.purchase_net) - n(r.purchase_returns_net)
  const buyVat = n(r.input_vat) - n(r.purchase_returns_vat)
  return [
    { kind: 'section', label: 'مالیاتِ فروش' },
    { kind: 'line', label: 'فروش', net: n(r.sales_net), vat: n(r.output_vat) },
    { kind: 'line', label: 'برگشت از فروش', net: -n(r.sales_returns_net), vat: -n(r.sales_returns_vat) },
    { kind: 'subtotal', label: 'خالصِ مالیاتِ فروش', net: salesNet, vat: salesVat },
    { kind: 'section', label: 'اعتبارِ مالیاتیِ خرید' },
    { kind: 'line', label: 'خرید', net: n(r.purchase_net), vat: n(r.input_vat) },
    { kind: 'line', label: 'برگشت از خرید', net: -n(r.purchase_returns_net), vat: -n(r.purchase_returns_vat) },
    { kind: 'subtotal', label: 'خالصِ اعتبارِ خرید', net: buyNet, vat: buyVat },
  ]
}

/** مالیاتِ خالصِ فصل از سرور؛ مثبت پرداختنی، منفی استردادی (یا انتقال به فصلِ بعد). */
export function vatNet(r: VatReport): { amount: number; label: string } {
  const amount = n(r.net_vat)
  return { amount, label: amount > 0 ? 'قابلِ پرداخت' : amount < 0 ? 'قابلِ استرداد' : 'بی‌مالیات' }
}

export const BREAKDOWN_ROWS: [string, keyof VatBreakdown][] = [
  ['کالای مشمول', 'taxable_goods'],
  ['خدمتِ مشمول', 'taxable_services'],
  ['کالای معاف', 'exempt_goods'],
  ['خدمتِ معاف', 'exempt_services'],
]

/** جمعِ ستونِ فروش و خریدِ ترکیبِ پایه. */
export function breakdownTotals(r: VatReport): { sales: number; purchase: number } {
  return BREAKDOWN_ROWS.reduce(
    (t, [, key]) => ({ sales: t.sales + n(r.sales_breakdown[key]), purchase: t.purchase + n(r.purchase_breakdown[key]) }),
    { sales: 0, purchase: 0 },
  )
}

/** CSVِ برگه‌ی محاسبه: همان ردیف‌های روی صفحه، به‌اضافه‌ی سطرِ خالصِ فصل. */
export function vatCsv(r: VatReport): (string | number)[][] {
  const net = vatNet(r)
  return [
    ...vatRows(r).map((row) => (row.kind === 'section' ? [row.label, '', ''] : [row.label, row.net, row.vat])),
    ['مالیاتِ خالصِ فصل', '', net.amount],
  ]
}
