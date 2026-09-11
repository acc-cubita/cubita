import { apiGet, apiGetAll } from './client'
import type { Item, Warehouse } from './types'

// فاکتورِ فروش — همان قراردادِ دسکتاپ/وب (POST /api/sales-invoices)، مجوزِ invoices.

export const fetchWarehouses = () => apiGet<Warehouse[]>('/api/warehouses')
export const fetchItems = () => apiGetAll<Item>('/api/items')
