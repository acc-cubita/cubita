// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { PosPage } from './PosPage'
import { createImmediateSalesInvoice, resolvePrice, type MeResponse } from '../api'

vi.mock('../api', () => ({
  fetchItemsLive: vi.fn().mockResolvedValue([{ id: 'item', sku: 'test', barcode: '123', name: 'کالا', unit: 'عدد', primary_unit_id: 'piece', sales_price: '100', is_active: true, is_service: false }]),
  fetchWarehousesLive: vi.fn().mockResolvedValue([{ id: 'warehouse', name: 'انبار' }]),
  fetchContacts: vi.fn().mockResolvedValue([]), fetchSaleTypes: vi.fn().mockResolvedValue([]),
  fetchStockLevels: vi.fn().mockResolvedValue([{ item_id: 'item', warehouse_id: 'warehouse', qty: '10' }]),
  newIdempotencyKey: vi.fn().mockReturnValue('idempotency'),
  resolvePrice: vi.fn(), createImmediateSalesInvoice: vi.fn().mockResolvedValue({ number: 1 }),
}))
vi.mock('../components/TransactionUnitPicker', async () => {
  const { useEffect, useRef } = await import('react')
  return { TransactionUnitPicker: ({ onChange, qty, unitId }: { onChange: (patch: object) => void; qty: string; unitId?: string }) => {
    const changed = useRef(onChange)
    changed.current = onChange
    useEffect(() => { changed.current({ baseQtyPreview: unitId === 'carton' ? '48' : qty }) }, [qty, unitId])
    return createElement('button', { type: 'button', 'data-unit': true, onClick: () => onChange({ unitId: 'carton', unitName: 'کارتن', baseQtyPreview: undefined, observations: [{ rule_id: 'measured', from_qty: '36.12345678', to_qty: '150.87654321' }] }) }, 'کارتن')
  } }
})
vi.mock('../components/ItemPicker', () => ({ ItemPicker: () => null }))
vi.mock('../components/CardPaymentDialog', () => ({ CardPaymentButton: () => null }))
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  vi.clearAllMocks()
  vi.mocked(resolvePrice).mockImplementation(async (_token, _item, ctx) => ctx?.unitId === 'carton' ? { unit_price: '2400' } as never : null)
  localStorage.setItem('pos_auto_print', '0')
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); localStorage.clear() })
async function renderAndScan() {
  await act(async () => root.render(createElement(PosPage, { token: 'test', me: { tenant_name: 'آزمون', name: 'صندوقدار' } as MeResponse })))
  const scan = container.querySelector('.pos-scan input') as HTMLInputElement
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(scan, '123')
    scan.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
  await act(async () => (container.querySelector('[data-unit]') as HTMLButtonElement).click())
}
it('submits entered unit, measured ratio and precise quantity; warns using base stock', async () => {
  await renderAndScan()
  const qty = container.querySelector('.pos-qty input') as HTMLInputElement
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(qty, '2.00000001')
    qty.dispatchEvent(new Event('input', { bubbles: true }))
  })
  expect(resolvePrice).toHaveBeenCalledWith('test', 'item', expect.objectContaining({ unitId: 'carton' }))
  expect(container.textContent).toContain('بیش از موجودی')
  await act(async () => (container.querySelector('.pos-checkout') as HTMLButtonElement).click())
  expect(createImmediateSalesInvoice).toHaveBeenCalledWith('test', expect.objectContaining({ lines: [{ item_id: 'item', qty: '2.00000001', unit_id: 'carton', unit_price: 2400, observations: [{ rule_id: 'measured', from_qty: '36.12345678', to_qty: '150.87654321' }] }] }), 'idempotency')
  expect(document.querySelector('.pos-receipt-print')?.textContent).toContain('۲.۰۰۰۰۰۰۰۱')
  expect(document.querySelector('.pos-receipt-print')?.textContent).toContain('کارتن')
})
it('requires an independent alternate-unit price when no price rule exists', async () => {
  vi.mocked(resolvePrice).mockResolvedValue(null)
  await renderAndScan()
  expect((container.querySelector('.pos-price') as HTMLInputElement).value).toBe('')
  expect((container.querySelector('.pos-checkout') as HTMLButtonElement).disabled).toBe(true)
  expect(createImmediateSalesInvoice).not.toHaveBeenCalled()
})
