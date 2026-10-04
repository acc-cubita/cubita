import type { SalesQuantityTotal } from '../api'
import { toFaDigits } from './jalali'

type QuantityKey = 'sold_qty' | 'returned_qty' | 'issued_qty' | 'unissued_qty'

/** The server groups quantities by unit; presentation never sums unlike units. */
export function salesQuantityText(row: {
  quantity_totals?: SalesQuantityTotal[]
  unit_name?: string
  sold_qty?: string | null
  returned_qty?: string | null
  issued_qty?: string | null
  unissued_qty?: string | null
}, key: QuantityKey): string {
  if (row.quantity_totals?.length) {
    return row.quantity_totals.map((group) => `${toFaDigits(group[key] ?? "—")} ${group.unit_name}`).join('، ')
  }
  const value = row[key]
  if (value == null) return '—'
  return `${toFaDigits(value)}${row.unit_name ? ` ${row.unit_name}` : ''}`
}
