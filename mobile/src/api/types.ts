// بازتابِ شکلِ DTOهای بک‌اند (منبعِ حقیقت: backend/app/schemas). عمداً کپیِ کد نیست،
// فقط تایپ‌های موردنیازِ اپ.

export interface TokenOut {
  access_token: string
  token_type: string
  // در M1 بک‌اند رفرش‌توکن هم می‌دهد؛ فعلاً اختیاری.
  refresh_token?: string
}

/** پاسخِ GET /api/auth/me — منطبق بر MeOut. */
export interface Me {
  id: string
  name: string
  email: string
  phone: string | null
  phone_verified: boolean
  email_verified: boolean
  role_key: string
  role_name: string
  permissions: Record<string, string[]>
  tenant_id: string
  tenant_name: string
  is_platform_admin: boolean
  is_super_admin: boolean
  tenant_kind: 'standard' | 'distributor' | 'retailer'
  is_trial: boolean
  trial_days_left: number | null
  trial_expired: boolean
  locked_features: string[]
}

/** پوششِ صفحه‌بندیِ keyset — منطبق بر Page[T]. */
export interface Page<T> {
  items: T[]
  next_cursor: string | null
}

export const isOwner = (me: Me): boolean => Boolean(me.permissions['*'])

// ── گزارش‌ها و شاخص‌ها (اعدادِ مالی به‌صورتِ رشته می‌آیند تا دقت حفظ شود) ──────

/** GET /api/sales-invoices/summary */
export interface SalesSummary {
  invoice_count: number
  total_net: string
  total_tax: string
  total_with_tax: string
  total_cost: string
  gross_profit: string
  margin_pct: string
  last_30_with_tax: string
  avg_invoice: string
}

export interface DashboardMonth {
  jy: number
  jm: number
  sales: string
  purchases: string
}
export interface DashboardItem {
  item_id: string
  name: string
  qty: string
  revenue: string
}
export interface DashboardCustomer {
  contact_id: string
  name: string
  total: string
}
/** GET /api/reports/dashboard?months=N */
export interface SalesDashboard {
  months: number
  monthly: DashboardMonth[]
  top_items: DashboardItem[]
  top_customers: DashboardCustomer[]
}

export interface AlertItem {
  category: 'check' | 'receivable' | 'credit' | 'recurring' | 'calendar' | 'stock' | string
  severity: 'danger' | 'warning' | 'info' | string
  title: string
  detail: string
  alert_date: string | null
  amount: string | null
  ref_id: string | null
}
/** GET /api/alerts */
export interface Alerts {
  as_of: string
  total: number
  counts: Record<string, number>
  items: AlertItem[]
}

export interface AccountBalance {
  account_id: string
  account_code: string
  account_name: string
  balance: string
}
/** GET /api/reports/income-statement */
export interface IncomeStatement {
  date_from: string | null
  date_to: string | null
  income: AccountBalance[]
  expenses: AccountBalance[]
  total_income: string
  total_expenses: string
  net_profit: string
}
/** GET /api/reports/balance-sheet */
export interface BalanceSheet {
  as_of: string
  assets: AccountBalance[]
  liabilities: AccountBalance[]
  equity: AccountBalance[]
  total_assets: string
  total_liabilities: string
  total_equity: string
  current_period_profit: string
}

export interface AgingRow {
  contact_id: string
  contact_name: string
  current: string
  d31_60: string
  d61_90: string
  over_90: string
  total: string
}
/** GET /api/reports/aging?kind=receivable|payable */
export interface AgingReport {
  as_of: string
  kind: 'receivable' | 'payable' | string
  rows: AgingRow[]
  total_current: string
  total_31_60: string
  total_61_90: string
  total_over_90: string
  grand_total: string
}

export interface InventoryRow {
  item_id: string
  sku: string
  name: string
  unit: string
  category: string
  qty_on_hand: string
  unit_cost: string
  stock_value: string
}
/** GET /api/reports/inventory */
export interface InventoryReport {
  as_of: string | null
  rows: InventoryRow[]
  total_value: string
  item_count: number
}
