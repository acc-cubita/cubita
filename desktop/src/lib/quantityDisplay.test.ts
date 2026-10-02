import { expect, it } from 'vitest'
import { quantityTotals } from './quantityDisplay'

it('keeps separate unit totals and eight decimal places above float precision', () => {
  expect(quantityTotals([
    { qty: '9999999999999999.00000001', unitKey: 'piece', unitName: 'عدد' },
    { qty: '0.00000001', unitKey: 'piece', unitName: 'عدد' },
    { qty: '2.5', unitKey: 'meter', unitName: 'متر' },
  ])).toEqual([
    { qty: '9999999999999999.00000002', unitKey: 'piece', unitName: 'عدد' },
    { qty: '2.5', unitKey: 'meter', unitName: 'متر' },
  ])
})

it('does not round unsupported input into a displayed valid quantity', () => {
  expect(quantityTotals(['0.000000001', 'NaN', '-2', ''].map(qty => ({
    qty, unitKey: 'piece', unitName: 'عدد',
  })))).toEqual([])
})
