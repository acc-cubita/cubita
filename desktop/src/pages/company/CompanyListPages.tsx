import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Gauge,
  ListChecks,
  Target,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import {
  fetchAuditEntries,
  fetchAuditSummary,
  fetchContactGroups,
  fetchContacts,
  fetchCostCenterReport,
  fetchGeoLocations,
  fetchInstallmentPlans,
  type AuditEntryRecord,
  type AuditSummary,
  type ContactGroupRecord,
  type ContactRecord,
  costCenterKindLabel,
  type CostCenterReportRow,
  type GeoLocationRecord,
  type InstallmentPlan,
  type MeResponse,
} from '../../api'
import type { PageKey } from '../../lib/navModel'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { EmptyState } from '../../components/EmptyState'
import { StatCard } from '../../components/StatCard'
import { Pager, usePagination } from '../../components/Pager'
import { CostCenterWorkspace } from './CostCenterWorkspace'
import { Reports } from '../../components/Reports'
import { BackupPage } from '../BackupPage'
import { BackupListPage } from '../BackupListPage'
import { formatJalali, isoToJalali, jalaliToIso, todayIso } from '../../lib/jalali'
import type { AccountCache } from '../../electron.d'

/**
 * صفحه‌های «فهرست»ِ ماژولِ شرکت.
 *
 * بیشترشان روی داده‌ای می‌نشینند که از قبل بود ولی جایی برای دیده‌شدن نداشت —
 * دفترِ ردِ حسابرسی، اقساط، مراکز هزینه. کارِ این‌جا نمایش است نه منطقِ تازه؛ منطق
 * همان‌جایی می‌ماند که هست.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const money = (v: string | number) => Number(v || 0).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

/** برچسبِ فارسیِ کنش‌های دفترِ رد — کلیدها همانی‌اند که سرور می‌نویسد. */
const ACTION_LABELS: Record<string, string> = {
  create: 'ایجاد',
  update: 'ویرایش',
  delete: 'حذف',
  void: 'ابطال',
  finalize: 'دائم‌کردن',
  login: 'ورود',
  post: 'ثبت سند',
  pay: 'پرداخت',
  close: 'بستن',
}

const ENTITY_LABELS: Record<string, string> = {
  sales_invoice: 'فاکتور فروش',
  purchase_invoice: 'فاکتور خرید',
  journal_entry: 'سند حسابداری',
  contact: 'طرف حساب',
  item: 'کالا',
  treasury: 'خزانه',
  check: 'چک',
  installment_plan: 'تقسیط',
  fiscal_year: 'سال مالی',
  membership: 'کاربر',
}

const label = (map: Record<string, string>, key: string) => map[key] ?? key

// ── ارسال / دریافت اطلاعات ───────────────────────────────────────────────────

/**
 * «ارسال اطلاعات» و «دریافت اطلاعات» همان برون‌ریز/درون‌ریزِ پشتیبان‌اند و منطقشان
 * در صفحه‌های پشتیبان‌گیری نشسته است. تکرارِ آن فرم‌ها یعنی دو مسیر برای یک کار که
 * دیر یا زود از هم واگرا می‌شوند؛ پس همان‌ها این‌جا میزبانی می‌شوند.
 */
export function DataExportPage(props: { token: string; me: MeResponse }) {
  return <BackupPage {...props} />
}

export function DataImportPage(props: { token: string; me: MeResponse }) {
  return <BackupListPage {...props} />
}

// ── فعالیت‌های روز ───────────────────────────────────────────────────────────

export function DayActivityPage({ token }: { token: string }) {
  const [rows, setRows] = useState<AuditEntryRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [day, setDay] = useState(todayIso())

  useEffect(() => {
    void fetchAuditEntries(token)
      .then(setRows)
      .catch((err) => setError(errText(err)))
  }, [token])

  const ofDay = useMemo(
    () => (rows ?? []).filter((r) => r.at.slice(0, 10) === day),
    [rows, day],
  )
  const pg = usePagination(ofDay, 10, day)

  const byActor = useMemo(() => {
    const map = new Map<string, number>()
    for (const r of ofDay) map.set(r.actor_email, (map.get(r.actor_email) ?? 0) + 1)
    return [...map.entries()].sort((a, b) => b[1] - a[1])
  }, [ofDay])

  return (
    <div className="page panels">
      <PageHeader
        icon={Activity}
        title="فعالیت‌های روز"
        description="هرچه امروز در برنامه ثبت یا عوض شده — از دفترِ ردِ حسابرسی، به ترتیبِ زمان."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard label="رویدادهای این روز" value={fa(ofDay.length)} icon={<Activity size={16} />} />
        <StatCard label="کاربرانِ فعال" value={fa(byActor.length)} icon={<UsersRound size={16} />} />
        <StatCard
          label="پرکارترین کاربر"
          value={byActor[0] ? byActor[0][0] : '—'}
          hint={byActor[0] ? `${fa(byActor[0][1])} رویداد` : undefined}
          icon={<Gauge size={16} />}
        />
      </div>

      <SectionCard
        icon={Activity}
        title="رویدادها"
        description="روزِ دیگری را انتخاب کنید تا فعالیتِ همان روز را ببینید."
        actions={<input type="date" value={day} onChange={(e) => setDay(e.target.value)} />}
      >
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : ofDay.length === 0 ? (
          <EmptyState icon={Activity} text="در این روز رویدادی ثبت نشده — تاریخِ دیگری را امتحان کنید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>ساعت</th>
                    <th>کاربر</th>
                    <th>کنش</th>
                    <th>موضوع</th>
                    <th>شرح</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td data-label="ساعت">
                        {new Date(r.at).toLocaleTimeString('fa-IR', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td data-label="کاربر">{r.actor_email || '—'}</td>
                      <td data-label="کنش">
                        <span className="badge">{label(ACTION_LABELS, r.action)}</span>
                      </td>
                      <td data-label="موضوع">{label(ENTITY_LABELS, r.entity_type)}</td>
                      <td className="card-title" data-label="شرح">{r.summary || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

// ── گزارش استفاده از نرم‌افزار ───────────────────────────────────────────────

const USAGE_RANGES = [7, 30, 90, 365]

export function UsageReportPage({ token }: { token: string }) {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<AuditSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    void fetchAuditSummary(token, days)
      .then(setData)
      .catch((err) => setError(errText(err)))
  }, [token, days])

  const peak = useMemo(
    () => (data?.by_day ?? []).reduce((max, r) => Math.max(max, r.count), 0),
    [data],
  )

  return (
    <div className="page panels">
      <PageHeader
        icon={Gauge}
        title="گزارش استفاده از نرم‌افزار"
        description="چه کسی، چقدر، روی چه چیزی کار کرده است. شمارش سمتِ سرور روی کلِ بازه انجام می‌شود، نه روی یک صفحه از فهرست."
      />
      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={Gauge}
        title="بازه"
        actions={
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {USAGE_RANGES.map((d) => (
              <option key={d} value={d}>
                {fa(d)} روزِ گذشته
              </option>
            ))}
          </select>
        }
      >
        {data == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <>
            <div className="stat-grid">
              <StatCard label="کلِ رویدادها" value={fa(data.total)} icon={<Activity size={16} />} />
              <StatCard label="کاربرانِ فعال" value={fa(data.by_actor.length)} icon={<UsersRound size={16} />} />
              <StatCard
                label="میانگینِ روزانه"
                value={fa(Math.round(data.total / Math.max(1, data.days)))}
                icon={<Gauge size={16} />}
              />
            </div>

            {/* نمودارِ ستونیِ ساده: ارتفاعِ هر ستون نسبت به پرکارترین روز. */}
            {data.by_day.length > 0 && (
              <div className="usage-chart" role="img" aria-label="فعالیتِ روزانه">
                {data.by_day.map((d) => (
                  <span
                    key={d.key}
                    className="usage-bar"
                    style={{ height: `${Math.max(4, (d.count / Math.max(1, peak)) * 100)}%` }}
                    title={`${formatJalali(d.key)} — ${fa(d.count)} رویداد`}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </SectionCard>

      {data && (
        <div className="usage-grid">
          <UsageTable title="به تفکیکِ کاربر" icon={UsersRound} rows={data.by_actor} total={data.total} />
          <UsageTable
            title="به تفکیکِ کنش"
            icon={Activity}
            rows={data.by_action.map((r) => ({ ...r, key: label(ACTION_LABELS, r.key) }))}
            total={data.total}
          />
          <UsageTable
            title="به تفکیکِ موضوع"
            icon={BarChart3}
            rows={data.by_entity.map((r) => ({ ...r, key: label(ENTITY_LABELS, r.key) }))}
            total={data.total}
          />
        </div>
      )}
    </div>
  )
}

function UsageTable({
  title,
  icon,
  rows,
  total,
}: {
  title: string
  icon: typeof Activity
  rows: { key: string; count: number }[]
  total: number
}) {
  return (
    <SectionCard icon={icon} title={title}>
      {rows.length === 0 ? (
        <p className="muted">داده‌ای در این بازه نیست.</p>
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <tbody>
              {rows.slice(0, 12).map((r) => (
                <tr key={r.key}>
                  <td className="card-title">{r.key}</td>
                  <td className="num" data-label="تعداد">{fa(r.count)}</td>
                  <td className="num muted" data-label="سهم">
                    {total ? `${fa(Math.round((r.count / total) * 100))}٪` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

// ── طرف حساب‌ها ──────────────────────────────────────────────────────────────

/**
 * نقش‌های یک طرف‌حساب — همه‌شان، نه فقط `type`.
 *
 * `type` دو نقشِ معاملاتی را نگه می‌دارد و واسطه و سهامدار پرچمِ جداگانه‌اند. اگر
 * این ستون فقط `type` را نشان دهد، واسطه‌ای که مشتری هم هست در فهرست «مشتری» دیده
 * می‌شود و نقشِ واسطه‌اش ناپیدا می‌ماند.
 */
function contactRoles(r: ContactRecord): string[] {
  const roles: string[] = []
  if (r.is_customer) roles.push('مشتری')
  if (r.is_supplier) roles.push('تأمین‌کننده')
  if (r.is_broker) roles.push('واسطه')
  if (r.is_shareholder) roles.push('سهامدار')
  return roles
}

const ROLE_FILTERS: Record<string, (r: ContactRecord) => boolean> = {
  customer: (r) => r.is_customer,
  supplier: (r) => r.is_supplier,
  broker: (r) => r.is_broker,
  shareholder: (r) => r.is_shareholder,
}

export function ContactListPage({
  token,
  onNavigate,
  onEditContact,
  presetRole = '',
}: {
  token: string
  /** ویرایش در فرمِ کامل — تا امروز ردیف‌های این جدول هیچ کنشی نداشتند. */
  onEditContact?: (id: string) => void
  onNavigate?: (page: PageKey) => void
  /** نقشِ ازپیش‌انتخاب‌شده — «فهرست تامین‌کنندگان»ِ گروهِ انبار همین صفحه است با
   *  `supplier`، نه جدولِ دومی از طرف‌حساب‌ها. */
  presetRole?: string
}) {
  const [rows, setRows] = useState<ContactRecord[] | null>(null)
  const [groups, setGroups] = useState<ContactGroupRecord[]>([])
  const [locations, setLocations] = useState<GeoLocationRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState(presetRole)

  useEffect(() => {
    void fetchContacts(token)
      .then(setRows)
      .catch((err) => setError(errText(err)))
    void fetchContactGroups(token).then(setGroups).catch(() => {})
    void fetchGeoLocations(token).then(setLocations).catch(() => {})
  }, [token])

  const groupName = useMemo(() => new Map(groups.map((g) => [g.id, g.name])), [groups])
  const geoPath = useMemo(() => new Map(locations.map((l) => [l.id, l.path])), [locations])

  const shown = useMemo(() => {
    const q = query.trim()
    return (rows ?? []).filter((r) => {
      if (groupFilter && r.group_id !== groupFilter) return false
      if (roleFilter && !ROLE_FILTERS[roleFilter]?.(r)) return false
      if (!q) return true
      return [r.name, r.phone ?? '', r.email ?? '', r.national_id ?? ''].some((v) => v.includes(q))
    })
  }, [rows, query, groupFilter, roleFilter])

  const pg = usePagination(shown, 10, `${query}|${groupFilter}|${roleFilter}`)

  return (
    <div className="page panels">
      <PageHeader
        icon={UsersRound}
        title={presetRole === 'supplier' ? 'تأمین‌کنندگان' : 'طرف حساب‌ها'}
        description={
          presetRole === 'supplier'
            ? 'طرف‌حساب‌هایی که نقشِ تأمین‌کننده دارند — همان فهرستِ طرف‌حساب‌ها، با فیلترِ نقش.'
            : 'همه‌ی مشتریان، تأمین‌کنندگان، واسطه‌ها و سهامداران — با گروه و محلِ جغرافیایی‌شان.'
        }
      />
      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={UsersRound}
        title={rows ? `${fa(shown.length)} طرف حساب` : 'در حال بارگذاری…'}
        actions={
          <>
            <select value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}>
              <option value="">همه‌ی گروه‌ها</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
            <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
              <option value="">همه‌ی نقش‌ها</option>
              <option value="customer">مشتری</option>
              <option value="supplier">تأمین‌کننده</option>
              <option value="broker">واسطه</option>
              <option value="shareholder">سهامدار</option>
            </select>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جست‌وجو…" />
            {/* راهِ ساختِ طرف‌حساب از این فهرست گم بود: کاربر «طرف حساب‌ها» را باز
                می‌کرد و هیچ راهی به فرمِ ساخت نداشت. ساخت همچنان یک‌جاست («شرکت ←
                طرف حساب جدید») و این فقط میان‌بُر است، نه فرمِ دوم. */}
            {onNavigate && (
              <button type="button" className="btn-primary" onClick={() => onNavigate('contactnew')}>
                <UserPlus size={13} /> طرف حساب جدید
              </button>
            )}
          </>
        }
      >
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : shown.length === 0 ? (
          <EmptyState
            icon={UsersRound}
            text={
              query || groupFilter
                ? 'چیزی پیدا نشد — فیلترها را تغییر دهید.'
                : 'هنوز طرف‌حسابی ثبت نشده — با «طرف حساب جدید» اولی را بسازید.'
            }
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>نام</th>
                    <th>نقش</th>
                    <th>گروه</th>
                    <th>محل</th>
                    <th>تلفن</th>
                    <th>وضعیت</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="نام">{r.name}</td>
                      <td data-label="نقش">{contactRoles(r).join('، ')}</td>
                      <td data-label="گروه">{r.group_id ? groupName.get(r.group_id) ?? '—' : '—'}</td>
                      <td data-label="محل">
                        {r.geo_location_id ? geoPath.get(r.geo_location_id) ?? '—' : '—'}
                      </td>
                      <td data-label="تلفن">{r.phone || '—'}</td>
                      <td data-label="وضعیت">
                        <span className={`badge ${r.is_active ? 'success' : ''}`}>
                          {r.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td className="card-actions">
                        {onEditContact && (
                          <button type="button" onClick={() => onEditContact(r.id)}>ویرایش</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

// ── تقسیط / همه اقساط ────────────────────────────────────────────────────────

const PLAN_STATUS: Record<string, string> = {
  active: 'جاری',
  completed: 'تسویه‌شده',
  cancelled: 'لغوشده',
}

export function InstallmentPlansPage({ token }: { token: string }) {
  const [plans, setPlans] = useState<InstallmentPlan[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetchInstallmentPlans(token)
      .then(setPlans)
      .catch((err) => setError(errText(err)))
  }, [token])

  const pg = usePagination(plans ?? [], 10)
  const totals = useMemo(() => {
    const rows = plans ?? []
    return {
      count: rows.length,
      active: rows.filter((p) => p.status === 'active').length,
      amount: rows.reduce((sum, p) => sum + Number(p.total_amount || 0), 0),
    }
  }, [plans])

  return (
    <div className="page panels">
      <PageHeader
        icon={CalendarClock}
        title="قراردادهای اقساطی"
        description="فهرستِ قراردادهای فروشِ اقساطی. برای ساخت، وصول و تنظیمِ زمان‌بندی به «شرکت ← فروش اقساطی» بروید."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard label="کلِ قراردادها" value={fa(totals.count)} icon={<CalendarClock size={16} />} />
        <StatCard label="جاری" value={fa(totals.active)} icon={<ListChecks size={16} />} />
        <StatCard label="مبلغِ کل" value={money(totals.amount)} hint="ریال" icon={<BarChart3 size={16} />} />
      </div>

      <SectionCard icon={CalendarClock} title="قراردادها">
        {plans == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : plans.length === 0 ? (
          <EmptyState icon={CalendarClock} text="هنوز قرارداد اقساطی ثبت نشده — از «شرکت ← فروش اقساطی» اولین قرارداد را بسازید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>طرف حساب</th>
                    <th>مبلغ کل</th>
                    <th>اقساط</th>
                    <th>پرداخت‌شده</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((p) => {
                    const paid = p.installments.filter((i) => i.status === 'paid').length
                    return (
                      <tr key={p.id}>
                        <td className="card-title" data-label="طرف حساب">{p.contact_name}</td>
                        <td className="num" data-label="مبلغ کل">{money(p.total_amount)}</td>
                        <td data-label="اقساط">{fa(p.installments.length)}</td>
                        <td data-label="پرداخت‌شده">
                          {fa(paid)} از {fa(p.installments.length)}
                        </td>
                        <td data-label="وضعیت">
                          <span className={`badge ${p.status === 'completed' ? 'success' : ''}`}>
                            {label(PLAN_STATUS, p.status)}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

export function AllInstallmentsPage({ token }: { token: string }) {
  const [plans, setPlans] = useState<InstallmentPlan[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<'all' | 'due' | 'overdue' | 'paid'>('all')

  useEffect(() => {
    void fetchInstallmentPlans(token)
      .then(setPlans)
      .catch((err) => setError(errText(err)))
  }, [token])

  //: تختِ همه‌ی اقساطِ همه‌ی قراردادها — نمای «سررسیدها»، نه نمای «قراردادها».
  const rows = useMemo(() => {
    const today = todayIso()
    const flat = (plans ?? []).flatMap((p) =>
      p.installments.map((i) => ({
        id: i.id,
        contact: p.contact_name,
        planStatus: p.status,
        number: i.seq,
        due: i.due_date,
        amount: i.remaining,
        paid: i.status === 'paid',
        overdue: i.status !== 'paid' && i.due_date < today,
      })),
    )
    flat.sort((a, b) => a.due.localeCompare(b.due))
    if (status === 'paid') return flat.filter((r) => r.paid)
    if (status === 'overdue') return flat.filter((r) => r.overdue)
    if (status === 'due') return flat.filter((r) => !r.paid)
    return flat
  }, [plans, status])

  const pg = usePagination(rows, 10, status)
  const overdueTotal = useMemo(
    () => rows.filter((r) => r.overdue).reduce((s, r) => s + Number(r.amount || 0), 0),
    [rows],
  )

  return (
    <div className="page panels">
      <PageHeader
        icon={ListChecks}
        title="همه اقساط"
        description="تکِ‌تکِ سررسیدها از همه‌ی قراردادها، مرتب بر اساسِ تاریخ — تا معوق‌ها لای قراردادها گم نشوند."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard label="اقساطِ نمایش‌داده‌شده" value={fa(rows.length)} icon={<ListChecks size={16} />} />
        <StatCard
          label="معوق"
          value={fa(rows.filter((r) => r.overdue).length)}
          hint={overdueTotal ? `${money(overdueTotal)} ریال` : undefined}
          icon={<AlertTriangle size={16} />}
          tone={rows.some((r) => r.overdue) ? 'danger' : 'default'}
        />
        <StatCard label="پرداخت‌شده" value={fa(rows.filter((r) => r.paid).length)} icon={<CheckCircle2 size={16} />} />
      </div>

      <SectionCard
        icon={ListChecks}
        title="سررسیدها"
        actions={
          <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            <option value="all">همه</option>
            <option value="due">پرداخت‌نشده</option>
            <option value="overdue">معوق</option>
            <option value="paid">پرداخت‌شده</option>
          </select>
        }
      >
        {plans == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={ListChecks} text="قسطی در این وضعیت نیست — فیلتر را عوض کنید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>سررسید</th>
                    <th>طرف حساب</th>
                    <th>قسط</th>
                    <th>مبلغ</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id} className={r.overdue ? 'row-danger' : undefined}>
                      <td data-label="سررسید">{formatJalali(r.due)}</td>
                      <td className="card-title" data-label="طرف حساب">{r.contact}</td>
                      <td data-label="قسط">{fa(r.number)}</td>
                      <td className="num" data-label="مبلغ">{money(r.amount)}</td>
                      <td data-label="وضعیت">
                        <span className={`badge ${r.paid ? 'success' : r.overdue ? 'danger' : ''}`}>
                          {r.paid ? 'پرداخت‌شده' : r.overdue ? 'معوق' : 'در انتظار'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

// ── مراکز هزینه ──────────────────────────────────────────────────────────────

export function CostCenterPage({
  token,
  accounts,
}: {
  token: string
  accounts: AccountCache[]
}) {
  return (
    <div className="page panels">
      <PageHeader
        icon={Target}
        title="مرکز هزینه"
        description="بُعدی برای برچسب‌زدنِ اسناد و سنجشِ سود به تفکیکِ پروژه، شعبه یا واحد. برچسب روی ردیفِ سند می‌نشیند، پس گزارش از تراکنشِ واقعی درمی‌آید — نه از تخصیصِ دستی."
      />
      <CostCenterWorkspace token={token} accounts={accounts} />
    </div>
  )
}

/**
 * فهرستِ خواندنیِ مراکز با ارقامِ همین سالِ مالی.
 *
 * عمداً «فقط نام و کد» نیست: فهرستی که رقم ندارد کاربر را وادار می‌کند برای هر
 * سؤالِ ساده‌ای به میزکار برود. ساخت و ویرایش همچنان فقط یک‌جاست — «شرکت ← مرکز هزینه».
 */
export function CostCenterListPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey) => void
}) {
  const [rows, setRows] = useState<CostCenterReportRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const { jy } = isoToJalali(todayIso())
    void fetchCostCenterReport(token, jalaliToIso(jy, 1, 1), todayIso())
      .then((r) => setRows(r.rows.filter((x) => x.cost_center_id !== null)))
      .catch((err) => setError(errText(err)))
  }, [token])

  const pg = usePagination(rows ?? [], 12)

  return (
    <div className="page panels">
      <PageHeader
        icon={Target}
        title="مراکز هزینه"
        description="فهرستِ مراکز/پروژه‌ها با سود و زیانِ سالِ جاری. برای ساخت، ویرایش و تحلیل به «شرکت ← مرکز هزینه» بروید."
      />
      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={Target}
        title={rows ? `${fa(rows.length)} مرکز` : 'در حال بارگذاری…'}
        description="ارقام از ابتدای سالِ مالی تا امروز"
        actions={
          onNavigate ? (
            <button type="button" onClick={() => onNavigate('costcenter')}>
              <Target size={13} /> میزکار مراکز
            </button>
          ) : undefined
        }
      >
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Target} text="هنوز مرکزی تعریف نشده — از «شرکت ← مرکز هزینه» اولین مرکز را بسازید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>مرکز</th>
                    <th>نوع</th>
                    <th>درآمد</th>
                    <th>هزینه</th>
                    <th>سود (با زیرمجموعه)</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.cost_center_id}>
                      <td data-label="کد">{r.cost_center_code || '—'}</td>
                      <td className="card-title" data-label="مرکز">
                        <span style={{ paddingInlineStart: r.depth * 14 }}>{r.cost_center_name}</span>
                      </td>
                      <td data-label="نوع">{costCenterKindLabel(r.kind)}</td>
                      <td data-label="درآمد" className="money-cell">{money(r.rollup_income)}</td>
                      <td data-label="هزینه" className="money-cell">{money(r.rollup_expense)}</td>
                      <td
                        data-label="سود"
                        className={`money-cell ${Number(r.rollup_profit) >= 0 ? 'pos-in' : 'pos-out'}`}
                      >
                        <strong>{money(r.rollup_profit)}</strong>
                      </td>
                      <td data-label="وضعیت">
                        <span className={`badge ${r.is_active ? 'success' : ''}`}>
                          {r.is_active ? 'فعال' : 'بسته'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

// ── گزارش‌ها و نمودارهای مدیریتی ─────────────────────────────────────────────

/**
 * مدیریتی = همان مرکزِ گزارش‌هاست. یک نسخه‌ی دومِ نمودارها یعنی دو جا که باید
 * هم‌زمان درست بمانند؛ پس همان کامپوننت این‌جا میزبانی می‌شود.
 */
export function ManagementReportsPage({ token }: { token: string }) {
  return (
    <div className="page panels">
      <PageHeader
        icon={BarChart3}
        title="گزارش‌ها و نمودارهای مدیریتی"
        description="سود و زیان، ترازنامه، جریان نقد، مطالبات و نمودارهای روند — نمای مدیریتیِ کسب‌وکار."
      />
      <Reports token={token} />
    </div>
  )
}
