import { apiGet } from './client'
import type {
  Alerts,
  AgingReport,
  BalanceSheet,
  IncomeStatement,
  InventoryReport,
  SalesDashboard,
  SalesSummary,
} from './types'

// fetcherهای گزارش‌ها و شاخص‌ها. همه GETِ ساده و اسکوپ‌شده به مستأجرِ توکن.

export const fetchSalesSummary = () => apiGet<SalesSummary>('/api/sales-invoices/summary')
export const fetchSalesDashboard = (months = 12) =>
  apiGet<SalesDashboard>(`/api/reports/dashboard?months=${months}`)
export const fetchAlerts = () => apiGet<Alerts>('/api/alerts')

export const fetchIncomeStatement = () => apiGet<IncomeStatement>('/api/reports/income-statement')
export const fetchBalanceSheet = () => apiGet<BalanceSheet>('/api/reports/balance-sheet')
export const fetchAging = (kind: 'receivable' | 'payable') =>
  apiGet<AgingReport>(`/api/reports/aging?kind=${kind}`)
export const fetchInventoryReport = () => apiGet<InventoryReport>('/api/reports/inventory')
