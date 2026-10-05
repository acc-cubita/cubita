import type { HistoricalReturnUnit, ReturnableLine } from '../api'
import { quantityAtoms } from './batchAllocation'

export function positiveQuantity(qty: string | number): boolean {
  try { return quantityAtoms(qty || '0') > 0n } catch { return false }
}
export function exceedsQuantity(qty: string | number, maximum: string): boolean {
  try { return quantityAtoms(qty || '0') > quantityAtoms(maximum) } catch { return true }
}
export function selectedReturnUnit(row: Pick<ReturnableLine, 'remaining' | 'unit' | 'unit_price' | 'return_unit_options'>,
  unitId?: string): HistoricalReturnUnit {
  return row.return_unit_options?.find((option) => option.unit_id === unitId)
    ?? row.return_unit_options?.[0]
    ?? { unit_id: '', unit_name: row.unit, remaining: row.remaining, unit_price: row.unit_price }
}
