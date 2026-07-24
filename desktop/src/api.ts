// build همیشه VITE_API_URL را صریح می‌دهد، پس این fallback در عمل کد مرده است —
// ولی همان دامنه‌ی قدیمی‌ای بود که در electron/main.ts هم یک‌بار جا مانده بود.
// یکسان نگه داشتنش ارزان‌تر از دوباره پیدا کردنش است.
const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? 'https://acc.cubita.ir' : 'http://localhost:8000')

export interface MeResponse {
  id: string
  name: string
  email: string
  role_key: string
  role_name: string
  permissions: Record<string, string[]>
  tenant_id: string
  tenant_name: string
  //: کاربر روی allowlist کنترل‌پنل فروش خودِ کوبیتاست، نه صاحب یک کسب‌وکار عادی.
  is_platform_admin: boolean
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

/** کلید یکتاسازی برای عملیاتی که سند مالی می‌سازد.
 *
 * سرور با همین کلید تشخیص می‌دهد که یک درخواست، تکرارِ درخواست قبلی است. سه حالتی
 * که بدون آن دو سند مالی ساخته می‌شود و هیچ‌کدام تقصیر کاربر نیست: دوبار کلیک،
 * گم شدن پاسخ در شبکه، و retry مرورگر.
 *
 * کلید باید به *عملیات* گره بخورد نه به هر تلاش شبکه‌ای — یعنی اگر کاربر بعد از
 * خطا دوباره دکمه را بزند، همان کلید برود. پس فراخواننده آن را یک‌بار می‌سازد و
 * برای همان فرم نگه می‌دارد.
 */
export const newIdempotencyKey = (): string =>
  (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`)

async function authedSend<T>(
  token: string,
  method: 'POST' | 'PATCH' | 'PUT',
  path: string,
  body: unknown,
  idempotencyKey?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `درخواست ناموفق بود (${res.status})`)
  }
  return res.json()
}

async function authedDelete(token: string, path: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  // ۲۰۴ بدنه ندارد، پس res.ok کافی است؛ فقط خطاها به پیام فارسی تبدیل می‌شوند.
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `حذف ناموفق بود (${res.status})`)
  }
}

export interface SubscriptionStatus {
  status: 'active' | 'grace' | 'expired' | 'cancelled' | 'none'
  expires_at: string | null
  days_left: number | null
  can_write: boolean
  should_warn: boolean
}

export const fetchSubscription = (token: string) => authedGet<SubscriptionStatus>(token, '/api/subscription')

export const fetchTrialBalance = (token: string) =>
  authedGet<TrialBalanceRow[]>(token, '/api/reports/trial-balance')

export const fetchIncomeStatement = (token: string) =>
  authedGet<IncomeStatement>(token, '/api/reports/income-statement')

export const fetchBalanceSheet = (token: string) =>
  authedGet<BalanceSheet>(token, '/api/reports/balance-sheet')

export interface VatReport {
  date_from: string | null
  date_to: string | null
  sales_net: string
  output_vat: string
  purchase_net: string
  input_vat: string
  net_vat: string
  sales_returns_net: string
  sales_returns_vat: string
  purchase_returns_net: string
  purchase_returns_vat: string
}

export const fetchVatReport = (token: string, dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<VatReport>(token, `/api/reports/vat${suffix}`)
}

export interface CashFlowLine {
  account_id: string
  account_code: string
  account_name: string
  amount: string
}

export interface CashFlow {
  date_from: string | null
  date_to: string | null
  opening_cash: string
  operating: CashFlowLine[]
  investing: CashFlowLine[]
  financing: CashFlowLine[]
  net_operating: string
  net_investing: string
  net_financing: string
  net_change: string
  closing_cash: string
}

export const fetchCashFlow = (token: string, dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<CashFlow>(token, `/api/reports/cash-flow${suffix}`)
}

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
  /** تخفیفِ ردیف به مبلغ. خالصِ ردیف = تعداد×قیمت − تخفیف. */
  discount: string
  description: string
}

export interface SalesInvoiceRecord {
  id: string
  number: number | null
  invoice_date: string
  warehouse_id: string
  contact_id: string | null
  description: string
  /** خالصِ پس از تخفیف، بدون مالیات. */
  total_amount: string
  total_discount: string
  total_cost: string
  tax_rate: string
  tax_amount: string
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
  total_discount: string
  tax_rate: string
  tax_amount: string
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
  tax_rate: string
  tax_amount: string
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
  tax_rate: string
  tax_amount: string
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
  data: {
    entry_date: string
    description: string
    cost_center_id?: string | null
    lines: { account_id: string; debit: number; credit: number }[]
  },
) => authedSend<unknown>(token, 'POST', '/api/journal-entries', data)

export const createSalesInvoiceDirect = (
  token: string,
  data: {
    invoice_date: string
    warehouse_id: string
    tax_rate?: number
    cost_center_id?: string | null
    contact_id?: string | null
    lines: { item_id: string; qty: number; unit_price: number; discount?: number }[]
  },
  idempotencyKey?: string,
) => authedSend<unknown>(token, 'POST', '/api/sales-invoices', data, idempotencyKey)

export const createPurchaseInvoiceDirect = (
  token: string,
  data: {
    invoice_date: string
    warehouse_id: string
    tax_rate?: number
    cost_center_id?: string | null
    lines: { item_id: string; qty: number; unit_cost: number; discount?: number }[]
  },
  idempotencyKey?: string,
) => authedSend<unknown>(token, 'POST', '/api/purchase-invoices', data, idempotencyKey)

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
  credit_limit: string
}

export interface ContactIn {
  name: string
  type: string
  phone: string | null
  email: string | null
  address: string
  tax_id: string | null
  credit_limit: number
}

export const fetchContacts = (token: string) => authedGetAll<ContactRecord>(token, '/api/contacts')

export const createContact = (token: string, data: ContactIn) =>
  authedSend<ContactRecord>(token, 'POST', '/api/contacts', data)

export const updateContact = (token: string, contactId: string, data: ContactIn) =>
  authedSend<ContactRecord>(token, 'PATCH', `/api/contacts/${contactId}`, data)

export interface CreditStatus {
  contact_id: string
  name: string
  credit_limit: string
  outstanding: string
  available: string
  over_limit: boolean
}

export const fetchCreditStatus = (token: string, contactId: string) =>
  authedGet<CreditStatus>(token, `/api/contacts/${contactId}/credit`)

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

// --- تقویم و یادآوری ---------------------------------------------------------------
// مثل اشخاص، مسیرِ مستقیمِ API است و در هر دو پلتفرم (Electron و وب) یکسان کار می‌کند.

export type CalendarCategory = 'reminder' | 'meeting' | 'payment' | 'tax' | 'task' | 'other'

export interface CalendarEventRecord {
  id: string
  title: string
  description: string
  event_date: string // ISO میلادی؛ تبدیل به شمسی فقط در UI
  start_time: string | null
  end_time: string | null
  category: CalendarCategory
  is_done: boolean
  created_by_id: string
}

export interface CalendarEventIn {
  title: string
  description: string
  event_date: string
  start_time: string | null
  end_time: string | null
  category: CalendarCategory
  is_done: boolean
}

export const fetchCalendarEvents = (
  token: string,
  opts: { from?: string; to?: string; includeDone?: boolean } = {},
) => {
  const qs = new URLSearchParams()
  if (opts.from) qs.set('from', opts.from)
  if (opts.to) qs.set('to', opts.to)
  if (opts.includeDone === false) qs.set('include_done', 'false')
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<CalendarEventRecord[]>(token, `/api/calendar-events${suffix}`)
}

export const createCalendarEvent = (token: string, data: CalendarEventIn) =>
  authedSend<CalendarEventRecord>(token, 'POST', '/api/calendar-events', data)

export const updateCalendarEvent = (token: string, id: string, data: CalendarEventIn) =>
  authedSend<CalendarEventRecord>(token, 'PUT', `/api/calendar-events/${id}`, data)

export const setCalendarEventDone = (token: string, id: string, done: boolean) =>
  authedSend<CalendarEventRecord>(token, 'PATCH', `/api/calendar-events/${id}/done`, { is_done: done })

export const deleteCalendarEvent = (token: string, id: string) =>
  authedDelete(token, `/api/calendar-events/${id}`)

// --- دارایی‌های ثابت و استهلاک ----------------------------------------------------

export interface FixedAssetRecord {
  id: string
  name: string
  category: string
  acquired_date: string
  cost: string
  salvage_value: string
  useful_life_months: number
  method: string
  accumulated_depreciation: string
  is_disposed: boolean
  disposed_date: string | null
  notes: string
  book_value: string
  monthly_depreciation: string
  fully_depreciated: boolean
}

export interface FixedAssetIn {
  name: string
  category: string
  acquired_date: string
  cost: number
  salvage_value: number
  useful_life_months: number
  notes: string
}

export const fetchFixedAssets = (token: string) => authedGet<FixedAssetRecord[]>(token, '/api/fixed-assets')

export const createFixedAsset = (token: string, data: FixedAssetIn) =>
  authedSend<FixedAssetRecord>(token, 'POST', '/api/fixed-assets', data)

export const updateFixedAsset = (token: string, id: string, data: FixedAssetIn) =>
  authedSend<FixedAssetRecord>(token, 'PUT', `/api/fixed-assets/${id}`, data)

export const disposeFixedAsset = (token: string, id: string, disposedDate: string) =>
  authedSend<FixedAssetRecord>(token, 'POST', `/api/fixed-assets/${id}/dispose`, { disposed_date: disposedDate })

export const deleteFixedAsset = (token: string, id: string) => authedDelete(token, `/api/fixed-assets/${id}`)

export interface DepreciationRunResult {
  period_date: string
  asset_count: number
  total_amount: string
  journal_entry_id: string | null
  journal_entry_number: number | null
}

export const runDepreciation = (token: string, periodDate: string) =>
  authedSend<DepreciationRunResult>(token, 'POST', '/api/depreciation/run', { period_date: periodDate })

export interface DepreciationEntryRecord {
  id: string
  asset_id: string
  asset_name: string
  period_date: string
  amount: string
  journal_entry_id: string | null
}

export const fetchDepreciationEntries = (token: string) =>
  authedGet<DepreciationEntryRecord[]>(token, '/api/depreciation')

// --- بودجه‌بندی -------------------------------------------------------------------

export interface BudgetLineRecord {
  id: string
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  period_date: string
  amount: string
  notes: string
}

export interface BudgetLineIn {
  account_id: string
  period_date: string
  amount: number
  notes: string
}

export interface BudgetReportRow {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  budget: string
  actual: string
  variance: string
  variance_pct: string | null
  favorable: boolean
}

export interface BudgetReport {
  date_from: string | null
  date_to: string | null
  rows: BudgetReportRow[]
  total_budget: string
  total_actual: string
  total_variance: string
}

export const fetchBudgetLines = (token: string) =>
  authedGet<BudgetLineRecord[]>(token, '/api/budgets')

export const createBudgetLine = (token: string, data: BudgetLineIn) =>
  authedSend<BudgetLineRecord>(token, 'POST', '/api/budgets', data)

export const updateBudgetLine = (token: string, id: string, data: BudgetLineIn) =>
  authedSend<BudgetLineRecord>(token, 'PUT', `/api/budgets/${id}`, data)

export const deleteBudgetLine = (token: string, id: string) =>
  authedDelete(token, `/api/budgets/${id}`)

export const fetchBudgetReport = (token: string, dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<BudgetReport>(token, `/api/budgets/report${suffix}`)
}

// --- مراکز هزینه / پروژه ----------------------------------------------------------

export interface CostCenterRecord {
  id: string
  code: string
  name: string
  is_active: boolean
  notes: string
}

export interface CostCenterIn {
  code: string
  name: string
  is_active: boolean
  notes: string
}

export const fetchCostCenters = (token: string) =>
  authedGet<CostCenterRecord[]>(token, '/api/cost-centers')

export const createCostCenter = (token: string, data: CostCenterIn) =>
  authedSend<CostCenterRecord>(token, 'POST', '/api/cost-centers', data)

export const updateCostCenter = (token: string, id: string, data: CostCenterIn) =>
  authedSend<CostCenterRecord>(token, 'PUT', `/api/cost-centers/${id}`, data)

export const deleteCostCenter = (token: string, id: string) =>
  authedDelete(token, `/api/cost-centers/${id}`)

export interface CostCenterReportRow {
  cost_center_id: string | null
  cost_center_code: string
  cost_center_name: string
  income: string
  expense: string
  profit: string
}

export interface CostCenterReport {
  date_from: string | null
  date_to: string | null
  rows: CostCenterReportRow[]
  total_income: string
  total_expense: string
  total_profit: string
}

export const fetchCostCenterReport = (token: string, dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<CostCenterReport>(token, `/api/reports/cost-center${suffix}`)
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

export interface AgingReport {
  as_of: string
  kind: 'receivable' | 'payable'
  rows: AgingRow[]
  total_current: string
  total_31_60: string
  total_61_90: string
  total_over_90: string
  grand_total: string
}

export const fetchAging = (token: string, kind: 'receivable' | 'payable', asOf?: string) => {
  const qs = new URLSearchParams({ kind })
  if (asOf) qs.set('as_of', asOf)
  return authedGet<AgingReport>(token, `/api/reports/aging?${qs}`)
}

export interface ContactStatementLine {
  txn_date: string
  kind: string
  number: number | null
  description: string
  debit: string
  credit: string
  balance: string
}

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

export const fetchContactStatement = (token: string, contactId: string, dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<ContactStatement>(token, `/api/reports/contact-statement/${contactId}${suffix}`)
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

export interface InventoryReport {
  as_of: string | null
  rows: InventoryRow[]
  total_value: string
  item_count: number
}

export const fetchInventoryReport = (token: string) =>
  authedGet<InventoryReport>(token, '/api/reports/inventory')

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

export interface SalesDashboard {
  months: number
  monthly: DashboardMonth[]
  top_items: DashboardItem[]
  top_customers: DashboardCustomer[]
}

export const fetchSalesDashboard = (token: string, months = 12) =>
  authedGet<SalesDashboard>(token, `/api/reports/dashboard?months=${months}`)

export interface KardexLine {
  entry_date: string
  source_type: string
  source_label: string
  qty_in: string
  qty_out: string
  unit_cost: string
  balance_qty: string
}

export interface KardexReport {
  item_id: string
  item_sku: string
  item_name: string
  unit: string
  warehouse_id: string | null
  date_from: string | null
  date_to: string | null
  opening_qty: string
  lines: KardexLine[]
  total_in: string
  total_out: string
  closing_qty: string
}

export const fetchKardex = (token: string, itemId: string, dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<KardexReport>(token, `/api/reports/kardex/${itemId}${suffix}`)
}

// --- سامانه مؤدیان (صورتحساب الکترونیکی) ------------------------------------------

export interface MoadianSettingsRecord {
  memory_id: string
  economic_code: string
  national_id: string
  /** کلید خصوصی هرگز از سرور برنمی‌گردد؛ فقط وجودش گزارش می‌شود. */
  has_private_key: boolean
  is_sandbox: boolean
  is_active: boolean
  base_url_override: string
  last_serial: number
  effective_base_url: string
}

export interface MoadianSettingsIn {
  memory_id: string
  economic_code: string
  national_id: string
  /** خالی = کلیدِ ذخیره‌شده دست‌نخورده بماند. */
  private_key_pem?: string
  is_sandbox: boolean
  is_active: boolean
  base_url_override: string
}

export interface MoadianSubmissionRecord {
  id: string
  sales_invoice_id: string
  tax_id: string
  serial: number
  invoice_date: string
  status: 'pending' | 'sent' | 'confirmed' | 'rejected' | 'failed'
  reference_number: string
  error_message: string
  sent_at: string | null
}

export const fetchMoadianSettings = (token: string) =>
  authedGet<MoadianSettingsRecord>(token, '/api/moadian/settings')

export const updateMoadianSettings = (token: string, data: MoadianSettingsIn) =>
  authedSend<MoadianSettingsRecord>(token, 'PUT', '/api/moadian/settings', data)

export const fetchMoadianSubmissions = (token: string) =>
  authedGet<MoadianSubmissionRecord[]>(token, '/api/moadian/submissions')

export const submitInvoiceToMoadian = (token: string, invoiceId: string) =>
  authedSend<MoadianSubmissionRecord>(token, 'POST', `/api/moadian/submit/${invoiceId}`, {})

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
