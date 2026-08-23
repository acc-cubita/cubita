import { apiGet, apiGetAll, apiPost } from './client'
import type { Item, SalesInvoiceIn, SalesInvoiceOut, Warehouse } from './types'

// فاکتورِ فروش — همان قراردادِ دسکتاپ/وب (POST /api/sales-invoices)، مجوزِ invoices.

export const fetchWarehouses = () => apiGet<Warehouse[]>('/api/warehouses')
export const fetchItems = () => apiGetAll<Item>('/api/items')

export const createSalesInvoice = (body: SalesInvoiceIn) =>
  apiPost<SalesInvoiceOut>('/api/sales-invoices', body)
