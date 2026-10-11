/** Sum entered quantities only within the same unit, without float conversion. */
export function quantityTotals(rows: { qty: string; unitKey: string; unitName: string }[]) {
  const groups = new Map<string, { quantity: bigint; unitName: string }>()
  for (const row of rows) {
    const match = /^(\d+)(?:\.(\d{0,8}))?$/.exec(row.qty.trim())
    if (!match) continue
    const quantity = BigInt(match[1]) * 100000000n + BigInt((match[2] ?? '').padEnd(8, '0'))
    if (quantity === 0n) continue
    const group = groups.get(row.unitKey) ?? { quantity: 0n, unitName: row.unitName }
    group.quantity += quantity
    groups.set(row.unitKey, group)
  }
  return [...groups].map(([unitKey, group]) => {
    const fraction = (group.quantity % 100000000n).toString().padStart(8, '0').replace(/0+$/, '')
    return { unitKey, unitName: group.unitName,
      qty: `${group.quantity / 100000000n}${fraction ? `.${fraction}` : ''}` }
  })
}
/** Increment the entered quantity without passing through a binary float. */
export function stepQuantity(qty: string, delta: 1 | -1): string {
  const match = /^(\d+)(?:\.(\d{0,8}))?$/.exec(qty.trim())
  if (!match) return qty
  const scale = 100000000n
  const value = BigInt(match[1]) * scale + BigInt((match[2] ?? '').padEnd(8, '0')) + BigInt(delta) * scale
  if (value <= 0n) return '0'
  const fraction = (value % scale).toString().padStart(8, '0').replace(/0+$/, '')
  return `${value / scale}${fraction ? `.${fraction}` : ''}`
}

/** Exact canonical remainder for pre-filling a server quantity, without conversion. */
export function remainingQuantity(total: string, used: string): string {
  const scaled = (value: string) => {
    const match = /^(\d+)(?:\.(\d{0,8}))?$/.exec(value.trim())
    if (!match) throw new Error('مقدار نامعتبر است')
    return BigInt(match[1]) * 100000000n + BigInt((match[2] ?? '').padEnd(8, '0'))
  }
  const value = scaled(total) - scaled(used)
  if (value <= 0n) return '0'
  const fraction = (value % 100000000n).toString().padStart(8, '0').replace(/0+$/, '')
  return `${value / 100000000n}${fraction ? `.${fraction}` : ''}`
}
