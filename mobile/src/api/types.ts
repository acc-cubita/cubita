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

/** مجوزِ منبع/کنش را می‌سنجد (مالک با «*» همه را دارد). */
export const hasPermission = (me: Me, resource: string, action: string): boolean =>
  Boolean(me.permissions['*']) || Boolean(me.permissions[resource]?.includes(action))

// ── خزانه: دریافت/پرداخت ─────────────────────────────────────────────────

/** GET /api/bank-accounts (فهرستِ ساده). */
export interface BankAccount {
  id: string
  name: string
}

/** بدنه‌ی POST /api/treasury/{receipts|payments} — منطبق بر TreasuryTransactionIn. */
export interface TreasuryTxnIn {
  transaction_date: string // YYYY-MM-DD
  contact_id: string
  amount: string
  method: 'cash' | 'bank'
  bank_account_id?: string | null
  description?: string
}

/** پاسخِ تراکنشِ خزانه — منطبق بر TreasuryTransactionOut (فقط فیلدهای موردنیاز). */
export interface TreasuryTxn {
  id: string
  type: string
  contact_name: string
  amount: string
  method: string
}

// ── فاکتورِ فروش ──────────────────────────────────────────────────────────

/** GET /api/warehouses */
export interface Warehouse {
  id: string
  code: string
  name: string
  is_active: boolean
}

/** GET /api/items (صفحه‌بندیِ keyset) — فقط فیلدهای موردنیازِ فاکتور. */
export interface Item {
  id: string
  sku: string
  name: string
  unit: string
  sales_price: string
  is_active: boolean
  barcode: string | null
}

/** ردیفِ فاکتور — منطبق بر SalesInvoiceLineIn. */
export interface SalesInvoiceLineIn {
  item_id: string
  qty: string
  unit_price: string
  discount?: string
  description?: string
}

/** بدنه‌ی POST /api/sales-invoices — منطبق بر SalesInvoiceIn. */
export interface SalesInvoiceIn {
  invoice_date: string // YYYY-MM-DD
  warehouse_id: string
  contact_id?: string | null
  description?: string
  lines: SalesInvoiceLineIn[]
  tax_rate?: string
  invoice_discount?: string
}

/** پاسخِ فاکتور — فقط فیلدهای موردنیازِ اپ (منطبق بر SalesInvoiceOut). */
export interface SalesInvoiceOut {
  id: string
  number: number | null
  invoice_date: string
  /** جمعِ خالصِ ردیف‌ها پس از تخفیف (پیش از مالیات). */
  total_amount: string
  tax_amount: string
  rounding: string
}

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

// ── اشخاص (طرف‌حساب‌ها) ────────────────────────────────────────────────────

/** آیتمِ GET /api/contacts (Page[ContactOut]) */
export interface Contact {
  id: string
  name: string
  type: string // customer | supplier | both
  phone: string | null
  email: string | null
  address: string
  is_active: boolean
  credit_limit: string
  entity_type: string
  national_id: string | null
}

/** GET /api/contacts/{id}/credit */
export interface CreditStatus {
  contact_id: string
  name: string
  credit_limit: string
  outstanding: string // ماندهٔ طلبِ ما از این شخص
  available: string
  over_limit: boolean
}

export interface ContactStatementLine {
  txn_date: string
  kind: string // sales_invoice | sales_return | purchase_invoice | purchase_return | receipt | payment
  number: number | null
  description: string
  debit: string
  credit: string
  balance: string // ماندهٔ در حال اجرا؛ مثبت = شخص به ما بدهکار است
}

/** GET /api/reports/contact-statement/{id} */
export interface ContactStatement {
  contact_id: string
  contact_name: string
  date_from: string | null
  date_to: string | null
  opening_balance: string
  lines: ContactStatementLine[]
  total_debit: string
  total_credit: string
  closing_balance: string
}

// ── بازارِ عمده‌فروشی + گفتگو ───────────────────────────────────────────────

/** ConnectionOut — اتصالِ پخش‌کننده↔فروشگاه. */
export interface MpConnection {
  id: string
  distributor_tenant_id: string
  retailer_tenant_id: string
  distributor_name: string
  retailer_name: string
  status: string // pending | approved | rejected | blocked
  requested_by: string
  unread_count: number
  last_message_at: string | null
  last_message_preview: string
}

export interface MpOrderLine {
  listing_id: string | null
  title: string
  unit_price: string
  qty: string
  line_total: string
  image: string | null
}

/** OrderOut — سفارشِ عمده. */
export interface MpOrder {
  id: string
  unread_count: number
  last_message_at: string | null
  last_message_preview: string
  distributor_tenant_id: string
  retailer_tenant_id: string
  distributor_name: string
  retailer_name: string
  order_number: number
  status: string // pending | confirmed | rejected | ...
  settlement_mode: string
  payment_status: string
  note: string
  subtotal: string
  total: string
  cash_amount: string
  lines: MpOrderLine[]
}

/** MessageOut — یک پیامِ چت. */
export interface MpMessage {
  id: string
  sender_role: string // distributor | retailer
  sender_user_id: string | null
  body: string
  created_at: string
}

/** MessagesPage — my_role مشخص می‌کند کدام حباب «مالِ من» است. */
export interface MpMessagesPage {
  my_role: string
  messages: MpMessage[]
}

// ── انبارگردانی ────────────────────────────────────────────────────────────

/** یک ردیفِ جلسه‌ی انبارگردانی — منطبق بر StockCountLineOut. */
export interface StockCountLine {
  id: string
  item_id: string
  item_name: string
  item_sku: string
  unit: string
  system_qty: string
  counted_qty: string
  unit_cost: string
  variance: string
  variance_value: string
}

/** سرِ جلسه با ردیف‌ها — منطبق بر StockCountSessionOut. */
export interface StockCountSession {
  id: string
  warehouse_id: string
  warehouse_name: string
  count_date: string
  status: 'open' | 'posted' | 'cancelled'
  notes: string
  journal_entry_id: string | null
  posted_at: string | null
  created_at: string | null
  line_count: number
  variance_line_count: number
  total_variance_value: string
  lines: StockCountLine[]
}

/** ردیفِ فهرستِ جلسه‌ها — منطبق بر StockCountSummaryOut (بدونِ lines). */
export interface StockCountSummary {
  id: string
  warehouse_id: string
  warehouse_name: string
  count_date: string
  status: 'open' | 'posted' | 'cancelled'
  notes: string
  posted_at: string | null
  created_at: string | null
  line_count: number
}
