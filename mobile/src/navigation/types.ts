// پارامترهای استک‌ها — منبعِ واحدِ تایپِ ناوبری.
export type HomeStackParams = {
  Dashboard: undefined
  Alerts: undefined
  Treasury: { type: 'receipt' | 'payment'; pickedContact?: { id: string; name: string } }
  ContactPicker: undefined
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
