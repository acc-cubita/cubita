import { describe, expect, it } from 'vitest'
import { exceedsQuantity, positiveQuantity, selectedReturnUnit } from './returnQuantity'

describe('historical return quantities', () => {
  it('compares large quantities without losing the last eight decimal places', () => {
    expect(exceedsQuantity('9999999999999999.00000002', '9999999999999999.00000001')).toBe(true)
    expect(exceedsQuantity('9999999999999999.00000001', '9999999999999999.00000001')).toBe(false)
    expect(positiveQuantity('0.00000001')).toBe(true)
  })
  it('rejects overprecision and invalid input instead of treating them as zero', () => {
    for (const qty of ['0.000000001', '-1', 'NaN', 'Infinity']) {
      expect(positiveQuantity(qty)).toBe(false)
      expect(exceedsQuantity(qty, '100')).toBe(true)
    }
    expect(exceedsQuantity('', '100')).toBe(false)
  })
  it('uses the frozen unit remaining and price even if the base amount differs', () => {
    const row = { remaining: '24', unit: 'عدد', unit_price: '100', return_unit_options: [
      {unit_id:'base', unit_name:'عدد', remaining:'24', unit_price:'100'},
      {unit_id:'carton', unit_name:'کارتن قدیم', remaining:'1', unit_price:'2400'},
    ] }
    expect(selectedReturnUnit(row, 'carton')).toEqual(row.return_unit_options[1])
    expect(selectedReturnUnit(row)).toEqual(row.return_unit_options[0])
    expect(selectedReturnUnit({...row,return_unit_options:[]}).remaining).toBe('24')
  })
})
