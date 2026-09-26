import { describe, expect, it } from 'vitest'

import type { VatReport } from '../api'
import { breakdownTotals, quarterRange, vatCsv, vatNet, vatRows } from './vatSheet'

const breakdown = (a: number, b: number, c: number, d: number) => ({
  taxable_goods: String(a),
  taxable_services: String(b),
  exempt_goods: String(c),
  exempt_services: String(d),
})

const report = (over: Partial<VatReport> = {}): VatReport => ({
  date_from: null,
  date_to: null,
  sales_net: '1000',
  output_vat: '100',
  sales_returns_net: '200',
  sales_returns_vat: '20',
  purchase_net: '500',
  input_vat: '50',
  purchase_returns_net: '100',
  purchase_returns_vat: '10',
  //: (۱۰۰ − ۲۰) − (۵۰ − ۱۰) = ۴۰ — همان فرمولِ سرور.
  net_vat: '40',
  sales_breakdown: breakdown(600, 300, 100, 0),
  purchase_breakdown: breakdown(400, 0, 0, 100),
  mixed_sales_invoices: [],
  mixed_purchase_invoices: [],
  ...over,
})

describe('quarterRange', () => {
  it('spans the Jalali quarter, including a 31-day and a leap Esfand end', () => {
    expect(quarterRange(1405, 1)).toEqual({ from: '2026-03-21', to: '2026-06-21' })
    const q4 = quarterRange(1403, 4)
    expect(q4.from).toBe('2024-12-21')
    //: ۱۴۰۳ کبیسه است: اسفند ۳۰ روزه.
    expect(q4.to).toBe('2025-03-20')
  })
})

describe('vatRows', () => {
  it('returns are negative so each section adds down to its subtotal', () => {
    const rows = vatRows(report())
    const lines = rows.filter((r) => r.kind === 'line') as { net: number; vat: number }[]
    const subs = rows.filter((r) => r.kind === 'subtotal') as { label: string; net: number; vat: number }[]
    expect(lines[0].vat + lines[1].vat).toBe(subs[0].vat)
    expect(lines[2].net + lines[3].net).toBe(subs[1].net)
    expect(subs.map((s) => [s.label, s.net, s.vat])).toEqual([
      ['خالصِ مالیاتِ فروش', 800, 80],
      ['خالصِ اعتبارِ خرید', 400, 40],
    ])
  })

  it('subtotals agree with the server net: sales − purchases', () => {
    const subs = vatRows(report()).filter((r) => r.kind === 'subtotal') as { vat: number }[]
    expect(subs[0].vat - subs[1].vat).toBe(vatNet(report()).amount)
  })
})

describe('vatNet', () => {
  it('names payable, refundable and zero', () => {
    expect(vatNet(report()).label).toBe('قابلِ پرداخت')
    expect(vatNet(report({ net_vat: '-5' }))).toEqual({ amount: -5, label: 'قابلِ استرداد' })
    expect(vatNet(report({ net_vat: '0' })).label).toBe('بی‌مالیات')
  })
})

describe('breakdownTotals / vatCsv', () => {
  it('sums the four base categories per side', () => {
    expect(breakdownTotals(report())).toEqual({ sales: 1000, purchase: 500 })
  })
  it('CSV carries the screen rows and the net line', () => {
    const csv = vatCsv(report())
    expect(csv[0]).toEqual(['مالیاتِ فروش', '', ''])
    expect(csv[2]).toEqual(['برگشت از فروش', -200, -20])
    expect(csv.at(-1)).toEqual(['مالیاتِ خالصِ فصل', '', 40])
  })
})
