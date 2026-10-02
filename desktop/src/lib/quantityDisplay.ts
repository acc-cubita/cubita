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
