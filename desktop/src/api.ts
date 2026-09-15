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

/** بیشترین ردیفی که سرور در یک درخواستِ صفحه‌بندی‌شده می‌دهد (`MAX_LIMIT` سمتِ بک‌اند).
 *  عددِ بزرگ‌تر ۴۲۲ می‌گیرد، نه پاسخِ کوتاه‌ترِ بی‌خطر. */
const SERVER_PAGE_MAX = 200

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

/** مثلِ authedDelete ولی پاسخِ JSON را برمی‌گرداند — برای حذف‌هایی که گزارش می‌دهند. */
async function authedDeleteJson<T>(token: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `حذف ناموفق بود (${res.status})`)
  }
  return res.json()
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
  /** ترکیبِ فروش/خریدِ دوره. برگشت‌ها اینجا نمی‌آیند — ارقامِ بالا خالصِ پس از برگشت‌اند. */
  sales_breakdown: VatBreakdown
  purchase_breakdown: VatBreakdown
  mixed_sales_invoices: MixedVatInvoice[]
  mixed_purchase_invoices: MixedVatInvoice[]
}

/** تفکیکِ پایه‌ی مالیاتی — جوابِ «چقدر فروشِ معاف داشته‌ایم؟». */
export interface VatBreakdown {
  taxable_goods: string
  taxable_services: string
  exempt_goods: string
  exempt_services: string
}

/** فاکتوری که ردیفِ معاف و مشمول را با هم دارد و نرخِ سربرگش غیرصفر است —
 *  یعنی روی ردیفِ معاف هم مالیات گرفته شده. */
export interface MixedVatInvoice {
  invoice_id: string
  number: number | null
  invoice_date: string
  tax_amount: string
  exempt_net: string
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
  /** کدهای کمبودِ هویتِ مالیاتی. خالی = آماده‌ی سامانه. */
  issues: string[]
  invoice_count: number
  gross: string
  discount: string
  net: string
  vat: string
  total: string
}

export interface SeasonalSection {
  rows: SeasonalPartyRow[]
  /** شمارشِ آمادگی — چند ردیف هویتِ مالیاتیِ کامل دارد و چند تا نه. */
  ready_count: number
  incomplete_count: number
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
  line_id: string
  entry_id: string
  entry_number: number | null
  entry_date: string
  entry_status: string
  source_type: string | null
  /** حسابِ خودِ ردیف؛ در دفترِ کل می‌گوید مبلغ از کدام زیرحساب آمده. */
  account_code: string
  account_name: string
  description: string
  debit: string
  credit: string
  balance: string
  /** ارز و پیگیری از قبل روی ردیفِ سند بودند و هیچ گزارشی نشانشان نمی‌داد. */
  currency_code: string | null
  fx_amount: string | null
  fx_rate: string | null
  tracking_no: string | null
  tracking_date: string | null
}

export interface GeneralLedger {
  /** در «دفترِ تفصیلی» حسابِ واحدی در کار نیست، پس هر سه می‌توانند خالی باشند. */
  account_id: string | null
  account_code: string | null
  account_name: string | null
  opening_balance: string
  lines: GeneralLedgerLine[]
  closing_balance: string
  fx_totals: { currency_code: string; amount: string }[]
}

/**
 * دامنه‌ی محاسبه‌ی گزارش‌های حسابداری — **یک مجموعه برای هر سه خانواده**.
 *
 * تراز و مرور حساب و دفتر باید با یک فیلتر یک عدد بدهند؛ راهش این است که هر سه
 * همین شیء را بفرستند. هر میدانِ خالی یعنی «محدود نکن».
 */
export interface ReportFilters {
  dateFrom?: string
  dateTo?: string
  entryFrom?: number
  entryTo?: number
  status?: 'temporary' | 'permanent'
  sourceType?: string
  costCenterId?: string
  analyticId?: string
  /** افتتاحیه، اختتامیه و بستنِ سود و زیان وارد محاسبه شوند. پیش‌فرضِ سرور: بله. */
  includeSystemEntries?: boolean
}

export function reportFiltersQs(f: ReportFilters = {}): string {
  const qs = new URLSearchParams()
  if (f.dateFrom) qs.set('date_from', f.dateFrom)
  if (f.dateTo) qs.set('date_to', f.dateTo)
  if (f.entryFrom != null) qs.set('entry_from', String(f.entryFrom))
  if (f.entryTo != null) qs.set('entry_to', String(f.entryTo))
  if (f.status) qs.set('status', f.status)
  if (f.sourceType) qs.set('source_type', f.sourceType)
  if (f.costCenterId) qs.set('cost_center_id', f.costCenterId)
  if (f.analyticId) qs.set('analytic_id', f.analyticId)
  //: فقط وقتی فرستاده می‌شود که خاموش باشد — پیش‌فرضِ سرور روشن است.
  if (f.includeSystemEntries === false) qs.set('include_system_entries', 'false')
  const out = qs.toString()
  return out ? `?${out}` : ''
}

export const fetchGeneralLedger = (token: string, accountId: string, filters: ReportFilters = {}) =>
  authedGet<GeneralLedger>(
    token,
    `/api/reports/general-ledger/${accountId}${reportFiltersQs(filters)}`,
  )

/** دفترِ تفصیلی — بدونِ حسابِ اجباری: گردشِ یک تفصیلی در همه‌ی حساب‌ها. */
export const fetchAnalyticLedger = (token: string, filters: ReportFilters) =>
  authedGet<GeneralLedger>(token, `/api/reports/general-ledger${reportFiltersQs(filters)}`)

export interface JournalEntryLine {
  id: string
  account_id: string
  cost_center_id?: string | null
  /** بُعدِ تحلیلیِ آزاد («تفصیلی سایر») — اختیاری، NULL برای ردیف‌های معمولی. */
  analytic_id?: string | null
  debit: string
  credit: string
  description: string
  /** ردیفِ ارزی: مبلغ و نرخِ لحظه‌ی ثبت. بدهکار/بستانکار همیشه ریالی است. */
  currency_code?: string | null
  fx_amount?: string | null
  fx_rate?: string | null
  /** پیگیری — ارجاعِ آزادِ این ردیف. فقط روی حسابی که «پیگیری» دارد پر می‌شود. */
  tracking_no?: string | null
  tracking_date?: string | null
}

/** عملیاتی که سند از آن آمده. `id`/`number` فقط وقتی می‌آیند که منبع یکتا باشد —
 *  حقوق و دستمزد یک سند برای کلِ دوره می‌زند و ده‌ها فیش به همان اشاره می‌کنند. */
export interface EntrySource {
  source_type: string
  model: string
  count: number
  id: string | null
  number: string | null
}

export interface JournalEntryRecord {
  id: string
  number: number | null
  /** شماره عطف — سرور لحظه‌ی ثبت می‌دهد و هیچ عملیاتی عوضش نمی‌کند. */
  atf_number: number | null
  /** شماره فرعی — ارجاعِ آزادِ کاربر. null = خالی. */
  sub_number: string | null
  entry_date: string
  description: string
  source_type: string
  /** null = سند عملیاتِ بیرونی ندارد (دستی، تسعیر، اختتامیه). */
  source: EntrySource | null
  /** `temporary` | `permanent` — سندِ دائم دیگر ادغام/بازشماره‌گذاری نمی‌شود. */
  status: string
  finalized_at?: string | null
  voided_at: string | null
  reverses_entry_id: string | null
  lines: JournalEntryLine[]
}

export const fetchJournalEntries = (token: string) =>
  authedGetAll<JournalEntryRecord>(token, '/api/journal-entries')

/** اصلاحِ شماره فرعیِ سند. فقط سندِ موقتِ باطل‌نشده؛ روی سندِ دائم سرور ۴۰۹ می‌دهد. */
export const setEntrySubNumber = (token: string, entryId: string, subNumber: string | null) =>
  authedSend<JournalEntryRecord>(
    token, 'PATCH', `/api/journal-entries/${entryId}/sub-number`, { sub_number: subNumber },
  )

/** ابطالِ سندِ دستی با ثبتِ سندِ معکوس. فقط سندِ دستیِ باطل‌نشده؛ وگرنه سرور ۴۰۹ می‌دهد. */
export const voidJournalEntry = (token: string, entryId: string, reason: string) =>
  authedSend<{ reversal_entry_id: string; reversal_entry_number: number | null }>(
    token, 'POST', `/api/journal-entries/${entryId}/void`, { reason },
  )

export interface CheckRecord {
  id: string
  type: 'receivable' | 'payable'
  number: string
  /** شماره‌ی پشتِ برگ — با شماره‌ی چک یکی نیست. */
  back_number: string
  /** شناسه‌ی صیادیِ ۱۶رقمی؛ یکتاییِ واقعیِ برگ همین است. */
  sayad_id: string
  bank_name: string
  amount: string
  issue_date: string
  due_date: string
  status: string
  description: string
  contact_id: string | null
  contact_name: string | null
  bank_account_id: string | null
  checkbook_id?: string | null
  /** اعلامیه‌ای که چک با آن صادر یا خرج شده — راهِ رفتن به همان سند. */
  payment_id?: string | null
  receipt_id?: string | null
  description2?: string
  branch_name?: string
  branch_code?: string
  account_number?: string
  owner_name?: string
  voided_at?: string | null
  /** صندوقی که چک در آن نقد شد — فقط برای وضعیتِ `cashed`. */
  cashbox_id?: string | null
  /** «الان کجاست» — مشتق از وضعیت و پیوندها، نه ستونِ ذخیره‌شده. */
  holder_kind?: 'company' | 'bank_account' | 'cashbox' | 'contact' | 'none'
  holder_label?: string
  holder_id?: string | null
}

/** فیلترهای جستجوی چک — **همه روی سرور** اعمال می‌شوند. */
export interface CheckSearchQuery {
  q?: string
  type?: 'receivable' | 'payable'
  status?: string
  dueFrom?: string
  dueTo?: string
  amountMin?: string
  amountMax?: string
  bankAccountId?: string
  cashboxId?: string
  contactId?: string
}

function checkSearchParams(query: CheckSearchQuery): URLSearchParams {
  const qs = new URLSearchParams()
  if (query.q?.trim()) qs.set('q', query.q.trim())
  if (query.type) qs.set('type', query.type)
  if (query.status) qs.set('status', query.status)
  if (query.dueFrom) qs.set('due_from', query.dueFrom)
  if (query.dueTo) qs.set('due_to', query.dueTo)
  if (query.amountMin) qs.set('amount_min', query.amountMin)
  if (query.amountMax) qs.set('amount_max', query.amountMax)
  if (query.bankAccountId) qs.set('bank_account_id', query.bankAccountId)
  if (query.cashboxId) qs.set('cashbox_id', query.cashboxId)
  if (query.contactId) qs.set('contact_id', query.contactId)
  return qs
}

/**
 * جستجوی چک.
 *
 * **فیلتر روی سرور است، نه در مرورگر.** نسخه‌ی قبلی همه‌ی چک‌ها را می‌گرفت و
 * این‌جا غربال می‌کرد؛ برای دفترِ بزرگ یعنی مگابایت داده برای یک برگ، و
 * «جستجو روی کدِ صیادی» اصلاً ممکن نبود چون آن ستون در غربالِ کلاینت نبود.
 */
export const fetchChecks = (token: string, query: CheckSearchQuery = {}) =>
  authedGetAll<CheckRecord>(token, `/api/checks?${checkSearchParams(query)}`)

/** شمارش و مبلغِ هر وضعیت — KPIهای بالای صفحه‌ی جستجو. */
export interface CheckStatusSummary {
  status: string
  label: string
  count: number
  amount: string
}

export const fetchCheckSummary = (token: string, type?: 'receivable' | 'payable') =>
  authedGet<CheckStatusSummary[]>(
    token,
    `/api/checks/summary${type ? `?type=${type}` : ''}`,
  )

/** یک گامِ تاریخچه‌ی چک. */
export interface CheckEventRecord {
  id: string
  check_id: string
  /** نامِ عملیات — از وضعیتِ مقصد مشتق **نمی‌شود**: «بازگشت از بانک» و «برگشت از
   *  خرج» هر دو به «نزدِ ما» می‌رسند ولی دو رویدادِ متفاوت‌اند. */
  operation: string
  operation_label: string
  from_status: string | null
  to_status: string
  to_status_label: string
  event_date: string
  at: string
  operation_no: number | null
  batch_id: string | null
  bank_account_id: string | null
  bank_account_name: string | null
  cashbox_id: string | null
  cashbox_name: string | null
  contact_id: string | null
  contact_name: string | null
  journal_entry_id: string | null
  /** سندِ **عملیاتی** که این گذر در آن ثبت شد — با سندِ حسابداری یکی نیست. */
  source_type?: 'receipt' | 'payment' | null
  source_id?: string | null
  source_label?: string | null
  source_number?: number | null
  note: string
}

/**
 * برچسبِ فارسیِ هر عملیات — کلیدها همان `OPERATION_LABEL`ِ سرور.
 *
 * سرور برچسب را روی هر ردیف می‌فرستد (`operation_label`)، ولی صافیِ فهرست باید
 * پیش از رسیدنِ داده گزینه‌هایش را بسازد، پس همین‌جا هم لازم است.
 */
export const CHECK_OPERATION_LABEL: Record<string, string> = {
  receive: 'دریافت',
  issue: 'صدور',
  deposit: 'واگذاری به بانک',
  undeposit: 'بازگشت از بانک',
  collect: 'وصول',
  dishonor: 'واخواست',
  cash: 'نقد کردن',
  endorse: 'خرج کردن',
  return_endorsed: 'برگشت از خرج',
  refund: 'استرداد',
}

export interface CheckOperationRow extends CheckEventRecord {
  check_number: string
  check_amount: string
  check_type: string
}

export const fetchCheckTimeline = (token: string, checkId: string) =>
  authedGet<CheckEventRecord[]>(token, `/api/checks/${checkId}/timeline`)

export const fetchCheckOperations = (
  token: string,
  query: { operation?: string; dateFrom?: string; dateTo?: string } = {},
) => {
  const qs = new URLSearchParams()
  if (query.operation) qs.set('operation', query.operation)
  if (query.dateFrom) qs.set('date_from', query.dateFrom)
  if (query.dateTo) qs.set('date_to', query.dateTo)
  return authedGet<CheckOperationRow[]>(token, `/api/check-operations?${qs}`)
}

export interface CheckOperationResult {
  operation_no: number | null
  batch_id: string
  operation: string
  operation_label: string
  done: { check_id: string; number: string; amount: string }[]
  /** **۲۰۱ لزوماً یعنی همه رفتند.** اینجا را بخوانید. */
  failed: { check_id: string; reason: string }[]
  total_amount: string
}

/** یک عملیات روی چند چک، با نتیجه‌ی جدا برای هر کدام. */
export const runCheckOperation = (
  token: string,
  data: {
    check_ids: string[]
    status: string
    bank_account_id?: string | null
    cashbox_id?: string | null
    contact_id?: string | null
    event_date?: string | null
    note?: string
  },
) => authedSend<CheckOperationResult>(token, 'POST', '/api/check-operations', data)

export const updateCheckStatus = (
  token: string,
  checkId: string,
  status: string,
  bankAccountId?: string,
  extra: { cashbox_id?: string | null; contact_id?: string | null; event_date?: string | null; note?: string } = {},
) =>
  authedSend<CheckRecord>(token, 'PATCH', `/api/checks/${checkId}/status`, {
    status,
    bank_account_id: bankAccountId ?? null,
    ...extra,
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

/**
 * استخدام = فعال‌کردنِ نقشِ کارمند روی یک طرف حساب.
 *
 * دو شکل کار می‌کند و **هیچ‌کدام هویتِ بی‌طرف‌حساب نمی‌سازد**:
 *
 *  • `contact_id` بدهید → نقش روی همان طرف حساب فعال می‌شود.
 *  • نام و کدِ ملی بدهید → سرور اول دنبالِ طرف‌حسابی با همان کدِ ملی می‌گردد؛
 *    اگر باشد همان را برمی‌دارد (نه رکوردِ تکراری)، وگرنه می‌سازدش.
 *
 * نام و کدِ ملی از این پس روی **طرف حساب** حقیقت دارند: اصلاحشان همان‌جا انجام
 * می‌شود و به فایلِ بانک و اظهارنامه‌ی مالیات و لیستِ بیمه می‌رسد.
 */
export const createEmployee = (
  token: string,
  data: {
    contact_id?: string
    first_name?: string
    last_name?: string
    national_id?: string
    phone?: string
    email?: string
    bank_account_number?: string
    hire_date: string
  },
) => authedSend<EmployeeRecord>(token, 'POST', '/api/employees', data)

/**
 * ویرایشِ پرونده‌ی کارمند — **جزئی**؛ فیلدی که نفرستی دست نمی‌خورد.
 *
 * `is_active` مهم‌ترینشان است: تنها گاردِ صدورِ فیشِ حقوقی همین ستون است، و تا
 * پیش از این هیچ مسیری نمی‌نوشتش — یعنی کارمندی که رفته بود هر دوره فیشِ کامل
 * می‌گرفت، با سند و بیمه و مالیاتش.
 *
 * **نام و کدِ ملی عمداً این‌جا نیستند.** آن‌ها واقعیتِ شخص‌اند و روی طرف‌حساب
 * حقیقت دارند؛ `updateContact` اصلاحشان می‌کند و همان به فایلِ بانک و اظهارنامه
 * می‌رسد. دو مسیر برای یک داده یعنی دو حقیقت.
 */
export const updateEmployee = (
  token: string,
  employeeId: string,
  data: Partial<{
    hire_date: string
    termination_date: string | null
    bank_account_number: string
    phone: string | null
    email: string | null
    is_active: boolean
  }>,
) => authedSend<EmployeeRecord>(token, 'PATCH', `/api/employees/${employeeId}`, data)

/**
 * قراردادِ حقوقی. تعریفِ کاملش — با ردیف‌های عوامل، اطلاعات استخدامی و بیمه —
 * پایین‌تر در بخشِ «حقوق و دستمزد» است؛ این‌جا فقط ارجاع می‌دهیم تا دو نسخه‌ی
 * ناهمگون از یک درخواست نداشته باشیم.
 */

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

/** یک قلمِ فیش — «این عدد از چه ساخته شد».
 *
 * `factor_id` برای اجزای سیستمی (پایه، بیمه، مالیات، قسطِ وام) خالی است، و
 * `factor_name` عکسِ لحظه‌ی صدور است — نه نامِ امروزِ عامل. */
export interface PayslipLineRecord {
  id: string
  seq: number
  factor_id: string | null
  factor_name: string
  direction: 'earning' | 'deduction'
  /** `contract` | `attendance` | `settings` | `loan` | `input` — کجا باید عوضش کرد.
   *
   * `input` یعنی «ورودیِ عواملِ همین دوره»، نه حکمِ حقوقی. */
  origin: string
  amount: string
  note: string
}

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
  /** دو کسورِ بعد از مالیات — با این دو، فیش جمع می‌زند:
   *  خالص = ناخالص − بیمه − مالیات − قسطِ وام − سایر کسورات */
  loan_deduction: string
  other_deductions: string
  net_pay: string
  /** تفکیکِ عامل‌به‌عامل. ستون‌های تجمیعیِ بالا حقیقتِ فیش‌اند و این‌ها توضیحشان؛
   *  جمعشان با خالص برابر است. فیش‌های پیش از مهاجرتِ ۰۱۲۸ خالی دارندش. */
  lines: PayslipLineRecord[]
}

export const fetchPayslips = (token: string, periodId: string) =>
  authedGetAll<PayslipRecord>(token, `/api/payslips?period_id=${periodId}`)

/**
 * دفترِ فیش‌ها — همه‌ی دوره‌ها، با فیلترِ اختیاریِ دوره و کارمند.
 *
 * `fetchPayslips` بالا فیش‌های *یک* دوره را برای صفحه‌ی صدور می‌آورد؛ این یکی
 * دفترِ مرورِ چنددوره‌ای است. فیلتر سمتِ سرور می‌رود، نه مرورگر.
 */
export const fetchPayslipLedger = (
  token: string,
  filters: { periodId?: string; employeeId?: string } = {},
) => {
  const q = new URLSearchParams()
  if (filters.periodId) q.set('period_id', filters.periodId)
  if (filters.employeeId) q.set('employee_id', filters.employeeId)
  const qs = q.toString()
  return authedGetAll<PayslipRecord>(token, `/api/payslips${qs ? `?${qs}` : ''}`)
}

export const generatePayslips = (token: string, periodId: string) =>
  authedSend<PayslipRecord[]>(token, 'POST', `/api/payroll-periods/${periodId}/generate-payslips`, {})

/** سه خروجیِ CSVِ دوره‌ی حقوق. نامِ فایل از خودِ سرور می‌آید، نه از حدسِ کلاینت. */
export type PayrollExportKind = 'insurance-list' | 'tax-list' | 'payment-list'

export async function downloadPayrollCsv(
  token: string,
  periodId: string,
  kind: PayrollExportKind,
): Promise<{ filename: string; blob: Blob }> {
  const res = await fetch(`${API_BASE_URL}/api/payroll-periods/${periodId}/${kind}.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: 'خطای ناشناخته' }))
    throw new Error(errBody.detail ?? `درخواست ناموفق بود (${res.status})`)
  }
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^"]+)"?/.exec(disposition)
  const blob = await res.blob()
  return { filename: match?.[1] ?? `${kind}.csv`, blob }
}

// نرخ‌های بیمه/مالیاتِ حقوق برای هر سالِ شمسی. صدورِ فیش تا وقتی این تنظیمات (با
// پلکانِ نرخ‌غیرصفر) ثبت نشود، توسط سرور مسدود می‌شود.
export interface TaxBracket {
  up_to: string | null // سقفِ تجمعیِ سالانه‌ی مشمول (پس از کسرِ معافیت)؛ null = نامحدود (ردیفِ آخر)
  rate: string // نرخ بین ۰ و ۱
}

/**
 * پارامترهای قانونی‌ای که تا مهاجرتِ ۰۱۳۸ داخلِ سورس‌کدِ سرور ثابت بودند.
 *
 * پیش‌فرضِ هر کدام **همان ثابتی است که جایش را گرفته**، پس فرمی که این‌ها را
 * نفرستد دقیقاً رفتارِ قبلی را می‌گیرد.
 */
export interface PayrollStatutoryParams {
  /** سقفِ روزانه‌ی دستمزدِ مشمولِ بیمه. صفر = بی‌سقف. */
  insurance_daily_ceiling: string
  /** بیمه‌ی بیکاری — سهمِ کارفرما، به نرخِ کارفرما اضافه می‌شود. */
  unemployment_rate: string
  /** نرخِ مشاغل سخت: ذخیره و نمایش داده می‌شود، ولی **اعمال نمی‌شود** —
   *  شمولش به کارمند وابسته است و کوبیتا هنوز آن پرچم را ندارد. */
  hard_job_rate: string
  eidi_base_multiplier: string
  severance_days_per_year: number
  monthly_work_days: string
  standard_monthly_hours: string
  overtime_multiplier: string
  /** چه کسری از هر بیمه از مبنای مالیات کم می‌شود. */
  tax_exempt_coef_social: string
  tax_exempt_coef_supplementary: string
  tax_exempt_coef_medical: string
  /** کدام عاملِ موجود نقشِ بیمه‌ی تکمیلی/درمان را دارد. */
  supplementary_employee_factor_id: string | null
  supplementary_employer_factor_id: string | null
  medical_factor_id: string | null
  allow_negative_tax: boolean
  /** خالص تا این تعداد رقم گِرد می‌شود (۳ = تا هزار ریال). صفر = بدونِ رند. */
  payment_rounding_digits: number
}

/** همان پارامترها هنگامِ **نوشتن** — عدد، نه رشته (خروجیِ سرور `Decimal` است). */
export interface PayrollStatutoryParamsIn {
  insurance_daily_ceiling: number
  unemployment_rate: number
  hard_job_rate: number
  eidi_base_multiplier: number
  severance_days_per_year: number
  monthly_work_days: number
  standard_monthly_hours: number
  overtime_multiplier: number
  tax_exempt_coef_social: number
  tax_exempt_coef_supplementary: number
  tax_exempt_coef_medical: number
  supplementary_employee_factor_id: string | null
  supplementary_employer_factor_id: string | null
  medical_factor_id: string | null
  allow_negative_tax: boolean
  payment_rounding_digits: number
}

export interface PayrollSettingsRecord extends PayrollStatutoryParams {
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
  } & Partial<PayrollStatutoryParamsIn>,
) => authedSend<PayrollSettingsRecord>(token, 'PUT', '/api/payroll-settings', data)

export interface ItemRecord {
  id: string
  sku: string
  name: string
  /** عنوانِ دوم — فیلدِ مستقل، نه پیوستِ نام. */
  name2: string
  category: string
  unit: string
  is_service: boolean
  is_active: boolean
  /** «قابل فروش» جدا از «فعال»: موادِ اولیه موجودی دارند و فروختنی نیستند. */
  is_sellable: boolean
  is_serial_tracked: boolean
  sales_price: string
  average_cost: string
  barcode: string | null
  /** سه شناسه‌ی جدا با sku و barcode — ایران‌کد و بارکدِ دوبعدی. */
  iran_code: string
  barcode2: string
  storefront_product_id: number | null
  reorder_point: string
  tax_stuff_id: string
  /** `taxable` (مشمول) یا `exempt` (معاف) — سمتِ **فروش**. */
  vat_status: string
  /** وضعیتِ مالیاتیِ سمتِ **خرید**، مستقل از فروش. */
  purchase_vat_status: string
  /** نرخِ کالا؛ «۰» یعنی «نرخِ سرِ فاکتور»، نه معافیت. */
  tax_rate: string
  duty_rate: string
  /** معینِ هزینه‌ی خریدِ خدمت. خالی = حسابِ پیش‌فرضِ «هزینه خرید خدمات». */
  expense_account_id: string | null
  expense_account_code: string
  expense_account_name: string
  expense_account_is_default: boolean
  /** واحدِ اصلی از داده‌ی پایه؛ `unit` بالا پرتوِ نامِ همین است. */
  primary_unit_id: string | null
  primary_unit_name: string
  secondary_unit_id: string | null
  secondary_unit_name: string
  /** «۱ کارتن = ۲۴ عدد». صفر یعنی نسبت هنوز تعریف نشده. */
  conversion_factor: string
  /** `fixed` یا `variable` — نسبتِ متغیر عمداً بی‌عدد است. */
  conversion_mode: string
  /** متادیتای حمل‌ونقل، نه موجودی. */
  unit_weight: string
  unit_volume: string
  /** قاعده‌ی برنامه‌ریزی، نه سدِ تراکنش. */
  min_stock: string
  max_stock: string
  /** فهرستِ خالی یعنی «همه‌ی انبارها»، نه «هیچ انباری». */
  warehouses: ItemWarehouseLink[]
  /** پیشنهادِ فرمِ فروش/خرید، نه قفل. */
  default_warehouse_id: string | null
  /** گروه یک رکورد است؛ `category` بالا پرتوِ نامِ همین است. */
  group_id: string | null
  group_name: string
  /** مشخصه‌ها ستونِ ثابتِ کالا نیستند: تعریف ← مقدار. */
  attributes: { attribute_id: string; attribute_name: string; value: string }[]
}

export const fetchItemsLive = (token: string) => authedGetAll<ItemRecord>(token, '/api/items')

/** پشتیبان‌گیری: خروجیِ کاملِ داده‌ی کسب‌وکار (فقط مالک؛ در وب برای دانلودِ فایل). */
export const fetchBackupExport = (token: string) => authedGet<Record<string, unknown>>(token, '/api/backup/export')

/** بازیابی: فایلِ پشتیبان را می‌فرستد و داده را *جایگزین* می‌کند (فقط مالک). */
export const importBackup = (token: string, data: unknown) =>
  authedSend<{ restored: boolean; total_rows: number }>(token, 'POST', '/api/backup/import', data)


/** ورودیِ ساختِ کالای جدید — دقیقاً منطبق بر ItemIn سمت سرور (sku و name الزامی‌اند). */
export interface ItemIn {
  sku: string
  name: string
  name2?: string
  category?: string
  unit?: string
  is_service?: boolean
  is_sellable?: boolean
  is_serial_tracked?: boolean
  sales_price?: number
  barcode?: string | null
  iran_code?: string
  barcode2?: string
  reorder_point?: number
  tax_stuff_id?: string
  vat_status?: string
  purchase_vat_status?: string
  tax_rate?: number
  duty_rate?: number
  expense_account_id?: string | null
  primary_unit_id?: string | null
  secondary_unit_id?: string | null
  conversion_factor?: number
  conversion_mode?: string
  unit_weight?: number
  unit_volume?: number
  min_stock?: number
  max_stock?: number
  warehouses?: { warehouse_id: string; is_default?: boolean; min_stock?: number | null; max_stock?: number | null }[]
  group_id?: string | null
  attributes?: { attribute_id: string; value: string }[]
}

/** فیلدهایی که سرور در `ItemUpdateIn` می‌پذیرد. `is_service` عمداً نیست: تبدیلِ
 *  کالا به خدمت پس از گردش، تاریخِ انبار را غیرمنطقی می‌کند. */
export type ItemPatch = Partial<Omit<ItemIn, 'is_service'>> & {
  is_active?: boolean
  average_cost?: number
  storefront_product_id?: number | null
}

export const createItemLive = (token: string, data: ItemIn) =>
  authedSend<ItemRecord>(token, 'POST', '/api/items', data)

/** ویرایشِ کالا — فقط فیلدهایی که سرور در ItemUpdateIn می‌پذیرد. */
export const updateItemLive = (token: string, itemId: string, patch: ItemPatch) =>
  authedSend<ItemRecord>(token, 'PATCH', `/api/items/${itemId}`, patch)

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
  currency_code: string | null
  exchange_rate: string
  voided_at: string | null
  void_reason: string
  /** فاکتورِ بسته دیگر ویرایش و ابطال نمی‌شود. null = باز. */
  closed_at: string | null
  salesperson_id: string | null
  sale_type_id: string | null
  /** واسطه‌ی معامله — طرف‌حسابی با نقشِ «واسط». null = بی‌واسطه. */
  broker_id: string | null
  /** کارمزدِ واسطه، قفل‌شده در لحظه‌ی ثبت (نه محاسبه از نرخِ امروز). */
  broker_commission: string
  broker_name: string | null
  /** نامِ فروشنده و نوعِ فروش برای نمایش؛ سرور پُرشان می‌کند. */
  salesperson_name: string | null
  sale_type_name: string | null
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
  warehouse_id: string | null
  contact_id: string | null
  supplier_invoice_number: string
  description: string
  description2: string
  total_amount: string
  total_discount: string
  /** تخفیفِ کلِ فاکتور (تسهیم‌شده در ردیف‌ها؛ در total_discount هم منظور شده). */
  invoice_discount: string
  total_additions: string
  total_duties: string
  tax_rate: string
  tax_amount: string
  currency_code: string | null
  exchange_rate: string
  final_amount: string
  transaction_final_amount: string
  received_total_qty: string
  /** `not_applicable` = فاکتوری که کالایی برای تحویل ندارد (فقط خدمت). */
  inventory_status: 'not_received' | 'partially_received' | 'fully_received' | 'not_applicable'
  settled_amount: string
  remaining_amount: string
  financial_status: 'unsettled' | 'partially_settled' | 'fully_settled'
  voided_at: string | null
  void_reason: string
  /** ثبت‌کننده‌ی فاکتور — چه کسی و با چه نقشی آن را زد. */
  created_by_id: string | null
  created_by_name: string | null
  created_by_role: string | null
  lines: (InvoiceLineRecord & {
    unit_cost: string
    addition: string
    duty_amount: string
    item_code_snapshot: string
    item_name_snapshot: string
    unit_snapshot: string
    received_qty: string
    remaining_qty: string
    /** معینِ هزینه‌ای که ردیفِ خدمت خورد (Snapshot). برای کالا خالی. */
    expense_account_id?: string | null
    expense_account_code?: string
    expense_account_name?: string
  })[]
}

export const fetchPurchaseInvoices =(token: string) => authedGetAll<PurchaseInvoiceRecord>(token, '/api/purchase-invoices')

export interface WarehouseReceiptRecord {
  id: string
  number: number
  receipt_date: string
  purchase_invoice_id: string
  warehouse_id: string
  status: string
  description: string
  voided_at: string | null
  lines: { id: string; purchase_invoice_line_id: string; item_id: string; qty: string; unit_cost: string }[]
}

export const fetchWarehouseReceipts = (token: string, invoiceId: string) =>
  authedGet<WarehouseReceiptRecord[]>(token, `/api/purchase-invoices/${invoiceId}/warehouse-receipts`)

export const createWarehouseReceipt = (
  token: string,
  invoiceId: string,
  data: { receipt_date: string; warehouse_id: string; description?: string; lines: { purchase_invoice_line_id: string; qty: number }[] },
) => authedSend<WarehouseReceiptRecord>(token, 'POST', `/api/purchase-invoices/${invoiceId}/warehouse-receipts`, data)

export interface PurchasePricePoint {
  invoice_id: string
  invoice_number: number | null
  invoice_date: string
  supplier_id: string | null
  base_unit_cost: string
  transaction_unit_cost: string
  currency_code: string
  exchange_rate: string
}

export const fetchPurchasePriceInfo = (token: string, itemId: string, supplierId?: string) =>
  authedGet<{ latest: PurchasePricePoint | null; supplier_latest: PurchasePricePoint | null }>(
    token,
    `/api/purchase-price-info/${itemId}${supplierId ? `?supplier_id=${encodeURIComponent(supplierId)}` : ''}`,
  )

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
  journal_entry_id: string | null
  voided_at: string | null
  void_reason: string
  /** برگشتِ فیزیکی (مهاجرتِ ۰۱۳۴) — `inline` یعنی خودِ این سند موجودی را برگردانده. */
  stock_mode?: 'inline' | 'issue_return'
  physical_status?: string
  physical_qty?: string
  physical_returned_qty?: string
  physical_remaining_qty?: string
  /** مشتق سمتِ سرور — هیچ‌کدام ستونِ ذخیره‌شده نیستند. */
  final_amount: string
  settled_amount: string
  remaining_amount: string
  accounting_status: string
  financial_status: string
  lines: {
    id: string
    item_id: string
    sales_invoice_line_id: string | null
    qty: string
    unit_price: string
    unit_cost: string
    return_reason_id: string | null
    description: string
  }[]
}

export const fetchSalesReturns = (token: string) => authedGetAll<SalesReturnRecord>(token, '/api/sales-returns')

export interface ReturnableLine {
  /** هویتِ ردیفِ مبدأ. یک کالا می‌تواند در یک فاکتور چند ردیف با چند قیمت داشته باشد. */
  sales_invoice_line_id: string | null
  purchase_invoice_line_id: string | null
  invoice_number: number | null
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
  data: {
    return_date: string
    sales_invoice_id: string
    description: string
    lines: { item_id?: string; sales_invoice_line_id?: string; qty: number; return_reason_id?: string | null }[]
  },
  idempotencyKey?: string,
) => authedSend<SalesReturnRecord>(token, 'POST', '/api/sales-returns', data, idempotencyKey)

export interface PurchaseReturnRecord {
  id: string
  number: number | null
  return_date: string
  /** برگشتی که به رسیدِ مستقیم لنگر زده فاکتوری ندارد. */
  purchase_invoice_id: string | null
  warehouse_receipt_id?: string | null
  warehouse_id?: string | null
  /** «تحویل‌گیرنده» — با تحویل‌دهنده‌ی رسید یکی نیست. */
  receiver_id?: string | null
  return_type?: string
  /** «خالص» (ارزشِ دفتری) و «خالص توافقی» — دو ستونِ جدا در فهرست. */
  base_amount?: string
  agreed_total?: string
  description: string
  total_amount: string
  tax_rate: string
  tax_amount: string
  journal_entry_id: string | null
  voided_at: string | null
  void_reason: string
  final_amount: string
  settled_amount: string
  remaining_amount: string
  accounting_status: string
  financial_status: string
  lines: {
    id: string
    item_id: string
    purchase_invoice_line_id: string | null
    qty: string
    unit_cost: string
    description: string
  }[]
}

export const fetchPurchaseReturns = (token: string) => authedGetAll<PurchaseReturnRecord>(token, '/api/purchase-returns')

export const createPurchaseReturn = (
  token: string,
  data: {
    return_date: string
    purchase_invoice_id: string
    description: string
    lines: { item_id?: string; purchase_invoice_line_id?: string; qty: number }[]
  },
  idempotencyKey?: string,
) => authedSend<PurchaseReturnRecord>(token, 'POST', '/api/purchase-returns', data, idempotencyKey)

export interface StockTransferRecord {
  id: string
  number: number | null
  transfer_date: string
  from_warehouse_id: string
  to_warehouse_id: string
  description: string
  journal_entry_id?: string | null
  voided_at?: string | null
  void_reason?: string
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
  //: تکرارِ شبکه‌ای نباید دو انتقال بسازد — کلید به همین حواله گره می‌خورد.
  idempotencyKey?: string,
) => authedSend<StockTransferRecord>(token, 'POST', '/api/stock-transfers', data, idempotencyKey)

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

/** کالاهایی که موجودی‌شان به/زیرِ نقطه‌ی سفارش یا حداقلِ موجودی رسیده. */
export interface LowStockRow {
  item_id: string
  sku: string
  name: string
  unit: string
  qty_on_hand: string
  reorder_point: string
  shortfall: string
  /** کدام آستانه این ردیف را آورده: `reorder` یا `min` — دو مفهومِ جدا. */
  trigger: string
  min_stock: string
}

export const fetchLowStock = (token: string) => authedGet<LowStockRow[]>(token, '/api/stock/low')

/**
 * انبار (کامل) — برای تبِ مدیریتِ انبارها.
 *
 * **هیچ فیلدِ موجودی ندارد و نباید داشته باشد.** انبار فقط یکی از ابعادِ موجودی
 * است؛ مانده همیشه از حرکاتِ انبار می‌آید.
 */
export interface WarehouseRecord {
  id: string
  code: string
  name: string
  /** عنوانِ دوم — فیلدِ مستقل، نه پیوستِ نام. */
  name2: string
  responsible: string
  phone: string
  address: string
  address2: string
  is_active: boolean
  /** معینِ انبار. `null` یعنی حسابِ پیش‌فرضِ موجودیِ کالا. */
  gl_account_id: string | null
  gl_account_code: string
  gl_account_name: string
  /** درست یعنی این حساب انتخابِ کاربر نبوده، پیش‌فرض است. */
  gl_account_is_default: boolean
}

export interface WarehouseInput {
  code: string
  name: string
  name2?: string
  responsible?: string
  phone?: string
  address?: string
  address2?: string
  gl_account_id?: string | null
}

/** کالاهای دارای موجودیِ غیرصفر — پیش از غیرفعال‌کردن پرسیده می‌شود. */
export interface WarehouseStockPositions {
  item_count: number
  items: { item_id: string; item_name: string; qty: string }[]
}

export const fetchWarehousesAdmin = (token: string) =>
  authedGet<WarehouseRecord[]>(token, '/api/warehouses')

export const createWarehouse = (token: string, data: WarehouseInput) =>
  authedSend<WarehouseRecord>(token, 'POST', '/api/warehouses', data)

export const updateWarehouse = (
  token: string,
  id: string,
  patch: Partial<WarehouseInput> & { is_active?: boolean },
) => authedSend<WarehouseRecord>(token, 'PATCH', `/api/warehouses/${id}`, patch)

export const fetchWarehouseStock = (token: string, id: string) =>
  authedGet<WarehouseStockPositions>(token, `/api/warehouses/${id}/stock-positions`)

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
  has_tracking: boolean
  accepts_tafsili: boolean
}

export const fetchAccountsLive = async (token: string) => {
  const rows = await authedGet<AccountLiveOut[]>(token, '/api/accounts')
  //: شکلِ خروجی عمداً با `AccountCache` (کشِ SQLite) یکی است تا فرم‌ها لازم نباشد
  //: بینِ وب و Electron شاخه بزنند — بولی به ۰/۱ همان‌جا تبدیل می‌شود.
  return rows.map((a) => ({
    ...a,
    is_group: a.is_group ? 1 : 0,
    has_tracking: a.has_tracking ? 1 : 0,
    accepts_tafsili: a.accepts_tafsili ? 1 : 0,
  }))
}

/** حسابِ کامل (با فعال‌بودن و نقشِ سیستمی) — برای مدیریتِ چارتِ حساب‌ها. */
export interface ChartAccount {
  id: string
  code: string
  name: string
  /** عنوانِ دوم (معمولاً انگلیسی) برای گزارشِ دوزبانه. خالی = ندارد. */
  name2: string
  type: string // asset | liability | equity | income | expense
  /** ماهیتِ *صریح*: debit | credit | any. null یعنی از نوعِ حساب مشتق می‌شود. */
  nature: string | null
  /** ماهیتِ *مؤثر* — همان که گزارشِ خلافِ ماهیت با آن می‌سنجد. همیشه پر است. */
  effective_nature: string
  is_group: boolean
  is_active: boolean
  /** صورتِ مالی: balance_sheet | income_statement. مشتق از نوعِ حساب، نه ستون. */
  statement_type: string
  parent_id: string | null
  system_role: string | null
  /** کنترلِ ماهیت طی دوره — رصدِ این حساب در گزارشِ خلافِ ماهیت. */
  nature_control: boolean
  /** ارزی — فیلدهای ارزِ ردیفِ سند را باز می‌کند. */
  is_fx: boolean
  /** تسعیرپذیر. فقط روی حسابِ ارزی؛ خاموش‌بودنش یعنی «ارزی هست، تسعیرش نکن». */
  fx_revaluable: boolean
  /** تفصیلی‌پذیر — ردیفِ سندِ این حساب **باید** تفصیلی داشته باشد. */
  accepts_tafsili: boolean
  /** پیگیری — شماره و تاریخِ پیگیری روی ردیفِ سندِ این حساب. */
  has_tracking: boolean
  /** نمایش در گزارشاتِ مدیریتی. پیش‌فرض روشن. */
  in_management_reports: boolean
}

/** شش پرچمِ «ویژگی‌های حساب» — همان قابِ فرمِ ویرایشِ حساب. */
export interface AccountTraits {
  nature_control: boolean
  is_fx: boolean
  fx_revaluable: boolean
  accepts_tafsili: boolean
  has_tracking: boolean
  in_management_reports: boolean
}

/** برچسب و توضیحِ هر ویژگی — یک‌جا، تا فرم و راهنما از هم جدا نیفتند. */
export const ACCOUNT_TRAIT_META: {
  key: keyof AccountTraits
  label: string
  hint: string
}[] = [
  {
    key: 'nature_control',
    label: 'کنترل ماهیت طی دوره',
    hint: 'این حساب در گزارشِ «خلافِ ماهیت» رصد می‌شود.',
  },
  { key: 'is_fx', label: 'ارزی', hint: 'فیلدهای ارز روی ردیفِ سندِ این حساب باز می‌شوند.' },
  {
    key: 'fx_revaluable',
    label: 'تسعیر پذیر',
    hint: 'فقط روی حسابِ ارزی. برداشتنش یعنی «ارزی هست ولی تسعیرش نکن».',
  },
  {
    key: 'accepts_tafsili',
    label: 'تفصیلی پذیر',
    hint: 'ردیفِ سندِ این حساب بدونِ تفصیلی ثبت نمی‌شود. (ربطی به زیرشاخه‌ی درختی ندارد.)',
  },
  {
    key: 'has_tracking',
    label: 'پیگیری',
    hint: 'شماره و تاریخِ پیگیری روی ردیفِ سندِ این حساب ظاهر می‌شود.',
  },
  {
    key: 'in_management_reports',
    label: 'نمایش در گزارشات مدیریتی',
    hint: 'برداشتنش حساب را از گزارش‌های مدیریتی کنار می‌گذارد، نه از دفتر.',
  },
]

/** صورتِ مالیِ حساب — از نوعش مشتق می‌شود، ذخیره نمی‌شود. */
export const STATEMENT_TYPE_LABELS: Record<string, string> = {
  balance_sheet: 'ترازنامه‌ای',
  income_statement: 'سود و زیانی',
}

/** ماهیتِ حساب — سمتی که مانده طبیعتاً باید در آن باشد. */
export const ACCOUNT_NATURE_LABELS: Record<string, string> = {
  debit: 'بدهکار',
  credit: 'بستانکار',
  any: 'مهم نیست',
}

export const fetchChartAccounts = (token: string) =>
  authedGet<ChartAccount[]>(token, '/api/accounts')

export const createAccount = (
  token: string,
  data: {
    code: string
    name: string
    name2?: string
    type: string
    nature?: string | null
    is_group?: boolean
    parent_id?: string | null
  } & Partial<AccountTraits>,
) => authedSend<ChartAccount>(token, 'POST', '/api/accounts', data)

export const updateAccount = (
  token: string,
  id: string,
  patch: {
    name?: string
    name2?: string
    nature?: string | null
    is_active?: boolean
  } & Partial<AccountTraits>,
) => authedSend<ChartAccount>(token, 'PATCH', `/api/accounts/${id}`, patch)

export const deleteAccount = (token: string, id: string) => authedDelete(token, `/api/accounts/${id}`)

/** نتیجه‌ی خام‌سازیِ درختواره. */
export interface WipeChartResult {
  deleted: number
  kept: KeptAccount[]
}

/**
 * خام‌سازیِ کلِ درختواره — سرور فقط وقتی می‌پذیرد که هیچ سندی ثبت نشده باشد.
 * آخرین راه است، نه دکمه‌ی روزمره: کدهای دلخواهِ کاربر از دست می‌روند.
 */
export const wipeChart = (token: string) =>
  authedDeleteJson<WipeChartResult>(token, '/api/accounts')

/** تغییرِ کدِ حساب — «کدینگ». امن است چون ثبتِ خودکار حساب را با نقشش می‌شناسد نه با کدش. */
export const changeAccountCode = (token: string, id: string, code: string) =>
  authedSend<ChartAccount>(token, 'PATCH', `/api/accounts/${id}/code`, { code })

/** پیامدِ یک سطحِ اجبار، تفکیک‌شده به سه چیزی که واقعاً فرق می‌کنند. */
export interface TafsiliModeEffects {
  manual: string
  module: string
  report: string
  warning: string
}

export interface TafsiliModeOption {
  key: string
  label: string
  hint: string
  effects: TafsiliModeEffects
  is_default: boolean
}

/**
 * سطحِ اجبارِ تفصیلی روی حساب‌های «تفصیلی پذیر» — انتخابِ کسب‌وکار.
 *
 * `options` از سرور می‌آید نه از این‌جا: متنِ پیامدها یک منبعِ حقیقت دارد و اگر
 * قاعده‌ای عوض شود، رابط خودبه‌خود همان را می‌گوید.
 */
export interface TafsiliMode {
  mode: string
  options: TafsiliModeOption[]
  /** false یعنی هنوز روی پیش‌فرضِ سرویس است و کاربر انتخابی نکرده. */
  is_explicit: boolean
}

export const fetchTafsiliMode = (token: string) =>
  authedGet<TafsiliMode>(token, '/api/accounts/tafsili-mode')

export const setTafsiliMode = (token: string, mode: string) =>
  authedSend<TafsiliMode>(token, 'PATCH', '/api/accounts/tafsili-mode', { mode })

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

/** یک حساب و اینکه پاک‌شدنی هست یا نه — پایه‌ی «حذفِ حساب» در تنظیمات. */
export interface DeletableAccount {
  id: string
  code: string
  name: string
  level: string
  is_group: boolean
  can_delete: boolean
  reason: string | null
}

export const fetchDeletableAccounts = (token: string) =>
  authedGet<DeletableAccount[]>(token, '/api/accounts/deletable')

/** حسابی که «برگرداندنِ قالب» نگه داشت، همراهِ دلیلش. */
export interface KeptAccount {
  code: string
  name: string
  reason: string
}

export interface RevertTemplateResult {
  removed: number
  codes: string[]
  kept: KeptAccount[]
}

/** حساب‌های *بی‌استفاده*‌ی یک قالب را برمی‌دارد — راهِ برگشت از درجِ اشتباه. */
export const revertChartTemplate = (token: string, key: string) =>
  authedDeleteJson<RevertTemplateResult>(token, `/api/accounts/templates/${key}`)

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

/** وضعیتِ آماده‌سازیِ چارت — «آیا کاربر چارت را گسترش داده؟»، نه «آیا حساب دارد؟».
 *  هر کسب‌وکار از لحظه‌ی ساخت چارتِ پایه دارد، پس سؤالِ دوم همیشه بله است. */
export interface ChartSetup {
  total: number
  /** حساب‌هایی که در چارتِ پایه نبوده‌اند — کارِ خودِ کاربر. */
  custom: number
  /** کلیدِ قالبِ صنفیِ کاملاً درج‌شده، یا null. */
  applied_template: string | null
}

export const fetchChartSetup = (token: string) =>
  authedGet<ChartSetup>(token, '/api/accounts/setup-status')

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
  currency_code: string
}

export const fetchBankAccountsLive = async (token: string) => {
  const rows = await authedGet<BankAccountLiveOut[]>(token, '/api/bank-accounts')
  return rows.map((b) => ({ id: b.id, name: b.name, bank_name: b.bank_name, currency_code: b.currency_code }))
}

/** حساب بانکیِ کامل — برای مدیریتِ حساب‌ها و «کارتِ حساب» (دفتر کلِ متناظر). */
export interface BankAccountRecord {
  id: string
  name: string
  name2: string
  bank_name: string
  branch_name: string
  account_number: string
  account_type: string
  /** سه شناسه‌ی جدا: شماره حساب، شماره کارت، شبا. هیچ‌کدام جای دیگری نیست. */
  card_number: string
  iban: string
  /** بُعدی که مانده‌ی این حساب را از بقیه جدا می‌کند. خالی = تفکیک‌نشده. */
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  gl_account_id: string
  currency_code: string
  opening_date: string | null
  holder_name: string
  holder_name2: string
  /** ذخیره‌شده — چیزی که بانک اعلام کرده، نه حاصلِ تراکنش‌ها. */
  blocked_amount: string
  cheque_print_format: string
  is_active: boolean
  /** هر سه **مشتق‌اند**؛ هیچ‌کدام ستونِ پایگاه‌داده نیستند. */
  opening_balance: string
  balance: string
  available_balance: string
}

export interface BankAccountInput {
  name: string
  name2?: string
  bank_name?: string
  branch_name?: string
  account_number?: string
  account_type?: string
  card_number?: string
  iban?: string
  analytic_id?: string | null
  currency_code?: string
  opening_date?: string | null
  holder_name?: string
  holder_name2?: string
  blocked_amount?: string | number
  cheque_print_format?: string
  is_active?: boolean
}

export const fetchBankAccountsAdmin = (token: string) =>
  authedGet<BankAccountRecord[]>(token, '/api/bank-accounts')

export const createBankAccount = (token: string, data: BankAccountInput) =>
  authedSend<BankAccountRecord>(token, 'POST', '/api/bank-accounts', data)

export const updateBankAccount = (token: string, id: string, patch: Partial<BankAccountInput>) =>
  authedSend<BankAccountRecord>(token, 'PATCH', `/api/bank-accounts/${id}`, patch)

export const deleteBankAccount = (token: string, id: string) =>
  authedDelete(token, `/api/bank-accounts/${id}`)

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
    analytic_id?: string | null
    /** پیش‌فرضِ سرور `temporary` است — سند اول در کارتابل بازبینی می‌شود. */
    status?: 'temporary' | 'permanent'
    /** شماره فرعی — اختیاری. عطف فرستاده نمی‌شود؛ آن را فقط سرور می‌دهد. */
    sub_number?: string | null
    lines: {
      account_id: string
      debit: number
      credit: number
      description?: string
      currency_code?: string | null
      fx_amount?: number | null
      fx_rate?: number | null
      analytic_id?: string | null
      /** پیگیری — سرور اگر حساب «پیگیری» نداشته باشد ردش می‌کند، نه اینکه دور بریزد. */
      tracking_no?: string | null
      tracking_date?: string | null
    }[]
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
    /** واسطه‌ی معامله. باید نقشِ «واسط» داشته باشد؛ کارمزدش را سرور از نرخِ خودش
     *  حساب و روی فاکتور قفل می‌کند. */
    broker_id?: string | null
    /** فروشنده — مبنای محاسبه‌ی پورسانت. باید کاربرِ همین کسب‌وکار باشد. */
    salesperson_id?: string | null
    /** نوعِ فروش (نقدی، اعتباری…). نوعِ غیرفعال پذیرفته نمی‌شود. */
    sale_type_id?: string | null
    lines: { item_id: string; qty: number; unit_price: number; discount?: number }[]
  },
  idempotencyKey?: string,
) => authedSend<unknown>(token, 'POST', '/api/sales-invoices', data, idempotencyKey)

export const createPurchaseInvoiceDirect = (
  token: string,
  data: {
    invoice_date: string
    warehouse_id?: string | null
    tax_rate?: number
    cost_center_id?: string | null
    contact_id?: string | null
    supplier_invoice_number?: string
    description?: string
    description2?: string
    currency_code?: string | null
    exchange_rate?: number
    /** تخفیفِ کلِ فاکتور به مبلغِ پایه (ریال). درصد در UI به مبلغ تبدیل می‌شود. */
    invoice_discount?: number
    invoice_addition?: number
    duty_amount?: number
    lines: { item_id: string; qty: number; unit_cost: number; discount?: number; addition?: number; duty_amount?: number; description?: string }[]
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
    /** برگِ کدام دسته‌چک است (فقط چکِ پرداختنی). */
    checkbook_id?: string | null
    back_number?: string
    sayad_id?: string
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

  // ── هویتِ تفکیک‌شده ──
  /** `name` نامِ نمایشی است و از این دو ساخته می‌شود؛ خالی = نامِ یک‌تکه (شرکت). */
  first_name: string
  last_name: string
  first_name2: string
  last_name2: string
  sub_type: string
  website: string
  registration_no: string | null
  passport_no: string | null
  marriage_date: string | null
  /** جدا از `is_active`: غیرفعال = دیگر کار نمی‌کنیم، لیستِ سیاه = با احتیاط. */
  is_blacklisted: boolean
  discount_rate: string
  tax_ministry_class: string
  /** با عبور از سقفِ اعتبار چه شود: none | warn | block. */
  credit_action: string
  /** نقشِ سوم — پرچمِ مستقل، نه مقدارِ `type`. */
  is_broker: boolean
  commission_rate: string
  /** کارمندِ متناظر در حقوق و دستمزد — پیوند، نه کپی. */
  employee_id: string | null
  /** تفصیلیِ متصل. کد و عنوان از خودِ تفصیلی خوانده می‌شوند، نه از طرف‌حساب. */
  analytic_id: string | null
  tafsili_code: string | null
  tafsili_title: string | null
  tafsili_title2: string
  /** مانده‌ی اول دوره — مبلغ نامنفی، سمت جدا. پس از ثبتِ افتتاحیه قفل می‌شود. */
  opening_ar_amount: string
  opening_ar_side: string
  opening_ap_amount: string
  opening_ap_side: string
  /** مشخصاتِ شخص — واقعیتِ آدم است نه شغلش، پس روی طرف‌حساب می‌نشیند نه کارمند. */
  gender: string
  marital_status: string
  marital_status_date: string | null
  children_count: number
  dependents_count: number
  education_level: string
  education_field: string
  is_employee: boolean
  /** نقشِ چهارم — پرچمِ مستقل، مثلِ واسطه. */
  is_shareholder: boolean
  share_percent: string
}

/** تلفن یا نشانیِ *اضافه*. کانالِ اصلی روی خودِ طرف‌حساب است (`phone`/`address`). */
export interface ContactChannel {
  id: string
  contact_id: string
  kind: 'phone' | 'address' | 'email'
  /** نوعِ کنترل‌شده (دفتر، انبار، همراه…)؛ `label` متنِ آزادِ کاربر است. */
  channel_type: string
  label: string
  value: string
  /** «اصلی» — سرور تضمین می‌کند در هر طرف‌حساب حداکثر یکی باشد. */
  is_primary: boolean
  notes: string
  is_active: boolean
}

export const CHANNEL_KIND_LABELS: Record<string, string> = {
  phone: 'تلفن',
  address: 'نشانی',
  email: 'ایمیل',
}

/** نوعِ تلفن — فهرستِ کنترل‌شده، چون «نوع» در فرم کشویی است نه متنِ آزاد. */
export const CHANNEL_TYPE_LABELS: Record<string, string> = {
  office: 'تلفن دفتر',
  warehouse: 'تلفن انبار',
  mobile: 'همراه',
  fax: 'فکس',
  home: 'منزل',
  other: 'سایر',
}

/** نوعِ نشانی. هرکدام کاربردِ عملیاتی دارد — «ارسال کالا» همان است که به مأمورِ ارسال می‌رود. */
export const ADDRESS_TYPE_LABELS: Record<string, string> = {
  official: 'رسمی',
  business: 'محل فعالیت',
  billing: 'ارسال صورتحساب',
  shipping: 'ارسال کالا',
  warehouse: 'انبار',
  home: 'منزل',
  postal: 'پستی',
  //: درِ خروجِ فهرست (کارگاه، نمایشگاه، دفترِ موقت) — عنوانِ نشانی می‌گوید دقیقاً چیست.
  other: 'سایر',
}

export const GENDER_LABELS: Record<string, string> = { male: 'مرد', female: 'زن' }
export const MARITAL_STATUS_LABELS: Record<string, string> = {
  single: 'مجرد',
  married: 'متأهل',
  divorced: 'مطلقه',
  widowed: 'همسر فوت‌شده',
}

/** یکی از نشانی‌های طرف‌حساب. جدا از تلفن چون شکلش واقعاً فرق دارد. */
export interface ContactAddress {
  id: string
  contact_id: string
  address_type: string
  is_primary: boolean
  geo_location_id: string | null
  title: string
  address: string
  address2: string
  postal_code: string
  latitude: string | null
  longitude: string | null
  /** «زون»ِ توزیع — وقتی موجودیتِ زون ساخته شد، کلیدِ خارجی می‌شود. */
  route_code: string
  route_title: string
  route_title2: string
  region_code: string
  region_title: string
  region_title2: string
  branch_code: string
  notes: string
  is_active: boolean
}

export type ContactAddressIn = Omit<ContactAddress, 'id' | 'contact_id'>

export const fetchContactAddresses = (token: string, contactId: string) =>
  authedGet<ContactAddress[]>(token, `/api/contacts/${contactId}/addresses`)

export const addContactAddress = (
  token: string,
  contactId: string,
  data: Partial<ContactAddressIn>,
) => authedSend<ContactAddress>(token, 'POST', `/api/contacts/${contactId}/addresses`, data)

export const deleteContactAddress = (token: string, contactId: string, addressId: string) =>
  authedDelete(token, `/api/contacts/${contactId}/addresses/${addressId}`)

/**
 * آیا این عنوانِ تفصیلی از قبل هست؟
 *
 * جواب `true` **ثبت را نمی‌بندد** — دو نفرِ هم‌نام واقعاً ممکن‌اند. فرم فقط قرمزش
 * می‌کند تا کاربر چیزی به آن اضافه کند و بعداً در فهرستِ تفصیلی گیج نشود.
 */
export const checkTafsiliTitleTaken = (token: string, title: string) =>
  authedGet<{ taken: boolean }>(
    token,
    `/api/contacts/tafsili-title-taken?title=${encodeURIComponent(title)}`,
  )

export const fetchContactChannels = (token: string, contactId: string) =>
  authedGet<ContactChannel[]>(token, `/api/contacts/${contactId}/channels`)

export const addContactChannel = (
  token: string,
  contactId: string,
  data: {
    kind?: string
    channel_type?: string
    label?: string
    value: string
    is_primary?: boolean
    notes?: string
  },
) => authedSend<ContactChannel>(token, 'POST', `/api/contacts/${contactId}/channels`, data)

export const deleteContactChannel = (token: string, contactId: string, channelId: string) =>
  authedDelete(token, `/api/contacts/${contactId}/channels/${channelId}`)

/** با عبور از سقفِ اعتبار چه شود. */
export const CREDIT_ACTION_LABELS: Record<string, string> = {
  none: 'بدون کنترل',
  warn: 'هشدار بده',
  block: 'جلوگیری کن',
}

/** دسته‌بندیِ وزارت دارایی — مبنای گزارشِ معاملاتِ فصلی. */
export const TAX_MINISTRY_CLASS_LABELS: Record<string, string> = {
  normal: 'عادی',
  gold: 'طلا و جواهر',
  currency: 'ارز',
  estate: 'املاک',
}

/**
 * آیا فرمِ طرف حساب باید کدِ تفصیلی بخواهد.
 *
 * از سطحِ اجبارِ تفصیلی می‌آید (تنظیمات ← شخصی‌سازی): `required` در «اجباری»،
 * `optional` در «ترکیبی»، `hidden` در «شناور».
 */
export interface TafsiliRequirement {
  requirement: 'required' | 'optional' | 'hidden'
  mode: string
  suggested_code: string | null
}

export const fetchContactTafsiliRequirement = (token: string) =>
  authedGet<TafsiliRequirement>(token, '/api/contacts/tafsili-requirement')

export interface ContactIn {
  name: string
  type: string
  /** غیرفعال = «دیگر پیشنهادش نکن»، نه «ناپدید شو». تاریخچه دست‌نخورده می‌ماند.
   *
   * سرور `PATCH` را جزئی می‌گیرد، پس **نفرستادنش یعنی دست نزن**. فرم‌هایی که این
   * فیلد را ندارند نباید نگرانِ فعال‌کردنِ دوباره‌ی یک طرف‌حسابِ غیرفعال باشند. */
  is_active?: boolean
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
  first_name?: string
  last_name?: string
  first_name2?: string
  last_name2?: string
  sub_type?: string
  website?: string
  registration_no?: string | null
  passport_no?: string | null
  marriage_date?: string | null
  is_blacklisted?: boolean
  discount_rate?: number
  tax_ministry_class?: string
  credit_action?: string
  is_broker?: boolean
  commission_rate?: number
  employee_id?: string | null
  //: کد و عنوانِ تفصیلی — سرور از آن‌ها یک تفصیلی می‌سازد یا موجود را به‌روز می‌کند.
  tafsili_code?: string | null
  tafsili_title?: string | null
  tafsili_title2?: string
  opening_ar_amount?: number
  opening_ar_side?: string
  opening_ap_amount?: number
  opening_ap_side?: string
  gender?: string
  marital_status?: string
  marital_status_date?: string | null
  children_count?: number
  dependents_count?: number
  education_level?: string
  education_field?: string
  is_employee?: boolean
  is_shareholder?: boolean
  share_percent?: number
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

/** ویرایشِ **جزئی** — فقط همان فیلدهایی که می‌فرستی عوض می‌شوند.
 *
 * `Partial` این‌جا تعارف نیست: سرور `ContactPatch` می‌گیرد و با `exclude_unset`
 * کار می‌کند، پس فیلدی که نیاید یعنی «دست نزن» نه «پیش‌فرضش کن». همین اجازه
 * می‌دهد یک دکمه‌ی «غیرفعال» تنها `{ is_active: false }` بفرستد بی‌آنکه بقیه‌ی
 * پرونده‌ی طرف‌حساب را با مقدارهای فرمِ باز بازنویسی کند. */
export const updateContact = (token: string, contactId: string, data: Partial<ContactIn>) =>
  authedSend<ContactRecord>(token, 'PATCH', `/api/contacts/${contactId}`, data)

/** حذفِ طرف حساب — فقط اگر هیچ‌جا استفاده نشده باشد؛ وگرنه ۴۰۹ با پیامِ روشن.
 *
 * طرف‌حسابی که فاکتور یا سند دارد پاک نمی‌شود، چون دفتر به نامش ارجاع می‌دهد.
 * راهِ درستش «غیرفعال» است — همان چیزی که پیامِ خطای سرور پیشنهاد می‌دهد. */
export const deleteContact = (token: string, contactId: string) =>
  authedDelete(token, `/api/contacts/${contactId}`)

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
  /** کدام صندوق. null = صندوقِ پیش‌فرض (تراکنش‌های پیش از مهاجرتِ ۰۱۰۵). */
  cashbox_id: string | null
  description: string
  journal_entry_id: string
  // متادیتای کارت (فقط برای رسیدِ کارتخوان پر می‌شود)
  paid_via?: string | null
  reference_no?: string | null
  trace_no?: string | null
  card_mask?: string | null
  terminal_no?: string | null
  /** لحظه‌ی تسویه‌ی کارتخوان — NULL یعنی هنوز تسویه نشده. */
  settled_at?: string | null
  voided_at?: string | null
  psp?: string | null
}

export interface TreasuryTransactionIn {
  transaction_date: string
  contact_id: string
  amount: number
  method: 'cash' | 'bank'
  bank_account_id: string | null
  /** فقط برای روشِ نقدی. خالی = صندوقِ پیش‌فرض. */
  cashbox_id?: string | null
  description: string
}

export const fetchTreasuryTransactions = (token: string) =>
  authedGetAll<TreasuryTransactionRecord>(token, '/api/treasury')

export const createTreasuryReceipt = (token: string, data: TreasuryTransactionIn) =>
  authedSend<TreasuryTransactionRecord>(token, 'POST', '/api/treasury/receipts', data)

export const createTreasuryPayment = (token: string, data: TreasuryTransactionIn) =>
  authedSend<TreasuryTransactionRecord>(token, 'POST', '/api/treasury/payments', data)

// --- اعلامیه‌ی پرداختِ چندابزاری ---------------------------------------------------

export interface PaymentCashIn {
  cashbox_id?: string | null
  amount: number
  description?: string
}

export interface PaymentBankWithdrawalIn {
  bank_account_id: string
  number?: string
  withdrawal_date?: string | null
  amount: number
  bank_fee?: number
  description?: string
  description2?: string
}

export interface PaymentPayableChequeIn {
  checkbook_id?: string | null
  bank_account_id?: string | null
  number: string
  amount: number
  due_date: string
  sayad_id?: string
  back_number?: string
  description?: string
  description2?: string
}

export interface PaymentDocumentIn {
  payment_type: 'supplier' | 'customer' | 'other'
  contact_id: string
  payment_date: string
  counterparty_account_id?: string | null
  bank_fee_account_id?: string | null
  discount_account_id?: string | null
  currency_code?: string
  exchange_rate?: number
  discount_amount?: number
  description?: string
  description2?: string
  establishment?: string
  cash: PaymentCashIn[]
  bank_withdrawals: PaymentBankWithdrawalIn[]
  payable_cheques: PaymentPayableChequeIn[]
  endorsed_cheques: { check_id: string }[]
  related_documents?: { document_type: string; document_id: string; allocated_amount?: number }[]
}

export interface PaymentComponentRecord {
  kind: 'cash' | 'bank_withdrawal' | 'payable_cheque' | 'endorsed_cheque'
  label: string
  amount: string
  bank_fee: string
  source_id: string | null
  reference_no: string
  due_date: string | null
  status: string
  description: string
}

export interface PaymentDocumentRecord {
  id: string
  number: number
  payment_type: string
  payment_type_label: string
  contact_id: string
  contact_name: string
  payment_date: string
  counterparty_account_id: string
  bank_fee_account_id: string | null
  discount_account_id: string | null
  currency_code: string
  exchange_rate: string
  payment_amount: string
  base_currency_amount: string
  discount_amount: string
  settlement_total: string
  bank_fee_amount: string
  description: string
  description2: string
  establishment: string
  journal_entry_id: string
  items_summary: string
  components: PaymentComponentRecord[]
  voided_at: string | null
  created_at: string
  updated_at: string
  created_by_name: string
  updated_by_name: string
}

export const fetchPaymentDocuments = (token: string) =>
  authedGetAll<PaymentDocumentRecord>(token, '/api/payments')

export const fetchEligibleReceivedCheques = (token: string) =>
  authedGet<CheckRecord[]>(token, '/api/payments/eligible-received-cheques')

export const createPaymentDocument = (token: string, data: PaymentDocumentIn, idempotencyKey: string) =>
  authedSend<PaymentDocumentRecord>(token, 'POST', '/api/payments', data, idempotencyKey)

export const voidPaymentDocument = (token: string, id: string, reason: string) =>
  authedSend<PaymentDocumentRecord>(token, 'POST', `/api/payments/${id}/void`, { reason })

/** قرینه‌ی چاپِ رسید — همان موتورِ سمتِ سرور، همان رکورد. */
export const openPaymentPrintView = (token: string, id: string) =>
  openInvoicePrintView(token, `/api/payments/${id}/print`)

// --- کارتخوان (POS) -----------------------------------------------------------------
// اتصالِ سخت‌افزار فقط در نسخه‌ی دسکتاپ (window.cubita.posTerminal) رخ می‌دهد؛ ثبتِ
// حسابداری سرور-ساید است و در هر دو نسخه یکسان دیده می‌شود.

export type PosTransport = 'simulator' | 'network' | 'serial' | 'sdk'

export interface PosTerminalRecord {
  id: string
  label: string
  name2: string
  /** شماره‌ی پایانه‌ای که دستگاه گزارش می‌کند. هویتِ رکورد نیست — آن `id` است. */
  terminal_no: string
  currency_code: string
  psp: string
  transport: PosTransport
  host: string
  port: number
  com_port: string
  bank_account_id: string | null
  bank_account_name: string | null
  bank_account_name2: string | null
  /** تفصیلیِ دستگاه روی «وجوهِ در راهِ کارت‌خوان» — بدونش مانده‌ی دفتریِ دستگاه‌ها یکی می‌شود. */
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  is_active: boolean
  is_default: boolean
  /** **مشتق** — جمعِ رسیدهای کارتیِ تسویه‌نشده. مانده‌ی بانک نیست. */
  unsettled_balance: string
}

export interface PosTerminalIn {
  label?: string
  name2?: string
  terminal_no?: string
  currency_code?: string
  psp?: string
  transport?: PosTransport
  host?: string
  port?: number
  com_port?: string
  bank_account_id?: string | null
  analytic_id?: string | null
  is_active?: boolean
  is_default?: boolean
}

export interface PosTerminalFilters {
  search?: string
  bankAccountId?: string
  currencyCode?: string
  activeOnly?: boolean
}

export const fetchPosTerminals = (token: string, filters: PosTerminalFilters = {}) => {
  const qs = new URLSearchParams()
  if (filters.search) qs.set('search', filters.search)
  if (filters.bankAccountId) qs.set('bank_account_id', filters.bankAccountId)
  if (filters.currencyCode) qs.set('currency_code', filters.currencyCode)
  if (filters.activeOnly) qs.set('active_only', 'true')
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<PosTerminalRecord[]>(token, `/api/pos-terminals${suffix}`)
}

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
  /** دستگاه — وقتی داده شود، حسابِ تسویه از خودش می‌آید و لازم نیست جدا بفرستیم. */
  pos_terminal_id?: string | null
  bank_account_id?: string | null
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
  /** «(۲)»ِ فرمِ سپیدار — نسخه‌ی لاتین، اختیاری. */
  name2?: string
  role2?: string
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
  /** «(۲)»ِ فرمِ سپیدار — نسخه‌ی لاتین، اختیاری. */
  name2?: string
  role2?: string
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
  /** عنوانِ دوم (لاتین) — «عنوان انگلیسی»ِ فرمِ سپیدار. خالی مجاز است. */
  name2: string
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
  name2: string
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

export interface CashboxRecord {
  id: string
  name: string
  name2: string
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  gl_account_id: string | null
  currency_code: string
  opening_date: string | null
  is_active: boolean
  /** هر دو **مشتق** از دفترند. یکی ابتدای دوره است و دیگری نتیجه‌ی هرچه بعدش افتاده. */
  opening_balance: string
  balance: string
}

export interface CashboxInput {
  name: string
  name2?: string
  analytic_id?: string | null
  gl_account_id?: string | null
  currency_code?: string
  opening_date?: string | null
  is_active?: boolean
}

export const fetchCashboxes = (token: string, includeInactive = true) =>
  authedGet<CashboxRecord[]>(token, `/api/cashboxes?include_inactive=${includeInactive}`)

export const createCashbox = (token: string, data: CashboxInput) =>
  authedSend<CashboxRecord>(token, 'POST', '/api/cashboxes', data)

export const updateCashbox = (token: string, id: string, data: Partial<CashboxInput>) =>
  authedSend<CashboxRecord>(token, 'PATCH', `/api/cashboxes/${id}`, data)

export const deleteCashbox = (token: string, id: string) =>
  authedDelete(token, `/api/cashboxes/${id}`)

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
  /** ردیابی — مانده‌ی اول دوره هیچ‌کدام را ندارد. */
  source_id?: string | null
  entry_number?: number | null
  entry_date?: string | null
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
  /** میانگینِ کلِ شرکت در پایانِ بازه. */
  unit_cost: string
  stock_value: string
  opening_qty: string
  opening_value: string
  in_qty: string
  in_value: string
  out_qty: string
  out_value: string
  /** جمعِ «مقدار × بهای سند»؛ اختلافش با stock_value ارزش‌گذاریِ منقضی است. */
  book_value: string
  stale_from: string | null
}

export interface InventoryReport {
  as_of: string | null
  date_from: string | null
  warehouse_id: string | null
  rows: InventoryRow[]
  total_value: string
  total_opening_value: string
  total_in_value: string
  total_out_value: string
  total_book_value: string
  stale_item_count: number
  item_count: number
}

/** بدونِ `dateFrom` فقط کالاهای دارای مانده؛ با آن، هر کالایی که در بازه گردش داشته. */
export const fetchInventoryReport = (token: string, asOf?: string, dateFrom?: string) => {
  const qs = new URLSearchParams()
  if (asOf) qs.set('as_of', asOf)
  if (dateFrom) qs.set('date_from', dateFrom)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGet<InventoryReport>(token, `/api/reports/inventory${suffix}`)
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
  source_id: string | null
  source_number: number | null
  /** حرکتِ سندِ باطل یا جبرانش — جمعشان صفر است و میانگین را تکان نمی‌دهند. */
  voided: boolean
  qty_in: string
  qty_out: string
  /** بهای ارزش‌گذاری (بازپخشِ دفتر به ترتیبِ تاریخ). */
  unit_cost: string
  /** بهایی که خودِ سند نوشته. */
  recorded_unit_cost: string
  /** بهای سند با میانگینِ همان تاریخ نمی‌خواند. */
  stale: boolean
  /** بها در «قیمت‌گذاری اسناد انبار» اصلاح شده؛ `recorded_unit_cost` بهای پس از اصلاح است. */
  adjusted: boolean
  value_in: string
  value_out: string
  balance_qty: string
  balance_value: string
  /** میانگینِ کلِ شرکت پس از این حرکت. */
  average_cost: string
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
  opening_value: string
  lines: KardexLine[]
  total_in: string
  total_out: string
  total_value_in: string
  total_value_out: string
  closing_qty: string
  closing_value: string
  average_cost: string
  stale_count: number
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
  /** شماره و خریدارِ فاکتورِ مربوط — تاریخچه باید بگوید «کدام فاکتور». */
  invoice_number: number | null
  buyer_name: string
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


export const inquireMoadianStatus = (token: string, submissionId: string) =>
  authedSend<MoadianSubmissionRecord>(token, 'POST', `/api/moadian/inquiry/${submissionId}`, {})

/** یک شرطِ ارسال — همان شرطی که مسیرِ ارسالِ سرور واقعاً می‌سنجد. */
export interface MoadianReadinessCheck {
  key: 'credentials' | 'signing' | 'stuff_ids' | 'activation'
  ok: boolean
  title: string
  detail: string
}

export interface MoadianReadiness {
  ready: boolean
  checks: MoadianReadinessCheck[]
  environment: 'sandbox' | 'production'
  pending_count: number
  blocked_count: number
}

/** یک ردیفِ صفِ ارسال. `blocked_reason` خالی یعنی همین حالا قابلِ ارسال است. */
export interface MoadianPendingInvoice {
  id: string
  number: number | null
  invoice_date: string
  buyer_name: string
  buyer_is_legal: boolean
  net_amount: string
  tax_amount: string
  payable: string
  blocked_reason: string
}

export interface MoadianBatchResult {
  invoice_id: string
  ok: boolean
  /** وضعیتِ ثبت‌شده، یا `skipped` وقتی قاعده جلوی ارسال را گرفت. */
  status: string
  tax_id: string
  reference_number: string
  error_message: string
}

export const fetchMoadianReadiness = (token: string) =>
  authedGet<MoadianReadiness>(token, '/api/moadian/readiness')

/** نگاشتِ واحدِ سنجش به کدِ رسمیِ سامانه. بدونِ آن هر ردیف «عدد» اظهار می‌شد. */
export interface MoadianUnitMap {
  id: string
  unit: string
  code: string
}

export const fetchMoadianUnitMaps = (token: string) =>
  authedGet<MoadianUnitMap[]>(token, '/api/moadian/unit-maps')

/** واحدهایی که روی کالاها به کار رفته‌اند ولی هنوز کد ندارند. */
export const fetchMoadianUnmappedUnits = (token: string) =>
  authedGet<string[]>(token, '/api/moadian/unmapped-units')

export const saveMoadianUnitMap = (token: string, unit: string, code: string) =>
  authedSend<MoadianUnitMap>(token, 'PUT', '/api/moadian/unit-maps', { unit, code })

export const deleteMoadianUnitMap = (token: string, id: string) =>
  authedDelete(token, `/api/moadian/unit-maps/${id}`)

export const fetchMoadianPending = (token: string) =>
  authedGet<MoadianPendingInvoice[]>(token, '/api/moadian/pending')

export const submitMoadianBatch = (token: string, invoiceIds: string[]) =>
  authedSend<MoadianBatchResult[]>(token, 'POST', '/api/moadian/submit-batch', { invoice_ids: invoiceIds })

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

export const printJournalEntry = (token: string, entryId: string) =>
  openInvoicePrintView(token, `/api/journal-entries/${entryId}/print`)

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
  number: number
  warehouse_id: string
  warehouse_name: string
  count_date: string
  status: StockCountStatus
  notes: string
  posted_at: string | null
  created_at: string | null
  line_count: number
  counted_line_count: number
}

export interface StockCountLine {
  id: string
  item_id: string
  item_name: string
  item_sku: string
  unit: string
  system_qty: string
  /** `null` = هنوز شمرده نشده. با «صفر شمردم» یکی نیست و نباید یکی نمایش داده شود. */
  counted_qty: string | null
  unit_cost: string
  counted_at: string | null
  variance: string | null
  variance_value: string | null
}

export interface StockCountSession {
  id: string
  number: number
  warehouse_id: string
  warehouse_name: string
  count_date: string
  status: StockCountStatus
  notes: string
  journal_entry_id: string | null
  posted_at: string | null
  created_at: string | null
  line_count: number
  counted_line_count: number
  variance_line_count: number
  total_variance_value: string
  lines: StockCountLine[]
}

export const fetchStockCounts = (token: string) =>
  authedGet<StockCountSummary[]>(token, '/api/stock-counts')

export const fetchStockCount = (token: string, id: string) =>
  authedGet<StockCountSession>(token, `/api/stock-counts/${id}`)

/** `item_ids` خالی = هر کالایی که در همین انبار سابقه‌ی حرکت دارد (نه کلِ کاتالوگ). */
export const createStockCount = (
  token: string,
  data: { warehouse_id: string; count_date: string; notes: string; item_ids?: string[] },
) => authedSend<StockCountSession>(token, 'POST', '/api/stock-counts', data)

/** `counted_qty: null` یعنی «شمارش را پس بگیر» — ردیف به حالتِ نشمرده برمی‌گردد. */
export const setStockCounts = (
  token: string,
  id: string,
  lines: { line_id: string; counted_qty: number | null }[],
) => authedSend<StockCountSession>(token, 'PUT', `/api/stock-counts/${id}/counts`, { lines })

/** کالاهایی که **پس از** ثبتِ شمارششان حرکت کرده‌اند — گزارش، نه گارد. */
export interface CountDrift {
  item_id: string
  item_name: string
  system_qty_at_count: string
  system_qty_now: string
  counted_at: string | null
}

export const fetchStockCountDrift = (token: string, id: string) =>
  authedGet<CountDrift[]>(token, `/api/stock-counts/${id}/drift`)

/** برگه‌های شمارش را باز می‌کند — عمداً بدونِ موجودیِ سیستمی (شمارشِ کور). */
export const printCountTags = (token: string, id: string) =>
  openInvoicePrintView(token, `/api/stock-counts/${id}/tags`)

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
  effective_from: string
}
/** یک قاعده‌ی قیمت: هدف + زمینه + نرخ + سیاستِ تغییر — همان ستون‌های ماتریسِ اعلامیه. */
export interface PriceListItemRecord {
  id: string
  item_id: string | null
  item_group_id: string | null
  price: string
  sale_type_id: string | null
  unit_id: string | null
  contact_group_id: string | null
  currency_code: string
  addition_percent: string
  allow_rate_change: boolean
  allow_discount_change: boolean
  max_increase_percent: string
  max_decrease_percent: string
}
/** ورودیِ یک قاعده. هدف اجباری است (کالا یا گروهِ فروشِ کالا)؛ بقیه پیش‌فرض دارند. */
export interface PriceRuleIn {
  item_id?: string | null
  item_group_id?: string | null
  price: number
  sale_type_id?: string | null
  unit_id?: string | null
  contact_group_id?: string | null
  currency_code?: string
  addition_percent?: number
  allow_rate_change?: boolean
  allow_discount_change?: boolean
  max_increase_percent?: number
  max_decrease_percent?: number
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
/** قاعده‌های فرستاده‌شده را می‌نشاند یا به‌روز می‌کند — ردیفِ نیامده **پاک نمی‌شود**. */
export const setPriceListItems = (token: string, listId: string, items: PriceRuleIn[]) =>
  authedSend<PriceListItemRecord[]>(token, 'PUT', `/api/price-lists/${listId}/items`, { items })

export const fetchStockBatches = (token: string, itemId?: string) =>
  authedGet<StockBatchRecord[]>(token, `/api/stock-batches${itemId ? `?item_id=${itemId}` : ''}`)
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

// ─────────────────────────────────────────────────────────────────────────────
// ماژولِ حسابداری — هجده عملیاتِ دفترداری زیرِ `/api/accounting`
//
// الگو یکسان است: هر عملیاتِ سندساز یک `…Preview` دارد که فقط می‌خواند و یک تابعِ
// صدور. صفحه‌ها همیشه اول پیش‌نمایش را نشان می‌دهند، پس هیچ سندی بی‌دیدن زده نمی‌شود.
// ─────────────────────────────────────────────────────────────────────────────

export interface EntrySummary {
  id: string
  number: number | null
  atf_number: number | null
  sub_number: string | null
  entry_date: string
  description: string
  source_type: string
  status: string
  voided_at: string | null
  total: string
  line_count: number
  accounts: string[]
}

export interface Cartable {
  total_count: number
  groups: { source_type: string; count: number; total: string }[]
  entries: EntrySummary[]
}

export const fetchCartable = (token: string, dateFrom?: string, dateTo?: string) =>
  authedGet<Cartable>(token, `/api/accounting/cartable${rangeQs(dateFrom, dateTo)}`)

export const finalizeEntries = (
  token: string,
  data: { date_from?: string; date_to?: string; entry_ids?: string[]; source_type?: string },
) =>
  authedSend<{ count: number; first_date: string; last_date: string }>(
    token, 'POST', '/api/accounting/entries/finalize', data,
  )

export interface RenumberRow {
  id: string
  entry_date: string
  description: string
  /** عطف در پیش‌نمایش می‌آید تا کاربر ببیند بازشماره‌گذاری به آن دست نمی‌زند. */
  atf_number: number | null
  old_number: number | null
  new_number: number
  changed: boolean
  status: string
  source_type: string
  accounts: string[]
}

export const fetchRenumberPreview = (
  token: string, dateFrom: string | undefined, dateTo: string | undefined, startNumber: number,
) => {
  const qs = new URLSearchParams({ start_number: String(startNumber) })
  if (dateFrom) qs.set('date_from', dateFrom)
  if (dateTo) qs.set('date_to', dateTo)
  return authedGet<{
    count: number
    changed_count: number
    /** اسنادِ دائمِ بازه که دست نمی‌خورند. */
    skipped_permanent: number
    rows: RenumberRow[]
    truncated: boolean
  }>(token, `/api/accounting/entries/renumber/preview?${qs}`)
}

export const renumberEntries = (
  token: string,
  data: {
    date_from?: string | null
    date_to?: string | null
    /** انتخابِ دستی. اگر داده شود **جای** بازه می‌نشیند نه کنارش. */
    entry_ids?: string[] | null
    start_number: number
  },
) =>
  authedSend<{ count: number; changed_count: number; first_number: number; last_number: number }>(
    token, 'POST', '/api/accounting/entries/renumber', data,
  )

export const mergeEntries = (token: string, entryIds: string[], description: string) =>
  authedSend<{
    entry_id: string
    number: number | null
    line_count: number
    merged_numbers: (number | null)[]
  }>(token, 'POST', '/api/accounting/entries/merge', { entry_ids: entryIds, description })

export interface FxRow {
  account_id: string
  account_code: string
  account_name: string
  /** بُعدهای ردیف؛ null یعنی مانده‌ی این گروه واقعاً بُعدی نداشته. */
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  cost_center_id: string | null
  cost_center_name: string | null
  currency_code: string
  fx_balance: string
  rate: string
  /** تاریخِ خودِ نرخ — اگر با تاریخِ تسعیر یکی نباشد، نرخ کهنه است. */
  rate_date: string
  book_value: string
  market_value: string
  difference: string
}

export const fetchFxPreview = (token: string, asOf: string) =>
  authedGet<{ as_of: string; items: FxRow[]; total_difference: string; missing_rates: string[] }>(
    token, `/api/accounting/fx-revaluation/preview?as_of=${asOf}`,
  )

export const issueFxRevaluation = (token: string, asOf: string, description: string) =>
  authedSend<{ entry_id: string; number: number | null; line_count: number; net_difference: string }>(
    token, 'POST', '/api/accounting/fx-revaluation', { as_of: asOf, description },
  )

export interface PnlPreviewRow {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  cost_center_id: string | null
  cost_center_name: string | null
  debit: string
  credit: string
  side: string
  amount: string
}

export interface PnlPreview {
  date_from: string | null
  date_to: string
  rows: PnlPreviewRow[]
  total_income: string
  total_expenses: string
  net_profit: string
  destination_account_code: string
  destination_account_name: string
  total_debit: string
  total_credit: string
  difference: string
  temporary_in_range: number
  already_closed: boolean
}

export const fetchPnlClosePreview = (token: string, dateTo: string) =>
  authedGet<PnlPreview>(token, `/api/accounting/pnl-close/preview?date_to=${dateTo}`)

/** گامِ اول: فقط سند را می‌زند. قفلِ دوره گامِ دومِ جداست و برگشت ندارد. */
export const issuePnlClose = (token: string, asOf: string, description: string) =>
  authedSend<{
    entry_id: string
    number: number | null
    line_count: number
    total_income: string
    total_expenses: string
    net_profit: string
  }>(token, 'POST', '/api/accounting/pnl-close', { as_of: asOf, description })

export interface ClosingRow {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  /** بُعدهای مانده — مانده‌ی یک حساب با سه تفصیلی سه ردیفِ جداست. */
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  cost_center_id: string | null
  cost_center_name: string | null
  debit: string
  credit: string
  balance: string
}

export const fetchClosingPreview = (token: string, asOf: string) =>
  authedGet<{
    as_of: string
    rows: ClosingRow[]
    total: string
    open_pnl_total: string
    temporary_count: number
  }>(token, `/api/accounting/closing-entry/preview?as_of=${asOf}`)

export const issueClosingEntry = (token: string, asOf: string, description: string) =>
  authedSend<{ entry_id: string; number: number | null; line_count: number; total: string }>(
    token, 'POST', '/api/accounting/closing-entry', { as_of: asOf, description },
  )

export const fetchOpeningPreview = (token: string, asOf: string, sourceDate: string) =>
  authedGet<{
    as_of: string
    source_date: string
    rows: ClosingRow[]
    closing_entry_id: string
    closing_entry_number: number | null
    total: string
  }>(token, `/api/accounting/opening-entry/preview?as_of=${asOf}&source_date=${sourceDate}`)

export const issueOpeningEntry = (
  token: string, asOf: string, sourceDate: string, description: string,
) =>
  authedSend<{ entry_id: string; number: number | null; line_count: number; total: string }>(
    token, 'POST', '/api/accounting/opening-entry',
    { as_of: asOf, source_date: sourceDate, description },
  )

export interface BalanceRow {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  parent_id: string | null
  opening_debit: string
  opening_credit: string
  period_debit: string
  period_credit: string
  closing_debit: string
  closing_credit: string
  balance: string
  /** «گردش داشته» نه «مانده دارد» — این دو از نظر حسابداری یکی نیستند. */
  has_activity: boolean
}

export const fetchAccountBalances = (
  token: string,
  filters: ReportFilters = {},
  includeZeroActivity = false,
) => {
  const qs = reportFiltersQs(filters)
  const zero = includeZeroActivity ? `${qs ? '&' : '?'}include_zero_activity=true` : ''
  return authedGet<BalanceRow[]>(token, `/api/accounting/balances${qs}${zero}`)
}

export interface LegalBookRow {
  entry_id: string
  entry_number: number | null
  entry_date: string
  status: string
  voided: boolean
  account_code: string
  account_name: string
  description: string
  debit: string
  credit: string
}

export const fetchLegalBook = (token: string, dateFrom: string, dateTo: string) =>
  authedGet<{
    date_from: string
    date_to: string
    rows: LegalBookRow[]
    total_debit: string
    total_credit: string
  }>(token, `/api/accounting/legal-book?date_from=${dateFrom}&date_to=${dateTo}`)

/** یک ترکیبِ (حساب، تفصیلی) که در تاریخِ اصلاح مانده دارد. */
export interface ReclassSource {
  account_id: string
  account_code: string
  account_name: string
  analytic_id: string | null
  analytic_code: string | null
  analytic_name: string | null
  balance: string
  /** نقشِ سیستمی مسدود نمی‌کند؛ فقط هشدار می‌دهد. */
  system_role: string | null
}

export interface ReclassItem {
  account_id: string
  account_code: string
  account_name: string
  analytic_id: string | null
  analytic_name: string | null
  balance: string
  source_debit: string
  source_credit: string
  dest_debit: string
  dest_credit: string
}

export interface ReclassPreview {
  as_of: string
  items: ReclassItem[]
  dest_account_id: string
  dest_account_code: string
  dest_account_name: string
  dest_analytic_id: string | null
  dest_analytic_name: string | null
  total_debit: string
  total_credit: string
  /** باید صفر باشد — اصلاحِ طبقه‌بندی از هیچ، دارایی یا سود نمی‌سازد. */
  difference: string
  warnings: string[]
}

export interface ReclassBody {
  as_of: string
  sources: { account_id: string; analytic_id: string | null }[]
  dest_account_id: string
  dest_analytic_id: string | null
  description?: string
}

export const fetchReclassSources = (token: string, asOf: string) =>
  authedGet<ReclassSource[]>(token, `/api/accounting/balance-reclass/sources?as_of=${asOf}`)

export const previewReclass = (token: string, body: ReclassBody) =>
  authedSend<ReclassPreview>(token, 'POST', '/api/accounting/balance-reclass/preview', body)

export const issueReclass = (token: string, body: ReclassBody) =>
  authedSend<{ entry_id: string; number: number | null; line_count: number; total: string }>(
    token, 'POST', '/api/accounting/balance-reclass', body,
  )

export const reclassifyAccounts = (
  token: string, items: { account_id: string; parent_id: string | null; type?: string }[],
) =>
  authedSend<{
    count: number
    changed: {
      account_id: string
      account_code: string
      account_name: string
      old_parent_id: string | null
      new_parent_id: string | null
      old_type: string
      new_type: string
    }[]
  }>(token, 'POST', '/api/accounting/accounts/reclassify', { items })

export interface AnalyticAccount {
  id: string
  code: string
  name: string
  group_name: string
  description: string
  is_active: boolean
  line_count: number
}

export const fetchAnalytics = (token: string) =>
  authedGet<AnalyticAccount[]>(token, '/api/accounting/analytics')

export const createAnalytic = (
  token: string, data: { code: string; name: string; group_name?: string; description?: string },
) => authedSend<AnalyticAccount>(token, 'POST', '/api/accounting/analytics', data)

export const updateAnalytic = (
  token: string,
  id: string,
  patch: { code?: string; name?: string; group_name?: string; description?: string; is_active?: boolean },
) => authedSend<AnalyticAccount>(token, 'PATCH', `/api/accounting/analytics/${id}`, patch)

export const deleteAnalytic = (token: string, id: string) =>
  authedDelete(token, `/api/accounting/analytics/${id}`)

/** فیلترِ فهرستِ اسناد — پایه‌ی «سند حسابداری»، «ادغام اسناد» و «گزارش دفتر». */
export interface JournalQuery {
  dateFrom?: string
  dateTo?: string
  status?: 'temporary' | 'permanent'
  sourceType?: string
  q?: string
  limit?: number
}

/** فیلتر سمتِ سرور انجام می‌شود، نه در مرورگر: کشیدنِ کلِ دفترِ یک کسب‌وکارِ چندساله
 *  برای فیلترکردنش این‌جا، همان چیزی است که صفحه‌بندیِ keyset برای جلوگیری‌اش ساخته شد. */
/** یک سند با ردیف‌ها و منشأش — آخرین پله‌ی drill-down از تراز و دفتر. */
export const fetchJournalEntry = (token: string, entryId: string) =>
  authedGet<JournalEntryRecord>(token, `/api/journal-entries/${entryId}`)

/** فهرستِ اسناد با فیلترهای سرور.
 *
 *  `limit` سقفِ *کلِ* ردیف‌هاست، نه اندازه‌ی یک صفحه: سرور بیش از ۲۰۰ ردیف در هر
 *  درخواست نمی‌دهد (`MAX_LIMIT`) و با عددِ بزرگ‌تر ۴۲۲ برمی‌گرداند. پس این‌جا با کرسر
 *  چند صفحه گرفته می‌شود تا سقف پر شود — وگرنه هر صفحه‌ای که «کلِ سال» می‌خواست،
 *  بی‌صدا خطا می‌گرفت و «سندی نیست» نشان می‌داد. */
export const fetchJournalEntriesFiltered = async (
  token: string,
  query: JournalQuery = {},
): Promise<JournalEntryRecord[]> => {
  const qs = new URLSearchParams()
  if (query.dateFrom) qs.set('date_from', query.dateFrom)
  if (query.dateTo) qs.set('date_to', query.dateTo)
  if (query.status) qs.set('status', query.status)
  if (query.sourceType) qs.set('source_type', query.sourceType)
  if (query.q) qs.set('q', query.q)
  const wanted = query.limit ?? 100
  const path = `/api/journal-entries?${qs}`

  const rows: JournalEntryRecord[] = []
  let cursor: string | null = null
  while (rows.length < wanted) {
    const page: Page<JournalEntryRecord> = await authedGetPage<JournalEntryRecord>(token, path, {
      limit: Math.min(wanted - rows.length, SERVER_PAGE_MAX),
      cursor,
    })
    rows.push(...page.items)
    if (!page.next_cursor) break
    cursor = page.next_cursor
  }
  return rows
}

// --- دریافت و پرداخت: دسته‌چک، مرورِ بانکی، تسویه‌ی کارتخوان -----------------------

export interface BankTransactionRecord {
  id: string
  bank_account_id: string
  transaction_date: string
  /** مثبت = واریز، منفی = برداشت. */
  amount: string
  description: string
  is_reconciled: boolean
  source_type: string
  journal_entry_id: string | null
}

export const fetchBankTransactions = (token: string, bankAccountId?: string) => {
  const qs = bankAccountId ? `?bank_account_id=${bankAccountId}` : ''
  return authedGetAll<BankTransactionRecord>(token, `/api/bank-transactions${qs}`)
}

export interface CheckbookRecord {
  id: string
  bank_account_id: string
  bank_account_name: string
  serial: string
  first_number: string
  last_number: string
  leaf_count: number
  /** چند برگ خرج شده و چند تا مانده — سرور از روی چک‌های وصل‌شده می‌شمارد. */
  used_count: number
  remaining_count: number
  issue_date: string | null
  description: string
  is_active: boolean
  /** خالی یعنی «از حسابِ بانکی ارث ببر». */
  cheque_print_format: string
}

export interface CheckbookIn {
  bank_account_id: string
  serial?: string
  first_number: string
  last_number: string
  /** ۰ بگذارید تا سرور از بازه‌ی شماره‌ها حساب کند. */
  leaf_count?: number
  issue_date?: string | null
  description?: string
  cheque_print_format?: string
}

/** ویرایشِ دسته — هرچه نفرستید دست نمی‌خورد. */
export interface CheckbookUpdateIn {
  bank_account_id?: string
  serial?: string
  first_number?: string
  last_number?: string
  leaf_count?: number
  issue_date?: string | null
  description?: string
  cheque_print_format?: string
  is_active?: boolean
}

/** یک برگِ خرج‌شده و چکی که از آن درآمد. */
export interface CheckbookLeaf {
  number: string
  check_id: string
  status: string
  amount: string
  issue_date: string
  due_date: string
  contact_name: string | null
}

export const fetchCheckbooks = (token: string) => authedGet<CheckbookRecord[]>(token, '/api/checkbooks')

export const createCheckbook = (token: string, data: CheckbookIn) =>
  authedSend<CheckbookRecord>(token, 'POST', '/api/checkbooks', data)

export const updateCheckbook = (token: string, id: string, data: CheckbookUpdateIn) =>
  authedSend<CheckbookRecord>(token, 'PATCH', `/api/checkbooks/${id}`, data)

export const setCheckbookActive = (token: string, id: string, isActive: boolean) =>
  updateCheckbook(token, id, { is_active: isActive })

export const deleteCheckbook = (token: string, id: string) => authedDelete(token, `/api/checkbooks/${id}`)

/** شماره‌ی برگِ بعدیِ دسته — رشته‌ی خالی یعنی دسته تمام شده. */
export const fetchNextCheckNumber = (token: string, id: string) =>
  authedGet<{ number: string }>(token, `/api/checkbooks/${id}/next-number`)

/** هر برگِ خرج‌شده‌ی این دسته کجا رفت — دسته ← برگ ← چک. */
export const fetchCheckbookLeaves = (token: string, id: string) =>
  authedGet<CheckbookLeaf[]>(token, `/api/checkbooks/${id}/leaves`)

/** سیاستِ کنترلِ شماره‌ی چکِ پرداختنی. */
export interface ChequeControlOption {
  key: string
  label: string
  hint: string
  effects: string[]
  is_default: boolean
}

export interface ChequeControl {
  mode: string
  options: ChequeControlOption[]
  /** False یعنی هنوز روی پیش‌فرضِ سرویس است، نه انتخابِ کاربر. */
  is_explicit: boolean
}

export const fetchChequeControl = (token: string) =>
  authedGet<ChequeControl>(token, '/api/cheque-number-control')

export const setChequeControl = (token: string, mode: string) =>
  authedSend<ChequeControl>(token, 'PATCH', '/api/cheque-number-control', { mode })

export interface PosPendingGroup {
  terminal_no: string
  /** دستگاهِ واقعی — برای رسیدهای پیشِ اتصال خالی است. */
  pos_terminal_id: string | null
  terminal_label: string | null
  transaction_date: string
  count: number
  gross_amount: string
}

export const fetchPosPending = (
  token: string,
  query: { terminalNo?: string; posTerminalId?: string; dateFrom?: string; dateTo?: string } = {},
) => {
  const qs = new URLSearchParams()
  if (query.posTerminalId) qs.set('pos_terminal_id', query.posTerminalId)
  if (query.terminalNo) qs.set('terminal_no', query.terminalNo)
  if (query.dateFrom) qs.set('date_from', query.dateFrom)
  if (query.dateTo) qs.set('date_to', query.dateTo)
  return authedGet<PosPendingGroup[]>(token, `/api/pos-settlements/pending?${qs}`)
}

/** یک رسیدِ منبع — چیزی که مبلغِ تسویه از آن ساخته شده. */
export interface PosSettlementReceipt {
  id: string
  transaction_date: string
  contact_id: string
  contact_name: string
  contact_name2: string
  amount: string
  reference_no: string | null
  trace_no: string | null
  card_mask: string | null
  description: string
}

export interface PosSettlement {
  id: string
  /** شماره‌ی عملیاتیِ خودِ تسویه — با شماره‌ی سند و شماره‌ی پایانه یکی نیست. */
  number: number
  settlement_date: string
  /** برشِ انتخابِ رسیدها. با `settlement_date` یکی نیست و نباید بشود. */
  settle_through: string
  date_from: string | null
  pos_terminal_id: string
  terminal_no: string
  terminal_label: string
  bank_account_id: string
  bank_account_name: string
  bank_account_name2: string
  gross_amount: string
  fee_amount: string
  net_amount: string
  receipt_count: number
  journal_entry_id: string
  bank_transaction_id: string | null
  voided_at: string | null
  void_reason: string
  note: string
}

export interface PosSettlementDetail extends PosSettlement {
  receipts: PosSettlementReceipt[]
}

/** پیش از ثبت: مبلغ از کدام رسیدها ساخته می‌شود. */
export interface PosSettlementPreview {
  pos_terminal_id: string
  terminal_no: string
  terminal_label: string
  bank_account_id: string | null
  bank_account_name: string
  bank_account_name2: string
  gross_amount: string
  receipt_count: number
  receipts: PosSettlementReceipt[]
}

export const fetchPosSettlements = (
  token: string,
  query: { posTerminalId?: string; dateFrom?: string; dateTo?: string } = {},
) => {
  const qs = new URLSearchParams()
  if (query.posTerminalId) qs.set('pos_terminal_id', query.posTerminalId)
  if (query.dateFrom) qs.set('date_from', query.dateFrom)
  if (query.dateTo) qs.set('date_to', query.dateTo)
  return authedGet<PosSettlement[]>(token, `/api/pos-settlements?${qs}`)
}

export const fetchPosSettlement = (token: string, id: string) =>
  authedGet<PosSettlementDetail>(token, `/api/pos-settlements/${id}`)

export const fetchPosSettlementPreview = (
  token: string,
  query: { posTerminalId: string; settleThrough: string; dateFrom?: string },
) => {
  const qs = new URLSearchParams({
    pos_terminal_id: query.posTerminalId,
    settle_through: query.settleThrough,
  })
  if (query.dateFrom) qs.set('date_from', query.dateFrom)
  return authedGet<PosSettlementPreview>(token, `/api/pos-settlements/preview?${qs}`)
}

export const settlePosTerminal = (
  token: string,
  data: {
    /** الزامی — حسابِ مقصد و تفصیلیِ وجوهِ در راه هر دو از خودِ دستگاه می‌آیند. */
    pos_terminal_id: string
    settlement_date: string
    settle_through: string
    date_from?: string | null
    fee_amount: number
    note?: string
  },
) => authedSend<PosSettlement>(token, 'POST', '/api/pos-settlements', data)

/** ابطال با سندِ معکوس — رسیدها دوباره تسویه‌نشده می‌شوند. */
export const voidPosSettlement = (token: string, id: string, reason: string) =>
  authedSend<PosSettlement>(token, 'POST', `/api/pos-settlements/${id}/void`, { reason })

// ═══════════════════════ تسویه‌ی حسابِ طرف مقابل ═══════════════════════
//
// **تسویه پول جابه‌جا نمی‌کند.** رسیدِ دریافت و اعلامیه‌ی پرداخت (بالاتر در همین
// فایل) گردشِ پول‌اند؛ این‌جا فقط گفته می‌شود کدام بدهکار با کدام بستانکار تسویه
// شد. پس هیچ‌کدام از این توابع سندِ حسابداری نمی‌سازند.

export type SettlementSide = 'debit' | 'credit'
export type OpenItemStatus = 'unsettled' | 'partial' | 'settled' | 'over'

export const OPEN_ITEM_STATUS_LABEL: Record<OpenItemStatus, string> = {
  unsettled: 'تسویه‌نشده',
  partial: 'تسویه جزئی',
  settled: 'تسویه کامل',
  over: 'تخصیصِ بیش از مانده',
}

/** معینِ طرف مقابل — دریافتنی یا پرداختنی. */
export interface CounterpartyAccount {
  id: string
  code: string
  name: string
}

/** یک قلمِ قابلِ تسویه. مبلغ و سمت از اثرِ واقعیِ سند در دفتر می‌آیند، نه از نامِ فرم. */
export interface OpenItem {
  source_type: string
  source_id: string
  label: string
  /** شماره‌ی خودِ سند. رسیدِ دریافت ندارد و با `entry_number` شناخته می‌شود. */
  number: number | null
  entry_number: number | null
  document_date: string
  side: SettlementSide
  document_amount: string
  settled_amount: string
  remaining_amount: string
  status: OpenItemStatus
  status_label: string
  currency_code: string | null
  fx_amount: string | null
}

export interface OpenItemSummary {
  account_id: string
  account_name: string
  /** ماندهٔ خامِ کلِ معین در دفتر — با `net` یکی نیست وقتی گردشِ بی‌سند هست. */
  account_ledger_net: string
  /**
   * گردشی که سندِ قابلِ تسویه ندارد: سندِ دستی روی دریافتنی/پرداختنی، ماندهٔ اول
   * دوره، و چکِ ثبت‌شده پیش از نسخه‌ی ۰۱۱۴. صفر یعنی هر ریالِ این معین لنگرِ سند دارد.
   */
  unattributed: string
  contact_id: string | null
  contact_name: string
  debit_total: string
  credit_total: string
  /** جمعِ جبری — باید با ماندهٔ همان معین در دفتر بخواند. */
  net: string
  open_debit: string
  open_credit: string
  items: OpenItem[]
}

export interface SettlementAllocation {
  side: SettlementSide
  source_type: string
  source_id: string
  label: string
  amount: string
  number: number | null
  entry_number: number | null
  document_date: string | null
  document_amount: string | null
  settled_amount: string | null
  remaining_amount: string | null
  status: OpenItemStatus | null
  /** سندِ منبع دیگر روی این معین گردشی ندارد — باطل یا ویرایش شده. */
  source_missing: boolean
}

export interface SettlementRow {
  id: string
  number: number
  settlement_date: string
  contact_id: string
  contact_name: string
  account_id: string
  account_name: string
  currency_code: string
  description: string
  description2: string
  total_amount: string
  item_count: number
  voided_at: string | null
  void_reason: string
  created_at: string | null
}

export interface SettlementDetail extends SettlementRow {
  allocations: SettlementAllocation[]
}

/** یک گامِ تخصیص روی یک سند — «کِی، چقدر، و بابتِ چه». */
export interface AllocationHistoryRow {
  settlement_id: string
  number: number
  settlement_date: string
  side: SettlementSide
  amount: string
  description: string
  voided: boolean
  counter_items: { source_type: string; source_id: string; label: string; amount: string }[]
}

export const fetchCounterpartyAccounts = (token: string) =>
  authedGet<CounterpartyAccount[]>(token, '/api/settlements/accounts')

export const fetchOpenItems = (
  token: string,
  query: {
    accountId: string
    contactId?: string
    asOf?: string
    onlyOpen?: boolean
    excludeSettlementId?: string
  },
) => {
  const qs = new URLSearchParams({ account_id: query.accountId })
  if (query.contactId) qs.set('contact_id', query.contactId)
  if (query.asOf) qs.set('as_of', query.asOf)
  if (query.onlyOpen === false) qs.set('only_open', 'false')
  if (query.excludeSettlementId) qs.set('exclude_settlement_id', query.excludeSettlementId)
  return authedGet<OpenItemSummary>(token, `/api/settlements/open-items?${qs}`)
}

export const fetchAllocationHistory = (token: string, sourceType: string, sourceId: string) =>
  authedGet<AllocationHistoryRow[]>(
    token,
    `/api/settlements/history?source_type=${encodeURIComponent(sourceType)}&source_id=${sourceId}`,
  )

export const fetchContactSettlements = (
  token: string,
  query: { contactId?: string; accountId?: string; dateFrom?: string; dateTo?: string } = {},
) => {
  const qs = new URLSearchParams()
  if (query.contactId) qs.set('contact_id', query.contactId)
  if (query.accountId) qs.set('account_id', query.accountId)
  if (query.dateFrom) qs.set('date_from', query.dateFrom)
  if (query.dateTo) qs.set('date_to', query.dateTo)
  return authedGet<SettlementRow[]>(token, `/api/settlements?${qs}`)
}

export const fetchContactSettlement = (token: string, id: string) =>
  authedGet<SettlementDetail>(token, `/api/settlements/${id}`)

export const createContactSettlement = (
  token: string,
  data: {
    settlement_date: string
    contact_id: string
    account_id: string
    description?: string
    description2?: string
    items: { source_type: string; source_id: string; side: SettlementSide; amount: number }[]
  },
) => authedSend<SettlementDetail>(token, 'POST', '/api/settlements', data)

/** برگشتِ تسویه — فقط رابطه آزاد می‌شود؛ فاکتور و رسید دست‌نخورده می‌مانند. */
export const voidContactSettlement = (token: string, id: string, reason: string) =>
  authedSend<SettlementRow>(token, 'POST', `/api/settlements/${id}/void`, { reason })

// ═══════════════════════ عملیاتِ ماژولِ فروش ═══════════════════════
//
// همه زیرِ `/api/sales-ops`. یک نکته‌ی طراحی که در تایپ‌ها هم دیده می‌شود: تخفیف و
// عاملِ افزاینده *یک* موجودیت‌اند (`PricingFactor` با `kind`)، چون شکلشان یکی است و
// تنها فرقشان جهتِ اثر است.

/**
 * هفت اسلاتِ حسابِ نوعِ فروش.
 *
 * این تایپ **پنج‌تایشان را نداشت** و برای همین کلِ پروفایلِ حسابداریِ نوعِ فروش
 * مرده بود: موتورِ ثبت از ابتدا کالا و خدمت را تفکیک می‌کرد، ولی هیچ صفحه‌ای
 * نمی‌توانست حسابی به آن بدهد، پس هر هفت ستون تا ابد `null` می‌ماندند.
 */
export interface SaleTypeAccounts {
  goods_revenue_account_id: string | null
  service_revenue_account_id: string | null
  goods_return_account_id: string | null
  service_return_account_id: string | null
  goods_discount_account_id: string | null
  service_discount_account_id: string | null
  addition_account_id: string | null
}

export interface SaleType extends SaleTypeAccounts {
  id: string
  name: string
  code: string | null
  title2: string
  due_days: number
  default_tax_rate: string | null
  description: string
  is_active: boolean
}
export const fetchSaleTypes = (token: string) =>
  authedGet<SaleType[]>(token, '/api/sales-ops/sale-types')
export const createSaleType = (token: string, data: Omit<SaleType, 'id'>) =>
  authedSend<SaleType>(token, 'POST', '/api/sales-ops/sale-types', data)
/**
 * ویرایشِ **جزئی**. سرور فقط کلیدهای فرستاده‌شده را می‌نویسد؛ پیش از این همه را
 * می‌نوشت و یک بدنه‌ی ناقص هر هفت حساب را `null` می‌کرد.
 */
export const updateSaleType = (token: string, id: string, data: Partial<Omit<SaleType, 'id'>>) =>
  authedSend<SaleType>(token, 'PATCH', `/api/sales-ops/sale-types/${id}`, data)

export interface DiscountGroup {
  id: string
  name: string
  description: string
  is_active: boolean
  item_ids: string[]
  item_count: number
}
export interface DiscountGroupIn {
  name: string
  description: string
  is_active: boolean
  item_ids: string[]
}
export const fetchDiscountGroups = (token: string) =>
  authedGet<DiscountGroup[]>(token, '/api/sales-ops/discount-groups')
export const createDiscountGroup = (token: string, data: DiscountGroupIn) =>
  authedSend<DiscountGroup>(token, 'POST', '/api/sales-ops/discount-groups', data)
export const updateDiscountGroup = (token: string, id: string, data: DiscountGroupIn) =>
  authedSend<DiscountGroup>(token, 'PATCH', `/api/sales-ops/discount-groups/${id}`, data)

/** `kind` جهتِ اثر است: `discount` کاهنده، `markup` افزاینده. */
export interface PricingFactor {
  id: string
  name: string
  kind: 'discount' | 'markup'
  mode: 'percent' | 'amount'
  value: string
  scope: 'all' | 'item' | 'group'
  item_id: string | null
  group_id: string | null
  valid_from: string | null
  valid_to: string | null
  is_active: boolean
  description: string
}
export type PricingFactorIn = Omit<PricingFactor, 'id' | 'value'> & { value: number }
export const fetchPricingFactors = (token: string, kind?: 'discount' | 'markup') =>
  authedGet<PricingFactor[]>(token, `/api/sales-ops/pricing-factors${kind ? `?kind=${kind}` : ''}`)
export const createPricingFactor = (token: string, data: PricingFactorIn) =>
  authedSend<PricingFactor>(token, 'POST', '/api/sales-ops/pricing-factors', data)
export const updatePricingFactor = (token: string, id: string, data: PricingFactorIn) =>
  authedSend<PricingFactor>(token, 'PATCH', `/api/sales-ops/pricing-factors/${id}`, data)

export interface PriceAnnouncement {
  id: string
  name: string
  effective_from: string
  notes: string
  is_active: boolean
  line_count: number
  lines: PriceListItemRecord[]
}
export const fetchPriceAnnouncements = (token: string) =>
  authedGet<PriceAnnouncement[]>(token, '/api/sales-ops/price-announcements')
export const createPriceAnnouncement = (
  token: string,
  data: {
    name: string
    effective_from: string
    notes: string
    is_active: boolean
    lines: PriceRuleIn[]
  },
) => authedSend<PriceAnnouncement>(token, 'POST', '/api/sales-ops/price-announcements', data)

export interface ProductBundle {
  id: string
  name: string
  bundle_price: string | null
  is_active: boolean
  description: string
  lines: { item_id: string; qty: string }[]
}
export const fetchBundles = (token: string) =>
  authedGet<ProductBundle[]>(token, '/api/sales-ops/bundles')
export const createBundle = (
  token: string,
  data: {
    name: string
    bundle_price: number | null
    is_active: boolean
    description: string
    lines: { item_id: string; qty: number }[]
  },
) => authedSend<ProductBundle>(token, 'POST', '/api/sales-ops/bundles', data)

export interface CommissionRule {
  id: string
  salesperson_id: string
  salesperson_name: string
  rate: string
  basis: 'net' | 'profit'
  is_active: boolean
  description: string
}
export const fetchCommissionRules = (token: string) =>
  authedGet<CommissionRule[]>(token, '/api/sales-ops/commission-rules')
export const createCommissionRule = (
  token: string,
  data: {
    salesperson_id: string
    rate: number
    basis: 'net' | 'profit'
    is_active: boolean
    description: string
  },
) => authedSend<CommissionRule>(token, 'POST', '/api/sales-ops/commission-rules', data)

export interface CommissionRow {
  salesperson_id: string
  salesperson_name: string
  invoice_count: number
  base_amount: string
  rate: string
  basis: string
  amount: string
}
export interface CommissionRun {
  id: string
  date_from: string
  date_to: string
  total_amount: string
  note: string
  created_at: string
  rows: CommissionRow[]
}
export const fetchCommissionPreview = (token: string, from: string, to: string) =>
  authedGet<{ date_from: string; date_to: string; total_amount: string; rows: CommissionRow[] }>(
    token,
    `/api/sales-ops/commission/preview?date_from=${from}&date_to=${to}`,
  )
export const createCommissionRun = (
  token: string,
  data: { date_from: string; date_to: string; note: string },
) => authedSend<CommissionRun>(token, 'POST', '/api/sales-ops/commission/runs', data)
export const fetchCommissionRuns = (token: string) =>
  authedGet<CommissionRun[]>(token, '/api/sales-ops/commission/runs')

export interface CustomsDeclaration {
  id: string
  declaration_no: string
  declaration_date: string
  customs_office: string
  hs_code: string
  destination_country: string
  declared_value: string
  currency_code: string
  invoice_id: string | null
  invoice_number: number | null
  description: string
}
export const fetchCustoms = (token: string) =>
  authedGet<CustomsDeclaration[]>(token, '/api/sales-ops/customs')
export const createCustoms = (
  token: string,
  data: Omit<CustomsDeclaration, 'id' | 'invoice_number' | 'declared_value'> & { declared_value: number },
) => authedSend<CustomsDeclaration>(token, 'POST', '/api/sales-ops/customs', data)

/** یک تعدیل: این سمت بدهکار، آن سمت بستانکار، به یک مبلغِ مشترک. */
export interface CreditDebitNoteLine {
  id: string
  seq: number
  debit_contact_id: string | null
  debit_contact_name: string
  debit_account_id: string
  debit_account_code: string
  debit_account_name: string
  credit_contact_id: string | null
  credit_contact_name: string
  credit_account_id: string
  credit_account_code: string
  credit_account_name: string
  /** به ارزِ سند. */
  amount: string
  /** معادلِ ریالی — همان عددی که در سندِ حسابداری نشسته. */
  base_amount: string
  description: string
}

export interface CreditDebitNote {
  id: string
  number: number | null
  note_date: string
  amount: string
  base_amount: string
  reason: string
  currency_code: string
  exchange_rate: string
  lines: CreditDebitNoteLine[]
  invoice_id: string | null
  journal_entry_id: string | null
  journal_entry_number: number | null
  journal_entry_date: string | null
  voided_at: string | null
  voided_by_name: string | null
  void_reason: string
  void_entry_id: string | null
  void_entry_number: number | null
  void_entry_date: string | null
  /** میراثِ شکلِ تک‌سمتی — فقط اعلامیه‌های پیش از مهاجرتِ ۰۱۲۷ پرش دارند. */
  kind: 'debit' | 'credit' | null
  contact_id: string | null
  contact_name: string
}

/** معینی که یک سمتِ اعلامیه می‌تواند رویش بنشیند — با عنوانش، نه فقط کدش. */
export interface NoteAccount {
  id: string
  code: string
  name: string
  /** `accounts_receivable` / `accounts_payable` برای حساب‌های طرف مقابل. */
  system_role: string | null
}

export interface CreditDebitNoteLineIn {
  debit_contact_id?: string | null
  debit_account_id?: string | null
  credit_contact_id?: string | null
  credit_account_id?: string | null
  amount: number
  description?: string
}

export interface NoteFilter {
  date_from?: string
  date_to?: string
  contact_id?: string
  status?: 'all' | 'active' | 'voided'
  q?: string
}

/** فیلتر سمتِ سرور؛ صفحه‌ها با کرسر جمع می‌شوند تا سقفِ ۲۰۰ردیفی نخورد. */
export const fetchNotes = (token: string, filter: NoteFilter = {}) => {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(filter)) if (v) qs.set(k, v)
  const suffix = qs.toString() ? `?${qs}` : ''
  return authedGetAll<CreditDebitNote>(token, `/api/sales-ops/notes${suffix}`)
}
/** `counterparty` = سمتِ دارای طرف حساب (دریافتنی/پرداختنی)؛ `other` = سمتِ بی‌طرف‌حساب. */
export const fetchNoteAccounts = (token: string, scope: 'counterparty' | 'other' = 'counterparty') =>
  authedGet<NoteAccount[]>(token, `/api/sales-ops/notes/accounts?scope=${scope}`)
export const createNote = (
  token: string,
  data: {
    note_date: string
    lines: CreditDebitNoteLineIn[]
    reason?: string
    currency_code?: string
    exchange_rate?: number
  },
  idempotencyKey?: string,
) =>
  authedSend<CreditDebitNote>(token, 'POST', '/api/sales-ops/notes', data, idempotencyKey)
/** `voidDate` خالی = تاریخِ خودِ اعلامیه. */
export const voidNote = (token: string, id: string, reason: string, voidDate?: string) =>
  authedSend<CreditDebitNote>(token, 'POST', `/api/sales-ops/notes/${id}/void`, {
    reason,
    void_date: voidDate || null,
  })

export const closeInvoices = (
  token: string,
  data: { invoice_ids?: string[]; date_from?: string | null; date_to?: string | null },
) =>
  authedSend<{ count: number; first_date: string; last_date: string; total: string }>(
    token,
    'POST',
    '/api/sales-ops/invoices/close',
    data,
  )

/** پیشنهادِ قیمت — *پیشنهاد* است نه حکم؛ `applied` می‌گوید عدد از کجا آمده. */
export const fetchPricingSuggestion = (token: string, itemId: string, qty: number, on?: string) =>
  authedGet<{
    unit_price: string
    gross: string
    discount: string
    net: string
    applied: { kind: string; name: string; value: string }[]
  }>(token, `/api/sales-ops/pricing/suggest?item_id=${itemId}&qty=${qty}${on ? `&on=${on}` : ''}`)

/** یک حسابِ خلافِ ماهیت — `balance` مثبت است و سمتش در `balance_side` می‌آید. */
export interface NatureViolation {
  account_id: string
  account_code: string
  account_name: string
  account_type: string
  nature: string
  /** ماهیت را کاربر ست کرده (true) یا از نوعِ حساب مشتق شده (false). */
  nature_is_explicit: boolean
  /** تیکِ «کنترل ماهیت طی دوره» روی همین حساب. */
  nature_control: boolean
  total_debit: number
  total_credit: number
  balance: number
  balance_side: string
}

/** ردیفی روی حسابِ «تفصیلی پذیر» که تفصیلی ندارد — سوراخِ گزارشِ تفصیلی. */
export interface MissingTafsili {
  account_id: string
  account_code: string
  account_name: string
  entry_id: string
  entry_number: number | null
  entry_date: string
  source_type: string
  /** سندِ دستی یا ساخته‌ی ماژول. */
  is_manual: boolean
  debit: string
  credit: string
  description: string
}

/** در هر سه سطحِ اجبار کار می‌کند — سطح تعیین می‌کند چه مسدود شود، نه چه دیده شود. */
export const fetchMissingTafsili = (token: string) =>
  authedGet<MissingTafsili[]>(token, '/api/reports/missing-tafsili')

export const fetchNatureViolations = (token: string, controlledOnly = false) =>
  authedGet<NatureViolation[]>(
    token,
    `/api/reports/nature-violations${controlledOnly ? '?controlled_only=true' : ''}`,
  )


// ── حقوق و دستمزد: جدول‌های مرجع و قرارداد ────────────────────────────────────

/** رسته شغل — فهرستِ بسته‌ی سپیدار، مبنای کدِ شغلِ بیمه. */
export const JOB_FAMILIES = [
  'مالی', 'مهندسی فرهنگی', 'امور اجتماعی', 'فناوری اطلاعات', 'بهداشت و درمان',
  'فنی مهندسی', 'خدمات', 'کشاورزی و محیط زیست', 'بازاریابی و فروش', 'حراست و نگهبانی',
  'کارگری', 'ترابری', 'تولیدی', 'کنترل کیفی', 'تحقیقات', 'انبارداری', 'فضا',
  'اعضای هیئت علمی دانشگاه',
]

/** نوعِ استخدام — فهرستِ بسته‌ی سپیدار. */
export const EMPLOYMENT_TYPES = [
  'سایر', 'پیمانی', 'رسمی', 'رسمی آزمایشی', 'قراردادی', 'روزمزد', 'خرید خدمت',
  'مأمور', 'ساعتی', 'رسمی فصلی', 'کارمزدی', 'شرکتی',
]

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  hire: 'استخدام',
  amend: 'اصلاح قرارداد',
}

export const FACTOR_CATEGORY_LABELS: Record<string, string> = {
  benefit: 'مزایا',
  deduction: 'کسورات',
}

export const FACTOR_KIND_LABELS: Record<string, string> = {
  fixed: 'قراردادی (ثابت)',
  variable: 'متغیر',
}

export const TAX_GROUP_KIND_LABELS: Record<string, string> = {
  normal: 'مناطق عادی',
  deprived: 'مناطق محروم',
  exempt: 'معاف',
}

export const BRANCH_KIND_LABELS: Record<string, string> = {
  insurance: 'شعبه بیمه',
  tax: 'حوزه مالیاتی',
  supplementary: 'بیمه تکمیلی',
}

/** «نحوه محاسبه مالیات» — فقط برای حوزه مالیاتی؛ سرور هم همین را می‌سنجد. */
export const TAX_CALC_METHOD_LABELS: Record<string, string> = {
  monthly: 'تعدیل ماهانه',
  annual: 'تعدیل سالانه',
  none: 'بدون تعدیل',
}

export interface ServiceLocationRecord {
  id: string
  code: string
  name: string
  name2: string
  is_active: boolean
}

export interface JobTitleRecord {
  id: string
  code: string
  name: string
  name2: string
  job_family: string
  insurance_job_code: string
  is_active: boolean
}

export interface PayrollFactorRecord {
  id: string
  name: string
  name2: string
  category: string
  kind: string
  is_extraordinary: boolean
  /** خالی = عاملِ ساخته‌ی کاربر؛ کلیددار = عاملی که موتورِ فیش می‌شناسدش. */
  system_key: string
  is_active: boolean
  /** ترتیبِ ردیف‌های فیش. **فقط نمایشی** — هیچ محاسبه‌ای از آن نمی‌خوانَد، و
   *  فیشِ صادرشده را هم تکان نمی‌دهد چون شماره‌ی ردیفش منجمد است. */
  display_priority: number
  /** پروفایلِ حسابداریِ عامل. خالی = حسابِ عمومیِ حقوق، یعنی رفتارِ امروز. */
  expense_account_id: string | null
  expense_detail_class: string
  payable_account_id: string | null
  payable_detail_class: string
  /** در حکمی یا فیشی نشسته؟ طبقه‌ی عاملِ در استفاده قفل است. */
  in_use: boolean
  /** ضریبِ **مؤثرِ** شرکت در هر مبنا — با پیش‌فرض‌ها حل‌شده، همان چیزی که موتور
   *  استفاده می‌کند. رابط قاعده‌ی پیش‌فرض را دوباره پیاده نمی‌کند. */
  participation: Record<string, string>
}

export interface PayrollTaxGroupRecord {
  id: string
  name: string
  kind: string
  percent: string
  is_active: boolean
}

export interface InsuranceTaxBranchRecord {
  id: string
  code: string
  name: string
  kind: string
  is_active: boolean
  /** طرف‌حسابِ سازمان — بدهیِ بیمه/مالیات رویش می‌نشیند. خالی = هنوز وصل نشده. */
  contact_id: string | null
  /** خوانده‌شده از خودِ طرف حساب، نه کپی‌شده. */
  contact_name: string
  analytic_code: string

  /** «کد شرکت / شماره پرونده» — پرونده مالیاتی یا کد کارگاه، بسته به نوع. */
  registration_code: string
  workplace_name: string
  workplace_address: string
  employer_name: string
  /** قرارداد کارفرما با مرجع قانونی — نه قرارداد استخدامی کارمند. */
  agreement_number: string
  /** عدد سرصفحه ثبت کارگاه؛ نمی‌گوید کدام کارمندان معاف‌اند. */
  insurance_exempt_count: number
  cost_center_id: string | null
  cost_center_name: string
  /** فقط برای `kind === 'tax'`. */
  tax_calculation_method: string
  /** روی حکمی نشسته؟ اگر بله، نوعش دیگر عوض نمی‌شود. */
  in_use: boolean
}

/** طرف‌حسابی که تیکِ «کارمند» دارد — ورودیِ فهرستِ «نام کارمند»ِ فرمِ قرارداد. */
export interface EmployeeCandidate {
  contact_id: string
  name: string
  national_id: string | null
  /** خالی = هنوز پرونده‌ی حقوق و دستمزد ندارد؛ اولین قرارداد می‌سازدش. */
  employee_id: string | null
  has_contract: boolean
}

export interface ContractLine {
  id?: string
  factor_id: string
  amount: number | string
  factor_name?: string
  factor_category?: string
}

export interface SalaryContractRecord {
  id: string
  employee_id: string
  employee_name: string
  effective_from: string
  contract_type: string
  number: string
  valid_until: string | null
  service_end_date: string | null
  employment_type: string
  service_location_id: string | null
  job_title_id: string | null
  cost_center_id: string | null
  base_salary: string
  housing_allowance: string
  food_allowance: string
  other_allowance: string
  tax_group_id: string | null
  tax_branch_id: string | null
  insurance_branch_id: string | null
  housing_loan_exempt_amount: string
  is_insured: boolean
  is_hard_job: boolean
  exempt_employee_insurance: boolean
  exempt_employer_insurance: boolean
  employer_exempt_percent: string
  exempt_unemployment_insurance: boolean
  employer_name: string
  has_supplementary_insurance: boolean
  supplementary_branch: string
  supplementary_insurer: string
  description: string
  lines: ContractLine[]
}

export const fetchServiceLocations = (token: string) =>
  authedGet<ServiceLocationRecord[]>(token, '/api/service-locations')
export const createServiceLocation = (token: string, body: Partial<ServiceLocationRecord>) =>
  authedSend<ServiceLocationRecord>(token, 'POST', '/api/service-locations', body)
export const updateServiceLocation = (token: string, id: string, body: Partial<ServiceLocationRecord>) =>
  authedSend<ServiceLocationRecord>(token, 'PATCH', `/api/service-locations/${id}`, body)

export const fetchJobTitles = (token: string) => authedGet<JobTitleRecord[]>(token, '/api/job-titles')
export const createJobTitle = (token: string, body: Partial<JobTitleRecord>) =>
  authedSend<JobTitleRecord>(token, 'POST', '/api/job-titles', body)
export const updateJobTitle = (token: string, id: string, body: Partial<JobTitleRecord>) =>
  authedSend<JobTitleRecord>(token, 'PATCH', `/api/job-titles/${id}`, body)

export const fetchPayrollFactors = (token: string) =>
  authedGet<PayrollFactorRecord[]>(token, '/api/payroll-factors')
export const createPayrollFactor = (token: string, body: Partial<PayrollFactorRecord>) =>
  authedSend<PayrollFactorRecord>(token, 'POST', '/api/payroll-factors', body)
/** عوامل پیش‌فرض را می‌سازد (بی‌خطر اگر از قبل باشند) و همه را برمی‌گرداند. */
export const createDefaultPayrollFactors = (token: string) =>
  authedSend<PayrollFactorRecord[]>(token, 'POST', '/api/payroll-factors/defaults', {})

export const fetchPayrollTaxGroups = (token: string) =>
  authedGet<PayrollTaxGroupRecord[]>(token, '/api/payroll-tax-groups')
export const createPayrollTaxGroup = (token: string, body: Partial<PayrollTaxGroupRecord>) =>
  authedSend<PayrollTaxGroupRecord>(token, 'POST', '/api/payroll-tax-groups', body)

export const fetchInsuranceTaxBranches = (token: string, kind?: string) =>
  authedGet<InsuranceTaxBranchRecord[]>(
    token,
    kind ? `/api/insurance-tax-branches?kind=${kind}` : '/api/insurance-tax-branches',
  )
export const createInsuranceTaxBranch = (token: string, body: Partial<InsuranceTaxBranchRecord>) =>
  authedSend<InsuranceTaxBranchRecord>(token, 'POST', '/api/insurance-tax-branches', body)

export const fetchEmployeeCandidates = (token: string, q = '') =>
  authedGet<EmployeeCandidate[]>(
    token,
    q ? `/api/payroll/employee-candidates?q=${encodeURIComponent(q)}` : '/api/payroll/employee-candidates',
  )

/** کدام نوعِ قرارداد برای این شخص مجاز است — «استخدام» فقط تا وقتی ثبت نشده. */
export const fetchAllowedContractTypes = (token: string, contactId: string) =>
  authedGet<{ allowed: string[]; labels: Record<string, string> }>(
    token,
    `/api/payroll/contract-types?contact_id=${contactId}`,
  )

export const fetchSalaryContracts = (token: string, employeeId?: string) =>
  authedGet<SalaryContractRecord[]>(
    token,
    employeeId ? `/api/salary-contracts?employee_id=${employeeId}` : '/api/salary-contracts',
  )

export const createSalaryContract = (token: string, body: Record<string, unknown>) =>
  authedSend<SalaryContractRecord>(token, 'POST', '/api/salary-contracts', body)


// ── وام‌های پرسنلی، تسویه حساب، اطلاعاتِ استقرار ──────────────────────────────

export interface LoanTypeRecord {
  id: string
  code: string
  name: string
  name2: string
  default_installments: number
  is_active: boolean
}

export const fetchLoanTypes = (token: string) =>
  authedGet<LoanTypeRecord[]>(token, '/api/loan-types')
export const createLoanType = (token: string, body: Partial<LoanTypeRecord>) =>
  authedSend<LoanTypeRecord>(token, 'POST', '/api/loan-types', body)

export interface LoanInstallmentRecord {
  id: string
  seq: number
  due_date: string
  amount: string
  /** کدام دوره‌ی حقوقی کسرش کرد. null = هنوز کسر نشده. */
  deducted_period_id: string | null
}

export interface EmployeeLoanRecord {
  id: string
  employee_id: string
  employee_name: string
  loan_type_id: string | null
  amount: string
  loan_date: string
  installment_count: number
  status: 'active' | 'settled' | 'cancelled'
  note: string
  /** مانده مشتق است — جمعِ اقساطِ کسرنشده، نه ستونی که بتواند از اقساط جدا بیفتد. */
  balance: string
  installments: LoanInstallmentRecord[]
}

export const LOAN_STATUS_LABELS: Record<string, string> = {
  active: 'در حال کسر',
  settled: 'تسویه‌شده',
  cancelled: 'لغوشده',
}

export const fetchEmployeeLoans = (token: string, employeeId?: string) =>
  authedGet<EmployeeLoanRecord[]>(
    token,
    employeeId ? `/api/employee-loans?employee_id=${employeeId}` : '/api/employee-loans',
  )

export const createEmployeeLoan = (token: string, body: Record<string, unknown>) =>
  authedSend<EmployeeLoanRecord>(token, 'POST', '/api/employee-loans', body)

export const cancelEmployeeLoan = (token: string, loanId: string) =>
  authedSend<EmployeeLoanRecord>(token, 'POST', `/api/employee-loans/${loanId}/cancel`, {})

export interface PayrollSettlementRecord {
  id: string
  employee_id: string
  employee_name: string
  settlement_date: string
  severance_amount: string
  leave_payout_amount: string
  other_earnings: string
  loan_balance: string
  other_deductions: string
  net_amount: string
  note: string
  journal_entry_id: string | null
}

export const fetchSettlements = (token: string) =>
  authedGet<PayrollSettlementRecord[]>(token, '/api/payroll-settlements')
export const createSettlement = (token: string, body: Record<string, unknown>) =>
  authedSend<PayrollSettlementRecord>(token, 'POST', '/api/payroll-settlements', body)

export interface DeploymentInfoRecord {
  id: string
  employee_id: string
  employee_name: string
  year: number
  cumulative_gross: string
  cumulative_tax: string
  cumulative_insurance: string
  leave_balance_days: string
  prior_service_days: number
  note: string
}

export const fetchDeploymentInfo = (token: string) =>
  authedGet<DeploymentInfoRecord[]>(token, '/api/payroll-deployment')

/** `PUT` است نه `POST`: یک وضعیتِ استقرار برای هر (کارمند، سال). */
export const saveDeploymentInfo = (token: string, body: Record<string, unknown>) =>
  authedSend<DeploymentInfoRecord>(token, 'PUT', '/api/payroll-deployment', body)

/* ── بررسیِ یکپارچگیِ دفتر (§۲۷) ──────────────────────────────────────────── */

export interface IntegrityRow {
  label: string
  detail: string
  debit: string
  credit: string
  /** «چقدر پرت است» — بررسی‌های ساختاری صفر می‌گذارند. */
  difference: string
  entry_id?: string | null
  account_id?: string | null
  /** لنگرِ کاردکس — برای بررسی‌های انبار. */
  item_id?: string | null
}

export interface IntegrityCheck {
  key: string
  title: string
  description: string
  /** error سلامتِ دفتر را زیر سؤال می‌برد؛ warning فقط دیده می‌شود. */
  severity: 'error' | 'warning'
  ok: boolean
  /** شمارشِ کاملِ یافته‌ها، حتی وقتی `rows` بریده شده. */
  count: number
  rows: IntegrityRow[]
  truncated: boolean
}

export interface IntegrityReport {
  date_from: string | null
  date_to: string | null
  total_debit: string
  total_credit: string
  difference: string
  ok: boolean
  checks: IntegrityCheck[]
}

/** گزارش است، نه گارد: چیزی مسدود نمی‌شود، فقط نشان داده می‌شود. */
export const fetchIntegrityReport = (token: string, filters: ReportFilters = {}) =>
  authedGet<IntegrityReport>(token, `/api/reports/integrity${reportFiltersQs(filters)}`)


// --- رسید دریافت -------------------------------------------------------------------
// قرینه‌ی «اعلامیه پرداخت». یک رسید می‌تواند هم‌زمان نقد و حواله و کارت‌خوان و چک
// داشته باشد و همه‌شان **یک** سند حسابداری می‌سازند؛ پس اینجا چهار آرایه‌ی
// تایپ‌دار داریم، نه یک آرایه‌ی یکسان با فیلدهای اختیاری.

export type ReceiptType = 'customer' | 'supplier' | 'intermediary' | 'other' | 'petty_holder'

export const RECEIPT_TYPE_LABELS: Record<ReceiptType, string> = {
  customer: 'دریافت از مشتری',
  supplier: 'دریافت از تأمین‌کننده',
  intermediary: 'دریافت از واسط',
  other: 'سایر دریافت‌ها',
  petty_holder: 'دریافت از تنخواه‌دار',
}

export interface ReceiptCashIn {
  amount: number
  /** خالی = صندوقِ پیش‌فرض، مثلِ بقیه‌ی مسیرها. */
  cashbox_id?: string | null
  description?: string
}

export interface ReceiptTransferIn {
  amount: number
  bank_account_id: string
  /** شماره‌ی حواله — روی ردیفِ سند هم می‌نشیند تا مغایرتِ بانکی پیدایش کند. */
  reference_no?: string
  description?: string
  description2?: string
}

export interface ReceiptCardIn {
  amount: number
  pos_terminal_id: string
  /** کد پیگیری اجباری است: کلیدِ پیدا کردنِ تراکنش و تطبیق با تسویه. */
  reference_no: string
  trace_no?: string
  card_mask?: string
  description?: string
}

export interface ReceiptChequeIn {
  amount: number
  number: string
  due_date: string
  issue_date?: string | null
  bank_name?: string
  /** کد صیادی، **جدا از** شماره‌ی چک. شانزده رقم. */
  sayad_id?: string
  back_number?: string
  branch_name?: string
  branch_code?: string
  account_number?: string
  /** صاحبِ چک — همیشه طرف‌حسابِ ما نیست (چکِ شخصِ ثالث). */
  owner_name?: string
  description?: string
  description2?: string
}

export interface ReceiptDocumentIn {
  receipt_type: ReceiptType
  contact_id: string
  receipt_date: string
  currency_code?: string
  exchange_rate?: number
  discount_amount?: number
  discount_account_id?: string | null
  description?: string
  description2?: string
  establishment?: string
  cash: ReceiptCashIn[]
  transfers: ReceiptTransferIn[]
  cards: ReceiptCardIn[]
  cheques: ReceiptChequeIn[]
  related_documents?: { document_type: string; document_id: string; allocated_amount?: number }[]
}

export interface ReceiptComponentRecord {
  kind: 'cash' | 'transfer' | 'cheque' | 'card'
  label: string
  amount: string
  description: string
  /** شناسه‌ی موجودیتِ واقعی: تراکنشِ خزانه یا چک. از همین به چک می‌رسیم. */
  source_id: string | null
  reference_no: string
  due_date: string | null
  status: string
}

export interface ReceiptDocumentRecord {
  id: string
  number: number
  receipt_type: ReceiptType
  receipt_type_label: string
  contact_id: string
  contact_name: string
  receipt_date: string
  counterparty_account_id: string
  discount_account_id: string | null
  currency_code: string
  exchange_rate: string
  /** پولی که واقعاً رسید. */
  receipt_amount: string
  /** معادلش به ارزِ پایه — همان که سند می‌خورد. */
  base_currency_amount: string
  discount_amount: string
  /** مبلغ + تخفیف؛ مانده‌ی طرف‌حساب به اندازه‌ی این حرکت می‌کند. */
  settlement_total: string
  description: string
  description2: string
  establishment: string
  journal_entry_id: string
  /** «وجه نقد، حواله، چک» — مشتق است، نه متنی که کاربر بنویسد. */
  items_summary: string
  components: ReceiptComponentRecord[]
  related_documents: { document_type: string; document_id: string; allocated_amount: string }[]
  voided_at: string | null
  created_at: string
  updated_at: string
  created_by_name: string
  updated_by_name: string
}

export interface ReceiptFilters {
  receipt_type?: string
  contact_id?: string
  date_from?: string
  date_to?: string
  search?: string
}

const receiptFiltersQs = (filters: ReceiptFilters): string => {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value) qs.set(key, String(value))
  }
  const text = qs.toString()
  return text ? `?${text}` : ''
}

/** فیلتر سمتِ سرور است؛ کشیدنِ کلِ دفتر برای فیلترکردنش در مرورگر با اولین
 *  کسب‌وکارِ چندساله از کار می‌افتد. */
export const fetchReceiptDocuments = (token: string, filters: ReceiptFilters = {}) =>
  authedGetAll<ReceiptDocumentRecord>(token, `/api/receipts${receiptFiltersQs(filters)}`)

export const fetchReceiptDocument = (token: string, id: string) =>
  authedGet<ReceiptDocumentRecord>(token, `/api/receipts/${id}`)

export const createReceiptDocument = (token: string, data: ReceiptDocumentIn, idempotencyKey: string) =>
  authedSend<ReceiptDocumentRecord>(token, 'POST', '/api/receipts', data, idempotencyKey)

export const voidReceiptDocument = (token: string, id: string, reason: string) =>
  authedSend<ReceiptDocumentRecord>(token, 'POST', `/api/receipts/${id}/void`, { reason })

/** پیش‌نویسِ رسیدِ تازه از روی یکی موجود — شناسه‌های یکتا پاک می‌آیند. */
export const fetchReceiptDuplicate = (token: string, id: string) =>
  authedGet<Record<string, unknown>>(token, `/api/receipts/${id}/duplicate`)

export interface RasResult {
  ras_date: string
  average_days: string
  total_amount: string
  counted_rows: number
  skipped_rows: number
}

/** راس‌گیری یک محاسبه است، نه تراکنش — هیچ چیزی ذخیره نمی‌شود. */
export const previewRas = (
  token: string,
  base_date: string,
  rows: { amount: number; due_date: string }[],
  include_same_day = true,
) => authedSend<RasResult>(token, 'POST', '/api/receipts/ras-preview', { base_date, rows, include_same_day })

export const openReceiptPrintView = (token: string, id: string) =>
  openInvoicePrintView(token, `/api/receipts/${id}/print`)

// ──────────────────────────── واحدهای سنجش (§۱۷–§۲۳) ────────────────────────────
//
// واحد تا امروز یک رشته‌ی آزاد روی کالا بود، پس «کیلوگرم» و «كيلوگرم» دو واحدِ
// متفاوت بودند و نگاشتِ کدِ واحدِ مؤدیان برای هر املا جدا لازم می‌شد.

export interface UnitRecord {
  id: string
  name: string
  name2: string
  is_active: boolean
  /** چند قلم کالا رویش نشسته — تا فهرست پیش از غیرفعال‌سازی خبر بدهد. */
  item_count: number
}

export const fetchUnits = (token: string) => authedGet<UnitRecord[]>(token, '/api/units')

export const createUnit = (token: string, data: { name: string; name2?: string }) =>
  authedSend<UnitRecord>(token, 'POST', '/api/units', data)

export const updateUnit = (
  token: string,
  unitId: string,
  patch: { name?: string; name2?: string; is_active?: boolean },
) => authedSend<UnitRecord>(token, 'PATCH', `/api/units/${unitId}`, patch)

/** حذف فقط برای واحدِ استفاده‌نشده؛ وگرنه سرور ۴۰۹ با پیامِ «غیرفعالش کنید» می‌دهد. */
export const deleteUnit = (token: string, unitId: string) => authedDelete(token, `/api/units/${unitId}`)

// ─────────────────── انبارهای مرتبط و مازادِ موجودی (§۲۴–§۳۳) ───────────────────

/** یک انبارِ مرتبط. `is_default` فقط پیشنهادِ فرم است، نه مالکیت. */
export interface ItemWarehouseLink {
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  is_default: boolean
  /** override‌های انبارمحور؛ `null` یعنی «همان عددِ کالا». */
  min_stock: string | null
  max_stock: string | null
}

/**
 * مازادِ موجودی — **سدِ تراکنش نیست**.
 *
 * حداکثرِ موجودی جلوی ورودِ کالا را نمی‌گیرد؛ فقط می‌گوید کجا مازاد داریم.
 */
export interface OverStockRow {
  item_id: string
  sku: string
  name: string
  unit: string
  qty_on_hand: string
  max_stock: string
  excess: string
}

export const fetchOverStock = (token: string) => authedGet<OverStockRow[]>(token, '/api/stock/over')

// ─────────────────── گروه‌بندی و مشخصات کالا (§۳۴–§۳۶) ───────────────────
//
// `category` یک متنِ آزاد بود، پس «لوازم خانگی» و «لوازم‌خانگی» دو گروه می‌شدند
// و گزارشِ گروهی قابلِ اعتماد نبود. برای «رنگ» و «سایز» هم جایی نبود — و برای هر
// مشخصه نباید ستونِ تازه‌ای روی کالا بنشیند.

export interface ItemGroupRecord {
  id: string
  code: string
  name: string
  name2: string
  notes: string
  is_active: boolean
  item_count: number
}

export const fetchItemGroups = (token: string) => authedGet<ItemGroupRecord[]>(token, '/api/item-groups')

export const createItemGroup = (token: string, data: { code?: string; name: string; name2?: string; notes?: string }) =>
  authedSend<ItemGroupRecord>(token, 'POST', '/api/item-groups', data)

export const updateItemGroup = (
  token: string,
  groupId: string,
  patch: { code?: string; name?: string; name2?: string; notes?: string; is_active?: boolean },
) => authedSend<ItemGroupRecord>(token, 'PATCH', `/api/item-groups/${groupId}`, patch)

/** حذف فقط برای گروهِ بی‌کالا؛ وگرنه سرور ۴۰۹ با پیامِ «ببندیدش» می‌دهد. */
export const deleteItemGroup = (token: string, groupId: string) =>
  authedDelete(token, `/api/item-groups/${groupId}`)

export interface ItemAttributeRecord {
  id: string
  name: string
  name2: string
  is_active: boolean
}

export const fetchItemAttributes = (token: string) =>
  authedGet<ItemAttributeRecord[]>(token, '/api/item-attributes')

export const createItemAttribute = (token: string, data: { name: string; name2?: string }) =>
  authedSend<ItemAttributeRecord>(token, 'POST', '/api/item-attributes', data)

export const updateItemAttribute = (
  token: string,
  attributeId: string,
  patch: { name?: string; name2?: string; is_active?: boolean },
) => authedSend<ItemAttributeRecord>(token, 'PATCH', `/api/item-attributes/${attributeId}`, patch)

/** حذفِ مشخصه، مقدارهایش روی همه‌ی کالاها را هم می‌برد. */
export const deleteItemAttribute = (token: string, attributeId: string) =>
  authedDelete(token, `/api/item-attributes/${attributeId}`)

// ═══════════════ برگشت از فروش: ابطال و علتِ برگشت (فصلِ «فاکتور برگشتی») ═══════════════
//
// بلوکِ تازه در **انتهای فایل** — قاعده‌ی تخته‌ی ادعا، تا دو ایجنتِ هم‌زمان در
// بدترین حالت یک تعارضِ ساده‌ی ته‌فایل بسازند نه یک فایلِ درهم.

/** علتِ برگشتِ کالا — مِسترِ مستقل، نه متنِ آزاد. */
export interface SalesReturnReasonRecord {
  id: string
  title: string
  title2: string
  is_active: boolean
}

/** `onlyActive` برای فرمِ ثبت است؛ فهرستِ کامل برای صفحه‌ی مدیریت و سندهای تاریخی. */
export const fetchSalesReturnReasons = (token: string, onlyActive = false) =>
  authedGet<SalesReturnReasonRecord[]>(
    token,
    `/api/sales-return-reasons${onlyActive ? '?only_active=true' : ''}`,
  )

export const createSalesReturnReason = (
  token: string,
  data: { title: string; title2?: string; is_active?: boolean },
) => authedSend<SalesReturnReasonRecord>(token, 'POST', '/api/sales-return-reasons', data)

export const updateSalesReturnReason = (
  token: string,
  id: string,
  data: { title: string; title2?: string; is_active?: boolean },
) => authedSend<SalesReturnReasonRecord>(token, 'PATCH', `/api/sales-return-reasons/${id}`, data)

/** ابطالِ سندِ برگشت — سندِ معکوس می‌خورد، ردیف پاک نمی‌شود. */
export const voidSalesReturn = (token: string, id: string, reason: string, voidDate?: string) =>
  authedSend<SalesReturnRecord>(token, 'POST', `/api/sales-returns/${id}/void`, {
    reason,
    void_date: voidDate ?? null,
  })

export const voidPurchaseReturn = (token: string, id: string, reason: string, voidDate?: string) =>
  authedSend<PurchaseReturnRecord>(token, 'POST', `/api/purchase-returns/${id}/void`, {
    reason,
    void_date: voidDate ?? null,
  })


// ── اعلامیه قیمت: حلِ قیمت و تغییرِ گروهیِ فی ──────────────────────────
//
// «چرا فیِ این ردیف این عدد است؟» تنها از این‌جا پرسیده می‌شود. تا پیش از فصلِ
// «اعلامیه قیمت» فرمِ فاکتور و صندوق هرکدام نگاشتِ `item_id → price`ِ خودشان را
// می‌ساختند و تاریخِ اجرا، فعال‌بودن و چهار بُعدِ زمینه را نمی‌دیدند — پس فرم یک
// قیمت پر می‌کرد و سرور با قاعده‌ی دیگری اعتبارش را می‌سنجید.

/** پاسخِ حلِ قیمت. `null` یعنی هیچ قاعده‌ای با این زمینه نخواند. */
export interface ResolvedPrice {
  rule_id: string
  announcement_id: string
  announcement_name: string
  effective_from: string
  unit_price: string
  currency_code: string
  addition_percent: string
  allow_rate_change: boolean
  allow_discount_change: boolean
  max_increase_percent: string
  max_decrease_percent: string
  /** حدها در دامنه حساب شده‌اند؛ رابط دوباره حسابشان نمی‌کند. `null` = بی‌حد. */
  min_price: string | null
  max_price: string | null
  /** چند قاعده هم‌رتبه خواندند: برنده پایدار است ولی پیکربندی مبهم است. */
  ambiguous: boolean
}

export interface PriceContext {
  saleTypeId?: string | null
  unitId?: string | null
  contactId?: string | null
  currencyCode?: string
  on?: string | null
}

export const resolvePrice = (token: string, itemId: string, ctx: PriceContext = {}) => {
  const q = new URLSearchParams({ item_id: itemId })
  if (ctx.saleTypeId) q.set('sale_type_id', ctx.saleTypeId)
  if (ctx.unitId) q.set('unit_id', ctx.unitId)
  if (ctx.contactId) q.set('contact_id', ctx.contactId)
  if (ctx.currencyCode) q.set('currency_code', ctx.currencyCode)
  if (ctx.on) q.set('on', ctx.on)
  return authedGet<ResolvedPrice | null>(token, `/api/sales-ops/pricing/resolve?${q.toString()}`)
}

/** حالت‌های دیالوگِ «تغییر فی». */
export type BulkPriceMode =
  | 'increase_percent'
  | 'increase_amount'
  | 'decrease_percent'
  | 'decrease_amount'
  | 'fixed'
  | 'none'

export interface BulkPriceIn {
  mode: BulkPriceMode
  value: number
  /** رند به مضربِ ریال (۱، ۱۰، ۱۰۰، ۱۰۰۰…) — قیمت عددِ صحیحِ ریالی است. */
  rounding?: number
  rule_ids?: string[]
  item_ids?: string[]
  sale_type_id?: string | null
  currency_code?: string | null
}

/**
 * «۲۰٪ اضافه کن» جابه‌جاکننده است نه نشاننده: تکرارِ درخواست ۱۰۰ را به ۱۴۴
 * می‌برد. پس کلیدِ یکتاسازی اینجا اختیاری نیست — فراخوان باید یک کلیدِ پایدار
 * بدهد و تا موفق‌شدن همان را نگه دارد.
 */
export const bulkChangePrices = (
  token: string,
  announcementId: string,
  data: BulkPriceIn,
  idempotencyKey: string,
) =>
  authedSend<{ announcement_id: string; changed: number; replayed: boolean }>(
    token,
    'POST',
    `/api/sales-ops/price-announcements/${announcementId}/bulk-price`,
    data,
    idempotencyKey,
  )

/** حذفِ یک قاعده‌ی قیمت — صریح، نه عارضه‌ی جانبیِ یک ذخیره. */
export const deletePriceListItem = (token: string, listId: string, rowId: string) =>
  authedDelete(token, `/api/price-lists/${listId}/items/${rowId}`)
/** ابطالِ رسید انبار؛ رسید و ردیف‌هایش باقی می‌مانند و حرکت جبرانی در کاردکس ثبت می‌شود. */
export const voidWarehouseReceipt = (token: string, id: string, reason: string) =>
  authedSend<WarehouseReceiptRecord>(token, 'POST', `/api/warehouse-receipts/${id}/void`, { reason })

/** صدور رسید با کلید تکرارنشدن؛ retry شبکه نباید موجودی را دوبار زیاد کند. */
export const createWarehouseReceiptIdempotent = (
  token: string,
  invoiceId: string,
  data: { receipt_date: string; warehouse_id: string; description?: string; lines: { purchase_invoice_line_id: string; qty: number }[] },
  idempotencyKey: string,
) => authedSend<WarehouseReceiptRecord>(
  token,
  'POST',
  `/api/purchase-invoices/${invoiceId}/warehouse-receipts`,
  data,
  idempotencyKey,
)

// فیلدهای Trace افزوده‌شده به خروجی خرید؛ declaration merging اجازه می‌دهد
// بلوک مشترک api.ts فقط در انتهای فایل رشد کند و محل‌های پرتصادم بالا دست‌نخورند.
export interface PurchaseInvoiceRecord {
  journal_entry_id: string | null
  related_payment_count: number
}

export interface PurchaseInvoiceDuplicateDraft {
  source_invoice_number: number | null
  contact_id: string | null
  cost_center_id: string | null
  description: string
  description2: string
  tax_rate: string | number
  currency_code: string | null
  exchange_rate: string | number
  invoice_discount: string | number
  invoice_addition: string | number
  duty_amount: string | number
  lines: Array<{
    item_id: string
    qty: string | number
    unit_cost: string | number
    discount: string | number
    addition: string | number
    duty_amount: string | number
    description: string
    expense_account_id?: string | null
  }>
  cleared_fields: string[]
}

/** پیش‌نویس رونوشت از سرور می‌آید تا هیچ شناسه یا تخصیص تاریخی دوباره استفاده نشود. */
export const fetchPurchaseInvoiceDuplicate = (token: string, id: string) =>
  authedGet<PurchaseInvoiceDuplicateDraft>(token, `/api/purchase-invoices/${id}/duplicate`)

// قرارداد تکمیلی پیش‌فاکتور در انتهای فایل می‌ماند تا declaration merging از
// دست‌کاری بلوک قدیمی و پرتصادم جلوگیری کند.
export interface SalesQuotationRecord {
  customer_name2: string
  delivery_location: string
  sale_type_id: string | null
  currency_code: string | null
  exchange_rate: string
  terminated_at: string | null
  is_expired: boolean
  commercial_status: 'not_invoiced' | 'partially_invoiced' | 'fully_invoiced'
  invoiced_invoice_ids: string[]
}

export interface SalesQuotationLine {
  item_code_snapshot: string
  item_name_snapshot: string
  unit_snapshot: string
  invoiced_qty: string
  remaining_invoiceable_qty: string
  issued_qty: string
  remaining_issueable_qty: string
}

export const duplicateSalesQuotation = (token: string, id: string) =>
  authedSend<SalesQuotationRecord>(token, 'POST', `/api/sales-quotations/${id}/duplicate`, {}, newIdempotencyKey())

export const terminateSalesQuotation = (token: string, id: string) =>
  authedSend<SalesQuotationRecord>(token, 'POST', `/api/sales-quotations/${id}/terminate`, {})

export const reopenSalesQuotation = (token: string, id: string) =>
  authedSend<SalesQuotationRecord>(token, 'POST', `/api/sales-quotations/${id}/reopen`, {})

export const createSalesQuotationIdempotent = (token: string, data: SalesQuotationInput, key: string) =>
  authedSend<SalesQuotationRecord>(token, 'POST', '/api/sales-quotations', data, key)

export const convertQuotationToInvoiceIdempotent = (token: string, id: string, key: string) =>
  authedSend<unknown>(token, 'POST', `/api/sales-quotations/${id}/convert`, {}, key)

// قرارداد تکمیلی فصل «فاکتور فروش» فقط در انتهای فایل افزوده شده است؛ سند تجاری،
// سند حسابداری، خروج انبار و وصول چهار وضعیت مستقل دارند.
export interface SalesInvoiceRecord {
  customer_snapshot: Record<string, string>
  seller_snapshot: Record<string, string>
  customer_name2: string
  delivery_location: string
  receivable_account_id: string | null
  settlement_terms: 'cash' | 'credit' | 'mixed'
  statement_date: string | null
  total_additions: string
  total_duties: string
  journal_entry_id: string | null
  accounting_status: 'unposted' | 'posted'
  fulfillment_status: 'not_applicable' | 'not_issued' | 'partially_issued' | 'fully_issued'
  issued_total_qty: string
  settled_amount: string
  remaining_amount: string
  financial_status: 'unsettled' | 'partially_settled' | 'fully_settled'
  related_receipt_count: number
  final_amount: string
}

export interface InvoiceLineRecord {
  addition: string
  duty_amount: string
  item_code_snapshot: string
  item_name_snapshot: string
  unit_snapshot: string
  tax_rate_snapshot: string
  tax_amount_snapshot: string
  issued_qty: string
  remaining_issueable_qty: string
}

export interface SalesInvoiceCommercialInput {
  invoice_date: string
  warehouse_id?: string | null
  contact_id?: string | null
  customer_name2?: string
  delivery_location?: string
  receivable_account_id?: string | null
  settlement_terms?: 'cash' | 'credit' | 'mixed'
  statement_date?: string | null
  description?: string
  tax_rate?: number
  cost_center_id?: string | null
  broker_id?: string | null
  salesperson_id?: string | null
  sale_type_id?: string | null
  currency_code?: string | null
  exchange_rate?: number
  invoice_discount?: number
  rounding?: number
  /** فاکتوری که از خروجِ ثبت‌شده ساخته می‌شود — موجودی را دوباره کم نمی‌کند. */
  source_warehouse_issue_id?: string | null
  lines: Array<{
    item_id: string
    qty: number
    unit_price: number
    discount?: number
    addition?: number
    duty_amount?: number
    description?: string
    source_issue_line_id?: string | null
  }>
}

export const createSalesInvoiceCommercial = (
  token: string,
  data: SalesInvoiceCommercialInput,
  idempotencyKey: string,
) => authedSend<SalesInvoiceRecord>(token, 'POST', '/api/sales-invoices', data, idempotencyKey)

export const createImmediateSalesInvoice = (
  token: string,
  data: Parameters<typeof createSalesInvoiceDirect>[1],
  idempotencyKey?: string,
) => authedSend<unknown>(token, 'POST', '/api/sales-invoices/immediate', data, idempotencyKey)

export interface WarehouseIssueRecord {
  id: string
  number: number
  issue_date: string
  /** `sale` | `consumption` | `other` — انتقال سندِ خودش را دارد. */
  issue_type: string
  /** `invoice`: «ثبت فاکتور» ساختش · `direct`: مستقل ثبت شد و شاید بعد فاکتور گرفت. */
  origin: string
  sales_invoice_id: string | null
  warehouse_id: string
  receiver_id: string | null
  source_quotation_id: string | null
  cost_center_id: string | null
  status: string
  description: string
  journal_entry_id: string | null
  voided_at: string | null
  void_reason: string
  created_by_id: string
  total_qty: string
  total_cost: string
  lines: Array<{
    id: string
    seq: number
    sales_invoice_line_id: string | null
    item_id: string
    qty: string
    unit_cost: string
    amount: string
    secondary_qty: string | null
    secondary_unit_snapshot: string
    account_id: string | null
    account_code: string
    account_name: string
    item_code_snapshot: string
    item_name_snapshot: string
    unit_snapshot: string
    description: string
  }>
}

export const issueSalesInvoiceJournal = (token: string, invoiceId: string) =>
  authedSend<SalesInvoiceRecord>(token, 'POST', `/api/sales-invoices/${invoiceId}/journal`, {})

export const fetchWarehouseIssues = (token: string, invoiceId: string) =>
  authedGet<WarehouseIssueRecord[]>(token, `/api/sales-invoices/${invoiceId}/warehouse-issues`)

export const createWarehouseIssueIdempotent = (
  token: string,
  invoiceId: string,
  data: {
    issue_date: string
    warehouse_id: string
    description?: string
    lines: { sales_invoice_line_id: string; qty: number }[]
  },
  idempotencyKey: string,
) => authedSend<WarehouseIssueRecord>(
  token,
  'POST',
  `/api/sales-invoices/${invoiceId}/warehouse-issues`,
  data,
  idempotencyKey,
)

export const voidWarehouseIssue = (token: string, id: string, reason: string) =>
  authedSend<WarehouseIssueRecord>(token, 'POST', `/api/warehouse-issues/${id}/void`, { reason })

// ── رسید انبار: رسیدِ مستقیم، حمل، برگشتِ رسید، چاپ و زمینه‌ی پرداخت ──────────
//
// همه‌ی عددها از سرور می‌آیند. «فی تمام‌شده»، سهمِ حمل و «خالص» در این‌جا حساب
// نمی‌شوند (§۲۳: «الگوریتم تسهیم را داخل UI ننویسیم»؛ §۲۷: خالص مشتق است).

/** انواعِ رسیدِ **انبار** — با `RECEIPT_TYPE_LABELS` (رسید دریافتِ خزانه) یکی نیست. */
export const WAREHOUSE_RECEIPT_TYPE_LABELS: Record<string, string> = {
  purchase_domestic: 'خرید (داخلی)',
  purchase_import: 'خرید (وارداتی)',
  production: 'تولید',
  other: 'سایر',
  opening: 'موجودی اول دوره',
}

/** برگشت «موجودی اول دوره» ندارد — فرمِ مرجع هم ندارَدش. */
export const RETURN_TYPE_LABELS: Record<string, string> = {
  purchase_domestic: 'خرید (داخلی)',
  purchase_import: 'خرید (وارداتی)',
  production: 'تولید',
  other: 'سایر',
}

export interface WarehouseReceiptLineFull {
  id: string
  seq: number
  purchase_invoice_line_id: string | null
  item_id: string
  qty: string
  /** «فی» — بهای خرید، پیش از حمل. */
  unit_cost: string
  freight_share: string
  /** «فی تمام‌شده» — با «فی» یکی نیست. */
  landed_unit_cost: string
  tax_rate_snapshot: string
  tax_amount_snapshot: string
  item_code_snapshot: string
  item_name_snapshot: string
  unit_snapshot: string
  description: string
}

export interface WarehouseReceiptFull {
  id: string
  number: number
  receipt_date: string
  purchase_invoice_id: string | null
  warehouse_id: string
  receipt_type: string
  contact_id: string | null
  carrier_id: string | null
  freight_agent_id: string | null
  currency_code: string | null
  exchange_rate: string
  freight_amount: string
  freight_tax: string
  freight_duty: string
  freight_basis: string
  tax_rate: string
  goods_amount: string
  /** «جمع مبلغ حمل»ِ پنجره‌ی حمل — جزءِ خالص نیست. */
  freight_total: string
  tax_amount: string
  duty_amount: string
  net_amount: string
  journal_entry_id: string | null
  status: string
  description: string
  description2: string
  voided_at: string | null
  void_reason: string
  created_by_id: string
  lines: WarehouseReceiptLineFull[]
}

export const fetchAllWarehouseReceipts = (
  token: string,
  filters: { receipt_type?: string; warehouse_id?: string; contact_id?: string } = {},
) => {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) qs.set(key, value)
  const query = qs.toString()
  return authedGetAll<WarehouseReceiptFull>(token, `/api/warehouse-receipts${query ? `?${query}` : ''}`)
}

export interface DirectWarehouseReceiptIn {
  receipt_date: string
  warehouse_id: string
  receipt_type: string
  contact_id?: string | null
  carrier_id?: string | null
  freight_amount?: number
  freight_tax?: number
  freight_duty?: number
  freight_basis?: string
  tax_rate?: number
  description?: string
  lines: { item_id: string; qty: number; unit_cost: number; description?: string }[]
}

export const createDirectWarehouseReceipt = (token: string, data: DirectWarehouseReceiptIn, idempotencyKey: string) =>
  authedSend<WarehouseReceiptFull>(token, 'POST', '/api/warehouse-receipts', data, idempotencyKey)

export const printWarehouseReceipt = (token: string, receiptId: string) =>
  openInvoicePrintView(token, `/api/warehouse-receipts/${receiptId}/print`)

export interface ReceiptReturnableLine {
  warehouse_receipt_line_id: string
  purchase_invoice_line_id: string | null
  receipt_number: number
  receipt_date: string
  item_id: string
  item_code: string
  item_name: string
  unit: string
  received: string
  already_returned: string
  remaining: string
  unit_cost: string
  landed_unit_cost: string
  /** مشتق از مقدارها، نه یک بولینِ مستقل. */
  return_status: 'not_returned' | 'partially_returned' | 'fully_returned'
}

export const fetchReceiptReturnable = (token: string, receiptId: string) =>
  authedGet<ReceiptReturnableLine[]>(token, `/api/warehouse-receipts/${receiptId}/returnable`)

export interface ReceiptReturnIn {
  return_date: string
  warehouse_receipt_id: string
  receiver_id?: string | null
  return_type: string
  description?: string
  lines: {
    warehouse_receipt_line_id: string
    qty: number
    /** خالی یعنی «همان ارزشِ دفتری» — هیچ اختلافی ساخته نمی‌شود. */
    agreed_unit_value?: number | null
    description?: string
  }[]
}

export const createReceiptReturn = (token: string, data: ReceiptReturnIn, idempotencyKey: string) =>
  authedSend<PurchaseReturnRecord>(token, 'POST', '/api/purchase-returns', data, idempotencyKey)

export interface ReceiptPaymentContext {
  payment_type: string
  contact_id: string
  contact_name: string
  document_type: 'warehouse_receipt'
  document_id: string
  receipt_number: number
  description: string
  /** «جمع مبلغ رسید انبار» — برای نمایش. */
  receipt_net_amount: string
  goods_due: string
  freight_due: string
  freight_payee_id: string | null
  /** پیشنهادِ قابلِ‌ویرایش — عمداً برابرِ خالص نیست؛ حمل بدهیِ حمل‌کننده است. */
  suggested_amount: string
  currency_code: string
  exchange_rate: string
}

export const fetchReceiptPaymentContext = (token: string, receiptId: string) =>
  authedGet<ReceiptPaymentContext>(token, `/api/warehouse-receipts/${receiptId}/payment-context`)

// ── سیاستِ صدورِ فاکتور فروش ─────────────────────────────────────────────
//
// «ثبت فاکتور» سندِ حسابداری و خروجِ انبار را هم بزند، یا آن دو را به فهرست
// بسپارد؟ همان شکلِ `ChequeControl` — یک پرچمِ سیاست روی کسب‌وکار.

/** همان شکلِ گزینه‌های سیاست؛ نامِ جدا فقط برای خوانایی در فراخوان‌هاست. */
export type SalesPostingOption = ChequeControlOption

export interface SalesPosting {
  mode: string
  options: SalesPostingOption[]
  /** False یعنی هنوز روی پیش‌فرضِ سرویس است، نه انتخابِ کاربر. */
  is_explicit: boolean
}

export const fetchSalesPosting = (token: string) =>
  authedGet<SalesPosting>(token, '/api/sales-invoice-posting')

export const setSalesPosting = (token: string, mode: string) =>
  authedSend<SalesPosting>(token, 'PATCH', '/api/sales-invoice-posting', { mode })

// ───────────────────── مرور جامع طرف حساب ─────────────────────

/** مانده‌ی یک نقشِ طرف حساب. `ledger_net` برابرِ null یعنی طرف حساب تفصیلی ندارد. */
export interface RolePosition {
  role: 'customer' | 'supplier'
  role_label: string
  account_id: string
  account_code: string
  account_name: string
  debit_total: string
  credit_total: string
  net: string
  open_net: string
  ledger_net: string | null
  unattributed: string | null
  document_count: number
}

export interface CounterpartySummary {
  contact_id: string
  contact_name: string
  contact_type: string
  has_analytic: boolean
  positions: RolePosition[]
  total_net: string
  open_net: string
  uncleared_cheques: string
  net_without_uncleared_cheques: string
}

export interface CounterpartyEvent {
  source_type: string
  source_id: string
  label: string
  number: number | null
  entry_number: number | null
  document_date: string
  role: 'customer' | 'supplier'
  role_label: string
  account_id: string
  account_code: string
  account_name: string
  side: 'debit' | 'credit'
  document_amount: string
  currency_code: string | null
  fx_amount: string | null
  settled_amount: string
  remaining_amount: string
  status: string
  status_label: string
  running_balance: string
}

export interface CounterpartyEventLine {
  kind: 'product' | 'journal' | 'adjustment'
  seq: number
  code: string
  title: string
  description: string
  quantity: string | null
  unit_price: string | null
  net_unit_price: string | null
  debit: string | null
  credit: string | null
}

export interface CounterpartyEventDetail {
  source_type: string
  source_id: string
  label: string
  journal_entry_id: string | null
  lines: CounterpartyEventLine[]
}

export const fetchCounterpartySummary = (token: string, contactId: string, asOf?: string) =>
  authedGet<CounterpartySummary>(
    token,
    `/api/reports/counterparty/${contactId}/summary${asOf ? `?as_of=${asOf}` : ''}`,
  )

export const fetchCounterpartyEvents = (
  token: string,
  contactId: string,
  opts: { from?: string; to?: string; role?: string } = {},
) => {
  const q = new URLSearchParams()
  if (opts.from) q.set('date_from', opts.from)
  if (opts.to) q.set('date_to', opts.to)
  if (opts.role) q.set('role', opts.role)
  const qs = q.toString()
  return authedGet<CounterpartyEvent[]>(
    token,
    `/api/reports/counterparty/${contactId}/events${qs ? `?${qs}` : ''}`,
  )
}

export const fetchCounterpartyEventLines = (
  token: string,
  contactId: string,
  sourceType: string,
  sourceId: string,
) =>
  authedGet<CounterpartyEventDetail>(
    token,
    `/api/reports/counterparty/${contactId}/events/${sourceType}/${sourceId}/lines`,
  )

// ───────────────────── مرور فروش ─────────────────────

export interface SalesReviewSummary {
  invoice_count: number
  line_count: number
  gross_amount: string
  discount: string
  tax: string
  return_amount: string
  net_sales: string
  sold_qty: string
  issued_qty: string
  /** فروخته‌شده منهای خارج‌شده. */
  unissued_qty: string
  item_count: number
}

export interface SalesByItem {
  item_id: string
  item_code: string
  item_name: string
  is_service: boolean
  unit_name: string
  secondary_unit_name: string
  sold_qty: string
  returned_qty: string
  net_qty: string
  issued_qty: string
  unissued_qty: string
  /** همان مقدار با واحدِ دیگر — هرگز با مقدارِ اصلی جمع نمی‌شود. */
  sold_qty_secondary: string | null
  issued_qty_secondary: string | null
  line_count: number
  gross_amount: string
  discount: string
  tax: string
  duty: string
  addition: string
  net_amount: string
  return_amount: string
  net_sales: string
  average_unit_price: string | null
  stock_qty: string
}

export interface SalesByCustomer {
  contact_id: string | null
  contact_name: string
  contact_type: string
  group_name: string
  credit_limit: string
  invoice_count: number
  sold_qty: string
  returned_qty: string
  issued_qty: string
  gross_amount: string
  discount: string
  tax: string
  duty: string
  addition: string
  net_amount: string
  return_amount: string
  net_sales: string
}

export interface SalesByWarehouse {
  warehouse_id: string
  warehouse_name: string
  issue_count: number
  invoice_count: number
  issued_qty: string
  issued_cost: string
}

export interface SalesReviewDocument {
  source_type: string
  source_id: string
  label: string
  number: number | null
  document_date: string
  contact_id: string | null
  contact_name: string
  sale_type_name: string
  is_voided: boolean
  line_count: number
  sold_qty: string
  returned_qty: string
  issued_qty: string
  gross_amount: string
  discount: string
  tax: string
  duty: string
  addition: string
  net_amount: string
  return_amount: string
  net_sales: string
}

export interface SalesReviewLine {
  line_id: string
  source_type: string
  source_id: string
  number: number | null
  document_date: string
  contact_id: string | null
  contact_name: string
  sale_type_name: string
  item_id: string
  item_code: string
  item_name: string
  barcode: string
  unit_name: string
  sold_qty: string
  sold_qty_secondary: string | null
  returned_qty: string
  issued_qty: string
  unissued_qty: string
  unit_price: string
  warehouse_names: string[]
  is_voided: boolean
  gross_amount: string
  discount: string
  tax: string
  duty: string
  addition: string
  net_amount: string
  return_amount: string
  net_sales: string
}

export interface PreinvoiceProgress {
  quotation_id: string
  line_id: string
  number: number | null
  quotation_date: string
  contact_id: string | null
  contact_name: string
  status: string
  item_id: string
  item_name: string
  unit_price: string
  quoted_qty: string
  invoiced_qty: string
  issued_qty: string
  invoice_line_count: number
  remaining_invoiceable: string
  remaining_issueable: string
}

export interface SalesReviewScope {
  from?: string
  to?: string
  contactId?: string
  itemId?: string
  saleTypeId?: string
  warehouseId?: string
  voided?: boolean
}

function salesReviewQuery(scope: SalesReviewScope): string {
  const q = new URLSearchParams()
  if (scope.from) q.set('date_from', scope.from)
  if (scope.to) q.set('date_to', scope.to)
  if (scope.contactId) q.set('contact_id', scope.contactId)
  if (scope.itemId) q.set('item_id', scope.itemId)
  if (scope.saleTypeId) q.set('sale_type_id', scope.saleTypeId)
  if (scope.warehouseId) q.set('warehouse_id', scope.warehouseId)
  if (scope.voided) q.set('voided', 'true')
  const qs = q.toString()
  return qs ? `?${qs}` : ''
}

export const fetchSalesReviewSummary = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<SalesReviewSummary>(token, `/api/reports/sales-review/summary${salesReviewQuery(scope)}`)

export const fetchSalesByItem = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<SalesByItem[]>(token, `/api/reports/sales-review/items${salesReviewQuery(scope)}`)

export const fetchSalesByCustomer = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<SalesByCustomer[]>(token, `/api/reports/sales-review/customers${salesReviewQuery(scope)}`)

export const fetchSalesByWarehouse = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<SalesByWarehouse[]>(token, `/api/reports/sales-review/warehouses${salesReviewQuery(scope)}`)

export const fetchSalesReviewDocuments = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<SalesReviewDocument[]>(token, `/api/reports/sales-review/documents${salesReviewQuery(scope)}`)

export const fetchSalesReviewLines = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<SalesReviewLine[]>(token, `/api/reports/sales-review/lines${salesReviewQuery(scope)}`)

export const fetchPreinvoiceProgress = (token: string, scope: SalesReviewScope = {}) =>
  authedGet<PreinvoiceProgress[]>(token, `/api/reports/sales-review/preinvoices${salesReviewQuery(scope)}`)

// ═══════════════════ خروج انبار (مهاجرت ۰۱۳۳) ═══════════════════

/** نوعِ خروج — «انتقال بین انبار» سندِ خودش را دارد ولی در همین فهرست می‌آید. */
export const WAREHOUSE_ISSUE_TYPE_LABELS: Record<string, string> = {
  sale: 'فروش',
  consumption: 'مصرف',
  other: 'سایر',
  transfer: 'انتقال بین انبار',
}

/** ردیفِ فهرستِ خروج‌ها — خروج یا انتقال، با ستون‌هایی که به نوع بسته‌اند. */
export interface WarehouseIssueRow {
  kind: 'issue' | 'transfer'
  id: string
  number: number | null
  doc_date: string
  issue_type: string
  type_label: string
  origin: string
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  receiver_id: string | null
  receiver_name: string
  destination_warehouse_id: string | null
  destination_warehouse_code: string
  destination_warehouse_name: string
  sales_invoice_id: string | null
  sales_invoice_number: number | null
  source_quotation_id: string | null
  quotation_number: number | null
  journal_entry_id: string | null
  journal_entry_number: number | null
  created_by_name: string
  line_count: number
  total_qty: string
  total_cost: string
  description: string
  voided_at: string | null
  void_reason: string
}

export interface WarehouseIssueLedgerFilters {
  issue_type?: string
  warehouse_id?: string
  receiver_id?: string
  date_from?: string
  date_to?: string
  state?: string
}

/** فیلتر سمتِ سرور است؛ صفحه‌ها با کرسر خوانده می‌شوند (سقفِ ۲۰۰). */
export const fetchWarehouseIssueLedger = (token: string, filters: WarehouseIssueLedgerFilters = {}) => {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) qs.set(key, value)
  const query = qs.toString()
  return authedGetAll<WarehouseIssueRow>(token, `/api/warehouse-issues${query ? `?${query}` : ''}`)
}

export const fetchWarehouseIssue = (token: string, issueId: string) =>
  authedGet<WarehouseIssueRecord>(token, `/api/warehouse-issues/${issueId}`)

export interface DirectWarehouseIssueIn {
  issue_date: string
  issue_type: 'sale' | 'consumption' | 'other'
  warehouse_id: string
  receiver_id?: string | null
  source_quotation_id?: string | null
  cost_center_id?: string | null
  account_id?: string | null
  description?: string
  lines: { item_id: string; qty: number; unit_id?: string | null; account_id?: string | null; description?: string }[]
}

export const createDirectWarehouseIssue = (token: string, data: DirectWarehouseIssueIn, idempotencyKey: string) =>
  authedSend<WarehouseIssueRecord>(token, 'POST', '/api/warehouse-issues', data, idempotencyKey)

/** قالبِ استاندارد یا A5 — همان سند، کاغذِ دیگر. */
export const printWarehouseIssue = (token: string, issueId: string, template: 'standard' | 'a5' = 'standard') =>
  openInvoicePrintView(token, `/api/warehouse-issues/${issueId}/print?template=${template}`)

export const printStockTransfer = (token: string, transferId: string, template: 'standard' | 'a5' = 'standard') =>
  openInvoicePrintView(token, `/api/stock-transfers/${transferId}/print?template=${template}`)

export const voidStockTransfer = (token: string, transferId: string, reason: string) =>
  authedSend<StockTransferRecord>(token, 'POST', `/api/stock-transfers/${transferId}/void`, { reason })

export interface IssueInvoiceContext {
  issue_id: string
  issue_number: number
  warehouse_id: string
  receiver_id: string | null
  receiver_name: string
  lines: {
    issue_line_id: string
    item_id: string
    item_name: string
    qty: string
    unit: string
    suggested_unit_price: string
  }[]
}

export const fetchIssueInvoiceContext = (token: string, issueId: string) =>
  authedGet<IssueInvoiceContext>(token, `/api/warehouse-issues/${issueId}/invoice-context`)

// ═════════════════ برگشت خروج انبار (مهاجرتِ ۰۱۳۴) ═════════════════

export type IssueReturnType = 'sale' | 'consumption' | 'other'

/** سه نوع — «انتقال» برگشت ندارد؛ انتقالِ برعکس یک انتقالِ دیگر است. */
export const ISSUE_RETURN_TYPE_LABELS: Record<string, string> = {
  sale: 'فروش',
  consumption: 'مصرف',
  other: 'سایر',
}

/** وضعیتِ برگشتِ فیزیکیِ یک فاکتور برگشتی — کنارِ وضعیتِ مالی، نه جایش. */
export const SALES_RETURN_PHYSICAL_LABELS: Record<string, string> = {
  inline: 'همراهِ برگشت',
  none: '—',
  not_returned: 'برنگشته',
  partially_returned: 'بخشی برگشته',
  fully_returned: 'کامل برگشته',
}

/** «ثبت برگشت به انبار» از دفترِ فاکتورهای برگشتی — فقط زمینه منتقل می‌شود. */
export const ISSUE_RETURN_PREFILL_KEY = 'cubita.inventory.issueReturnPrefill'
export type IssueReturnPrefill = { kind: 'sales_return' | 'issue'; id: string; return_type: IssueReturnType }

export interface IssueReturnRow {
  id: string
  number: number
  return_date: string
  return_type: IssueReturnType
  type_label: string
  origin: 'direct' | 'sales_return'
  warehouse_id: string
  warehouse_code: string
  warehouse_name: string
  deliverer_id: string | null
  deliverer_name: string
  sales_return_numbers: number[]
  issue_numbers: number[]
  journal_entry_id: string | null
  journal_entry_number: number | null
  journal_entry_date: string | null
  created_by_name: string
  line_count: number
  total_qty: string
  total_cost: string
  description: string
  voided_at: string | null
  void_reason: string
}

export interface IssueReturnLedgerFilters {
  return_type?: string
  warehouse_id?: string
  deliverer_id?: string
  date_from?: string
  date_to?: string
  state?: string
}

/** فیلتر سمتِ سرور است؛ صفحه‌ها با کرسر خوانده می‌شوند (سقفِ ۲۰۰). */
export const fetchIssueReturnLedger = (token: string, filters: IssueReturnLedgerFilters = {}) => {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) qs.set(key, value)
  const query = qs.toString()
  return authedGetAll<IssueReturnRow>(token, `/api/warehouse-issue-returns${query ? `?${query}` : ''}`)
}

export interface IssueReturnLineRecord {
  id: string
  seq: number
  warehouse_issue_line_id: string
  sales_return_line_id: string | null
  item_id: string
  qty: string
  unit_cost: string
  amount: string
  account_id: string | null
  account_code: string
  account_name: string
  cost_center_id: string | null
  secondary_qty: string | null
  secondary_unit_snapshot: string
  item_code_snapshot: string
  item_name_snapshot: string
  unit_snapshot: string
  description: string
  issue_id: string | null
  issue_number: number | null
  sales_return_id: string | null
  sales_return_number: number | null
}

export interface IssueReturnRecord {
  id: string
  number: number
  return_date: string
  return_type: IssueReturnType
  origin: 'direct' | 'sales_return'
  warehouse_id: string
  deliverer_id: string | null
  sales_return_id: string | null
  description: string
  journal_entry_id: string | null
  voided_at: string | null
  void_reason: string
  created_by_id: string
  total_qty: string
  total_cost: string
  lines: IssueReturnLineRecord[]
}

export const fetchIssueReturn = (token: string, returnId: string) =>
  authedGet<IssueReturnRecord>(token, `/api/warehouse-issue-returns/${returnId}`)

/** هر ردیف دقیقاً یک مبنا دارد: ردیفِ فاکتور برگشتی یا ردیفِ خود خروج. */
export interface IssueReturnIn {
  return_date: string
  return_type: IssueReturnType
  warehouse_id: string
  deliverer_id?: string | null
  description?: string
  lines: {
    sales_return_line_id?: string | null
    warehouse_issue_line_id?: string | null
    qty: number
    unit_id?: string | null
    description?: string
  }[]
}

export const createIssueReturn = (token: string, data: IssueReturnIn, idempotencyKey: string) =>
  authedSend<IssueReturnRecord>(token, 'POST', '/api/warehouse-issue-returns', data, idempotencyKey)

export const voidIssueReturn = (token: string, returnId: string, reason: string) =>
  authedSend<IssueReturnRecord>(token, 'POST', `/api/warehouse-issue-returns/${returnId}/void`, { reason })

/** برگه‌ی «برگشت خروج انبار» — با فی و مبلغِ بها؛ استاندارد یا A5. */
export const printIssueReturn = (token: string, returnId: string, template: 'standard' | 'a5' = 'standard') =>
  openInvoicePrintView(token, `/api/warehouse-issue-returns/${returnId}/print?template=${template}`)

export interface IssueReturnBasisDoc {
  kind: 'sales_return' | 'issue'
  id: string
  number: number | null
  doc_date: string
  party_id: string | null
  party_name: string
  warehouse_id: string | null
  warehouse_name: string
  remaining_qty: string
}

/** پنجره‌ی «مبنا» — سندهایی که هنوز کالایی برای برگشت دارند. */
export const fetchIssueReturnBasis = (token: string, returnType: IssueReturnType) =>
  authedGet<IssueReturnBasisDoc[]>(token, `/api/warehouse-issue-returns/basis?return_type=${returnType}`)

export interface IssueReturnBasisLine {
  kind: 'sales_return' | 'issue'
  basis_line_id: string
  item_id: string
  item_code: string
  item_name: string
  unit: string
  qty: string
  returned: string
  remaining: string
  unit_cost: string
  amount: string
  source_warehouse_id: string | null
}

export interface IssueReturnBasis {
  kind: 'sales_return' | 'issue'
  id: string
  number: number | null
  doc_date: string
  party_id: string | null
  party_name: string
  warehouse_id: string | null
  lines: IssueReturnBasisLine[]
}

export const fetchIssueReturnBasisDetail = (token: string, kind: string, docId: string) =>
  authedGet<IssueReturnBasis>(token, `/api/warehouse-issue-returns/basis/${kind}/${docId}`)

// ── فاکتور خرید خدمات و کسورات (مالیات تکلیفی، بیمه) ──
// فیلدهای تازه‌ی خروجیِ فاکتور خرید با declaration merging این‌جا می‌نشینند.

export type PurchaseInvoiceKind = 'goods' | 'service'
export type PurchaseDeductionNature = 'withholding_tax' | 'insurance'
export type PurchaseDeductionBasis = 'net_before_tax' | 'gross'

export const PURCHASE_DEDUCTION_NATURE_LABELS: Record<PurchaseDeductionNature, string> = {
  withholding_tax: 'مالیات تکلیفی',
  insurance: 'بیمه',
}

export const PURCHASE_DEDUCTION_BASIS_LABELS: Record<PurchaseDeductionBasis, string> = {
  net_before_tax: 'خالص پیش از مالیات و عوارض',
  gross: 'ناخالص (مقدار × فی)',
}

export interface PurchaseInvoiceDeductionRecord {
  id: string
  deduction_type_id: string | null
  nature: PurchaseDeductionNature
  name_snapshot: string
  basis: PurchaseDeductionBasis
  basis_amount: string
  rate: string
  amount: string
  account_id: string
  account_code: string
  account_name: string
}

export interface PurchaseInvoiceRecord {
  kind: PurchaseInvoiceKind
  /** جمعِ کسورات — از جمعِ فاکتور کم نمی‌شود، فقط از بدهی به تأمین‌کننده. */
  total_deductions: string
  /** بدهیِ مستقیم به تأمین‌کننده = جمعِ فاکتور − کسورات. `remaining_amount` از همین است. */
  payable_amount: string
  withholding_total: string
  insurance_total: string
  deductions: PurchaseInvoiceDeductionRecord[]
  journal_entry_number: number | null
  journal_entry_date: string | null
}

export const fetchPurchaseInvoicesOfKind = (token: string, kind: PurchaseInvoiceKind) =>
  authedGetAll<PurchaseInvoiceRecord>(token, `/api/purchase-invoices?kind=${kind}`)

export interface PurchaseDeductionType {
  id: string
  code: string
  name: string
  nature: PurchaseDeductionNature
  nature_label: string
  basis: PurchaseDeductionBasis
  basis_label: string
  rate: string
  account_id: string | null
  account_code: string
  account_name: string
  account_is_default: boolean
  is_active: boolean
  description: string
  /** در فاکتوری خورده — حذف نمی‌شود و ماهیتش عوض نمی‌شود. */
  in_use: boolean
}

export interface PurchaseDeductionTypeInput {
  code: string
  name: string
  nature: PurchaseDeductionNature
  basis: PurchaseDeductionBasis
  rate: number
  account_id: string | null
  is_active: boolean
  description: string
}

export const fetchPurchaseDeductionTypes = (token: string, includeInactive = true) =>
  authedGet<PurchaseDeductionType[]>(token, `/api/purchase-deduction-types?include_inactive=${includeInactive}`)

export const createPurchaseDeductionType = (token: string, data: PurchaseDeductionTypeInput) =>
  authedSend<PurchaseDeductionType>(token, 'POST', '/api/purchase-deduction-types', data)

export const updatePurchaseDeductionType = (token: string, id: string, data: PurchaseDeductionTypeInput) =>
  authedSend<PurchaseDeductionType>(token, 'PATCH', `/api/purchase-deduction-types/${id}`, data)

export const deletePurchaseDeductionType = (token: string, id: string) =>
  authedDelete(token, `/api/purchase-deduction-types/${id}`)

export interface ServicePurchaseInvoiceInput {
  kind: 'service'
  invoice_date: string
  contact_id: string
  supplier_invoice_number: string
  cost_center_id: string | null
  description: string
  description2: string
  tax_rate: number
  currency_code: string | null
  exchange_rate: number
  invoice_discount: number
  invoice_addition: number
  duty_amount: number
  lines: {
    item_id: string
    /** خالی = معینِ خودِ خدمت. */
    expense_account_id: string | null
    qty: number
    unit_cost: number
    discount: number
    addition: number
    duty_amount: number
    description: string
  }[]
  /** `rate`/`amount` خالی = از نوعِ کسر حساب کن. */
  deductions: { deduction_type_id: string; rate: number | null; amount: number | null }[]
}

export const createServicePurchaseInvoice = (token: string, data: ServicePurchaseInvoiceInput, idempotencyKey: string) =>
  authedSend<PurchaseInvoiceRecord>(token, 'POST', '/api/purchase-invoices', data, idempotencyKey)

export interface PurchaseInvoiceDuplicateDraft {
  kind: PurchaseInvoiceKind
  deductions: { deduction_type_id: string | null; rate: string | number }[]
}

// ── اعلامیه بدهکار/بستانکار — جزئیات و رونوشت (مهاجرتِ ۰۱۴۲) ──────────────

export const fetchNote = (token: string, id: string) =>
  authedGet<CreditDebitNote>(token, `/api/sales-ops/notes/${id}`)

/** پیش‌نویسِ «رونوشت» — بدونِ شماره، تاریخ، سند و ابطال؛ سرور چیزی نمی‌نویسد. */
export interface NoteDraft {
  reason: string
  currency_code: string
  exchange_rate: string
  source_number: number | null
  lines: {
    debit_contact_id: string | null
    debit_account_id: string | null
    credit_contact_id: string | null
    credit_account_id: string | null
    amount: string
    description: string
  }[]
  cleared_fields: string[]
}

export const fetchNoteDuplicateDraft = (token: string, id: string) =>
  authedGet<NoteDraft>(token, `/api/sales-ops/notes/${id}/duplicate-draft`)

/** پیش‌پرکردنِ فرمِ اعلامیه از فهرست («رونوشت» یا «اصلاح»). */
export const NOTE_PREFILL_KEY = 'cubita.note.prefill'
export interface NotePrefill {
  draft: NoteDraft
  /** اگر از «اصلاح» آمده: شماره‌ی اعلامیه‌ای که همین حالا باطل شد. */
  corrects?: number | null
}
/** ویرایشِ شعبه — تنها راهی که شعبه‌های موجود طرف حساب می‌گیرند (مهاجرت ۰۱۳۶). */
export const updateInsuranceTaxBranch = (
  token: string,
  id: string,
  body: Partial<InsuranceTaxBranchRecord>,
) => authedSend<InsuranceTaxBranchRecord>(token, 'PATCH', `/api/insurance-tax-branches/${id}`, body)

// ── جدول مالیات ─────────────────────────────────────────────────────────────

export interface TaxBracketRow {
  seq: number
  /** مرزِ پایینِ پله — مشتق از سقفِ پله‌ی قبل، نه ستونِ ذخیره‌شده. */
  from_amount: string
  /** `null` = سقفِ نامحدود. */
  up_to: string | null
  /** کسر، نه درصد: ۰٫۰۷۵ یعنی ۷٫۵٪. */
  rate: string
}

export interface TaxTableRecord {
  id: string
  title: string
  title2: string
  effective_from: string
  tax_group_id: string | null
  tax_group_name: string
  calculation_type: string
  brackets: TaxBracketRow[]
  /** فیشی به این جدول استناد کرده؟ */
  in_use: boolean
}

export interface TaxBreakdownStep {
  seq: number
  from_amount: string
  up_to: string | null
  rate: string
  consumed: string
  tax: string
  cumulative: string
}

export interface TaxBreakdown {
  payslip_id: string
  tax_amount: string
  annual_taxable: string
  annual_exemption: string
  tax_table_id: string | null
  tax_table_title: string
  tax_group_name: string
  steps: TaxBreakdownStep[]
}

export const TAX_CALC_PURPOSE_LABELS: Record<string, string> = {
  salary: 'حقوق',
  eidi: 'عیدی',
}

export const fetchTaxTables = (token: string, calculationType?: string) =>
  authedGet<TaxTableRecord[]>(
    token,
    calculationType ? `/api/tax-tables?calculation_type=${calculationType}` : '/api/tax-tables',
  )
export const createTaxTable = (token: string, body: unknown) =>
  authedSend<TaxTableRecord>(token, 'POST', '/api/tax-tables', body)
export const updateTaxTable = (token: string, id: string, body: unknown) =>
  authedSend<TaxTableRecord>(token, 'PATCH', `/api/tax-tables/${id}`, body)
export const deleteTaxTable = (token: string, id: string) =>
  authedDelete(token, `/api/tax-tables/${id}`)
export const fetchTaxBreakdown = (token: string, payslipId: string) =>
  authedGet<TaxBreakdown>(token, `/api/payslips/${payslipId}/tax-breakdown`)

/** مبناهایی که یک عاملِ حقوق می‌تواند در آن‌ها شرکت کند. */
export const FACTOR_PURPOSE_LABELS: Record<string, string> = {
  insurance_base: 'مبنای بیمه',
  tax_base: 'مبنای مالیات',
  eidi_base: 'مبنای عیدی',
  severance_base: 'مبنای سنوات',
  leave_base: 'مبنای بازخرید مرخصی',
}

/** ضریبِ شرکتِ یک عامل در مبناها. ردیفِ برابرِ پیش‌فرض روی سرور پاک می‌شود. */
export const setFactorParticipation = (
  token: string,
  factorId: string,
  participation: Record<string, number>,
) =>
  authedSend<PayrollFactorRecord>(token, 'PUT', `/api/payroll-factors/${factorId}/participation`, {
    participation,
  })

/** بُعدِ تفصیلیِ ردیفِ سندی که یک عاملِ حقوق می‌سازد. */
export const FACTOR_DETAIL_CLASS_LABELS: Record<string, string> = {
  '': 'بدون تفصیلی',
  cost_center: 'مرکز هزینه',
  counterparty: 'طرف مقابل',
}

/** ویرایشِ عامل — شاملِ فعال/غیرفعال‌کردن. طبقه‌ی عاملِ در استفاده قفل است. */
export const updatePayrollFactor = (
  token: string,
  factorId: string,
  body: Partial<Omit<PayrollFactorRecord, 'id' | 'participation' | 'in_use'>>,
) => authedSend<PayrollFactorRecord>(token, 'PATCH', `/api/payroll-factors/${factorId}`, body)

// ── قیمت‌گذاری اسناد انبار — پیش‌نمایش، اجرا و ابطال (مهاجرتِ ۰۱۴۹) ──────────────
// محاسبه چیزی نمی‌نویسد؛ ثبت با توکنِ همان پیش‌نمایش است و روی دفترِ عوض‌شده ۴۰۹ می‌گیرد.

export interface ValuationScope {
  /** تاریخِ پایانِ دامنه — و تاریخِ سندِ اصلاحی. */
  dateTo: string
  dateFrom?: string
  /** فقط کالاها را انتخاب می‌کند؛ میانگین مالِ کلِ شرکت است. */
  warehouseId?: string
  itemId?: string
}

export interface ValuationSource {
  source_type: string
  source_label: string
  source_number: number | null
}

export interface ValuationNegative extends ValuationSource {
  item_id: string
  item_name: string
  warehouse_name: string
  entry_date: string
  qty: string
}

export interface ValuationItem {
  item_id: string
  sku: string
  name: string
  move_count: number
  value_delta: string
  from_date: string
}

export interface ValuationMove extends ValuationSource {
  stock_ledger_id: string
  item_id: string
  item_name: string
  entry_date: string
  warehouse_name: string
  qty: string
  previous_cost: string
  new_cost: string
  /** اثرِ علامت‌دار بر ارزشِ موجودی (ریال). */
  value_delta: string
  counter_account_name: string
}

export interface ValuationAccount {
  account_id: string
  code: string
  name: string
  debit: string
  credit: string
}

export interface ValuationSkipped extends ValuationSource {
  item_name: string
  entry_date: string
  qty: string
  reason: string
}

export interface ValuationPreview {
  date_from: string | null
  date_to: string
  warehouse_id: string | null
  item_id: string | null
  token: string
  /** موجودیِ منفی در خطِ زمان — ثبت ممکن نیست. */
  blocked: boolean
  negatives: ValuationNegative[]
  items: ValuationItem[]
  moves: ValuationMove[]
  moves_truncated: boolean
  /** سندِ اصلاحی‌ای که ثبت خواهد شد. */
  accounts: ValuationAccount[]
  skipped: ValuationSkipped[]
  move_count: number
  item_count: number
  total_delta: string
}

export interface ValuationRun {
  id: string
  number: number
  date_from: string | null
  date_to: string
  warehouse_id: string | null
  warehouse_name: string
  item_id: string | null
  item_name: string
  description: string
  move_count: number
  item_count: number
  total_delta: string
  journal_entry_id: string | null
  journal_entry_number: number | null
  created_at: string
  created_by_name: string
  voided_at: string | null
  voided_by_name: string
  void_reason: string
  void_entry_number: number | null
  /** فقط آخرین اجرای باطل‌نشده. */
  voidable: boolean
}

const valuationQs = (scope: ValuationScope) => {
  const qs = new URLSearchParams({ date_to: scope.dateTo })
  if (scope.dateFrom) qs.set('date_from', scope.dateFrom)
  if (scope.warehouseId) qs.set('warehouse_id', scope.warehouseId)
  if (scope.itemId) qs.set('item_id', scope.itemId)
  return qs.toString()
}

export const fetchValuationPreview = (token: string, scope: ValuationScope) =>
  authedGet<ValuationPreview>(token, `/api/inventory-valuation/preview?${valuationQs(scope)}`)

export const createValuationRun = (
  token: string,
  scope: ValuationScope,
  previewToken: string,
  description: string,
  idempotencyKey: string,
) =>
  authedSend<ValuationRun>(
    token,
    'POST',
    '/api/inventory-valuation/runs',
    {
      date_from: scope.dateFrom ?? null,
      date_to: scope.dateTo,
      warehouse_id: scope.warehouseId ?? null,
      item_id: scope.itemId ?? null,
      token: previewToken,
      description,
    },
    idempotencyKey,
  )

export const fetchValuationRunList = (token: string) =>
  authedGetAll<ValuationRun>(token, '/api/inventory-valuation/runs')

export const voidValuationRun = (token: string, runId: string, reason: string) =>
  authedSend<ValuationRun>(token, 'POST', `/api/inventory-valuation/runs/${runId}/void`, { reason })
// ── گزارش‌های انبار: ابعاد و ردیابیِ سریال ────────────────────────────────────
//
// مبالغ می‌توانند `null` باشند — یعنی کاربر مجوزِ بها ندارد. `null` است نه صفر،
// چون صفر عددِ واقعی است. رابط باید خط تیره نشان دهد، نه «۰ ریال».

export type InventoryDimension = 'supplier' | 'customer' | 'purpose'

export const INVENTORY_DIMENSION_LABELS: Record<InventoryDimension, string> = {
  supplier: 'تأمین‌کننده',
  customer: 'مشتری',
  purpose: 'هدف حرکت',
}

export interface InventoryBreakdownRow {
  key: string
  label: string
  item_count: number
  in_qty: string
  out_qty: string
  net_qty: string
  in_value: string | null
  out_value: string | null
  net_value: string | null
  /** چند حرکتِ این ردیف ارزش‌گذاریِ منقضی دارد — «این مبلغ هنوز بازمحاسبه نشده». */
  stale_count: number
}

export interface InventoryBreakdown {
  dimension: InventoryDimension
  dimension_label: string
  date_from: string | null
  date_to: string | null
  warehouse_id: string | null
  rows: InventoryBreakdownRow[]
  total_in_qty: string
  total_out_qty: string
  total_in_value: string | null
  total_out_value: string | null
  stale_count: number
}

export const fetchInventoryBreakdown = (
  token: string,
  params: { dimension: InventoryDimension; date_from?: string; date_to?: string; warehouse_id?: string },
) =>
  authedGet<InventoryBreakdown>(
    token,
    `/api/reports/inventory-breakdown?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][],
    ).toString()}`,
  )

export interface SerialEventRow {
  event_type: string
  event_label: string
  entry_date: string
  source_type: string
  source_label: string
  source_id: string | null
  source_number: number | null
  counterparty: string
  notes: string
}

/** یک سریال با **کلِ تاریخچه‌اش** — `in_stock` مشتق است، نه ذخیره‌شده. */
export interface SerialTrace {
  serial_id: string
  serial: string
  status: string
  item_id: string | null
  item_sku: string
  item_name: string
  batch_number: string
  in_stock: boolean
  last_event_type: string | null
  last_event_label: string
  last_source_type: string | null
  last_source_id: string | null
  last_entry_date: string | null
  events: SerialEventRow[]
}

export const searchSerials = (
  token: string,
  params: { serial?: string; item_id?: string; source_type?: string; date_from?: string; date_to?: string },
) =>
  authedGet<SerialTrace[]>(
    token,
    `/api/serials/search?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][],
    ).toString()}`,
  )

/** چسباندنِ سریال‌ها به یک سند. گامِ جداست: فاکتور نمی‌داند کدام سه تا از پنج تا رفت. */
export const assignSerials = (
  token: string,
  body: {
    item_id: string
    serials: string[]
    source_type: string
    source_id: string
    entry_date: string
    event_type?: string
  },
) => authedSend<{ assigned: number; created: number; replayed: number }>(
  token, 'POST', '/api/serials/assign', body,
)

// ── قیمت‌گذاریِ ورودی‌های بی‌فی ───────────────────────────────────────────────
//
// رسیدِ انبارِ مستقیم می‌تواند بی فی ثبت شود — کالایی که خارج از سیستم تهیه شده و
// بهایش هنوز معلوم نیست (تولیدِ کارگاهی، خریدی که سندش نرسیده). تا وقتی فی
// نخورَد، آن کالا در انبار هست و ارزشش صفر است.
//
// گرید **کالا‌محور** است، نه ردیف‌محور: یک فی برای یک کالا، و `receipts` می‌گوید
// آن فی روی کدام اسناد می‌نشیند.

export type UnpricedReceiptRef = {
  number: number
  receipt_date: string
  type_label: string
}

export type UnpricedOutput = {
  item_id: string
  sku: string
  name: string
  unit: string
  qty: string
  receipts: UnpricedReceiptRef[]
}

export type ApplyPricesResult = { receipts: number; lines: number; value: string }

export const fetchUnpricedOutputs = (
  token: string,
  scope: { warehouse_id: string; date_from: string; date_to: string },
) =>
  authedGet<UnpricedOutput[]>(
    token,
    `/api/warehouse-receipts/unpriced?${new URLSearchParams(scope).toString()}`,
  )

/** فی را روی ردیف‌های بی‌فیِ دامنه می‌نشاند. حرکتِ انبارِ تازه‌ای ساخته نمی‌شود. */
export const applyReceiptPrices = (
  token: string,
  body: {
    warehouse_id: string
    date_from: string
    date_to: string
    prices: { item_id: string; unit_cost: number }[]
  },
) => authedSend<ApplyPricesResult>(token, 'POST', '/api/warehouse-receipts/apply-prices', body)

// ═════════════════ ورودیِ عواملِ متغیر در یک دوره ═════════════════
//
// لایه‌ای که نبود. تا مهاجرتِ ۰۱۴۷ عاملِ «متغیر» دقیقاً مثلِ «قراردادی» رفتار
// می‌کرد — مبلغش از حکم می‌آمد — پس مأموریت و پاداش نمی‌توانستند ماه‌به‌ماه فرق
// کنند. حالا مبلغِ عاملِ متغیر برای هر دوره جدا وارد می‌شود.

export interface FactorInputRecord {
  id: string
  employee_id: string
  employee_name: string
  factor_id: string
  factor_name: string
  /** `benefit` یا `deduction` — جهتِ عدد از این می‌آید، نه از علامتش. */
  factor_category: string
  amount: string
  notes: string
}

export const fetchFactorInputs = (token: string, periodId: string) =>
  authedGet<FactorInputRecord[]>(token, `/api/payroll-periods/${periodId}/factor-inputs`)

/** فقط ردیف‌های نام‌برده نوشته می‌شوند؛ بقیه دست نمی‌خورند. `amount = 0` حذف است. */
export const saveFactorInputs = (
  token: string,
  periodId: string,
  rows: { employee_id: string; factor_id: string; amount: number; notes?: string }[],
) =>
  authedSend<FactorInputRecord[]>(
    token,
    'PUT',
    `/api/payroll-periods/${periodId}/factor-inputs`,
    { rows },
  )

// ═════════════════ پیمانکاری — پیمان (فازِ ۱) ═════════════════

export type ContractStatus = 'draft' | 'active' | 'suspended' | 'terminated' | 'completed' | 'cancelled'

export interface ContractRecord {
  id: string
  number: number
  external_reference: string
  contact_id: string
  contact_name: string
  subject: string
  total_amount: string
  start_date: string
  end_date: string | null
  retention_percent: string
  advance_percent: string
  status: ContractStatus
  cost_center_id: string | null
  notes: string
}

export interface ContractIn {
  contact_id: string
  external_reference?: string
  subject?: string
  total_amount: number
  start_date: string
  end_date?: string | null
  retention_percent?: number
  advance_percent?: number
  cost_center_id?: string | null
  notes?: string
}

export const fetchContracts = (token: string, query?: { status?: string; contact_id?: string }) => {
  const qs = new URLSearchParams()
  if (query?.status) qs.set('status', query.status)
  if (query?.contact_id) qs.set('contact_id', query.contact_id)
  const suffix = qs.toString()
  return authedGetAll<ContractRecord>(token, `/api/contracting/contracts${suffix ? `?${suffix}` : ''}`)
}

export const createContract = (token: string, data: ContractIn, idempotencyKey?: string) =>
  authedSend<ContractRecord>(token, 'POST', '/api/contracting/contracts', data, idempotencyKey)

export const changeContractStatus = (token: string, contractId: string, status: ContractStatus) =>
  authedSend<ContractRecord>(token, 'PATCH', `/api/contracting/contracts/${contractId}/status`, { status })

// ═════════════════ پیمانکاری — متممِ پیمان (فازِ ۲) ═════════════════

export interface ContractAmendmentRecord {
  id: string
  number: number
  contract_id: string
  contract_number: number | null
  date: string
  description: string
  amount_delta: string
  new_end_date: string | null
  notes: string
}

export interface ContractAmendmentIn {
  contract_id: string
  date: string
  description: string
  amount_delta?: number
  new_end_date?: string | null
  notes?: string
}

export const fetchContractAmendments = (token: string, query?: { contract_id?: string }) => {
  const qs = new URLSearchParams()
  if (query?.contract_id) qs.set('contract_id', query.contract_id)
  const suffix = qs.toString()
  return authedGetAll<ContractAmendmentRecord>(token, `/api/contracting/amendments${suffix ? `?${suffix}` : ''}`)
}

export const createContractAmendment = (token: string, data: ContractAmendmentIn, idempotencyKey?: string) =>
  authedSend<ContractAmendmentRecord>(token, 'POST', '/api/contracting/amendments', data, idempotencyKey)

// ═════════════════ پیمانکاری — صورت‌وضعیتِ دریافتی (فازِ ۳) ═════════════════

export interface ContractStatementRecord {
  id: string
  number: number
  contract_id: string
  contract_number: number | null
  date: string
  gross_amount: string
  retention_percent: string
  advance_percent: string
  retention_amount: string
  advance_deduction: string
  other_deductions: string
  net_amount: string
  notes: string
}

export interface ContractStatementIn {
  contract_id: string
  date: string
  gross_amount: number
  other_deductions?: number
  notes?: string
}

export const fetchContractStatements = (token: string, query?: { contract_id?: string }) => {
  const qs = new URLSearchParams()
  if (query?.contract_id) qs.set('contract_id', query.contract_id)
  const suffix = qs.toString()
  return authedGetAll<ContractStatementRecord>(token, `/api/contracting/statements${suffix ? `?${suffix}` : ''}`)
}

export const createContractStatement = (token: string, data: ContractStatementIn, idempotencyKey?: string) =>
  authedSend<ContractStatementRecord>(token, 'POST', '/api/contracting/statements', data, idempotencyKey)
