// build همیشه VITE_API_URL را صریح می‌دهد، پس این fallback در عمل کد مرده است —
// ولی همان دامنه‌ی قدیمی‌ای بود که در electron/main.ts هم یک‌بار جا مانده بود.
// یکسان نگه داشتنش ارزان‌تر از دوباره پیدا کردنش است.
const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? 'https://acc.cubita.ir' : 'http://localhost:8000')

export interface MeResponse {
  id: string
  name: string
  email: string
  phone: string | null
  //: شماره‌ی موبایلِ فعلی با کدِ پیامکی تأیید شده — برای نشانِ «تأییدشده» و بازیابیِ رمز با پیامک.
  phone_verified: boolean
  //: ایمیلِ کاربر با کدِ ایمیلی تأیید شده — ثبت‌نامِ خودسرویسِ تازه همیشه true است.
  email_verified: boolean
  role_key: string
  role_name: string
  permissions: Record<string, string[]>
  tenant_id: string
  tenant_name: string
  //: کاربر روی allowlist کنترل‌پنل فروش خودِ کوبیتاست، نه صاحب یک کسب‌وکار عادی.
  is_platform_admin: boolean
  //: سوپرادمینِ کلِ سامانه (فقط مالک) — گیتِ ماژولِ «مدیریت اکانت‌ها».
  is_super_admin: boolean
  //: نوعِ حساب در بازارِ عمده‌فروشی: standard | distributor (پخش‌کننده) | retailer (فروشگاه).
  //: ماژول‌های «پخشِ من» / «بازارِ خرید» با این گیت می‌شوند.
  tenant_kind: string
  //: حسابِ آزمایشیِ رایگان — نوارِ «X روز مانده»، باکسِ خرید و صفحه‌ی قفل از این مشتق می‌شوند.
  is_trial: boolean
  //: روزهای مانده تا انقضای آزمایشی (منفی = گذشته). برای مشتریِ واقعی null.
  trial_days_left: number | null
  //: دوره‌ی آزمایشی تمام شده — فقط صفحه‌ی خرید نشان داده می‌شود.
  trial_expired: boolean
  //: قابلیت‌های قفل‌شده در آزمایشی (moadian/storefront) — جای ماژول باکسِ «خرید پلن» می‌آید.
  locked_features: string[]
  //: ── شخصی‌سازیِ پنل ──
  //: صنفِ کسب‌وکار — قالبِ پیش‌فرضِ ماژول‌ها.
  industry: string
  //: کلیدِ ماژول‌های *روشن* (ترجیحِ مالک، شاملِ core). ناوبری با این فیلتر می‌شود.
  enabled_modules: string[]
  //: کلیدِ ماژول‌های *مجاز* (حقِ دسترسی). نمایشِ نهایی = enabled ∩ allowed.
  allowed_modules: string[]
}

//: صفحه‌ی پلن‌ها و خرید روی سایتِ تجاری. خریدِ کاربرِ آزمایشی با همین ایمیل، حسابش را
//: سرِ جا به واقعی تبدیل می‌کند و دیتایش حفظ می‌شود.
export const PLANS_URL = 'https://cubita.ir/#pricing'

//: نمایشِ زنده‌ی قالبِ فروشگاه — سایتِ استاتیکِ دموی خوداتکا روی VPS (بدونِ بک‌اند).
export const STOREFRONT_DEMO_URL = 'https://cubita.ir/shop-demo/'

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

/** ثبت‌نامِ خودسرویس — کسب‌وکار و مالکش با هم ساخته می‌شوند و حسابِ آزمایشیِ ۱۴روزه می‌گیرند. */
/**
 * گامِ اولِ ثبت‌نام: کدِ تأیید را به ایمیل می‌فرستد (حساب هنوز ساخته نمی‌شود).
 * برمی‌گرداند که ایمیل واقعاً فرستاده شد و نشانیِ ماسک‌شده را برای نمایش.
 */
export async function requestSignupCode(email: string): Promise<{ sent: boolean; email: string; expires_in: number }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/signup/request-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(body.detail ?? 'ارسال کد تأیید ناموفق بود')
  }
  return res.json()
}

export async function signup(
  businessName: string,
  ownerName: string,
  email: string,
  password: string,
  code: string,
  industry: string,
): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ business_name: businessName, owner_name: ownerName, email, password, code, industry }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(body.detail ?? 'ثبت‌نام ناموفق بود')
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

// کمکِ ساختِ کوئری‌استرینگِ بازه‌ی تاریخ (date_from/date_to؛ خالی = از ابتدا تا امروز)
const rangeQs = (dateFrom?: string, dateTo?: string) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  return qs.toString() ? `?${qs}` : ''
}

export const fetchTrialBalance = (token: string, dateFrom?: string, dateTo?: string) =>
  authedGet<TrialBalanceRow[]>(token, `/api/reports/trial-balance${rangeQs(dateFrom, dateTo)}`)

export const fetchIncomeStatement = (token: string, dateFrom?: string, dateTo?: string) =>
  authedGet<IncomeStatement>(token, `/api/reports/income-statement${rangeQs(dateFrom, dateTo)}`)

export const fetchBalanceSheet = (token: string, asOf?: string) =>
  authedGet<BalanceSheet>(token, `/api/reports/balance-sheet${asOf ? `?as_of=${asOf}` : ''}`)

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

// ── گزارش معاملات فصلی (ماده ۱۶۹ ق.م.م) ──
export interface SeasonalPartyRow {
  contact_id: string | null
  contact_name: string
  entity_type: 'real' | 'legal' | 'aggregate'
  national_id: string | null
  economic_code: string | null
  postal_code: string | null
  invoice_count: number
  gross: string
  discount: string
  net: string
  vat: string
  total: string
}

export interface SeasonalSection {
  rows: SeasonalPartyRow[]
  total_gross: string
  total_discount: string
  total_net: string
  total_vat: string
  total_total: string
}

export interface SeasonalReport {
  year: number
  quarter: number
  quarter_label: string
  date_from: string
  date_to: string
  sales: SeasonalSection
  purchases: SeasonalSection
}

export const fetchSeasonalReport = (token: string, year: number, quarter: number) =>
  authedGet<SeasonalReport>(token, `/api/reports/seasonal?year=${year}&quarter=${quarter}`)

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

export const fetchGeneralLedger = (token: string, accountId: string, dateFrom?: string, dateTo?: string) =>
  authedGet<GeneralLedger>(token, `/api/reports/general-ledger/${accountId}${rangeQs(dateFrom, dateTo)}`)

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
  voided_at: string | null
  reverses_entry_id: string | null
  lines: JournalEntryLine[]
}

export const fetchJournalEntries = (token: string) =>
  authedGetAll<JournalEntryRecord>(token, '/api/journal-entries')

/** ابطالِ سندِ دستی با ثبتِ سندِ معکوس. فقط سندِ دستیِ باطل‌نشده؛ وگرنه سرور ۴۰۹ می‌دهد. */
export const voidJournalEntry = (token: string, entryId: string, reason: string) =>
  authedSend<{ reversal_entry_id: string; reversal_entry_number: number | null }>(
    token, 'POST', `/api/journal-entries/${entryId}/void`, { reason },
  )

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
  contact_name: string | null
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

// ── سال مالی ────────────────────────────────────────────────────────────────

export interface FiscalYearRecord {
  id: string
  title: string
  start_date: string
  end_date: string
  status: 'open' | 'closed'
  is_active: boolean
  notes: string
  opening_entry_id: string | null
  closing_entry_id: string | null
  closed_at: string | null
  entry_count: number
}

export interface FiscalYearSuggestion {
  jalali_year: number
  title: string
  start_date: string
  end_date: string
  days: number
  is_leap: boolean
}

export interface NumberingRule {
  doc_type: string
  label: string
  last_number: number
  next_number: number
}

export const fetchNumbering = (token: string) =>
  authedGet<NumberingRule[]>(token, '/api/numbering')

export const setNumbering = (token: string, docType: string, nextNumber: number) =>
  authedSend<NumberingRule>(token, 'PATCH', `/api/numbering/${docType}`, { next_number: nextNumber })

export const fetchFiscalYears = (token: string) =>
  authedGet<FiscalYearRecord[]>(token, '/api/fiscal-years')

export const fetchFiscalYearSuggestion = (token: string) =>
  authedGet<FiscalYearSuggestion>(token, '/api/fiscal-years/suggest')

export const createFiscalYear = (
  token: string,
  data: { title: string; start_date: string; end_date: string; notes?: string; activate?: boolean },
) => authedSend<FiscalYearRecord>(token, 'POST', '/api/fiscal-years', data)

export const updateFiscalYear = (
  token: string,
  id: string,
  data: { title?: string; start_date?: string; end_date?: string; notes?: string },
) => authedSend<FiscalYearRecord>(token, 'PATCH', `/api/fiscal-years/${id}`, data)

export const activateFiscalYear = (token: string, id: string) =>
  authedSend<FiscalYearRecord>(token, 'POST', `/api/fiscal-years/${id}/activate`, {})

export const carryForwardFiscalYear = (token: string, id: string) =>
  authedSend<{ journal_entry_id: string; line_count: number; total: string }>(
    token, 'POST', `/api/fiscal-years/${id}/carry-forward`, {},
  )

export const closeFiscalYear = (token: string, id: string) =>
  authedSend<FiscalYearRecord>(token, 'POST', `/api/fiscal-years/${id}/close`, {})

export const deleteFiscalYear = (token: string, id: string) =>
  authedDelete(token, `/api/fiscal-years/${id}`)

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

// نرخ‌های بیمه/مالیاتِ حقوق برای هر سالِ شمسی. صدورِ فیش تا وقتی این تنظیمات (با
// پلکانِ نرخ‌غیرصفر) ثبت نشود، توسط سرور مسدود می‌شود.
export interface TaxBracket {
  up_to: string | null // سقفِ تجمعیِ سالانه‌ی مشمول (پس از کسرِ معافیت)؛ null = نامحدود (ردیفِ آخر)
  rate: string // نرخ بین ۰ و ۱
}

export interface PayrollSettingsRecord {
  id: string
  year: number
  insurance_employee_rate: string
  insurance_employer_rate: string
  tax_exemption_annual: string
  tax_brackets: TaxBracket[]
  min_base_wage: string
  annual_leave_days: number
  notes: string
}

export const fetchPayrollSettings = (token: string) =>
  authedGet<PayrollSettingsRecord[]>(token, '/api/payroll-settings')

export const upsertPayrollSettings = (
  token: string,
  data: {
    year: number
    insurance_employee_rate: number
    insurance_employer_rate: number
    tax_exemption_annual: number
    tax_brackets: { up_to: number | null; rate: number }[]
    min_base_wage: number
    annual_leave_days: number
    notes: string
  },
) => authedSend<PayrollSettingsRecord>(token, 'PUT', '/api/payroll-settings', data)

export interface ItemRecord {
  id: string
  sku: string
  name: string
  category: string
  unit: string
  is_service: boolean
  is_active: boolean
  sales_price: string
  average_cost: string
  barcode: string | null
  storefront_product_id: number | null
  reorder_point: string
  tax_stuff_id: string
}

export const fetchItemsLive = (token: string) => authedGetAll<ItemRecord>(token, '/api/items')

/** پشتیبان‌گیری: خروجیِ کاملِ داده‌ی کسب‌وکار (فقط مالک؛ در وب برای دانلودِ فایل). */
export const fetchBackupExport = (token: string) => authedGet<Record<string, unknown>>(token, '/api/backup/export')

/** بازیابی: فایلِ پشتیبان را می‌فرستد و داده را *جایگزین* می‌کند (فقط مالک). */
export const importBackup = (token: string, data: unknown) =>
  authedSend<{ restored: boolean; total_rows: number }>(token, 'POST', '/api/backup/import', data)

/** جست‌وجوی کالا با بارکد (اسکن در صندوقِ فروشگاهی). ۴۰۴ اگر پیدا نشود. */
export const fetchItemByBarcode = (token: string, code: string) =>
  authedGet<ItemRecord>(token, `/api/items/by-barcode?code=${encodeURIComponent(code)}`)

/** ورودیِ ساختِ کالای جدید — دقیقاً منطبق بر ItemIn سمت سرور (sku و name الزامی‌اند). */
export interface ItemIn {
  sku: string
  name: string
  category?: string
  unit?: string
  is_service?: boolean
  sales_price?: number
  barcode?: string | null
  reorder_point?: number
  tax_stuff_id?: string
}

export const createItemLive = (token: string, data: ItemIn) =>
  authedSend<ItemRecord>(token, 'POST', '/api/items', data)

/** ویرایشِ کالا — فقط فیلدهایی که سرور در ItemUpdateIn می‌پذیرد. */
export const updateItemLive = (
  token: string,
  itemId: string,
  patch: { name?: string; sales_price?: number; is_active?: boolean; barcode?: string | null; reorder_point?: number; tax_stuff_id?: string },
) => authedSend<ItemRecord>(token, 'PATCH', `/api/items/${itemId}`, patch)

/** حذفِ کالا — فقط اگر در هیچ سند/موجودی استفاده نشده باشد؛ وگرنه سرور ۴۰۹ با پیامِ راهنما می‌دهد. */
export const deleteItemLive = (token: string, itemId: string) => authedDelete(token, `/api/items/${itemId}`)

export const updateItemStorefrontMapping = (token: string, itemId: string, storefrontProductId: number | null) =>
  authedSend<ItemRecord>(token, 'PATCH', `/api/items/${itemId}`, { storefront_product_id: storefrontProductId })

export const updateItemCost = (token: string, itemId: string, averageCost: number) =>
  authedSend<ItemRecord>(token, 'PATCH', `/api/items/${itemId}`, { average_cost: averageCost })

export interface SyncResult {
  orders_imported: number[]
  orders_skipped: { order_id: number | null; reason: string }[]
  items_pushed: string[]
  items_push_failed: { sku: string; error: string }[]
}

export const triggerStorefrontSync = (token: string) =>
  authedSend<SyncResult>(token, 'POST', '/api/integration/sync', {})

export interface StorefrontSettings {
  base_url: string
  admin_email: string
  has_password: boolean
  cutover_order_id: number
  is_active: boolean
}

export interface StorefrontSettingsIn {
  base_url: string
  admin_email: string
  admin_password: string
  cutover_order_id: number
  is_active: boolean
}

export const fetchStorefrontSettings = (token: string) =>
  authedGet<StorefrontSettings>(token, '/api/integration/settings')

export const updateStorefrontSettings = (token: string, data: StorefrontSettingsIn) =>
  authedSend<StorefrontSettings>(token, 'PUT', '/api/integration/settings', data)

// ── فروشگاهِ بومیِ کوبیتا (/api/storefront/*) ────────────────────────────────────
// جدا از اتصالِ بیرونی بالا: این‌جا کاربر فروشگاهِ خودش را می‌سازد و منتشر می‌کند.

export interface NativeStorefront {
  slug: string
  theme_id: string
  theme_config: Record<string, unknown>
  seo_title: string
  seo_description: string
  contact_block: Record<string, unknown>
  allowed_origin: string
  /** کلیدِ publishable — در سایتِ استاتیک بیک می‌شود؛ رازِ پنهان نیست. */
  publishable_key: string
  status: string // draft | published
  last_built_at: string | null
}

export interface NativeStorefrontIn {
  theme_id: string
  theme_config: Record<string, unknown>
  seo_title: string
  seo_description: string
  contact_block: Record<string, unknown>
  allowed_origin: string
}

export interface StorefrontItem {
  item_id: string
  name: string
  sku: string
  sales_price: number
  is_listed: boolean
  images: string[]
  long_description: string
  slug: string
  sort: number
  badge: string
}

export interface StorefrontItemIn {
  is_listed: boolean
  images?: string[]
  long_description?: string
  slug?: string
  sort?: number
  badge?: string
}

export interface StorefrontGateway {
  provider: string
  has_merchant: boolean
  is_active: boolean
}

export interface StorefrontOrderLine {
  item_id: string
  item_name: string
  qty: number
  unit_price: number
  line_total: number
}

export interface StorefrontOrder {
  id: string
  order_number: number
  tracking_code: string
  customer_name: string
  customer_phone: string
  customer_email: string
  shipping_address: string
  note: string
  subtotal: number
  total: number
  payment_status: string // pending | paid | failed | cancelled
  fulfillment_status: string // new | confirmed | shipped | done | cancelled
  sales_invoice_id: string | null
  created_at: string
  lines: StorefrontOrderLine[]
}

export const fetchNativeStorefront = (token: string) =>
  authedGet<NativeStorefront>(token, '/api/storefront')

export const updateNativeStorefront = (token: string, data: NativeStorefrontIn) =>
  authedSend<NativeStorefront>(token, 'PUT', '/api/storefront', data)

export const rotateStorefrontKey = (token: string) =>
  authedSend<NativeStorefront>(token, 'POST', '/api/storefront/key/rotate', {})

export const publishStorefront = (token: string) =>
  authedSend<NativeStorefront>(token, 'POST', '/api/storefront/publish', {})

export const unpublishStorefront = (token: string) =>
  authedSend<NativeStorefront>(token, 'POST', '/api/storefront/unpublish', {})

export const fetchStorefrontItems = (token: string) =>
  authedGet<StorefrontItem[]>(token, '/api/storefront/items')

export const updateStorefrontItem = (token: string, itemId: string, data: StorefrontItemIn) =>
  authedSend<StorefrontItem>(token, 'PUT', `/api/storefront/items/${itemId}`, data)

export const fetchStorefrontGateways = (token: string) =>
  authedGet<StorefrontGateway[]>(token, '/api/storefront/gateways')

export const updateStorefrontGateway = (
  token: string,
  provider: string,
  data: { merchant_id: string; is_active: boolean },
) => authedSend<StorefrontGateway>(token, 'PUT', `/api/storefront/gateways/${provider}`, data)

export const fetchStorefrontOrders = (token: string) =>
  authedGet<StorefrontOrder[]>(token, '/api/storefront/orders')

export const confirmStorefrontOrder = (token: string, id: string) =>
  authedSend<StorefrontOrder>(token, 'POST', `/api/storefront/orders/${id}/confirm-payment`, {})

export const updateStorefrontFulfillment = (token: string, id: string, status: string) =>
  authedSend<StorefrontOrder>(token, 'PUT', `/api/storefront/orders/${id}/fulfillment`, {
    fulfillment_status: status,
  })

/** بسته‌ی ZIPِ سایت را می‌گیرد (config.js با apiBase/slug/key این کسب‌وکار بیک شده). */
export async function downloadStorefrontBundle(token: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE_URL}/api/storefront/site-bundle`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`ساختِ بسته‌ی سایت ناموفق بود (${res.status})`)
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const m = cd.match(/filename="?([^"]+)"?/)
  return { blob, filename: m && m[1] ? m[1] : 'cubita-storefront.zip' }
}

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
  customer_name: string | null
  description: string
  status: 'draft' | 'sent' | 'accepted' | 'rejected' | 'converted'
  total_amount: string
  converted_invoice_id: string | null
  lines: SalesQuotationLine[]
}

export const fetchSalesQuotations = (token: string) =>
  authedGetAll<SalesQuotationRecord>(token, '/api/sales-quotations')

export interface SalesQuotationInput {
  quotation_date: string
  valid_until: string | null
  warehouse_id: string
  contact_id?: string | null
  customer_name?: string | null
  description: string
  lines: { item_id: string; qty: number; unit_price: number; description: string }[]
}

export const createSalesQuotation = (token: string, data: SalesQuotationInput) =>
  authedSend<SalesQuotationRecord>(token, 'POST', '/api/sales-quotations', data)

export const updateSalesQuotation = (token: string, quotationId: string, data: SalesQuotationInput) =>
  authedSend<SalesQuotationRecord>(token, 'PUT', `/api/sales-quotations/${quotationId}`, data)

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
  /** تخفیفِ کلِ فاکتور (تسهیم‌شده در ردیف‌ها؛ در total_discount هم منظور شده). */
  invoice_discount: string
  /** تعدیلِ گِرد کردنِ مبلغِ نهایی، علامت‌دار. قابل پرداخت = خالص + مالیات + rounding. */
  rounding: string
  total_cost: string
  tax_rate: string
  tax_amount: string
  voided_at: string | null
  void_reason: string
  /** ثبت‌کننده‌ی فاکتور — چه کسی و با چه نقشی آن را زد. */
  created_by_id: string | null
  created_by_name: string | null
  created_by_role: string | null
  lines: (InvoiceLineRecord & { unit_price: string; unit_cost: string })[]
}

export const fetchSalesInvoices = (token: string) => authedGetAll<SalesInvoiceRecord>(token, '/api/sales-invoices')

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

/** شاخص‌های فروش، محاسبه‌شده سمت سرور — به‌جای دانلودِ کلِ فاکتورها در کلاینت. */
export const fetchSalesSummary = (token: string) =>
  authedGet<SalesSummary>(token, '/api/sales-invoices/summary')

export interface PurchaseInvoiceRecord {
  id: string
  number: number | null
  invoice_date: string
  warehouse_id: string
  contact_id: string | null
  description: string
  total_amount: string
  total_discount: string
  /** تخفیفِ کلِ فاکتور (تسهیم‌شده در ردیف‌ها؛ در total_discount هم منظور شده). */
  invoice_discount: string
  tax_rate: string
  tax_amount: string
  voided_at: string | null
  void_reason: string
  /** ثبت‌کننده‌ی فاکتور — چه کسی و با چه نقشی آن را زد. */
  created_by_id: string | null
  created_by_name: string | null
  created_by_role: string | null
  lines: (InvoiceLineRecord & { unit_cost: string })[]
}

export const fetchPurchaseInvoices = (token: string) => authedGetAll<PurchaseInvoiceRecord>(token, '/api/purchase-invoices')

export interface PurchaseSummary {
  invoice_count: number
  total_net: string
  total_tax: string
  total_with_tax: string
  last_30_with_tax: string
  avg_invoice: string
}

/** شاخص‌های خرید، محاسبه‌شده سمت سرور — به‌جای دانلودِ کلِ فاکتورها در کلاینت. */
export const fetchPurchaseSummary = (token: string) =>
  authedGet<PurchaseSummary>(token, '/api/purchase-invoices/summary')

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

export interface ReturnableLine {
  item_id: string
  item_name: string
  unit: string
  sold: string
  already_returned: string
  remaining: string
  unit_price: string
}

/** باقی‌ماندهٔ قابلِ برگشتِ هر کالای یک فاکتور فروش. */
export const fetchReturnable = (token: string, invoiceId: string) =>
  authedGet<ReturnableLine[]>(token, `/api/sales-invoices/${invoiceId}/returnable`)

/** باقی‌ماندهٔ قابلِ برگشتِ هر کالای یک فاکتور خرید (`unit_price` بهای واحد را حمل می‌کند). */
export const fetchPurchaseReturnable = (token: string, invoiceId: string) =>
  authedGet<ReturnableLine[]>(token, `/api/purchase-invoices/${invoiceId}/returnable`)

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
  unit_cost: string
  stock_value: string
}

export const fetchStockLevels = (token: string) => authedGet<StockLevel[]>(token, '/api/stock')

/** کالاهایی که موجودی‌شان به/زیرِ نقطه‌ی سفارش رسیده — هشدارِ سفارشِ مجدد. */
export interface LowStockRow {
  item_id: string
  sku: string
  name: string
  unit: string
  qty_on_hand: string
  reorder_point: string
  shortfall: string
}

export const fetchLowStock = (token: string) => authedGet<LowStockRow[]>(token, '/api/stock/low')

/** انبار (کامل، با وضعیتِ فعال) — برای تبِ مدیریتِ انبارها. */
export interface WarehouseRecord {
  id: string
  code: string
  name: string
  is_active: boolean
}

export const fetchWarehousesAdmin = (token: string) =>
  authedGet<WarehouseRecord[]>(token, '/api/warehouses')

export const createWarehouse = (token: string, data: { code: string; name: string }) =>
  authedSend<WarehouseRecord>(token, 'POST', '/api/warehouses', data)

export const updateWarehouse = (token: string, id: string, patch: { name?: string; is_active?: boolean }) =>
  authedSend<WarehouseRecord>(token, 'PATCH', `/api/warehouses/${id}`, patch)

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

/** حسابِ کامل (با فعال‌بودن و نقشِ سیستمی) — برای مدیریتِ چارتِ حساب‌ها. */
export interface ChartAccount {
  id: string
  code: string
  name: string
  type: string // asset | liability | equity | income | expense
  is_group: boolean
  is_active: boolean
  parent_id: string | null
  system_role: string | null
}

export const fetchChartAccounts = (token: string) =>
  authedGet<ChartAccount[]>(token, '/api/accounts')

export const createAccount = (
  token: string,
  data: { code: string; name: string; type: string; is_group?: boolean; parent_id?: string | null },
) => authedSend<ChartAccount>(token, 'POST', '/api/accounts', data)

export const updateAccount = (token: string, id: string, patch: { name?: string; is_active?: boolean }) =>
  authedSend<ChartAccount>(token, 'PATCH', `/api/accounts/${id}`, patch)

export const deleteAccount = (token: string, id: string) => authedDelete(token, `/api/accounts/${id}`)

/** تغییرِ کدِ حساب — «کدینگ». امن است چون ثبتِ خودکار حساب را با نقشش می‌شناسد نه با کدش. */
export const changeAccountCode = (token: string, id: string, code: string) =>
  authedSend<ChartAccount>(token, 'PATCH', `/api/accounts/${id}/code`, { code })

/** قالبِ آماده‌ی کدینگِ صنفی. */
export interface ChartTemplate {
  key: string
  label: string
  hint: string
  total: number
  /** چند حساب از این قالب هنوز در چارت نیست. */
  missing: number
}

/** قاعده‌ی کدینگِ چارت — رقمِ افزوده در هر سطح. */
export interface CodingRule {
  widths: number[]
  levels: { name: string; width: number; total: number; example: string }[]
}

export const fetchCodingRule = (token: string) =>
  authedGet<CodingRule>(token, '/api/accounts/coding-rule')

export const setCodingRule = (token: string, widths: number[]) =>
  authedSend<CodingRule>(token, 'PATCH', '/api/accounts/coding-rule', { widths })

/** کدِ آزادِ بعدی زیرِ یک سرفصل، طبقِ قاعده — تا فرم حدس نزند. */
export const fetchNextAccountCode = (token: string, parentId: string | null) =>
  authedGet<{ code: string; level: string; digits: number }>(
    token,
    `/api/accounts/next-code${parentId ? `?parent_id=${parentId}` : ''}`,
  )

export const fetchChartTemplates = (token: string) =>
  authedGet<ChartTemplate[]>(token, '/api/accounts/templates')

export const applyChartTemplate = (token: string, key: string) =>
  authedSend<{ created: number; skipped: number; codes: string[] }>(
    token, 'POST', `/api/accounts/templates/${key}`, {},
  )

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

/** حساب بانکیِ کامل — برای مدیریتِ حساب‌ها و «کارتِ حساب» (دفتر کلِ متناظر). */
export interface BankAccountRecord {
  id: string
  name: string
  bank_name: string
  account_number: string
  iban: string
  gl_account_id: string
  is_active: boolean
}

export const fetchBankAccountsAdmin = (token: string) =>
  authedGet<BankAccountRecord[]>(token, '/api/bank-accounts')

export const createBankAccount = (
  token: string,
  data: { name: string; bank_name?: string; account_number?: string; iban?: string },
) => authedSend<BankAccountRecord>(token, 'POST', '/api/bank-accounts', data)

export const updateBankAccount = (
  token: string,
  id: string,
  patch: { name?: string; bank_name?: string; account_number?: string; iban?: string; is_active?: boolean },
) => authedSend<BankAccountRecord>(token, 'PATCH', `/api/bank-accounts/${id}`, patch)

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
    currency_code?: string | null
    exchange_rate?: number
    /** تخفیفِ کلِ فاکتور به مبلغِ پایه (ریال). درصد در UI به مبلغ تبدیل می‌شود. */
    invoice_discount?: number
    /** تعدیلِ گِرد کردنِ مبلغِ نهایی (پس از مالیات)، علامت‌دار. */
    rounding?: number
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
    contact_id?: string | null
    currency_code?: string | null
    exchange_rate?: number
    /** تخفیفِ کلِ فاکتور به مبلغِ پایه (ریال). درصد در UI به مبلغ تبدیل می‌شود. */
    invoice_discount?: number
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
    contact_id?: string | null
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

// ── مدیریت اکانت‌ها (فقط سوپرادمین) ──────────────────────────────────────────
export interface AdminAccountUser {
  name: string
  email: string
  status: string // عضویت: active | invited | disabled
  is_owner: boolean
  last_login_at: string | null
}

export interface AdminAccount {
  tenant_id: string
  name: string
  slug: string
  status: string // active | suspended | cancelled
  kind: string // standard | distributor | retailer
  //: صنف (قالبِ ماژول‌ها) و ماژول‌های محدودِ گرنت‌شده — شخصی‌سازیِ سوپرادمین.
  industry: string
  granted_modules: string[]
  owner_name: string
  owner_email: string
  created_at: string
  user_count: number
  max_users: number | null
  subscription_status: string // active | grace | expired | cancelled | none
  expires_at: string | null
  days_left: number | null
  plan_name: string
  is_trial: boolean
  trial_days_left: number | null
  trial_expired: boolean
  owner_last_login_at: string | null
  last_activity_at: string | null
  users: AdminAccountUser[]
}

export const fetchAdminAccounts = (token: string) =>
  authedGet<AdminAccount[]>(token, '/api/admin/accounts')

export const createAdminAccount = (
  token: string,
  data: { business_name: string; owner_name: string; email: string; password: string; days: number; kind?: string },
) => authedSend<AdminAccount>(token, 'POST', '/api/admin/accounts', data)

export const setAdminAccountKind = (token: string, tenantId: string, kind: string) =>
  authedSend<AdminAccount>(token, 'POST', `/api/admin/accounts/${tenantId}/kind`, { kind })

export const extendAdminAccount = (
  token: string,
  tenantId: string,
  data: { days?: number; expires_at?: string },
) => authedSend<AdminAccount>(token, 'POST', `/api/admin/accounts/${tenantId}/extend`, data)

export const setAdminAccountStatus = (token: string, tenantId: string, status: 'active' | 'suspended') =>
  authedSend<AdminAccount>(token, 'POST', `/api/admin/accounts/${tenantId}/status`, { status })

export const resetAdminAccountPassword = (token: string, tenantId: string, password: string) =>
  authedSend<AdminAccount>(token, 'POST', `/api/admin/accounts/${tenantId}/reset-password`, { password })

export const deleteAdminAccount = (token: string, tenantId: string) =>
  authedDelete(token, `/api/admin/accounts/${tenantId}`)

//: صنفِ اکانت را می‌گذارد (ماژول‌ها به قالبِ صنف بازنشانی + محدودهای قالب گرنت می‌شوند).
export const setAdminAccountIndustry = (token: string, tenantId: string, industry: string) =>
  authedSend<AdminAccount>(token, 'POST', `/api/admin/accounts/${tenantId}/industry`, { industry })

//: «حقِ دسترسی»ِ ماژول‌های محدود را می‌گذارد (فهرستِ کاملِ محدودهای مجاز، نه افزایشی).
export const setAdminAccountModules = (token: string, tenantId: string, granted: string[]) =>
  authedSend<AdminAccount>(token, 'POST', `/api/admin/accounts/${tenantId}/modules`, { granted })

// ── شخصی‌سازیِ پنل توسطِ مالک ──

//: وضعیتِ کاملِ ماژول‌های کسب‌وکار — منبعِ صفحه‌ی «شخصی‌سازیِ پنل».
export interface ModulesState {
  industry: string
  //: کلیدِ ماژول‌های روشن (ترجیحِ مالک، شاملِ core).
  enabled: string[]
  //: کلیدِ ماژول‌های مجاز (حقِ دسترسی).
  allowed: string[]
  //: رجیستریِ سرور (منبعِ واحد).
  core: string[]
  optional: string[]
  restricted: string[]
  industries: string[]
}

export const fetchModules = (token: string) => authedGet<ModulesState>(token, '/api/modules')

//: ترجیحِ نمایشِ مالک را ذخیره می‌کند (فهرستِ کلیدِ ماژول‌های اختیاریِ روشن).
export const updateModules = (token: string, enabled: string[]) =>
  authedSend<ModulesState>(token, 'PUT', '/api/modules', { enabled })

export interface ContactRecord {
  id: string
  name: string
  type: 'customer' | 'supplier' | 'both'
  phone: string | null
  email: string | null
  address: string
  tax_id: string | null
  is_active: boolean
  birthday: string | null
  credit_limit: string
  default_price_list_id: string | null
  entity_type: 'real' | 'legal'
  national_id: string | null
  economic_code: string | null
  postal_code: string | null
  group_id: string | null
  geo_location_id: string | null
}

export interface ContactIn {
  name: string
  type: string
  phone: string | null
  email: string | null
  address: string
  tax_id: string | null
  birthday?: string | null
  credit_limit: number
  default_price_list_id?: string | null
  entity_type?: 'real' | 'legal'
  national_id?: string | null
  economic_code?: string | null
  postal_code?: string | null
  //: دسته‌بندیِ سطحِ شرکت — هر دو اختیاری.
  group_id?: string | null
  geo_location_id?: string | null
}

// ── راه‌اندازی: ورودِ گروهی + مانده‌های اول دوره ──
export interface ImportResult {
  created: number
  skipped: number
  errors: { row: number; message: string }[]
}

export interface ItemImportRow {
  sku: string
  name: string
  category?: string
  unit?: string
  is_service?: boolean
  sales_price?: number
  barcode?: string | null
}

export interface ContactImportRow {
  name: string
  type?: string
  phone?: string | null
  email?: string | null
  address?: string
  entity_type?: string
  national_id?: string | null
  economic_code?: string | null
  postal_code?: string | null
}

export const importItems = (token: string, rows: ItemImportRow[]) =>
  authedSend<ImportResult>(token, 'POST', '/api/import/items', { rows })

export const importContacts = (token: string, rows: ContactImportRow[]) =>
  authedSend<ImportResult>(token, 'POST', '/api/import/contacts', { rows })

export interface OpeningStatus {
  exists: boolean
  entry_id: string | null
  entry_number: number | null
  entry_date: string | null
}

export interface OpeningAccountLine {
  account_id: string
  debit?: number
  credit?: number
  description?: string
}

export interface OpeningStockLine {
  item_id: string
  warehouse_id: string
  qty: number
  unit_cost: number
}

export interface OpeningBalancesIn {
  entry_date: string
  lines?: OpeningAccountLine[]
  stock?: OpeningStockLine[]
  balancing_account_id?: string | null
}

export const fetchOpeningStatus = (token: string) =>
  authedGet<OpeningStatus>(token, '/api/opening-balances/status')

export const createOpeningBalances = (token: string, data: OpeningBalancesIn) =>
  authedSend<{ id: string; number: number | null }>(token, 'POST', '/api/opening-balances', data)

// ── فروش اقساطی ──
export interface Installment {
  id: string
  seq: number
  due_date: string
  amount: string
  paid_amount: string
  remaining: string
  paid_date: string | null
  status: 'pending' | 'partial' | 'paid' | 'overdue'
  /** روزهای تأخیر و جریمه — سرور با تاریخِ امروز حساب می‌کند، ذخیره نمی‌شود. */
  days_late: number
  penalty: string
}

export interface InstallmentPayment {
  id: string
  installment_id: string
  installment_seq: number
  amount: string
  paid_on: string
  method: string
  treasury_transaction_id: string | null
  notes: string
}

export interface InstallmentPlan {
  id: string
  number: number | null
  contact_id: string
  contact_name: string
  sales_invoice_id: string | null
  title: string
  total_amount: string
  cash_price: string
  profit_amount: string
  profit_pct: string
  down_payment: string
  financed: string
  num_installments: number
  interval_months: number
  start_date: string
  status: 'active' | 'completed' | 'cancelled'
  penalty_rate: string
  guarantor_name: string
  guarantor_phone: string
  guarantor_national_id: string
  notes: string
  installments: Installment[]
  payments: InstallmentPayment[]
  total_paid: string
  total_remaining: string
  next_due_date: string | null
  next_due_amount: string
  overdue_amount: string
  overdue_count: number
  penalty_total: string
  collected_pct: string
  worst_days_late: number
}

export interface InstallmentPlanIn {
  contact_id: string
  sales_invoice_id?: string | null
  title?: string
  total_amount: number
  cash_price?: number | null
  profit_amount?: number | null
  down_payment?: number
  num_installments: number
  interval_months?: number
  start_date: string
  penalty_rate?: number
  guarantor_name?: string
  guarantor_phone?: string
  guarantor_national_id?: string
  notes?: string
}

export interface InstallmentPayIn {
  amount: number
  transaction_date: string
  method: 'cash' | 'bank'
  bank_account_id?: string | null
  notes?: string
}

export interface EarlySettlement {
  remaining: string
  unearned_profit: string
  discount: string
  payable: string
}

export interface InstallmentAgingBucket {
  key: string
  label: string
  count: number
  amount: string
}

export interface InstallmentDebtor {
  contact_id: string
  contact_name: string
  remaining: string
  overdue: string
  plans: number
}

export interface InstallmentSummary {
  active_plans: number
  total_financed: string
  total_collected: string
  total_remaining: string
  collected_pct: string
  overdue_amount: string
  overdue_count: number
  penalty_total: string
  due_this_week: string
  due_this_month: string
  buckets: InstallmentAgingBucket[]
  top_debtors: InstallmentDebtor[]
}

export const fetchInstallmentPlans = (token: string) =>
  authedGet<InstallmentPlan[]>(token, '/api/installment-plans')

export const fetchInstallmentSummary = (token: string) =>
  authedGet<InstallmentSummary>(token, '/api/installment-plans/summary')

export const createInstallmentPlan = (token: string, data: InstallmentPlanIn) =>
  authedSend<InstallmentPlan>(token, 'POST', '/api/installment-plans', data)

export const payInstallment = (token: string, planId: string, installmentId: string, data: InstallmentPayIn) =>
  authedSend<InstallmentPlan>(token, 'POST', `/api/installment-plans/${planId}/installments/${installmentId}/pay`, data)

/** یک فیش، چند قسط — سرور از قدیمی‌ترین قسطِ باز به بعد تسهیم می‌کند. */
export const settleInstallments = (token: string, planId: string, data: InstallmentPayIn) =>
  authedSend<InstallmentPlan>(token, 'POST', `/api/installment-plans/${planId}/settle`, data)

export const rescheduleInstallments = (
  token: string,
  planId: string,
  lines: { installment_id: string; due_date: string; amount: number }[],
) => authedSend<InstallmentPlan>(token, 'POST', `/api/installment-plans/${planId}/reschedule`, { lines })

export const fetchEarlySettlement = (token: string, planId: string, discount = 0) =>
  authedGet<EarlySettlement>(
    token,
    `/api/installment-plans/${planId}/early-settlement?discount=${discount}`,
  )

export const cancelInstallmentPlan = (token: string, planId: string) =>
  authedSend<InstallmentPlan>(token, 'POST', `/api/installment-plans/${planId}/cancel`, {})

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
  // متادیتای کارت (فقط برای رسیدِ کارتخوان پر می‌شود)
  paid_via?: string | null
  reference_no?: string | null
  trace_no?: string | null
  card_mask?: string | null
  terminal_no?: string | null
  psp?: string | null
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

// --- کارتخوان (POS) -----------------------------------------------------------------
// اتصالِ سخت‌افزار فقط در نسخه‌ی دسکتاپ (window.cubita.posTerminal) رخ می‌دهد؛ ثبتِ
// حسابداری سرور-ساید است و در هر دو نسخه یکسان دیده می‌شود.

export type PosTransport = 'simulator' | 'network' | 'serial' | 'sdk'

export interface PosTerminalRecord {
  id: string
  label: string
  psp: string
  transport: PosTransport
  host: string
  port: number
  com_port: string
  bank_account_id: string | null
  is_active: boolean
  is_default: boolean
}

export interface PosTerminalIn {
  label?: string
  psp?: string
  transport?: PosTransport
  host?: string
  port?: number
  com_port?: string
  bank_account_id?: string | null
  is_active?: boolean
  is_default?: boolean
}

export const fetchPosTerminals = (token: string) =>
  authedGet<PosTerminalRecord[]>(token, '/api/pos-terminals')

export const createPosTerminal = (token: string, data: PosTerminalIn) =>
  authedSend<PosTerminalRecord>(token, 'POST', '/api/pos-terminals', data)

export const updatePosTerminal = (token: string, id: string, data: PosTerminalIn) =>
  authedSend<PosTerminalRecord>(token, 'PATCH', `/api/pos-terminals/${id}`, data)

export const deletePosTerminal = (token: string, id: string) =>
  authedDelete(token, `/api/pos-terminals/${id}`)

/** پرداختِ کارتیِ موفق → ثبتِ رسیدِ بانکی. contact_id خالی = فروشِ گذری (طرف‌حسابِ سیستمی). */
export interface CardPaymentIn {
  transaction_date: string
  amount: number
  bank_account_id: string
  contact_id?: string | null
  reference_no: string
  trace_no?: string
  card_mask?: string
  terminal_no?: string
  psp?: string
  description?: string
}

export const recordCardPayment = (token: string, data: CardPaymentIn) =>
  authedSend<TreasuryTransactionRecord>(token, 'POST', '/api/treasury/card-payment', data)

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
  /** حسابِ تأمینِ خرید (بانک/صندوق/پرداختنی)؛ اگر داده شود سندِ خرید خودکار ثبت می‌شود. */
  funding_account_id?: string | null
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
  cost_center_id: string | null
  cost_center_name: string
}

export interface BudgetLineIn {
  account_id: string
  period_date: string
  amount: number
  notes: string
  /** خالی یعنی بودجه‌ی کلِ کسب‌وکار؛ پرشده یعنی بودجه‌ی همان مرکز. */
  cost_center_id?: string | null
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

export const fetchBudgetLines = (token: string, costCenterId?: string) =>
  authedGet<BudgetLineRecord[]>(
    token,
    costCenterId ? `/api/budgets?cost_center_id=${costCenterId}` : '/api/budgets',
  )

export const createBudgetLine = (token: string, data: BudgetLineIn) =>
  authedSend<BudgetLineRecord>(token, 'POST', '/api/budgets', data)

export const updateBudgetLine = (token: string, id: string, data: BudgetLineIn) =>
  authedSend<BudgetLineRecord>(token, 'PUT', `/api/budgets/${id}`, data)

export const deleteBudgetLine = (token: string, id: string) =>
  authedDelete(token, `/api/budgets/${id}`)

export const fetchBudgetReport = (
  token: string,
  dateFrom?: string,
  dateTo?: string,
  costCenterId?: string,
) => {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  if (costCenterId) qs.set('cost_center_id', costCenterId)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<BudgetReport>(token, `/api/budgets/report${suffix}`)
}

/* ── ماژولِ «شرکت»: گروهِ طرف‌حساب، محلِ جغرافیایی، فردِ مرتبط ─────────────── */

export interface ContactGroupRecord {
  id: string
  name: string
  code: string
  notes: string
  is_active: boolean
  contact_count: number
}

export interface ContactGroupIn {
  name: string
  code?: string
  notes?: string
  is_active?: boolean
}

export const fetchContactGroups = (token: string) =>
  authedGet<ContactGroupRecord[]>(token, '/api/company/groups')

export const createContactGroup = (token: string, data: ContactGroupIn) =>
  authedSend<ContactGroupRecord>(token, 'POST', '/api/company/groups', data)

export const updateContactGroup = (token: string, id: string, data: ContactGroupIn) =>
  authedSend<ContactGroupRecord>(token, 'PUT', `/api/company/groups/${id}`, data)

export const deleteContactGroup = (token: string, id: string) =>
  authedDelete(token, `/api/company/groups/${id}`)

/** سطح‌های درختِ جغرافیایی — کلیدها با GEO_KINDS سمتِ سرور یکی‌اند. */
export const GEO_KIND_LABELS: Record<string, string> = {
  country: 'کشور',
  province: 'استان',
  city: 'شهر',
  district: 'منطقه',
}

export interface GeoLocationRecord {
  id: string
  name: string
  kind: string
  code: string
  parent_id: string | null
  is_active: boolean
  path: string
  contact_count: number
}

export interface GeoLocationIn {
  name: string
  kind: string
  code?: string
  parent_id?: string | null
  is_active?: boolean
}

export const fetchGeoLocations = (token: string) =>
  authedGet<GeoLocationRecord[]>(token, '/api/company/locations')

export const createGeoLocation = (token: string, data: GeoLocationIn) =>
  authedSend<GeoLocationRecord>(token, 'POST', '/api/company/locations', data)

export const updateGeoLocation = (token: string, id: string, data: GeoLocationIn) =>
  authedSend<GeoLocationRecord>(token, 'PUT', `/api/company/locations/${id}`, data)

export const deleteGeoLocation = (token: string, id: string) =>
  authedDelete(token, `/api/company/locations/${id}`)

export interface RelatedPersonRecord {
  id: string
  contact_id: string
  name: string
  role: string
  phone: string
  email: string
  is_primary: boolean
  is_active: boolean
  notes: string
  contact_name: string
}

export interface RelatedPersonIn {
  contact_id: string
  name: string
  role?: string
  phone?: string
  email?: string
  is_primary?: boolean
  is_active?: boolean
  notes?: string
}

export const fetchRelatedPersons = (token: string, contactId?: string) =>
  authedGet<RelatedPersonRecord[]>(
    token,
    `/api/company/persons${contactId ? `?contact_id=${contactId}` : ''}`,
  )

export const createRelatedPerson = (token: string, data: RelatedPersonIn) =>
  authedSend<RelatedPersonRecord>(token, 'POST', '/api/company/persons', data)

export const updateRelatedPerson = (token: string, id: string, data: RelatedPersonIn) =>
  authedSend<RelatedPersonRecord>(token, 'PUT', `/api/company/persons/${id}`, data)

export const deleteRelatedPerson = (token: string, id: string) =>
  authedDelete(token, `/api/company/persons/${id}`)

/* ── گزارش‌ساز: تعریفِ گزارش‌های ذخیره‌شده ────────────────────────────────── */

export interface SavedReportRecord {
  id: string
  name: string
  description: string
  source: string
  config: Record<string, unknown>
  is_pinned: boolean
}

export interface SavedReportIn {
  name: string
  description?: string
  source: string
  config: Record<string, unknown>
  is_pinned?: boolean
}

export const fetchSavedReports = (token: string) =>
  authedGet<SavedReportRecord[]>(token, '/api/company/reports')

export const createSavedReport = (token: string, data: SavedReportIn) =>
  authedSend<SavedReportRecord>(token, 'POST', '/api/company/reports', data)

export const updateSavedReport = (token: string, id: string, data: SavedReportIn) =>
  authedSend<SavedReportRecord>(token, 'PUT', `/api/company/reports/${id}`, data)

export const deleteSavedReport = (token: string, id: string) =>
  authedDelete(token, `/api/company/reports/${id}`)

/* ── دفترِ ردِ حسابرسی: رویدادها و خلاصه‌ی استفاده ────────────────────────── */

export interface AuditEntryRecord {
  id: string
  at: string
  actor_email: string
  action: string
  entity_type: string
  entity_id: string
  summary: string
}

export const fetchAuditEntries = (token: string) =>
  authedGetAll<AuditEntryRecord>(token, '/api/audit')

export interface AuditUsageRow {
  key: string
  count: number
}

export interface AuditSummary {
  days: number
  total: number
  by_actor: AuditUsageRow[]
  by_action: AuditUsageRow[]
  by_entity: AuditUsageRow[]
  by_day: AuditUsageRow[]
}

export const fetchAuditSummary = (token: string, days: number) =>
  authedGet<AuditSummary>(token, `/api/audit/summary?days=${days}`)

// --- مراکز هزینه / پروژه ----------------------------------------------------------

export const COST_CENTER_KINDS = [
  { value: 'project', label: 'پروژه' },
  { value: 'branch', label: 'شعبه' },
  { value: 'department', label: 'واحد سازمانی' },
  { value: 'product', label: 'خط محصول' },
  { value: 'contract', label: 'قرارداد' },
  { value: 'other', label: 'سایر' },
] as const

export const costCenterKindLabel = (kind: string) =>
  COST_CENTER_KINDS.find((k) => k.value === kind)?.label ?? kind

export interface CostCenterRecord {
  id: string
  code: string
  name: string
  kind: string
  parent_id: string | null
  manager: string
  start_date: string | null
  end_date: string | null
  is_active: boolean
  notes: string
  /** عمق و مسیر را سرور می‌سازد؛ کلاینت درخت را دوباره نمی‌پیماید. */
  depth: number
  path: string
  child_count: number
}

export interface CostCenterIn {
  code: string
  name: string
  kind: string
  parent_id: string | null
  manager: string
  start_date: string | null
  end_date: string | null
  is_active: boolean
  notes: string
}

export interface CostCenterAccountRow {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  amount: string
  share_pct: string
}

export interface CostCenterMonthPoint {
  label: string
  income: string
  expense: string
  profit: string
}

export interface CostCenterChildRow {
  id: string
  code: string
  name: string
  kind: string
  is_active: boolean
  income: string
  expense: string
  profit: string
}

export interface CostCenterAnalysis {
  center: CostCenterRecord
  date_from: string | null
  date_to: string | null
  include_children: boolean
  income: string
  expense: string
  profit: string
  margin_pct: string | null
  budget_income: string
  budget_expense: string
  budget_profit: string
  profit_variance: string | null
  has_budget: boolean
  entry_count: number
  first_entry_date: string | null
  last_entry_date: string | null
  elapsed_pct: string | null
  income_accounts: CostCenterAccountRow[]
  expense_accounts: CostCenterAccountRow[]
  monthly: CostCenterMonthPoint[]
  children: CostCenterChildRow[]
}

export interface CostCenterLedgerRow {
  line_id: string
  entry_id: string
  entry_number: number | null
  entry_date: string
  description: string
  source_type: string
  account_code: string
  account_name: string
  account_type: string
  debit: string
  credit: string
  cost_center_id: string
  cost_center_name: string
}

export interface CostCenterReportRow {
  cost_center_id: string | null
  cost_center_code: string
  cost_center_name: string
  kind: string
  parent_id: string | null
  depth: number
  path: string
  is_active: boolean
  income: string
  expense: string
  profit: string
  rollup_income: string
  rollup_expense: string
  rollup_profit: string
  budget_income: string
  budget_expense: string
  profit_variance: string | null
  entry_count: number
}

export interface CostCenterReport {
  date_from: string | null
  date_to: string | null
  rows: CostCenterReportRow[]
  total_income: string
  total_expense: string
  total_profit: string
  untagged_share_pct: string
}

export const fetchCostCenters = (token: string) =>
  authedGet<CostCenterRecord[]>(token, '/api/cost-centers')

export const createCostCenter = (token: string, data: CostCenterIn) =>
  authedSend<CostCenterRecord>(token, 'POST', '/api/cost-centers', data)

export const updateCostCenter = (token: string, id: string, data: CostCenterIn) =>
  authedSend<CostCenterRecord>(token, 'PUT', `/api/cost-centers/${id}`, data)

export const deleteCostCenter = (token: string, id: string) =>
  authedDelete(token, `/api/cost-centers/${id}`)

function rangeQuery(dateFrom?: string, dateTo?: string, extra?: Record<string, string>) {
  const qs = new URLSearchParams()
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  for (const [k, v] of Object.entries(extra ?? {})) qs.set(k, v)
  return qs.toString() ? `?${qs}` : ''
}

export const fetchCostCenterReport = (token: string, dateFrom?: string, dateTo?: string) =>
  authedGet<CostCenterReport>(token, `/api/cost-centers/report${rangeQuery(dateFrom, dateTo)}`)

export const fetchCostCenterAnalysis = (
  token: string,
  id: string,
  dateFrom?: string,
  dateTo?: string,
  includeChildren = true,
) =>
  authedGet<CostCenterAnalysis>(
    token,
    `/api/cost-centers/${id}/analysis${rangeQuery(dateFrom, dateTo, {
      include_children: String(includeChildren),
    })}`,
  )

export const fetchCostCenterLedger = (
  token: string,
  id: string,
  dateFrom?: string,
  dateTo?: string,
  includeChildren = true,
  limit = 50,
) =>
  authedGet<CostCenterLedgerRow[]>(
    token,
    `/api/cost-centers/${id}/ledger${rangeQuery(dateFrom, dateTo, {
      include_children: String(includeChildren),
      limit: String(limit),
    })}`,
  )

export const fetchCostCenterBudget = (token: string, id: string) =>
  authedGet<BudgetLineRecord[]>(token, `/api/cost-centers/${id}/budget`)

export const setCostCenterBudget = (token: string, id: string, data: BudgetLineIn) =>
  authedSend<BudgetLineRecord>(token, 'POST', `/api/cost-centers/${id}/budget`, data)

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

export const fetchInventoryReport = (token: string, asOf?: string) =>
  authedGet<InventoryReport>(token, `/api/reports/inventory${asOf ? `?as_of=${asOf}` : ''}`)

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
  /** گواهیِ امضا هم فقط وجود/نبودش گزارش می‌شود. */
  has_certificate: boolean
  /** شناسه‌ی پیش‌فرضِ کالا/خدمتِ ۱۳رقمی (وقتی کالایی کدِ خودش را ندارد). */
  default_stuff_id: string
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
  /** خالی = گواهیِ ذخیره‌شده دست‌نخورده بماند. */
  certificate_pem?: string
  /** شناسه‌ی پیش‌فرضِ کالا/خدمتِ ۱۳رقمی برای ردیف‌هایی که کدِ خودشان را ندارند. */
  default_stuff_id: string
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

export interface MoadianConnectionTest {
  ok: boolean
  environment: string
  status_code: number | null
  message: string
  server_key_id: string | null
}

export const fetchMoadianSettings = (token: string) =>
  authedGet<MoadianSettingsRecord>(token, '/api/moadian/settings')

export const testMoadianConnection = (token: string) =>
  authedSend<MoadianConnectionTest>(token, 'POST', '/api/moadian/test-connection', {})

export const updateMoadianSettings = (token: string, data: MoadianSettingsIn) =>
  authedSend<MoadianSettingsRecord>(token, 'PUT', '/api/moadian/settings', data)

export const fetchMoadianSubmissions = (token: string) =>
  authedGet<MoadianSubmissionRecord[]>(token, '/api/moadian/submissions')

export const submitInvoiceToMoadian = (token: string, invoiceId: string) =>
  authedSend<MoadianSubmissionRecord>(token, 'POST', `/api/moadian/submit/${invoiceId}`, {})

export const inquireMoadianStatus = (token: string, submissionId: string) =>
  authedSend<MoadianSubmissionRecord>(token, 'POST', `/api/moadian/inquiry/${submissionId}`, {})

// --- کاربران کسب‌وکار، بازیابی و تغییر رمز ----------------------------------------

export type PermissionMap = Record<string, string[]>

export interface Member {
  id: string
  user_id: string
  name: string
  email: string
  role_key: string
  role_name: string
  status: 'active' | 'invited' | 'disabled'
  is_me: boolean
  /** دسترسیِ مؤثر — اختصاصی اگر تنظیم شده باشد، وگرنه مجوزِ نقش. */
  permissions: PermissionMap
  /** دسترسی دستی تنظیم شده و دیگر از نقش پیروی نمی‌کند. */
  custom_permissions: boolean
}

export interface RoleInfo {
  key: string
  name: string
  permissions: PermissionMap
  member_count: number
}

export interface PermissionModule {
  key: string
  label: string
  hint: string | null
  actions: { key: string; label: string }[]
}

export interface MemberList {
  members: Member[]
  seats: { used: number; limit: number | null }
}

export const fetchMembers = (token: string) => authedGet<MemberList>(token, '/api/members')

export const fetchRoles = (token: string) => authedGet<RoleInfo[]>(token, '/api/members/roles')

export const fetchPermissionModules = (token: string) =>
  authedGet<PermissionModule[]>(token, '/api/members/permission-modules')

export const inviteMember = (
  token: string,
  data: { email: string; name: string; role_key: string; permissions?: PermissionMap | null },
) => authedSend<{ member: Member; email_sent: boolean }>(token, 'POST', '/api/members/invite', data)

export const resendInvite = (token: string, membershipId: string) =>
  authedSend<{ member: Member; email_sent: boolean }>(
    token, 'POST', `/api/members/${membershipId}/resend-invite`, {},
  )

/** `null` یعنی بازگشت به مجوزِ نقش. */
export const setMemberPermissions = (token: string, membershipId: string, permissions: PermissionMap | null) =>
  authedSend<Member>(token, 'PATCH', `/api/members/${membershipId}/permissions`, { permissions })

export const changeMemberRole = (token: string, membershipId: string, roleKey: string) =>
  authedSend<Member>(token, 'PATCH', `/api/members/${membershipId}/role`, { role_key: roleKey })

export const setMemberActive = (token: string, membershipId: string, active: boolean) =>
  authedSend<Member>(token, 'PATCH', `/api/members/${membershipId}/status`, { active })

export const changePassword = (token: string, currentPassword: string, newPassword: string) =>
  authedSend<{ access_token: string }>(token, 'POST', '/api/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })

/** ویرایشِ پروفایلِ خودِ کاربر. تغییرِ ایمیل به `current_password` نیاز دارد. */
export interface ProfileUpdate {
  name?: string
  phone?: string | null
  email?: string
  current_password?: string
}

export const updateProfile = (token: string, patch: ProfileUpdate) =>
  authedSend<MeResponse>(token, 'PATCH', '/api/auth/me', patch)

/** نتیجه‌ی ارسالِ کدِ تأییدِ شماره. `phone` ماسک‌شده است (۰۹۱۲****۵۶۷). */
export interface PhoneCodeResult {
  sent: boolean
  phone: string
  expires_in: number
}

/** کدِ تأییدِ شماره را پیامک می‌کند (شماره را هم تأییدنشده روی حساب ذخیره می‌کند). */
export const sendPhoneCode = (token: string, phone: string) =>
  authedSend<PhoneCodeResult>(token, 'POST', '/api/auth/phone/send-code', { phone })

/** کدِ تأیید را می‌سنجد؛ در صورتِ درستی، `me`ی به‌روز (با phone_verified=true) برمی‌گرداند. */
export const verifyPhoneCode = (token: string, code: string) =>
  authedSend<MeResponse>(token, 'POST', '/api/auth/phone/verify', { code })

/** تغییرِ نامِ کسب‌وکارِ جاری — فقط مالک؛ سرور غیرمالک را با ۴۰۳ رد می‌کند. */
export const updateBusinessName = (token: string, name: string) =>
  authedSend<MeResponse>(token, 'PATCH', '/api/auth/business', { name })

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

/** بازیابیِ رمز با پیامک — گامِ اول: کدِ ۶رقمی به شماره‌ی تأییدشده می‌رود. پاسخ عمداً
 *  یکنواخت است (وجود/نبودِ شماره را لو نمی‌دهد). */
export const requestPasswordResetSms = (phone: string) =>
  anonPost<{ detail: string }>('/api/auth/forgot-password/sms', { phone })

/** گامِ دوم: کد + رمزِ تازه را می‌فرستد و در صورتِ درستی توکنِ ورود برمی‌گرداند. */
export const resetPasswordSms = (phone: string, code: string, password: string) =>
  anonPost<{ access_token: string }>('/api/auth/reset-password/sms', { phone, code, password })

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

export const printSalesQuotation = (token: string, quotationId: string) =>
  openInvoicePrintView(token, `/api/sales-quotations/${quotationId}/print`)

export const printSalesReturn = (token: string, returnId: string) =>
  openInvoicePrintView(token, `/api/sales-returns/${returnId}/print`)

export const printPurchaseReturn = (token: string, returnId: string) =>
  openInvoicePrintView(token, `/api/purchase-returns/${returnId}/print`)

/** فایل PDF فاکتور را با احراز هویت می‌گیرد و دانلود می‌کند.
 *
 * چون اندپوینت توکن می‌خواهد نمی‌شود صرفاً لینک داد؛ blob را با هدر می‌گیریم و با یک
 * لینکِ موقتِ Blob دانلود می‌کنیم — در الکترون (کرومیوم) و مرورگر هر دو کار می‌کند.
 */
export async function downloadInvoicePdf(token: string, path: string, filename: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`دریافت PDF ناموفق بود (${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const downloadSalesInvoicePdf = (token: string, invoiceId: string, number: number | null) =>
  downloadInvoicePdf(token, `/api/sales-invoices/${invoiceId}/pdf`, `فاکتور-فروش-${number ?? invoiceId}.pdf`)

export const downloadPurchaseInvoicePdf = (token: string, invoiceId: string, number: number | null) =>
  downloadInvoicePdf(token, `/api/purchase-invoices/${invoiceId}/pdf`, `فاکتور-خرید-${number ?? invoiceId}.pdf`)

export const downloadSalesQuotationPdf = (token: string, quotationId: string, number: number | null) =>
  downloadInvoicePdf(token, `/api/sales-quotations/${quotationId}/pdf`, `پیش‌فاکتور-${number ?? quotationId}.pdf`)

// --- انبارگردانی (شمارش فیزیکی موجودی) ---

export type StockCountStatus = 'open' | 'posted' | 'cancelled'

export interface StockCountSummary {
  id: string
  warehouse_id: string
  warehouse_name: string
  count_date: string
  status: StockCountStatus
  notes: string
  posted_at: string | null
  created_at: string | null
  line_count: number
}

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

export interface StockCountSession {
  id: string
  warehouse_id: string
  warehouse_name: string
  count_date: string
  status: StockCountStatus
  notes: string
  journal_entry_id: string | null
  posted_at: string | null
  created_at: string | null
  line_count: number
  variance_line_count: number
  total_variance_value: string
  lines: StockCountLine[]
}

export const fetchStockCounts = (token: string) =>
  authedGet<StockCountSummary[]>(token, '/api/stock-counts')

export const fetchStockCount = (token: string, id: string) =>
  authedGet<StockCountSession>(token, `/api/stock-counts/${id}`)

export const createStockCount = (
  token: string,
  data: { warehouse_id: string; count_date: string; notes: string },
) => authedSend<StockCountSession>(token, 'POST', '/api/stock-counts', data)

export const setStockCounts = (
  token: string,
  id: string,
  lines: { line_id: string; counted_qty: number }[],
) => authedSend<StockCountSession>(token, 'PUT', `/api/stock-counts/${id}/counts`, { lines })

export const postStockCount = (token: string, id: string) =>
  authedSend<StockCountSession>(token, 'POST', `/api/stock-counts/${id}/post`, {})

export const cancelStockCount = (token: string, id: string) =>
  authedSend<StockCountSession>(token, 'POST', `/api/stock-counts/${id}/cancel`, {})

// --- اسناد تکرارشونده ---

export type RecurringFrequency = 'weekly' | 'monthly' | 'yearly'

export interface RecurringLine {
  id: string
  account_id: string
  account_code: string
  account_name: string
  debit: string
  credit: string
  description: string
}

export interface RecurringEntry {
  id: string
  title: string
  description: string
  frequency: RecurringFrequency
  interval: number
  start_date: string
  end_date: string | null
  next_run_date: string
  last_run_date: string | null
  is_active: boolean
  cost_center_id: string | null
  created_at: string | null
  is_due: boolean
  amount: string
  lines: RecurringLine[]
}

export interface RecurringEntryInput {
  title: string
  description: string
  frequency: RecurringFrequency
  interval: number
  start_date: string
  end_date: string | null
  cost_center_id: string | null
  lines: { account_id: string; debit: number; credit: number; description?: string }[]
}

export interface RecurringRunResult {
  generated: number
  skipped: number
  entries: { id: string; number: number | null; entry_date: string; title: string }[]
}

export const fetchRecurringEntries = (token: string) =>
  authedGet<RecurringEntry[]>(token, '/api/recurring-entries')

export const createRecurringEntry = (token: string, data: RecurringEntryInput) =>
  authedSend<RecurringEntry>(token, 'POST', '/api/recurring-entries', data)

export const updateRecurringEntry = (token: string, id: string, data: RecurringEntryInput) =>
  authedSend<RecurringEntry>(token, 'PUT', `/api/recurring-entries/${id}`, data)

export const setRecurringActive = (token: string, id: string, isActive: boolean) =>
  authedSend<RecurringEntry>(token, 'POST', `/api/recurring-entries/${id}/set-active?is_active=${isActive}`, {})

export const deleteRecurringEntry = (token: string, id: string) =>
  authedDelete(token, `/api/recurring-entries/${id}`)

export const runRecurringDue = (token: string) =>
  authedSend<RecurringRunResult>(token, 'POST', '/api/recurring-entries/run', {})

export const runRecurringOne = (token: string, id: string) =>
  authedSend<RecurringRunResult>(token, 'POST', `/api/recurring-entries/${id}/run`, {})

// --- مرکز هشدارها ---

export type AlertCategory = 'check' | 'receivable' | 'credit' | 'recurring' | 'calendar' | 'stock' | 'installment'
export type AlertSeverity = 'danger' | 'warning' | 'info'

export interface AlertItem {
  category: AlertCategory
  severity: AlertSeverity
  title: string
  detail: string
  alert_date: string | null
  amount: string | null
  ref_id: string | null
}

export interface Alerts {
  as_of: string
  total: number
  counts: Record<string, number>
  items: AlertItem[]
}

export const fetchAlerts = (token: string) => authedGet<Alerts>(token, '/api/alerts')

// --- مزایای حقوق (عیدی/سنوات/مرخصی) ---

export interface BenefitRow {
  employee_id: string
  employee_name: string
  base_salary: string
  eidi: string
  severance: string
  leave_entitled: string
  leave_used: string
  leave_remaining: string
  leave_value: string
}

export interface BenefitsReport {
  year: number
  as_of: string
  min_base_wage: string
  annual_leave_days: number
  rows: BenefitRow[]
  total_eidi: string
  total_severance: string
  total_leave_value: string
}

export interface LeaveRecordRow {
  id: string
  employee_id: string
  leave_date: string
  days: string
  note: string
}

export interface BenefitIssueResult {
  kind: string
  amount: string
  journal_entry_number: number | null
}

export const fetchBenefits = (token: string, year: number, asOf?: string) =>
  authedGet<BenefitsReport>(token, `/api/payroll/benefits?year=${year}${asOf ? `&as_of=${asOf}` : ''}`)

export const setBenefitSettings = (
  token: string,
  data: { year: number; min_base_wage: number; annual_leave_days: number },
) => authedSend<{ year: number; min_base_wage: string; annual_leave_days: number }>(token, 'PUT', '/api/payroll/benefit-settings', data)

export const fetchLeaveRecords = (token: string, employeeId?: string) =>
  authedGet<LeaveRecordRow[]>(token, `/api/payroll/leave${employeeId ? `?employee_id=${employeeId}` : ''}`)

export const recordLeave = (
  token: string,
  data: { employee_id: string; leave_date: string; days: number; note: string },
) => authedSend<LeaveRecordRow>(token, 'POST', '/api/payroll/leave', data)

export const issueEidi = (token: string, year: number) =>
  authedSend<BenefitIssueResult>(token, 'POST', `/api/payroll/eidi?year=${year}`, {})

export const issueSeverance = (token: string, employeeId: string, asOf?: string) =>
  authedSend<BenefitIssueResult>(token, 'POST', `/api/payroll/severance/${employeeId}${asOf ? `?as_of=${asOf}` : ''}`, {})

export const issueLeavePayout = (token: string, employeeId: string, year: number) =>
  authedSend<BenefitIssueResult>(token, 'POST', `/api/payroll/leave-payout/${employeeId}?year=${year}`, {})

// --- چندارزی ---

export interface Currency {
  id: string
  code: string
  name: string
  symbol: string
}

export interface ExchangeRate {
  id: string
  currency_code: string
  rate_date: string
  rate: string
}

export interface LatestRate {
  currency_code: string
  rate: string | null
  rate_date: string | null
}

export const fetchCurrencies = (token: string) => authedGet<Currency[]>(token, '/api/currencies')

export const createCurrency = (token: string, data: { code: string; name: string; symbol: string }) =>
  authedSend<Currency>(token, 'POST', '/api/currencies', data)

export const deleteCurrency = (token: string, id: string) => authedDelete(token, `/api/currencies/${id}`)

export const fetchRates = (token: string, currencyCode?: string) =>
  authedGet<ExchangeRate[]>(token, `/api/currencies/rates${currencyCode ? `?currency_code=${currencyCode}` : ''}`)

export const upsertRate = (token: string, data: { currency_code: string; rate_date: string; rate: number }) =>
  authedSend<ExchangeRate>(token, 'POST', '/api/currencies/rates', data)

export const fetchLatestRate = (token: string, currencyCode: string) =>
  authedGet<LatestRate>(token, `/api/currencies/rates/latest?currency_code=${currencyCode}`)

// ── باشگاه مشتریان / CRM ─────────────────────────────────────────────
export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'won' | 'lost'
export type ActivityKind = 'call' | 'meeting' | 'note' | 'task'

export interface LeadRecord {
  id: string
  name: string
  phone: string
  email: string
  company: string
  source: string
  status: LeadStatus
  estimated_value: string
  notes: string
  next_action_date: string | null
  assigned_to_id: string | null
  converted_contact_id: string | null
}

export interface LeadInput {
  name: string
  phone?: string
  email?: string
  company?: string
  source?: string
  status?: LeadStatus
  estimated_value?: number
  notes?: string
  next_action_date?: string | null
}

export interface CrmActivityRecord {
  id: string
  kind: ActivityKind
  subject: string
  body: string
  activity_date: string
  done: boolean
  lead_id: string | null
  contact_id: string | null
  assigned_to_id: string | null
}

export interface LoyaltyBalance {
  contact_id: string
  contact_name: string
  balance: number
}

export interface LoyaltyTxnRecord {
  id: string
  contact_id: string
  points: number
  reason: string
  txn_date: string
}

export const fetchLeads = (token: string, status?: string) =>
  authedGet<LeadRecord[]>(token, `/api/crm/leads${status ? `?status=${encodeURIComponent(status)}` : ''}`)
export const createLead = (token: string, data: LeadInput) =>
  authedSend<LeadRecord>(token, 'POST', '/api/crm/leads', data)
export const updateLead = (token: string, id: string, data: Partial<LeadInput>) =>
  authedSend<LeadRecord>(token, 'PATCH', `/api/crm/leads/${id}`, data)
export const deleteLead = (token: string, id: string) => authedDelete(token, `/api/crm/leads/${id}`)
export const convertLead = (token: string, id: string) =>
  authedSend<{ contact_id: string }>(token, 'POST', `/api/crm/leads/${id}/convert`, {})

export const fetchCrmActivities = (
  token: string,
  params?: { lead_id?: string; contact_id?: string; done?: boolean },
) => {
  const qs = new URLSearchParams()
  if (params?.lead_id) qs.set('lead_id', params.lead_id)
  if (params?.contact_id) qs.set('contact_id', params.contact_id)
  if (params?.done !== undefined) qs.set('done', String(params.done))
  const q = qs.toString()
  return authedGet<CrmActivityRecord[]>(token, `/api/crm/activities${q ? `?${q}` : ''}`)
}
export const createCrmActivity = (
  token: string,
  data: { kind: ActivityKind; subject: string; body?: string; activity_date: string; lead_id?: string | null; contact_id?: string | null },
) => authedSend<CrmActivityRecord>(token, 'POST', '/api/crm/activities', data)
export const updateCrmActivity = (token: string, id: string, data: { done?: boolean; subject?: string; body?: string; activity_date?: string }) =>
  authedSend<CrmActivityRecord>(token, 'PATCH', `/api/crm/activities/${id}`, data)
export const deleteCrmActivity = (token: string, id: string) => authedDelete(token, `/api/crm/activities/${id}`)

export const fetchLoyaltyBalances = (token: string) =>
  authedGet<LoyaltyBalance[]>(token, '/api/crm/loyalty')

export interface LoyaltySettings {
  is_enabled: boolean
  amount_per_point: string
  tier_basis: 'points' | 'spend'
  tier_discount_auto: boolean
  birthday_gift_points: number
}
export const fetchLoyaltySettings = (token: string) =>
  authedGet<LoyaltySettings>(token, '/api/crm/loyalty/settings')
export const setLoyaltySettings = (
  token: string,
  data: {
    is_enabled: boolean
    amount_per_point: number
    tier_basis?: 'points' | 'spend'
    tier_discount_auto?: boolean
    birthday_gift_points?: number
  },
) => authedSend<LoyaltySettings>(token, 'PUT', '/api/crm/loyalty/settings', data)
export const addLoyaltyTxn = (
  token: string,
  data: { contact_id: string; points: number; reason?: string; txn_date: string },
) => authedSend<LoyaltyTxnRecord>(token, 'POST', '/api/crm/loyalty/transactions', data)

/** گردشِ امتیازِ یک مشتری (کسب/مصرف)، تازه‌ترین اول — برای «تاریخچه‌ی امتیاز». */
export const fetchLoyaltyTransactions = (token: string, contactId?: string) =>
  authedGet<LoyaltyTxnRecord[]>(token, `/api/crm/loyalty/transactions${contactId ? `?contact_id=${contactId}` : ''}`)

// ── ابزارهای پیشرفته‌ی باشگاه ────────────────────────────────────────
export type CustomerSegment = 'champion' | 'loyal' | 'at_risk' | 'new' | 'dormant' | 'regular'
export interface SegmentCustomer {
  contact_id: string
  contact_name: string
  recency_days: number
  frequency: number
  monetary: string
  last_purchase: string | null
  r: number
  f: number
  m: number
  segment: CustomerSegment
}
export interface SegmentSummaryRow {
  segment: CustomerSegment
  count: number
  monetary: string
}
export interface RfmResult {
  customers: SegmentCustomer[]
  summary: SegmentSummaryRow[]
  total_customers: number
}
export const fetchSegments = (token: string) => authedGet<RfmResult>(token, '/api/crm/segments')

export interface LoyaltyTier {
  id: string
  name: string
  threshold: string
  discount_percent: string
  sort_order: number
}
export interface TierInput {
  name: string
  threshold: number
  discount_percent: number
  sort_order?: number
}
export const fetchTiers = (token: string) => authedGet<LoyaltyTier[]>(token, '/api/crm/loyalty/tiers')
export const createTier = (token: string, data: TierInput) =>
  authedSend<LoyaltyTier>(token, 'POST', '/api/crm/loyalty/tiers', data)
export const updateTier = (token: string, id: string, data: TierInput) =>
  authedSend<LoyaltyTier>(token, 'PUT', `/api/crm/loyalty/tiers/${id}`, data)
export const deleteTier = (token: string, id: string) => authedDelete(token, `/api/crm/loyalty/tiers/${id}`)

export interface TierMember {
  contact_id: string
  contact_name: string
  value: string
  tier_id: string
  tier_name: string
  discount_percent: string
}
export const fetchTierMembers = (token: string) =>
  authedGet<TierMember[]>(token, '/api/crm/loyalty/tier-members')
export interface ContactTier {
  basis: 'points' | 'spend'
  value: string
  tier_id: string | null
  tier_name: string | null
  discount_percent: string
}
export const fetchContactTier = (token: string, contactId: string) =>
  authedGet<ContactTier>(token, `/api/crm/loyalty/tier/${contactId}`)

export type RewardKind = 'discount' | 'gift' | 'other'
export interface LoyaltyReward {
  id: string
  name: string
  points_cost: number
  kind: RewardKind
  value: string
  is_active: boolean
}
export interface RewardInput {
  name: string
  points_cost: number
  kind: RewardKind
  value: string
  is_active: boolean
}
export const fetchRewards = (token: string) => authedGet<LoyaltyReward[]>(token, '/api/crm/loyalty/rewards')
export const createReward = (token: string, data: RewardInput) =>
  authedSend<LoyaltyReward>(token, 'POST', '/api/crm/loyalty/rewards', data)
export const updateReward = (token: string, id: string, data: RewardInput) =>
  authedSend<LoyaltyReward>(token, 'PUT', `/api/crm/loyalty/rewards/${id}`, data)
export const deleteReward = (token: string, id: string) => authedDelete(token, `/api/crm/loyalty/rewards/${id}`)
export const redeemReward = (token: string, data: { contact_id: string; reward_id: string; txn_date?: string }) =>
  authedSend<LoyaltyTxnRecord>(token, 'POST', '/api/crm/loyalty/redeem', data)

export interface BirthdayRow {
  contact_id: string
  contact_name: string
  birthday: string
  next_birthday: string
  days_until: number
  turning_age: number
}
export const fetchBirthdays = (token: string, days = 30) =>
  authedGet<BirthdayRow[]>(token, `/api/crm/birthdays?days=${days}`)

// ── تولید و بهای تمام‌شده (BOM) ──────────────────────────────────────
export interface BomLineRecord {
  id: string
  component_item_id: string
  qty: string
}
export interface BomRecord {
  id: string
  finished_item_id: string
  name: string
  yield_qty: string
  is_active: boolean
  notes: string
  lines: BomLineRecord[]
}
export interface ProductionOrderLineRecord {
  component_item_id: string
  qty: string
  unit_cost: string
}
export interface ProductionOrderRecord {
  id: string
  number: number | null
  bom_id: string
  finished_item_id: string
  warehouse_id: string
  production_date: string
  qty_produced: string
  component_cost: string
  overhead_cost: string
  unit_cost: string
  lines: ProductionOrderLineRecord[]
}

export interface BomInput {
  finished_item_id: string
  name?: string
  yield_qty?: number
  notes?: string
  lines: { component_item_id: string; qty: number }[]
}

export const fetchBoms = (token: string) => authedGet<BomRecord[]>(token, '/api/boms')
export const createBom = (token: string, data: BomInput) => authedSend<BomRecord>(token, 'POST', '/api/boms', data)
export const updateBom = (token: string, id: string, patch: Partial<BomInput> & { is_active?: boolean }) =>
  authedSend<BomRecord>(token, 'PATCH', `/api/boms/${id}`, patch)
export const deleteBom = (token: string, id: string) => authedDelete(token, `/api/boms/${id}`)

export const fetchProductionOrders = (token: string) => authedGet<ProductionOrderRecord[]>(token, '/api/production-orders')
export const createProductionOrder = (
  token: string,
  data: { bom_id: string; warehouse_id: string; production_date: string; qty_produced: number; overhead_cost?: number },
) => authedSend<ProductionOrderRecord>(token, 'POST', '/api/production-orders', data)

// ── انبار پیشرفته: لیستِ قیمت و بچ/انقضا ─────────────────────────────
export interface PriceListRecord {
  id: string
  name: string
  is_active: boolean
  notes: string
}
export interface PriceListItemRecord {
  id: string
  item_id: string
  price: string
}
export interface StockBatchRecord {
  id: string
  item_id: string
  warehouse_id: string
  batch_number: string
  expiry_date: string | null
  qty: string
  received_qty: string
  unit_cost: string
  consumer_price: string
  production_date: string | null
  source_type: string // purchase_invoice | manual | marketplace
  source_id: string | null
  received_date: string
  notes: string
  defect_qty: string
  serial_count: number
}

export interface BatchSerialRecord {
  id: string
  batch_id: string
  serial: string
  status: string // ok | defect
  notes: string
}

export const fetchPriceLists = (token: string) => authedGet<PriceListRecord[]>(token, '/api/price-lists')
export const createPriceList = (token: string, data: { name: string; notes?: string }) =>
  authedSend<PriceListRecord>(token, 'POST', '/api/price-lists', data)
export const updatePriceList = (token: string, id: string, patch: { name?: string; is_active?: boolean; notes?: string }) =>
  authedSend<PriceListRecord>(token, 'PATCH', `/api/price-lists/${id}`, patch)
export const deletePriceList = (token: string, id: string) => authedDelete(token, `/api/price-lists/${id}`)
export const fetchPriceListItems = (token: string, listId: string) =>
  authedGet<PriceListItemRecord[]>(token, `/api/price-lists/${listId}/items`)
export const setPriceListItems = (token: string, listId: string, items: { item_id: string; price: number }[]) =>
  authedSend<PriceListItemRecord[]>(token, 'PUT', `/api/price-lists/${listId}/items`, { items })

export const fetchStockBatches = (token: string, itemId?: string) =>
  authedGet<StockBatchRecord[]>(token, `/api/stock-batches${itemId ? `?item_id=${itemId}` : ''}`)
export const fetchExpiringBatches = (token: string, days = 30) =>
  authedGet<StockBatchRecord[]>(token, `/api/stock-batches/expiring?days=${days}`)
export interface StockBatchIn {
  item_id: string
  warehouse_id: string
  batch_number: string
  expiry_date?: string | null
  production_date?: string | null
  qty?: number
  unit_cost?: number
  consumer_price?: number
  received_date: string
  notes?: string
}
export const createStockBatch = (token: string, data: StockBatchIn) =>
  authedSend<StockBatchRecord>(token, 'POST', '/api/stock-batches', data)
export const updateStockBatch = (token: string, id: string, data: StockBatchIn) =>
  authedSend<StockBatchRecord>(token, 'PATCH', `/api/stock-batches/${id}`, data)
export const deleteStockBatch = (token: string, id: string) => authedDelete(token, `/api/stock-batches/${id}`)

// سریالِ کارتنِ یک بار
export const fetchBatchSerials = (token: string, batchId: string) =>
  authedGet<BatchSerialRecord[]>(token, `/api/stock-batches/${batchId}/serials`)
export const addBatchSerials = (
  token: string,
  batchId: string,
  data: { serials?: string[]; prefix?: string; start?: number; count?: number; pad?: number },
) => authedSend<BatchSerialRecord[]>(token, 'POST', `/api/stock-batches/${batchId}/serials`, data)
export const setBatchSerialStatus = (token: string, serialId: string, status: 'ok' | 'defect') =>
  authedSend<BatchSerialRecord>(token, 'PATCH', `/api/stock-batch-serials/${serialId}`, { status })
export const deleteBatchSerial = (token: string, serialId: string) =>
  authedDelete(token, `/api/stock-batch-serials/${serialId}`)

// کسری/معیوب/ضایعاتِ یک بار (از موجودی و حسابداری کم می‌شود)
export const adjustBatch = (
  token: string,
  batchId: string,
  data: { qty: number; reason: 'shortage' | 'defect' | 'wastage'; notes?: string; adjustment_date: string },
) => authedSend<StockBatchRecord>(token, 'POST', `/api/stock-batches/${batchId}/adjust`, data)

// --- بازارِ عمده‌فروشی (پخش‌کننده ↔ فروشگاه) --------------------------------------

export interface MarketplaceSettings {
  display_name: string
  settlement_mode: 'credit' | 'online'
  is_active: boolean
  //: گردشِ کارِ «تحویل با مامور حمل» — ورودِ کالا به انبارِ فروشگاه هنگامِ ثبتِ تحویل.
  require_delivery?: boolean
  return_policy?: string
  return_window_days?: number
}

export interface ListingComponent {
  item_id: string
  item_name: string
  qty: string
}

export interface Listing {
  id: string
  kind: 'single' | 'pack'
  title: string
  code: string
  unit: string
  wholesale_price: string
  consumer_price: string
  currency_code: string
  description: string
  images: string[]
  category: string
  is_published: boolean
  min_order_qty: string
  max_order_qty: string
  daily_order_limit: number
  item_id: string | null
  components: ListingComponent[]
}

export interface ListingIn {
  kind: 'single' | 'pack'
  title: string
  code?: string
  unit?: string
  wholesale_price: number
  consumer_price?: number
  currency_code?: string
  description?: string
  images?: string[]
  category?: string
  is_published?: boolean
  min_order_qty?: number
  max_order_qty?: number
  daily_order_limit?: number
  item_id?: string | null
  components?: { item_id: string; qty: number }[]
}

// سمتِ پخش‌کننده
export const fetchMpSettings = (token: string) =>
  authedGet<MarketplaceSettings>(token, '/api/marketplace/distributor/settings')

export const updateMpSettings = (token: string, data: MarketplaceSettings) =>
  authedSend<MarketplaceSettings>(token, 'PUT', '/api/marketplace/distributor/settings', data)

export const fetchMpListings = (token: string) =>
  authedGet<Listing[]>(token, '/api/marketplace/distributor/listings')

export const createMpListing = (token: string, data: ListingIn) =>
  authedSend<Listing>(token, 'POST', '/api/marketplace/distributor/listings', data)

export const updateMpListing = (token: string, id: string, data: ListingIn) =>
  authedSend<Listing>(token, 'PUT', `/api/marketplace/distributor/listings/${id}`, data)

export const setMpListingPublished = (token: string, id: string, published: boolean) =>
  authedSend<Listing>(token, 'POST', `/api/marketplace/distributor/listings/${id}/publish?is_published=${published}`, {})

export const deleteMpListing = (token: string, id: string) =>
  authedDelete(token, `/api/marketplace/distributor/listings/${id}`)

// --- اتصال‌ها و کاتالوگِ سمتِ فروشگاه (M3) --------------------------------------

export type MpConnectionStatus = 'pending' | 'approved' | 'rejected' | 'blocked'

export interface DistributorCard {
  tenant_id: string
  display_name: string
  connection_status: MpConnectionStatus | null
}

export interface MpMessage {
  id: string
  sender_role: 'distributor' | 'retailer'
  sender_user_id: string | null
  body: string
  created_at: string
}

export interface MpMessagesPage {
  my_role: 'distributor' | 'retailer'
  messages: MpMessage[]
}

export interface MpConnection {
  id: string
  distributor_tenant_id: string
  retailer_tenant_id: string
  distributor_name: string
  retailer_name: string
  status: MpConnectionStatus
  requested_by: 'retailer' | 'distributor'
  // زونِ ارسال (فقط سمتِ پخش‌کننده معنا دارد).
  zone_id: string | null
  zone_name: string | null
  // گفتگو (برای سمتِ بیننده محاسبه می‌شود؛ فقط اتصالِ approved).
  unread_count: number
  last_message_at: string | null
  last_message_preview: string
}

export interface CatalogListing {
  id: string
  distributor_tenant_id: string
  distributor_name: string
  kind: 'single' | 'pack'
  title: string
  code: string
  unit: string
  wholesale_price: string
  consumer_price: string
  currency_code: string
  description: string
  images: string[]
  category: string
  min_order_qty: string
  max_order_qty: string
  daily_order_limit: number
  components: { item_name: string; qty: string }[]
}

// سمتِ پخش‌کننده — اتصال‌ها
export const fetchMpDistributorConnections = (token: string) =>
  authedGet<MpConnection[]>(token, '/api/marketplace/distributor/connections')

export const setMpConnectionStatus = (token: string, id: string, status: 'approved' | 'rejected' | 'blocked') =>
  authedSend<MpConnection>(token, 'POST', `/api/marketplace/distributor/connections/${id}/status`, { status })

// --- زونِ ارسال (پخش‌کننده) --------------------------------------
export interface MpZone {
  id: string
  name: string
  notes: string
  connection_count: number
}
export const fetchMpZones = (token: string) =>
  authedGet<MpZone[]>(token, '/api/marketplace/distributor/zones')
export const createMpZone = (token: string, data: { name: string; notes?: string }) =>
  authedSend<MpZone>(token, 'POST', '/api/marketplace/distributor/zones', data)
export const updateMpZone = (token: string, id: string, data: { name: string; notes?: string }) =>
  authedSend<MpZone>(token, 'PUT', `/api/marketplace/distributor/zones/${id}`, data)
export const deleteMpZone = (token: string, id: string) =>
  authedDelete(token, `/api/marketplace/distributor/zones/${id}`)
export const assignMpConnectionZone = (token: string, connectionId: string, zoneId: string | null) =>
  authedSend<MpConnection>(token, 'POST', `/api/marketplace/distributor/connections/${connectionId}/zone`, { zone_id: zoneId })

// --- مرجوعیِ بازار --------------------------------------
export type MpReturnStatus = 'requested' | 'approved' | 'rejected'
export interface MpReturnLine {
  order_line_id: string
  title: string
  unit_price: string
  qty: string
  line_total: string
}
export interface MpReturn {
  id: string
  order_id: string
  order_number: number
  distributor_tenant_id: string
  retailer_tenant_id: string
  distributor_name: string
  retailer_name: string
  return_number: number
  status: MpReturnStatus
  reason: string
  response_note: string
  total: string
  created_at: string
  lines: MpReturnLine[]
}
export interface MpReturnRequestIn {
  order_id: string
  lines: { order_line_id: string; qty: number }[]
  reason?: string
}
// سمتِ فروشگاه
export const fetchMpRetailerReturns = (token: string) =>
  authedGet<MpReturn[]>(token, '/api/marketplace/retailer/returns')
export const requestMpReturn = (token: string, data: MpReturnRequestIn) =>
  authedSend<MpReturn>(token, 'POST', '/api/marketplace/retailer/returns', data)
// سمتِ پخش‌کننده
export const fetchMpDistributorReturns = (token: string) =>
  authedGet<MpReturn[]>(token, '/api/marketplace/distributor/returns')
export const approveMpReturn = (token: string, id: string) =>
  authedSend<MpReturn>(token, 'POST', `/api/marketplace/distributor/returns/${id}/approve`, {})
export const rejectMpReturn = (token: string, id: string, response_note?: string) =>
  authedSend<MpReturn>(token, 'POST', `/api/marketplace/distributor/returns/${id}/reject`, { response_note: response_note ?? '' })

// سمتِ فروشگاه — کشف/اتصال/کاتالوگ
export const fetchMpDistributors = (token: string) =>
  authedGet<DistributorCard[]>(token, '/api/marketplace/retailer/distributors')

export const fetchMpRetailerConnections = (token: string) =>
  authedGet<MpConnection[]>(token, '/api/marketplace/retailer/connections')

export const requestMpConnection = (token: string, distributor_tenant_id: string) =>
  authedSend<MpConnection>(token, 'POST', '/api/marketplace/retailer/connections', { distributor_tenant_id })

// گفتگوی اتصال (مشترک بین فروشگاه و پخش‌کننده) — رشته‌ی دائم به‌ازای هر اتصالِ approved.
export const fetchMpMessages = (token: string, connectionId: string, afterIso?: string) =>
  authedGet<MpMessagesPage>(
    token,
    `/api/marketplace/connections/${connectionId}/messages${afterIso ? `?after=${encodeURIComponent(afterIso)}` : ''}`,
  )

export const sendMpMessage = (token: string, connectionId: string, body: string) =>
  authedSend<MpMessage>(token, 'POST', `/api/marketplace/connections/${connectionId}/messages`, { body })

// جمعِ پیام‌های خوانده‌نشده‌ی همه‌ی اتصال‌های approved — برای نشانِ نویگیشن.
export const fetchMpUnread = (token: string) => authedGet<number>(token, '/api/marketplace/unread')

export const fetchMpCatalog = (token: string, distributorId?: string) =>
  authedGet<CatalogListing[]>(
    token,
    `/api/marketplace/retailer/catalog${distributorId ? `?distributor_id=${distributorId}` : ''}`,
  )

// --- سفارش‌ها (M4) --------------------------------------------------------------

export type MpOrderStatus = 'placed' | 'confirmed' | 'delivered' | 'rejected' | 'shipped' | 'received' | 'cancelled'

export interface MpOrderLine {
  id: string | null
  listing_id: string | null
  title: string
  image?: string | null
  unit_price: string
  qty: string
  line_total: string
}

export interface MpOrder {
  id: string
  distributor_tenant_id: string
  retailer_tenant_id: string
  distributor_name: string
  retailer_name: string
  order_number: number
  status: MpOrderStatus
  settlement_mode: 'credit' | 'online'
  payment_status: 'unpaid' | 'paid' | 'refunded'
  note: string
  subtotal: string
  total: string
  cash_amount: string
  //: تحویلِ بار (گردشِ کارِ مامور حمل) — تا تحویل ثبت نشده خالی‌اند.
  delivered_at: string | null
  delivered_by_name: string
  return_policy: string
  return_window_days: number
  distributor_sales_invoice_id: string | null
  retailer_purchase_invoice_id: string | null
  lines: MpOrderLine[]
  // گفتگوی سفارش (برای سمتِ بیننده محاسبه می‌شود).
  unread_count: number
  last_message_at: string | null
  last_message_preview: string
}

export interface MpOrderPlaceIn {
  distributor_tenant_id: string
  lines: { listing_id: string; qty: number }[]
  note?: string
}

// سمتِ فروشگاه
export const placeMpOrder = (token: string, data: MpOrderPlaceIn) =>
  authedSend<MpOrder>(token, 'POST', '/api/marketplace/retailer/orders', data)

export const fetchMpRetailerOrders = (token: string) =>
  authedGet<MpOrder[]>(token, '/api/marketplace/retailer/orders')

export const payMpOrder = (token: string, id: string) =>
  authedSend<{ redirect_url: string }>(token, 'POST', `/api/marketplace/retailer/orders/${id}/pay`, {})

// سمتِ پخش‌کننده
export const fetchMpDistributorOrders = (token: string) =>
  authedGet<MpOrder[]>(token, '/api/marketplace/distributor/orders')

export const confirmMpOrder = (token: string, id: string, cashPercent = 0) =>
  authedSend<MpOrder>(token, 'POST', `/api/marketplace/distributor/orders/${id}/confirm`, { cash_percent: cashPercent })

// ثبتِ تحویل توسطِ مامور حمل/انتقال — ورودِ کالا به انبارِ فروشگاه اینجا انجام می‌شود.
export const deliverMpOrder = (token: string, id: string, cashPercent = 0) =>
  authedSend<MpOrder>(token, 'POST', `/api/marketplace/distributor/orders/${id}/deliver`, { cash_percent: cashPercent })

export const rejectMpOrder = (token: string, id: string) =>
  authedSend<MpOrder>(token, 'POST', `/api/marketplace/distributor/orders/${id}/reject`, {})

// گفتگوی زیرِ هر سفارش — رشته‌ی جدا؛ هر دو سمتِ همان سفارش (بدونِ گیتِ وضعیت).
export const fetchMpOrderMessages = (token: string, orderId: string, afterIso?: string) =>
  authedGet<MpMessagesPage>(
    token,
    `/api/marketplace/orders/${orderId}/messages${afterIso ? `?after=${encodeURIComponent(afterIso)}` : ''}`,
  )

export const sendMpOrderMessage = (token: string, orderId: string, body: string) =>
  authedSend<MpMessage>(token, 'POST', `/api/marketplace/orders/${orderId}/messages`, { body })

// ── کمیسیونِ پلتفرم (۲٪) ───────────────────────────────────────────────
export interface MpCommissionPeriod {
  distributor_tenant_id: string
  distributor_name: string
  period: string // "1405-05"
  order_count: number
  total_base: number
  total_amount: number
  pending_amount: number
  settled_amount: number
  status: 'pending' | 'settled'
}

export interface MpCommissionOverview {
  total_amount: number
  pending_amount: number
  settled_amount: number
  distributor_count: number
  rate: number
}

// سوپرادمین (مالکِ سامانه)
export const fetchMpCommissionOverview = (token: string) =>
  authedGet<MpCommissionOverview>(token, '/api/marketplace/admin/commissions/overview')

export const fetchMpCommissions = (token: string) =>
  authedGet<MpCommissionPeriod[]>(token, '/api/marketplace/admin/commissions')

export const settleMpCommission = (
  token: string,
  data: { distributor_tenant_id: string; period: string; note?: string },
) =>
  authedSend<{ distributor_tenant_id: string; period: string; count: number; amount: number }>(
    token,
    'POST',
    '/api/marketplace/admin/commissions/settle',
    data,
  )

// پخش‌کننده — صورتِ کمیسیونِ خودش
export const fetchMyMpCommissions = (token: string) =>
  authedGet<MpCommissionPeriod[]>(token, '/api/marketplace/distributor/commissions')
