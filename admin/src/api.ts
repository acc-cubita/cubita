/**
 * کلاینتِ API اپِ ستاد.
 *
 * لایه‌ی انتقال (`get`/`send`/`del`) عمداً همان شکلِ `desktop/src/api.ts:205-320`
 * را دارد — از جمله تبدیلِ `detail`ِ فارسیِ سرور به پیامِ خطا — تا دو اپ یکسان
 * شکست بخورند و عیب‌یابیِ یکی به دیگری هم بخورد.
 *
 * `API_BASE_URL` موقعِ build داخلِ باندل بیک می‌شود. در production همان مبدأِ
 * خودِ اپ است (`admin.cubita.ir`)، چون vhost مسیرِ `/api/` را به همان بک‌اندِ
 * acc پراکسی می‌کند. هم‌مبدأ بودن دو سود دارد: نه preflight، و نه امکانِ
 * جابه‌جاییِ بی‌صدای دو باندل (گاردِ `deploy.sh` روی همین رشته کار می‌کند).
 */
const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.PROD ? 'https://admin.cubita.ir' : 'http://localhost:8000')

/** وقتی سرور ۴۰۱ می‌دهد، نشست تمام است — `App` توکن را پاک می‌کند. */
export class UnauthorizedError extends Error {
  constructor() {
    super('نشستِ شما تمام شده است؛ دوباره وارد شوید')
    this.name = 'UnauthorizedError'
  }
}

async function fail(res: Response): Promise<never> {
  if (res.status === 401) throw new UnauthorizedError()
  const body = await res.json().catch(() => ({ detail: null }))
  throw new Error(body.detail ?? `درخواست ناموفق بود (${res.status})`)
}

async function get<T>(token: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) await fail(res)
  return res.json()
}

async function send<T>(
  token: string,
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) await fail(res)
  return res.json()
}

// ── هویت ────────────────────────────────────────────────────────────────────

export interface StaffMe {
  id: string
  user_id: string
  name: string
  email: string
  role: 'owner' | 'admin' | 'finance' | 'support'
  role_label: string
  permissions: Record<string, string[]>
  last_login_at: string | null
  via: 'staff' | 'legacy'
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/api/admin/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: null }))
    //: ۴۲۹ پیامِ خودش را دارد؛ بقیه پیامِ یکنواختِ سرور را می‌گیرند.
    throw new Error(
      res.status === 429
        ? 'تلاشِ بیش از حد. چند دقیقه صبر کنید.'
        : (body.detail ?? 'ورود ناموفق بود'),
    )
  }
  return (await res.json()).access_token as string
}

export const fetchMe = (t: string) => get<StaffMe>(t, '/api/admin/auth/me')

export const changePassword = (t: string, current_password: string, new_password: string) =>
  send<StaffMe>(t, 'POST', '/api/admin/auth/change-password', { current_password, new_password })

export interface Diagnostics {
  env: string
  database_name: string
  alembic_version: string | null
  tenant_count: number
  staff_count: number
  legacy_admin_allowlist: boolean
}

export const fetchDiagnostics = (t: string) => get<Diagnostics>(t, '/api/admin/diagnostics')

// ── اکانت‌ها ────────────────────────────────────────────────────────────────

export interface AccountUser {
  name: string
  email: string
  status: string
  is_owner: boolean
  last_login_at: string | null
}

export interface Account {
  tenant_id: string
  name: string
  slug: string
  status: string
  kind: string
  industry: string | null
  granted_modules: string[]
  owner_name: string | null
  owner_email: string | null
  created_at: string
  user_count: number
  max_users: number | null
  subscription_status: string
  expires_at: string | null
  days_left: number | null
  plan_name: string | null
  is_trial: boolean
  trial_days_left: number | null
  trial_expired: boolean
  owner_last_login_at: string | null
  last_activity_at: string | null
  users: AccountUser[]
}

export const fetchAccounts = (t: string) => get<Account[]>(t, '/api/admin/accounts')
export const fetchAccount = (t: string, id: string) => get<Account>(t, `/api/admin/accounts/${id}`)

export const createAccount = (
  t: string,
  data: { business_name: string; owner_name: string; email: string; password: string; days: number },
) => send<Account>(t, 'POST', '/api/admin/accounts', data)

export const extendAccount = (t: string, id: string, days: number) =>
  send<Account>(t, 'POST', `/api/admin/accounts/${id}/extend`, { days })

export const setAccountStatus = (t: string, id: string, status: 'active' | 'suspended') =>
  send<Account>(t, 'POST', `/api/admin/accounts/${id}/status`, { status })

export const setAccountKind = (t: string, id: string, kind: string) =>
  send<Account>(t, 'POST', `/api/admin/accounts/${id}/kind`, { kind })

export const setAccountIndustry = (t: string, id: string, industry: string) =>
  send<Account>(t, 'POST', `/api/admin/accounts/${id}/industry`, { industry })

export const setAccountModules = (t: string, id: string, granted: string[]) =>
  send<Account>(t, 'POST', `/api/admin/accounts/${id}/modules`, { granted })

export const resetAccountPassword = (t: string, id: string, password: string) =>
  send<Account>(t, 'POST', `/api/admin/accounts/${id}/reset-password`, { password })

/** حذفِ برگشت‌ناپذیر. `confirm_slug` باید دقیقاً شناسه‌ی همان کسب‌وکار باشد. */
export const deleteAccount = (t: string, id: string, confirm_slug: string, reason: string) =>
  send<{ deleted: boolean }>(t, 'DELETE', `/api/admin/accounts/${id}`, { confirm_slug, reason })

// ── کاربرانِ ستاد ───────────────────────────────────────────────────────────

export interface StaffRow {
  id: string
  user_id: string
  name: string
  email: string
  role: StaffMe['role']
  role_label: string
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export const fetchStaff = (t: string) => get<StaffRow[]>(t, '/api/admin/staff')

export const createStaff = (
  t: string,
  data: { name: string; email: string; password: string; role: string },
) => send<StaffRow>(t, 'POST', '/api/admin/staff', data)

export const setStaffRole = (t: string, id: string, role: string) =>
  send<StaffRow>(t, 'PATCH', `/api/admin/staff/${id}/role`, { role })

export const setStaffStatus = (t: string, id: string, active: boolean) =>
  send<StaffRow>(t, 'PATCH', `/api/admin/staff/${id}/status`, { active })

export const resetStaffPassword = (t: string, id: string, password: string) =>
  send<StaffRow>(t, 'POST', `/api/admin/staff/${id}/reset-password`, { password })

// ── کمیسیونِ بازار ──────────────────────────────────────────────────────────

export interface CommissionOverview {
  total_amount: number
  pending_amount: number
  settled_amount: number
  distributor_count: number
  rate: number
}

export interface CommissionPeriod {
  distributor_tenant_id: string
  distributor_name: string | null
  period: string
  order_count: number
  total_base: number
  total_amount: number
  pending_amount: number
  settled_amount: number
  status: string
}

export const fetchCommissionOverview = (t: string) =>
  get<CommissionOverview>(t, '/api/admin/commissions/overview')

export const fetchCommissions = (t: string) => get<CommissionPeriod[]>(t, '/api/admin/commissions')

export const settleCommission = (
  t: string,
  distributor_tenant_id: string,
  period: string,
  note: string,
) =>
  send<{ amount: number; count: number }>(t, 'POST', '/api/admin/commissions/settle', {
    distributor_tenant_id,
    period,
    note,
  })

// ── کارتابلِ حسابرسی ────────────────────────────────────────────────────────

export interface StaffEngagement {
  id: string
  tenant_id: string
  tenant_name: string | null
  status: string
  period_from: string
  period_to: string
  requested_at: string
  contact_phone: string | null
  request_note: string | null
  reject_reason: string | null
  auditor_name: string | null
  auditor_email: string | null
  owner_email: string | null
  access_expires_at: string | null
  last_score: number | null
  last_run_at: string | null
}

export const fetchEngagements = (t: string, status?: string) =>
  get<StaffEngagement[]>(
    t,
    `/api/admin/assurance${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`,
  )

export const approveEngagement = (
  t: string,
  id: string,
  data: { auditor_email: string; days: number; period_from?: string; period_to?: string },
) => send<StaffEngagement>(t, 'POST', `/api/admin/assurance/${id}/approve`, data)

export const rejectEngagement = (t: string, id: string, reason: string) =>
  send<StaffEngagement>(t, 'POST', `/api/admin/assurance/${id}/reject`, { reason })

export const assignAuditor = (t: string, id: string, auditor_email: string, days?: number) =>
  send<StaffEngagement>(t, 'POST', `/api/admin/assurance/${id}/assign`, { auditor_email, days })

export const extendEngagement = (t: string, id: string, days: number) =>
  send<StaffEngagement>(t, 'POST', `/api/admin/assurance/${id}/extend`, { days })

export const runEngagement = (t: string, id: string) =>
  send<{ score: number | null }>(t, 'POST', `/api/admin/assurance/${id}/run`, {})

export const closeEngagement = (t: string, id: string, note: string) =>
  send<StaffEngagement>(t, 'POST', `/api/admin/assurance/${id}/close`, { note })

// ── خریدهای سایتِ تجاری ─────────────────────────────────────────────────────

export interface Purchase {
  id: string
  customer_email: string
  customer_name: string | null
  business_name: string
  phone: string | null
  amount_toman: number
  billing_period: string
  status: string
  created_at: string
  fulfilled_at: string | null
  admin_notes: string | null
}

export const fetchPurchases = (t: string) => get<Purchase[]>(t, '/api/admin/purchases')

export const fulfillPurchase = (t: string, id: string, admin_notes: string) =>
  send<Purchase>(t, 'POST', `/api/admin/purchases/${id}/fulfill`, { admin_notes })

// ── گزارش‌های خطای کلاینت ───────────────────────────────────────────────────

export interface ClientErrorRow {
  id: string
  occurred_at: string
  received_at: string
  fatal: boolean
  name: string
  message: string
  stack: string | null
  screen: string | null
  app_version: string | null
  platform: string | null
  os_version: string | null
  device: string | null
}

export const fetchClientErrors = (t: string, onlyFatal: boolean) =>
  get<ClientErrorRow[]>(t, `/api/admin/client-errors?only_fatal=${onlyFatal}`)

// ── مجوزهای کوبیتا سازمانی ──────────────────────────────────────────────────

export interface EnterpriseLicense {
  id: string
  lic_id: string
  org_name: string
  contact: string | null
  seats: number | null
  mods: string[] | null
  feat: string[] | null
  expires_at: string | null
  grace_days: number
  code_hint: string
  status: 'active' | 'revoked'
  revoked_at: string | null
  bound: boolean
  bound_at: string | null
  last_issued_at: string | null
  issue_count: number
  note: string | null
  created_by_email: string | null
  created_at: string
}

export interface EnterpriseLicenseEvent {
  kind: 'create' | 'update' | 'activate' | 'issue' | 'refuse' | 'transfer' | 'revoke' | 'code'
  actor: string
  detail: Record<string, unknown> | null
  created_at: string
}

export interface EnterpriseLicenseDetail extends EnterpriseLicense {
  events: EnterpriseLicenseEvent[]
}

export interface EnterpriseLicenseInput {
  org_name: string
  contact?: string | null
  seats?: number | null
  /** null = دائمی */
  days?: number | null
  grace_days?: number
  feat?: string[] | null
  note?: string | null
}

export interface EnterpriseLicenseUpdate {
  org_name?: string
  contact?: string
  seats?: number
  clear_seats?: boolean
  extend_days?: number
  make_perpetual?: boolean
  grace_days?: number
  feat?: string[]
  all_features?: boolean
  note?: string
}

export const fetchLicenses = (t: string, q = '') =>
  get<EnterpriseLicense[]>(t, `/api/admin/licenses${q ? `?q=${encodeURIComponent(q)}` : ''}`)
export const fetchLicense = (t: string, id: string) =>
  get<EnterpriseLicenseDetail>(t, `/api/admin/licenses/${id}`)
export const createLicense = (t: string, data: EnterpriseLicenseInput) =>
  send<{ license: EnterpriseLicense; activation_code: string }>(t, 'POST', '/api/admin/licenses', data)
export const updateLicense = (t: string, id: string, data: EnterpriseLicenseUpdate) =>
  send<EnterpriseLicenseDetail>(t, 'PATCH', `/api/admin/licenses/${id}`, data)
export const issueLicenseOffline = (t: string, id: string, requestCode: string) =>
  send<{ token: string }>(t, 'POST', `/api/admin/licenses/${id}/issue`, { request_code: requestCode })
export const transferLicense = (t: string, id: string) =>
  send<EnterpriseLicenseDetail>(t, 'POST', `/api/admin/licenses/${id}/transfer`, {})
export const revokeLicense = (t: string, id: string) =>
  send<EnterpriseLicenseDetail>(t, 'POST', `/api/admin/licenses/${id}/revoke`, {})
export const regenerateLicenseCode = (t: string, id: string) =>
  send<{ activation_code: string }>(t, 'POST', `/api/admin/licenses/${id}/code`, {})
