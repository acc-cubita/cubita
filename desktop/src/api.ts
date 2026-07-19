const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? 'https://acc.ipnetcity.ir' : 'http://localhost:8000')

export interface MeResponse {
  id: string
  name: string
  email: string
  role_key: string
  role_name: string
  permissions: Record<string, string[]>
  tenant_id: string
  tenant_name: string
}

/** آیا این نقش اجازه‌ی یک اکشن روی یک ماژول را دارد؟ همان منطق سمت سرور.
 *
 * سرور همچنان مرجع است و هر درخواست را خودش می‌سنجد؛ این فقط برای پنهان کردن
 * دکمه‌ای است که به ۴۰۳ می‌خورد. اگر جایی این را به‌جای بررسی سرور بگیرند، مجوز
 * به کلاینت منتقل می‌شود — که یعنی اصلاً مجوزی وجود ندارد. */
export function can(me: MeResponse, module: string, action: string): boolean {
  for (const key of [module, '*']) {
    const actions = me.permissions[key]
    if (actions && (actions.includes(action) || actions.includes('*'))) return true
  }
  return false
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(body.detail ?? 'ورود ناموفق بود')
  }
  const data = await res.json()
  return data.access_token as string
}

export async function fetchMe(token: string): Promise<MeResponse> {
  const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('دریافت اطلاعات کاربر ناموفق بود')
  return res.json()
}

export interface TrialBalanceRow {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  total_debit: string
  total_credit: string
  balance: string
}

export interface AccountBalance {
  account_id: string
  account_code: string
  account_name: string
  balance: string
}

export interface IncomeStatement {
  date_from: string | null
  date_to: string | null
  income: AccountBalance[]
  expenses: AccountBalance[]
  total_income: string
  total_expenses: string
  net_profit: string
}

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

async function authedGet<T>(token: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`دریافت اطلاعات ناموفق بود (${res.status})`)
  return res.json()
}

/** پوشش پاسخ اندپوینت‌های لیستی صفحه‌بندی‌شده در بک‌اند. */
export interface Page<T> {
  items: T[]
  next_cursor: string | null
}

/** یک صفحه می‌گیرد. وقتی UI صفحه‌بندی واقعی گرفت (اسکرول بی‌نهایت یا دکمه‌ی صفحه) از این استفاده کند. */
export async function authedGetPage<T>(
  token: string,
  path: string,
  opts: { limit?: number; cursor?: string | null } = {},
): Promise<Page<T>> {
  const qs = new URLSearchParams()
  if (opts.limit != null) qs.set('limit', String(opts.limit))
  if (opts.cursor) qs.set('cursor', opts.cursor)
  const sep = path.includes('?') ? '&' : '?'
  const suffix = qs.toString() ? `${sep}${qs}` : ''
  return authedGet<Page<T>>(token, `${path}${suffix}`)
}

const MAX_PAGES = 200

/** همه‌ی صفحه‌ها را دنبال می‌کند و آرایه‌ی مسطح برمی‌گرداند.
 *
 * این پل موقت است: بک‌اند حالا صفحه‌بندی می‌کند ولی UI هنوز همه‌ی ردیف‌ها را یکجا
 * می‌خواهد. سود اصلی همین حالا گرفته می‌شود — سرور دیگر کل جدول را در یک کوئری با
 * selectinload نمی‌خواند — ولی تا وقتی صفحه‌ها در UI پیاده نشوند، کلاینت هنوز کل
 * داده را می‌گیرد. سقف MAX_PAGES جلوی حلقه‌ی بی‌پایان روی کرسر خراب را می‌گیرد.
 */
async function authedGetAll<T>(token: string, path: string): Promise<T[]> {
  const all: T[] = []
  let cursor: string | null = null
  for (let i = 0; i < MAX_PAGES; i++) {
    const page: Page<T> = await authedGetPage<T>(token, path, { limit: 200, cursor })
    all.push(...page.items)
    if (!page.next_cursor) return all
    cursor = page.next_cursor
  }
  throw new Error(`دریافت لیست ${path} از ${MAX_PAGES} صفحه فراتر رفت`)
}

async function authedSend<T>(token: string, method: 'POST' | 'PATCH' | 'PUT', path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `درخواست ناموفق بود (${res.status})`)
  }
  return res.json()
}

export const fetchTrialBalance = (token: string) =>
  authedGet<TrialBalanceRow[]>(token, '/api/reports/trial-balance')

export const fetchIncomeStatement = (token: string) =>
  authedGet<IncomeStatement>(token, '/api/reports/income-statement')

export const fetchBalanceSheet = (token: string) =>
  authedGet<BalanceSheet>(token, '/api/reports/balance-sheet')

export interface GeneralLedgerLine {
  entry_id: string
  entry_number: number | null
  entry_date: string
  description: string
  debit: string
  credit: string
  balance: string
}

export interface GeneralLedger {
  account_id: string
  account_code: string
  account_name: string
  opening_balance: string
  lines: GeneralLedgerLine[]
  closing_balance: string
}

export const fetchGeneralLedger = (token: string, accountId: string) =>
  authedGet<GeneralLedger>(token, `/api/reports/general-ledger/${accountId}`)

export interface JournalEntryLine {
  id: string
  account_id: string
  debit: string
  credit: string
  description: string
}

export interface JournalEntryRecord {
  id: string
  number: number | null
  entry_date: string
  description: string
  source_type: string
  lines: JournalEntryLine[]
}

export const fetchJournalEntries = (token: string) =>
  authedGetAll<JournalEntryRecord>(token, '/api/journal-entries')

export interface CheckRecord {
  id: string
  type: 'receivable' | 'payable'
  number: string
  bank_name: string
  amount: string
  issue_date: string
  due_date: string
  status: string
  description: string
  contact_id: string | null
  bank_account_id: string | null
}

export const fetchChecks = (token: string) => authedGetAll<CheckRecord>(token, '/api/checks')

export const updateCheckStatus = (token: string, checkId: string, status: string, bankAccountId?: string) =>
  authedSend<CheckRecord>(token, 'PATCH', `/api/checks/${checkId}/status`, {
    status,
    bank_account_id: bankAccountId ?? null,
  })

export interface PettyCashRecord {
  id: string
  type: 'charge' | 'expense'
  transaction_date: string
  amount: string
  description: string
}

export const fetchPettyCashTransactions = (token: string) => authedGetAll<PettyCashRecord>(token, '/api/petty-cash')

export const fetchPettyCashBalance = (token: string) =>
  authedGet<{ balance: string }>(token, '/api/petty-cash/balance')

export const createPettyCashCharge = (
  token: string,
  data: { transaction_date: string; amount: number; source_account_id: string; description: string },
) => authedSend<PettyCashRecord>(token, 'POST', '/api/petty-cash/charge', data)

export const createPettyCashExpense = (
  token: string,
  data: { transaction_date: string; amount: number; expense_account_id: string; description: string },
) => authedSend<PettyCashRecord>(token, 'POST', '/api/petty-cash/expense', data)

export const createBankTransaction = (
  token: string,
  data: {
    bank_account_id: string
    transaction_date: string
    amount: number
    counter_account_id: string
    description: string
  },
) => authedSend<unknown>(token, 'POST', '/api/bank-transactions', data)

export interface BankStatementLineRecord {
  id: string
  bank_account_id: string
  line_date: string
  amount: string
  description: string
  matched_transaction_id: string | null
}

export const fetchStatementLines = (token: string, bankAccountId: string) =>
  authedGet<BankStatementLineRecord[]>(token, `/api/bank-accounts/${bankAccountId}/statement-lines`)

export const importStatementLines = (
  token: string,
  bankAccountId: string,
  lines: { line_date: string; amount: number; description: string }[],
) => authedSend<BankStatementLineRecord[]>(token, 'POST', `/api/bank-accounts/${bankAccountId}/statement-lines`, { lines })

export const autoMatchStatement = (token: string, bankAccountId: string) =>
  authedSend<{ matched_count: number }>(token, 'POST', `/api/bank-accounts/${bankAccountId}/auto-match`, {})

export const matchStatementLine = (token: string, lineId: string, bankTransactionId: string) =>
  authedSend<BankStatementLineRecord>(token, 'POST', `/api/bank-statement-lines/${lineId}/match`, {
    bank_transaction_id: bankTransactionId,
  })

export const unmatchStatementLine = (token: string, lineId: string) =>
  authedSend<BankStatementLineRecord>(token, 'POST', `/api/bank-statement-lines/${lineId}/unmatch`, {})

export interface ReconciliationSummary {
  statement_total: string
  matched_count: number
  unmatched_statement_lines: BankStatementLineRecord[]
  unreconciled_system_transactions: {
    id: string
    bank_account_id: string
    transaction_date: string
    amount: string
    description: string
    is_reconciled: boolean
    source_type: string
  }[]
}

export const fetchReconciliationSummary = (token: string, bankAccountId: string) =>
  authedGet<ReconciliationSummary>(token, `/api/bank-accounts/${bankAccountId}/reconciliation-summary`)

export interface FiscalPeriodCloseRecord {
  id: string
  closing_date: string
  net_profit: string
  notes: string
  journal_entry_id: string
}

export const fetchPeriodCloses = (token: string) => authedGet<FiscalPeriodCloseRecord[]>(token, '/api/fiscal-period-closes')

export const createPeriodClose = (token: string, data: { closing_date: string; notes: string }) =>
  authedSend<FiscalPeriodCloseRecord>(token, 'POST', '/api/fiscal-period-closes', data)

export interface EmployeeRecord {
  id: string
  first_name: string
  last_name: string
  national_id: string
  phone: string | null
  email: string | null
  bank_account_number: string
  hire_date: string
  termination_date: string | null
  is_active: boolean
}

export const fetchEmployees = (token: string) => authedGet<EmployeeRecord[]>(token, '/api/employees')

export const createEmployee = (
  token: string,
  data: {
    first_name: string
    last_name: string
    national_id: string
    phone: string
    email: string
    bank_account_number: string
    hire_date: string
  },
) => authedSend<EmployeeRecord>(token, 'POST', '/api/employees', data)

export const createSalaryContract = (
  token: string,
  data: {
    employee_id: string
    effective_from: string
    base_salary: number
    housing_allowance: number
    food_allowance: number
    other_allowance: number
  },
) => authedSend<unknown>(token, 'POST', '/api/salary-contracts', data)

export interface PayrollPeriodRecord {
  id: string
  year: number
  month: number
  status: 'draft' | 'finalized'
}

export const fetchPayrollPeriods = (token: string) => authedGet<PayrollPeriodRecord[]>(token, '/api/payroll-periods')

export const createPayrollPeriod = (token: string, data: { year: number; month: number }) =>
  authedSend<PayrollPeriodRecord>(token, 'POST', '/api/payroll-periods', data)

export const upsertAttendance = (
  token: string,
  data: { employee_id: string; period_id: string; worked_days: number; absent_days: number; overtime_hours: number },
) => authedSend<unknown>(token, 'PUT', '/api/attendance', data)

export const fetchAttendance = (token: string, periodId: string) =>
  authedGet<{ employee_id: string; worked_days: string; absent_days: string; overtime_hours: string }[]>(
    token,
    `/api/attendance?period_id=${periodId}`,
  )

export interface PayslipRecord {
  id: string
  number: number | null
  employee_id: string
  period_id: string
  base_salary: string
  allowances_total: string
  overtime_pay: string
  gross_pay: string
  insurance_employee_share: string
  insurance_employer_share: string
  taxable_pay: string
  tax_amount: string
  net_pay: string
}

export const fetchPayslips = (token: string, periodId: string) =>
  authedGetAll<PayslipRecord>(token, `/api/payslips?period_id=${periodId}`)

export const generatePayslips = (token: string, periodId: string) =>
  authedSend<PayslipRecord[]>(token, 'POST', `/api/payroll-periods/${periodId}/generate-payslips`, {})

export async function downloadInsuranceListCsv(token: string, periodId: string): Promise<{ filename: string; blob: Blob }> {
  const res = await fetch(`${API_BASE_URL}/api/payroll-periods/${periodId}/insurance-list.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `درخواست ناموفق بود (${res.status})`)
  }
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^"]+)"?/.exec(disposition)
  const filename = match?.[1] ?? 'insurance-list.csv'
  const blob = await res.blob()
  return { filename, blob }
}

export interface ItemRecord {
  id: string
  sku: string
  name: string
  is_service: boolean
  is_active: boolean
  storefront_product_id: number | null
}

export const fetchItemsLive = (token: string) => authedGetAll<ItemRecord>(token, '/api/items')

export const updateItemStorefrontMapping = (token: string, itemId: string, storefrontProductId: number | null) =>
  authedSend<ItemRecord>(token, 'PATCH', `/api/items/${itemId}`, { storefront_product_id: storefrontProductId })

export interface SyncResult {
  orders_imported: number[]
  orders_skipped: { order_id: number | null; reason: string }[]
  items_pushed: string[]
  items_push_failed: { sku: string; error: string }[]
}

export const triggerStorefrontSync = (token: string) =>
  authedSend<SyncResult>(token, 'POST', '/api/integration/sync', {})

export interface StockAdjustmentRecord {
  id: string
  item_id: string
  warehouse_id: string
  qty_diff: string
  unit_cost: string
  reason: string
  adjustment_date: string
}

export const fetchStockAdjustments = (token: string) =>
  authedGetAll<StockAdjustmentRecord>(token, '/api/stock-adjustments')

export const createStockAdjustment = (
  token: string,
  data: { item_id: string; warehouse_id: string; qty_diff: number; reason: string; adjustment_date: string },
) => authedSend<StockAdjustmentRecord>(token, 'POST', '/api/stock-adjustments', data)

export interface SalesQuotationLine {
  id: string
  item_id: string
  qty: string
  unit_price: string
  description: string
}

export interface SalesQuotationRecord {
  id: string
  number: number | null
  quotation_date: string
  valid_until: string | null
  warehouse_id: string
  contact_id: string | null
  description: string
  status: 'draft' | 'sent' | 'accepted' | 'rejected' | 'converted'
  total_amount: string
  converted_invoice_id: string | null
  lines: SalesQuotationLine[]
}

export const fetchSalesQuotations = (token: string) =>
  authedGetAll<SalesQuotationRecord>(token, '/api/sales-quotations')

export const createSalesQuotation = (
  token: string,
  data: {
    quotation_date: string
    valid_until: string | null
    warehouse_id: string
    description: string
    lines: { item_id: string; qty: number; unit_price: number; description: string }[]
  },
) => authedSend<SalesQuotationRecord>(token, 'POST', '/api/sales-quotations', data)

export const updateQuotationStatus = (token: string, quotationId: string, status: string) =>
  authedSend<SalesQuotationRecord>(token, 'PATCH', `/api/sales-quotations/${quotationId}/status`, { status })

export const convertQuotationToInvoice = (token: string, quotationId: string) =>
  authedSend<unknown>(token, 'POST', `/api/sales-quotations/${quotationId}/convert`, {})

export interface InvoiceLineRecord {
  id: string
  item_id: string
  qty: string
  description: string
}

export interface SalesInvoiceRecord {
  id: string
  number: number | null
  invoice_date: string
  warehouse_id: string
  contact_id: string | null
  description: string
  total_amount: string
  total_cost: string
  voided_at: string | null
  void_reason: string
  lines: (InvoiceLineRecord & { unit_price: string; unit_cost: string })[]
}

export const fetchSalesInvoices = (token: string) => authedGetAll<SalesInvoiceRecord>(token, '/api/sales-invoices')

export interface PurchaseInvoiceRecord {
  id: string
  number: number | null
  invoice_date: string
  warehouse_id: string
  contact_id: string | null
  description: string
  total_amount: string
  voided_at: string | null
  void_reason: string
  lines: (InvoiceLineRecord & { unit_cost: string })[]
}

export const fetchPurchaseInvoices = (token: string) => authedGetAll<PurchaseInvoiceRecord>(token, '/api/purchase-invoices')

export interface SalesReturnRecord {
  id: string
  number: number | null
  return_date: string
  sales_invoice_id: string
  description: string
  total_amount: string
  total_cost: string
  lines: { id: string; item_id: string; qty: string; unit_price: string; unit_cost: string; description: string }[]
}

export const fetchSalesReturns = (token: string) => authedGetAll<SalesReturnRecord>(token, '/api/sales-returns')

export const createSalesReturn = (
  token: string,
  data: { return_date: string; sales_invoice_id: string; description: string; lines: { item_id: string; qty: number }[] },
) => authedSend<SalesReturnRecord>(token, 'POST', '/api/sales-returns', data)

export interface PurchaseReturnRecord {
  id: string
  number: number | null
  return_date: string
  purchase_invoice_id: string
  description: string
  total_amount: string
  lines: { id: string; item_id: string; qty: string; unit_cost: string; description: string }[]
}

export const fetchPurchaseReturns = (token: string) => authedGetAll<PurchaseReturnRecord>(token, '/api/purchase-returns')

export const createPurchaseReturn = (
  token: string,
  data: { return_date: string; purchase_invoice_id: string; description: string; lines: { item_id: string; qty: number }[] },
) => authedSend<PurchaseReturnRecord>(token, 'POST', '/api/purchase-returns', data)

export interface StockTransferRecord {
  id: string
  number: number | null
  transfer_date: string
  from_warehouse_id: string
  to_warehouse_id: string
  description: string
  lines: { id: string; item_id: string; qty: string }[]
}

export const fetchStockTransfers = (token: string) => authedGetAll<StockTransferRecord>(token, '/api/stock-transfers')

export const createStockTransfer = (
  token: string,
  data: {
    transfer_date: string
    from_warehouse_id: string
    to_warehouse_id: string
    description: string
    lines: { item_id: string; qty: number }[]
  },
) => authedSend<StockTransferRecord>(token, 'POST', '/api/stock-transfers', data)

export interface StockLevel {
  item_id: string
  item_sku: string
  item_name: string
  warehouse_id: string
  warehouse_name: string
  qty: string
}

export const fetchStockLevels = (token: string) => authedGet<StockLevel[]>(token, '/api/stock')

// --- مسیر «وب مستقیم» (بدون Electron): برای اجرای همین اپ در مرورگر (دموی وب/ورود وب)، جای صف آفلاین و
// کش محلی SQLite، همه‌چیز مستقیم و زنده از API خوانده/نوشته می‌شود. شکل خروجی هرکدام با Cache-type متناظر در
// electron.d.ts سازگار نگه داشته شده تا کامپوننت‌های صفحات بدون شاخه‌بندی جدا، هم در Electron و هم در وب کار کنند.

interface AccountLiveOut {
  id: string
  code: string
  name: string
  type: string
  is_group: boolean
  parent_id: string | null
}

export const fetchAccountsLive = async (token: string) => {
  const rows = await authedGet<AccountLiveOut[]>(token, '/api/accounts')
  return rows.map((a) => ({ ...a, is_group: a.is_group ? 1 : 0 }))
}

interface WarehouseLiveOut {
  id: string
  code: string
  name: string
  is_active: boolean
}

export const fetchWarehousesLive = async (token: string) => {
  const rows = await authedGet<WarehouseLiveOut[]>(token, '/api/warehouses')
  return rows.map((w) => ({ id: w.id, code: w.code, name: w.name }))
}

interface BankAccountLiveOut {
  id: string
  name: string
  bank_name: string
}

export const fetchBankAccountsLive = async (token: string) => {
  const rows = await authedGet<BankAccountLiveOut[]>(token, '/api/bank-accounts')
  return rows.map((b) => ({ id: b.id, name: b.name, bank_name: b.bank_name }))
}

interface ItemWithPricingLiveOut {
  id: string
  sku: string
  name: string
  unit: string
  sales_price: string
  is_service: boolean
}

export const fetchItemsWithPricingLive = async (token: string) => {
  const rows = await authedGetAll<ItemWithPricingLiveOut>(token, '/api/items')
  return rows.map((i) => ({ ...i, is_service: i.is_service ? 1 : 0 }))
}

export const createJournalEntryDirect = (
  token: string,
  data: { entry_date: string; description: string; lines: { account_id: string; debit: number; credit: number }[] },
) => authedSend<unknown>(token, 'POST', '/api/journal-entries', data)

export const createSalesInvoiceDirect = (
  token: string,
  data: {
    invoice_date: string
    warehouse_id: string
    lines: { item_id: string; qty: number; unit_price: number }[]
  },
) => authedSend<unknown>(token, 'POST', '/api/sales-invoices', data)

export const createPurchaseInvoiceDirect = (
  token: string,
  data: {
    invoice_date: string
    warehouse_id: string
    lines: { item_id: string; qty: number; unit_cost: number }[]
  },
) => authedSend<unknown>(token, 'POST', '/api/purchase-invoices', data)

export const createCheckDirect = (
  token: string,
  data: {
    type: string
    number: string
    bank_name: string
    amount: number
    issue_date: string
    due_date: string
    description: string
  },
) => authedSend<unknown>(token, 'POST', '/api/checks', data)

export interface PurchaseRecord {
  id: string
  plan_id: string
  plan_name: string
  customer_name: string
  customer_email: string
  customer_phone: string
  business_name: string
  amount_toman: string
  status: string
  zarinpal_ref_id: string | null
  admin_notes: string
  created_at: string
}

export const fetchAdminPurchases = (token: string) => authedGet<PurchaseRecord[]>(token, '/api/admin/purchases')

export const fulfillPurchase = (token: string, purchaseId: string, adminNotes: string) =>
  authedSend<PurchaseRecord>(token, 'POST', `/api/admin/purchases/${purchaseId}/fulfill`, { admin_notes: adminNotes })

export interface ContactRecord {
  id: string
  name: string
  type: 'customer' | 'supplier' | 'both'
  phone: string | null
  email: string | null
  address: string
  tax_id: string | null
  is_active: boolean
}

export interface ContactIn {
  name: string
  type: string
  phone: string | null
  email: string | null
  address: string
  tax_id: string | null
}

export const fetchContacts = (token: string) => authedGetAll<ContactRecord>(token, '/api/contacts')

export const createContact = (token: string, data: ContactIn) =>
  authedSend<ContactRecord>(token, 'POST', '/api/contacts', data)

export const updateContact = (token: string, contactId: string, data: ContactIn) =>
  authedSend<ContactRecord>(token, 'PATCH', `/api/contacts/${contactId}`, data)

export interface TreasuryTransactionRecord {
  id: string
  type: 'receipt' | 'payment'
  transaction_date: string
  contact_id: string
  contact_name: string
  amount: string
  method: 'cash' | 'bank'
  bank_account_id: string | null
  description: string
  journal_entry_id: string
}

export interface TreasuryTransactionIn {
  transaction_date: string
  contact_id: string
  amount: number
  method: 'cash' | 'bank'
  bank_account_id: string | null
  description: string
}

export const fetchTreasuryTransactions = (token: string) =>
  authedGetAll<TreasuryTransactionRecord>(token, '/api/treasury')

export const createTreasuryReceipt = (token: string, data: TreasuryTransactionIn) =>
  authedSend<TreasuryTransactionRecord>(token, 'POST', '/api/treasury/receipts', data)

export const createTreasuryPayment = (token: string, data: TreasuryTransactionIn) =>
  authedSend<TreasuryTransactionRecord>(token, 'POST', '/api/treasury/payments', data)

// --- کاربران کسب‌وکار، بازیابی و تغییر رمز ----------------------------------------

export interface Member {
  id: string
  user_id: string
  name: string
  email: string
  role_key: string
  role_name: string
  status: 'active' | 'invited' | 'disabled'
  is_me: boolean
}

export interface MemberList {
  members: Member[]
  seats: { used: number; limit: number | null }
}

export const fetchMembers = (token: string) => authedGet<MemberList>(token, '/api/members')

export const inviteMember = (token: string, data: { email: string; name: string; role_key: string }) =>
  authedSend<{ member: Member; email_sent: boolean }>(token, 'POST', '/api/members/invite', data)

export const changeMemberRole = (token: string, membershipId: string, roleKey: string) =>
  authedSend<Member>(token, 'PATCH', `/api/members/${membershipId}/role`, { role_key: roleKey })

export const setMemberActive = (token: string, membershipId: string, active: boolean) =>
  authedSend<Member>(token, 'PATCH', `/api/members/${membershipId}/status`, { active })

export const changePassword = (token: string, currentPassword: string, newPassword: string) =>
  authedSend<{ access_token: string }>(token, 'POST', '/api/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })

/** درخواست‌های بدون احراز هویت. پاسخ خطا همان detail بک‌اند است تا پیام فارسی حفظ شود. */
async function anonPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `درخواست ناموفق بود (${res.status})`)
  }
  return res.json()
}

export const requestPasswordReset = (email: string) =>
  anonPost<{ detail: string }>('/api/auth/forgot-password', { email })

export const resetPassword = (token: string, password: string) =>
  anonPost<{ access_token: string }>('/api/auth/reset-password', { token, password })

export const acceptInvite = (token: string, password: string, name?: string) =>
  anonPost<{ access_token: string }>('/api/auth/accept-invite', { token, password, name: name || null })


// --- ابطال و چاپ فاکتور ------------------------------------------------------------

export interface VoidResult {
  reversal_entry_id: string
  reversal_entry_number: number | null
}

export const voidSalesInvoice = (token: string, invoiceId: string, reason: string) =>
  authedSend<VoidResult>(token, 'POST', `/api/sales-invoices/${invoiceId}/void`, { reason })

export const voidPurchaseInvoice = (token: string, invoiceId: string, reason: string) =>
  authedSend<VoidResult>(token, 'POST', `/api/purchase-invoices/${invoiceId}/void`, { reason })

/** نمای چاپی را در پنجره‌ی تازه باز می‌کند.
 *
 * چون اندپوینت احراز هویت می‌خواهد، نمی‌شود صرفاً URL را باز کرد — توکن در هدر
 * می‌رود نه در آدرس. عمداً هم در آدرس گذاشته نمی‌شود: توکن در نوار آدرس، در
 * تاریخچه‌ی مرورگر و در لاگ هر پراکسی میانی می‌ماند.
 */
export async function openInvoicePrintView(token: string, path: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`دریافت نمای چاپی ناموفق بود (${res.status})`)
  const html = await res.text()

  const win = window.open('', '_blank')
  if (!win) throw new Error('مرورگر پنجره‌ی تازه را مسدود کرد؛ اجازه‌ی باز کردن پنجره را بدهید.')
  win.document.write(html)
  win.document.close()
}

export const printSalesInvoice = (token: string, invoiceId: string) =>
  openInvoicePrintView(token, `/api/sales-invoices/${invoiceId}/print`)

export const printPurchaseInvoice = (token: string, invoiceId: string) =>
  openInvoicePrintView(token, `/api/purchase-invoices/${invoiceId}/print`)
