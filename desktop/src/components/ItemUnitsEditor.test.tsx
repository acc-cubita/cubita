// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ItemUnitsEditor } from './ItemUnitsEditor'
import { fetchItemUnits, fetchItemConversionRules, saveItemConversionRule, previewItemQuantity,
  type ItemRecord, type ItemUnitRecord, type UnitRecord } from '../api'

vi.mock('../api', () => ({ fetchItemUnits: vi.fn(), fetchItemConversionRules: vi.fn(),
  addItemUnit: vi.fn(), updateItemUnit: vi.fn(), saveItemConversionRule: vi.fn(),
  deactivateItemConversionRule: vi.fn(), previewItemQuantity: vi.fn() }))

const members: ItemUnitRecord[] = [
  { unit_id: 'piece', unit_name: 'عدد', is_base: true, purchase_allowed: true, sale_allowed: true,
    inventory_allowed: true, production_allowed: true, decimal_allowed: true, is_active: true },
  { unit_id: 'carton', unit_name: 'کارتن', is_base: false, purchase_allowed: true, sale_allowed: true,
    inventory_allowed: true, production_allowed: true, decimal_allowed: true, is_active: true },
]
let container: HTMLDivElement
let root: Root
beforeEach(async () => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  vi.clearAllMocks()
  vi.mocked(fetchItemUnits).mockResolvedValue(members)
  vi.mocked(fetchItemConversionRules).mockResolvedValue([])
  vi.mocked(saveItemConversionRule).mockResolvedValue({ id: 'rule', from_unit_id: 'carton', to_unit_id: 'piece', mode: 'fixed', factor: '24', version: 1, is_active: true })
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
  await act(async () => root.render(createElement(ItemUnitsEditor, {
    token: 'test', item: { id: 'item', name: 'کالای آزمون' } as ItemRecord,
    masterUnits: members.map(m => ({ id: m.unit_id, name: m.unit_name, is_active: true })) as UnitRecord[], onClose: vi.fn(),
  })))
})
afterEach(() => { act(() => root.unmount()); container.remove() })
async function select(element: HTMLSelectElement, value: string) {
  await act(async () => { element.value = value; element.dispatchEvent(new Event('change', { bubbles: true })) })
}
async function input(element: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
async function click(label: string) {
  const button = [...container.querySelectorAll('button')].find(b => b.textContent === label)
  expect(button).toBeDefined(); await act(async () => button!.click())
}
it('keeps a 30-digit factor exact from input to the API', async () => {
  const selects = container.querySelectorAll<HTMLFieldSetElement>('fieldset')[1].querySelectorAll('select')
  await select(selects[0], 'carton'); await select(selects[1], 'piece')
  const factor = '123456789012345678.123456789012'
  await input(container.querySelectorAll('fieldset')[1].querySelector('input')!, factor)
  await click('ثبت نسبت')
  expect(saveItemConversionRule).toHaveBeenCalledWith('test', 'item', { from_unit_id: 'carton', to_unit_id: 'piece', mode: 'fixed', factor }, undefined)
})
it('shows the server quantity, including its final rounding residual', async () => {
  vi.mocked(previewItemQuantity).mockResolvedValue({ source_qty: '1', source_unit_id: 'carton', target_qty: '0.33333334', target_unit_id: 'piece', numerator: '1', denominator: '3', path: [] })
  await select(container.querySelectorAll('fieldset')[2].querySelector('select')!, 'carton')
  await click('محاسبه')
  expect(previewItemQuantity).toHaveBeenCalledWith('test', 'item', { qty: '1', unit_id: 'carton', context: 'inventory' })
  expect(container.textContent).toContain('۰.۳۳۳۳۳۳۳۴')
})
it('keeps the entered factor available to repair after a cycle error', async () => {
  vi.mocked(saveItemConversionRule).mockRejectedValue(new Error('دو مسیر تبدیل با هم سازگار نیستند'))
  const fieldset = container.querySelectorAll('fieldset')[1]
  const selects = fieldset.querySelectorAll('select')
  await select(selects[0], 'carton'); await select(selects[1], 'piece'); await input(fieldset.querySelector('input')!, '2')
  await click('ثبت نسبت')
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('دو مسیر تبدیل با هم سازگار نیستند')
  expect(fieldset.querySelector('input')?.value).toBe('۲')
})
