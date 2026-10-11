import { expect, it } from 'vitest'
import { quantityTotals, remainingQuantity, stepQuantity } from './quantityDisplay'

it('preserves eight decimals in large production remainders', () => {
  expect(remainingQuantity('9999999999999999.12345678', '9999999999999998.12345677')).toBe('1.00000001')
  expect(remainingQuantity('0.3', '0.1')).toBe('0.2')
  expect(remainingQuantity('1', '2')).toBe('0')
  expect(() => remainingQuantity('1.000000001', '0')).toThrow()
})

it('steps POS quantities without losing the entered fraction', () => {
  expect(stepQuantity('9999999999999998.12345678', 1)).toBe('9999999999999999.12345678')
  expect(stepQuantity('2.00000001', -1)).toBe('1.00000001')
  expect(stepQuantity('0.5', -1)).toBe('0')
  expect(stepQuantity('0.000000001', 1)).toBe('0.000000001')
})

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
