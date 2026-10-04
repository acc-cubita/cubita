import { expect, it } from 'vitest'
import { salesQuantityText } from './salesQuantityDisplay'

it('shows separate unit totals without rounding entered fractions', () => {
  const row = { sold_qty: null, quantity_totals: [
    { unit_key: 'piece', unit_name: 'عدد', sold_qty: '9999999999999999.00000001', returned_qty: '0', issued_qty: '0', unissued_qty: '0' },
    { unit_key: 'meter', unit_name: 'متر', sold_qty: '2.12345678', returned_qty: '0', issued_qty: '0', unissued_qty: '0' },
  ] }
  expect(salesQuantityText(row, 'sold_qty')).toBe('۹۹۹۹۹۹۹۹۹۹۹۹۹۹۹۹.۰۰۰۰۰۰۰۱ عدد، ۲.۱۲۳۴۵۶۷۸ متر')
})

it('preserves the sign and does not render an unknown scalar as zero', () => {
  expect(salesQuantityText({ unissued_qty: '-0.00000001', unit_name: 'متر' }, 'unissued_qty')).toBe('-۰.۰۰۰۰۰۰۰۱ متر')
  expect(salesQuantityText({ sold_qty: null }, 'sold_qty')).toBe('—')
})
