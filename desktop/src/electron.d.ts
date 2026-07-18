export interface AccountCache {
  id: string
  code: string
  name: string
  type: string
  is_group: number
  parent_id: string | null
}

export interface WarehouseCache {
  id: string
  code: string
  name: string
}

export interface ItemCache {
  id: string
  sku: string
  name: string
  unit: string
  sales_price: string
  is_service: number
}

export interface BankAccountCache {
  id: string
  name: string
  bank_name: string
}

export interface OutboxEntry {
  local_id: string
  payload: string
  created_at: string
  synced: number
  server_id: string | null
  server_number: number | null
  sync_error: string | null
}

export interface CubitaBridge {
  setAuthToken: (token: string | null) => Promise<void>
  pullAll: () => Promise<void>
  pushOutbox: () => Promise<{ pushed: number; failed: number }>
  queueJournalEntry: (payload: unknown) => Promise<string>
  listOutbox: () => Promise<OutboxEntry[]>
  queueSalesInvoice: (payload: unknown) => Promise<string>
  listSalesInvoiceOutbox: () => Promise<OutboxEntry[]>
  queueCheck: (payload: unknown) => Promise<string>
  listCheckOutbox: () => Promise<OutboxEntry[]>
  queuePurchaseInvoice: (payload: unknown) => Promise<string>
  listPurchaseInvoiceOutbox: () => Promise<OutboxEntry[]>
  listCachedAccounts: () => Promise<AccountCache[]>
  listCachedWarehouses: () => Promise<WarehouseCache[]>
  listCachedItems: () => Promise<ItemCache[]>
  listCachedBankAccounts: () => Promise<BankAccountCache[]>
}

export interface WindowControlsBridge {
  minimize: () => Promise<void>
  toggleMaximize: () => Promise<void>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
  onMaximizedChanged: (cb: (maximized: boolean) => void) => () => void
}

declare global {
  interface Window {
    cubita: CubitaBridge
    windowControls: WindowControlsBridge
  }
}
