// پارامترهای استک‌ها — منبعِ واحدِ تایپِ ناوبری.
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
  Chat: { scope: 'connection' | 'order'; id: string; title: string }
}
