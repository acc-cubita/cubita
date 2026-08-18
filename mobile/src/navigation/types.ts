// پارامترهای استکِ گزارش‌ها — منبعِ واحدِ تایپِ ناوبری.
export type ReportsStackParams = {
  ReportsList: undefined
  IncomeStatement: undefined
  BalanceSheet: undefined
  Aging: { kind: 'receivable' | 'payable' }
  Inventory: undefined
}
