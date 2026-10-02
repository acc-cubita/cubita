// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { TransactionUnitPicker } from './TransactionUnitPicker'
import { fetchItemUnits, fetchItemConversionRules, previewItemQuantity,
  type ItemUnitRecord, type QuantityConversionSnapshot } from '../api'

vi.mock('../api', () => ({ fetchItemUnits: vi.fn(), fetchItemConversionRules: vi.fn(), previewItemQuantity: vi.fn() }))
const members: ItemUnitRecord[] = [
  { unit_id: 'piece', unit_name: 'عدد', is_base: true, purchase_allowed: true, sale_allowed: true,
    inventory_allowed: true, production_allowed: true, decimal_allowed: true, is_active: true },
  { unit_id: 'carton', unit_name: 'کارتن', is_base: false, purchase_allowed: true, sale_allowed: false,
    inventory_allowed: true, production_allowed: true, decimal_allowed: true, is_active: true },
]
const result: QuantityConversionSnapshot = { source_qty: '1', source_unit_id: 'piece', target_qty: '0.33333334',
  target_unit_id: 'piece', target_unit_name: 'عدد', numerator: '1', denominator: '3', path: [] }
let container: HTMLDivElement
let root: Root
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  vi.useFakeTimers(); vi.clearAllMocks()
  vi.mocked(fetchItemUnits).mockResolvedValue(members)
  vi.mocked(fetchItemConversionRules).mockResolvedValue([])
  vi.mocked(previewItemQuantity).mockResolvedValue(result)
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.useRealTimers() })

it('filters units by transaction context and uses the server quantity without recalculation', async () => {
  const changed = vi.fn()
  await act(async () => root.render(createElement(TransactionUnitPicker, { token: 'test', itemId: 'item',
    qty: '1234567890123456.12345678', context: 'sale', onChange: changed })))
  expect([...container.querySelectorAll('option')].map((o) => o.value)).toEqual(['piece'])
  await act(async () => vi.advanceTimersByTimeAsync(250))
  expect(previewItemQuantity).toHaveBeenCalledWith('test', 'item', { qty: '1234567890123456.12345678',
    unit_id: 'piece', context: 'sale', observations: [] })
  expect(container.textContent).toContain('۰.۳۳۳۳۳۳۳۴')
  expect(changed).toHaveBeenCalledWith({ baseQtyPreview: '0.33333334' })
})

it('passes measured ratios as decimal strings', async () => {
  const observations = [{ rule_id: 'variable', from_qty: '36.12345678', to_qty: '150.87654321' }]
  await act(async () => root.render(createElement(TransactionUnitPicker, { token: 'test', itemId: 'item',
    qty: '2.00000001', unitId: 'carton', observations, context: 'purchase', onChange: vi.fn() })))
  await act(async () => vi.advanceTimersByTimeAsync(250))
  expect(previewItemQuantity).toHaveBeenCalledWith('test', 'item', { qty: '2.00000001', unit_id: 'carton',
    context: 'purchase', observations })
})

it('ignores a stale preview when the entered quantity changes', async () => {
  let finish!: (value: QuantityConversionSnapshot) => void
  vi.mocked(previewItemQuantity).mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
  const changed = vi.fn()
  const render = (qty: string) => act(async () => root.render(createElement(TransactionUnitPicker, {
    token: 'test', itemId: 'item', qty, context: 'sale', onChange: changed })))
  await render('1'); await act(async () => vi.advanceTimersByTimeAsync(250))
  await render('2')
  await act(async () => finish({ ...result, target_qty: '999' }))
  expect(changed).not.toHaveBeenCalled()
  await act(async () => vi.advanceTimersByTimeAsync(250))
  expect(changed).toHaveBeenCalledWith({ baseQtyPreview: '0.33333334' })
  expect(container.textContent).not.toContain('۹۹۹')
})
