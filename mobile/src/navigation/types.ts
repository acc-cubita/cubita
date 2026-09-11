// پارامترهای استک‌ها — منبعِ واحدِ تایپِ ناوبری.
export type HomeStackParams = {
  Dashboard: undefined
  Alerts: undefined
  Treasury: { type: 'receipt' | 'payment'; pickedContact?: { id: string; name: string } }
  /** returnTo: به کدام صفحه برگردد (پیش‌فرض: خزانه). */
  ContactPicker: { returnTo?: 'Treasury' | 'NewInvoice' } | undefined
  Outbox: undefined
  NewInvoice: { pickedContact?: { id: string; name: string }; pickedItem?: { id: string; name: string; unit: string; sales_price: string } } | undefined
  ItemPicker: undefined
}

export type ReportsStackParams = {
  ReportsList: undefined
  IncomeStatement: undefined
  BalanceSheet: undefined
  Aging: { kind: 'receivable' | 'payable' }
  Inventory: undefined
}

export type ContactsStackParams = {
  ContactsList: undefined
  ContactDetail: { id: string; name: string }
}

export type MarketStackParams = {
  MarketHome: undefined
  Chat: { scope: 'connection' | 'order'; id: string; title?: string }
}

export type StockStackParams = {
  StockCounts: undefined
  StockCount: { id: string; title?: string }
  StockScan: { sessionId: string }
}
