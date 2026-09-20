import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Building2,
  CalendarRange,
  CheckCircle2,
  ChevronLeft,
  FolderTree,
  Layers,
  ListTree,
  Pencil,
  Plus,
  Receipt,
  Save,
  Target,
  Trash2,
  TrendingUp,
  UserCog,
  Wallet,
  X,
} from 'lucide-react'
import {
  COST_CENTER_KINDS,
  costCenterKindLabel,
  createCostCenter,
  deleteCostCenter,
  fetchCostCenterAnalysis,
  fetchCostCenterBudget,
  fetchCostCenterLedger,
  fetchCostCenterReport,
  fetchCostCenters,
  setCostCenterBudget,
  updateCostCenter,
  type BudgetLineRecord,
  type CostCenterAnalysis,
  type CostCenterIn,
  type CostCenterLedgerRow,
  type CostCenterRecord,
  type CostCenterReport,
} from '../../api'
import type { AccountCache } from '../../electron.d'
import { SectionCard } from '../../components/SectionCard'
import { StatCard } from '../../components/StatCard'
import { EmptyState } from '../../components/EmptyState'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import {
  JALALI_MONTH_NAMES,
  formatJalali,
  isoToJalali,
  jalaliToIso,
  toFaDigits,
  todayIso,
} from '../../lib/jalali'
import { faCompact } from '../../lib/format'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * میزکارِ «مرکز هزینه» — تنها جای برنامه که مرکز ساخته، سنجیده و بودجه‌بندی می‌شود.
 *
 * سه چیز این صفحه را از یک فهرستِ ساده جدا می‌کند:
 *
 * * **درخت.** شعبه جمعِ پروژه‌هایش است. ستونِ «تجمیعی» رقمِ خود و زیرشاخه‌ها را
 *   می‌دهد و ستونِ «مستقیم» فقط سندهای خودِ مرکز را — دو عددِ متفاوت که هرکدام
 *   جای خودش را دارد و قاطی‌شدنشان همان اشتباهی است که گزارشِ پروژه را بی‌اعتبار می‌کند.
 * * **بودجه.** رقمِ واقعی بدونِ برنامه فقط یک عدد است؛ کنارِ بودجه تازه تبدیل به
 *   «جلوتر یا عقب‌تر از برنامه» می‌شود.
 * * **ریزِ سند.** هر رقم باید تا سندش قابلِ دنبال‌کردن باشد، وگرنه کسی به آن تکیه نمی‌کند.
 */

const fa = (v: string | number) => Number(v || 0).toLocaleString('fa-IR')
const faInt = (n: number) => n.toLocaleString('fa-IR')

type Msg = { text: string; kind: 'ok' | 'err' } | null
type Tab = 'overview' | 'ledger' | 'budget'
type Preset = 'all' | 'year' | 'quarter' | 'month' | 'custom'

const PRESETS: { key: Preset; label: string }[] = [
  { key: 'all', label: 'از ابتدا' },
  { key: 'year', label: 'امسال' },
  { key: 'quarter', label: 'این فصل' },
  { key: 'month', label: 'این ماه' },
  { key: 'custom', label: 'دلخواه' },
]

const EMPTY_FORM: CostCenterIn = {
  code: '',
  name: '',
  name2: '',
  kind: 'project',
  parent_id: null,
  manager: '',
  start_date: null,
  end_date: null,
  is_active: true,
  notes: '',
}

/** بازه‌ی میلادیِ هر پیش‌تنظیم، از تقویمِ شمسی — «امسال» یعنی سالِ شمسی نه ژانویه. */
function presetRange(preset: Preset): { from?: string; to?: string } {
  if (preset === 'all' || preset === 'custom') return {}
  const { jy, jm } = isoToJalali(todayIso())
  if (preset === 'year') return { from: jalaliToIso(jy, 1, 1), to: todayIso() }
  if (preset === 'month') return { from: jalaliToIso(jy, jm, 1), to: todayIso() }
  const qStart = jm <= 3 ? 1 : jm <= 6 ? 4 : jm <= 9 ? 7 : 10
  return { from: jalaliToIso(jy, qStart, 1), to: todayIso() }
}

function monthLabel(iso: string): string {
  try {
    const { jy, jm } = isoToJalali(iso)
    return `${JALALI_MONTH_NAMES[jm - 1]} ${toFaDigits(jy)}`
  } catch {
    return iso
  }
}

/** «۱۴۰۴/۰۵» → «مرداد ۰۴» برای محورِ نمودار، که جا تنگ است. */
function trendLabel(label: string): string {
  const [y, m] = label.split('/')
  const idx = Number(m) - 1
  return `${JALALI_MONTH_NAMES[idx] ?? m} ${toFaDigits(y.slice(2))}`
}

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return (
    <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
      {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <div>{msg.text}</div>
    </div>
  )
}

function errText(err: unknown) {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

/** رقمِ فشرده‌ی نوارِ بالا — سبک‌تر از کارتِ KPI، چون کنارِ کنترل‌های بازه می‌نشیند. */
function Metric({
  icon,
  label,
  value,
  hint,
  tone = 'plain',
}: {
  icon: React.ReactNode
  label: string
  value: string
  hint?: string
  tone?: 'in' | 'out' | 'plain'
}) {
  return (
    <div className="cc-metric">
      <span className="cc-metric-label">
        {icon}
        {label}
      </span>
      <span className={`cc-metric-value ${tone === 'plain' ? '' : tone === 'in' ? 'pos-in' : 'pos-out'}`}>
        {value}
      </span>
      {hint && <span className="cc-metric-hint">{hint}</span>}
    </div>
  )
}

// ── نمودارِ روند ──────────────────────────────────────────────────────────────

/**
 * دو سریِ درآمد/هزینه در ۱۲ ماهِ شمسی. یک محور و یک واحد، پس میله‌ی گروهی درست است
 * و محورِ دوم لازم نمی‌شود — کارِ داده «تغییر در زمان» است، نه مقایسه‌ی دو مقیاس.
 */
function TrendChart({ points }: { points: CostCenterAnalysis['monthly'] }) {
  const [hover, setHover] = useState<number | null>(null)
  const values = points.flatMap((p) => [Number(p.income), Number(p.expense)])
  const max = Math.max(1, ...values)
  if (values.every((v) => v === 0)) {
    return <p className="hint">در ۱۲ ماهِ گذشته سندی به این مرکز برچسب نخورده.</p>
  }

  const W = 680
  const H = 220
  const padTop = 12
  const padBottom = 30
  const padLeft = 6
  const padRight = 44
  const plotW = W - padLeft - padRight
  const plotH = H - padTop - padBottom
  const baseY = padTop + plotH
  const groupW = plotW / Math.max(1, points.length)
  const barW = Math.min(14, (groupW * 0.6) / 2)
  const yAt = (v: number) => baseY - (Math.max(0, v) / max) * plotH
  const grid = Array.from({ length: 5 }, (_, i) => (max * i) / 4)

  return (
    <div className="cc-chart">
      <div className="trend-legend">
        <div className="trend-legend-item">
          <span className="trend-legend-dot" style={{ background: 'var(--series-1)' }} /> درآمد
        </div>
        <div className="trend-legend-item">
          <span className="trend-legend-dot" style={{ background: 'var(--series-2)' }} /> هزینه
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="bars-chart-svg" preserveAspectRatio="xMidYMid meet">
        {grid.map((gv, i) => (
          <g key={i}>
            <line x1={padLeft} x2={W - padRight} y1={yAt(gv)} y2={yAt(gv)} className="trend-gridline" />
            <text x={W - padRight + 4} y={yAt(gv) + 3} className="trend-axis-label" textAnchor="start">
              {faCompact(gv)}
            </text>
          </g>
        ))}
        {points.map((p, i) => {
          const cx = padLeft + groupW * i + groupW / 2
          const inc = Number(p.income)
          const exp = Number(p.expense)
          return (
            <g key={p.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect
                x={padLeft + groupW * i}
                y={padTop}
                width={groupW}
                height={plotH}
                fill="transparent"
              />
              <rect
                x={cx - barW - 1}
                y={yAt(inc)}
                width={barW}
                height={Math.max(0, baseY - yAt(inc))}
                rx={3}
                fill="var(--series-1)"
                opacity={hover === null || hover === i ? 1 : 0.45}
              />
              <rect
                x={cx + 1}
                y={yAt(exp)}
                width={barW}
                height={Math.max(0, baseY - yAt(exp))}
                rx={3}
                fill="var(--series-2)"
                opacity={hover === null || hover === i ? 1 : 0.45}
              />
              <text x={cx} y={H - 10} className="trend-axis-label" textAnchor="middle">
                {trendLabel(p.label)}
              </text>
            </g>
          )
        })}
      </svg>
      {hover !== null && points[hover] && (
        <div className="cc-chart-readout">
          <strong>{trendLabel(points[hover].label)}</strong>
          <span>درآمد {fa(points[hover].income)}</span>
          <span>هزینه {fa(points[hover].expense)}</span>
          <span className={Number(points[hover].profit) >= 0 ? 'pos-in' : 'pos-out'}>
            سود {fa(points[hover].profit)}
          </span>
        </div>
      )}
    </div>
  )
}

/** سهمِ هر حساب از درآمد یا هزینه — «پول کجا رفت» که رقمِ کل هرگز نمی‌گوید. */
function ShareList({ rows, tone }: { rows: CostCenterAnalysis['expense_accounts']; tone: 'in' | 'out' }) {
  if (rows.length === 0) return <p className="hint">در این بازه ثبتی نبوده.</p>
  return (
    <ul className="cc-share">
      {rows.slice(0, 8).map((r) => (
        <li key={r.account_id}>
          <div className="cc-share-head">
            <span className="cc-share-name" title={`${r.account_code} — ${r.account_name}`}>
              {r.account_name}
            </span>
            <span className="cc-share-amount">{fa(r.amount)}</span>
          </div>
          <div className="cc-share-track">
            <span
              className={`cc-share-fill cc-share-fill--${tone}`}
              style={{ width: `${Math.min(100, Number(r.share_pct))}%` }}
            />
          </div>
          <div className="cc-share-pct">{toFaDigits(r.share_pct)}٪</div>
        </li>
      ))}
    </ul>
  )
}

// ── فرمِ مرکز ─────────────────────────────────────────────────────────────────

function CenterForm({
  form,
  setForm,
  centers,
  editingId,
  onSubmit,
  onCancel,
  msg,
}: {
  form: CostCenterIn
  setForm: (f: CostCenterIn) => void
  centers: CostCenterRecord[]
  editingId: string | null
  onSubmit: (e: React.FormEvent) => void
  onCancel: () => void
  msg: Msg
}) {
  // مرکزِ در حالِ ویرایش و نوادگانش از فهرستِ «بالادستی» حذف می‌شوند تا کاربر اصلاً
  // نتواند حلقه بسازد؛ سرور هم رد می‌کند ولی گزینه‌ی نمایش‌داده‌شده‌ی نامعتبر بد است.
  const forbidden = useMemo(() => {
    if (!editingId) return new Set<string>()
    const out = new Set([editingId])
    let grew = true
    while (grew) {
      grew = false
      for (const c of centers) {
        if (c.parent_id && out.has(c.parent_id) && !out.has(c.id)) {
          out.add(c.id)
          grew = true
        }
      }
    }
    return out
  }, [centers, editingId])

  return (
    <form className="invoice-form form-full cc-form" onSubmit={onSubmit}>
      <label>
        نام مرکز
        <input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="پروژه برج آسمان"
        />
      </label>
      <label>
        عنوان (۲)
        <input
          value={form.name2}
          onChange={(e) => setForm({ ...form, name2: e.target.value })}
          dir="ltr"
          maxLength={200}
        />
        <span className="field-hint">عنوانِ لاتین برای گزارشِ دوزبانه. اختیاری.</span>
      </label>
      <label>
        کد (اختیاری)
        <input
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value })}
          placeholder="PRJ-01"
        />
      </label>
      <label>
        نوع
        <SearchSelect value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          {COST_CENTER_KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </SearchSelect>
      </label>
      <label>
        زیرمجموعه‌ی
        <SearchSelect
          value={form.parent_id ?? ''}
          onChange={(e) => setForm({ ...form, parent_id: e.target.value || null })}
        >
          <option value="">— سطحِ اول —</option>
          {centers
            .filter((c) => !forbidden.has(c.id))
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.path}
              </option>
            ))}
        </SearchSelect>
      </label>
      <label>
        سرپرست
        <input
          value={form.manager}
          onChange={(e) => setForm({ ...form, manager: e.target.value })}
          placeholder="نام مسئولِ مرکز"
        />
      </label>
      <label>
        تاریخ شروع
        <JalaliDatePicker
          value={form.start_date ?? ''}
          onChange={(iso) => setForm({ ...form, start_date: iso || null })}
        />
      </label>
      <label>
        تاریخ پایان
        <JalaliDatePicker
          value={form.end_date ?? ''}
          onChange={(iso) => setForm({ ...form, end_date: iso || null })}
        />
      </label>
      <label className="cc-form-wide">
        توضیحات
        <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </label>
      <label className="cal-check-inline">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
        />
        فعال (در فرم‌های ثبتِ سند پیشنهاد شود)
      </label>
      <div className="invoice-form-footer">
        {editingId && (
          <button type="button" onClick={onCancel}>
            <X size={13} /> انصراف
          </button>
        )}
        <button type="submit" className="btn-primary">
          <Save size={14} /> {editingId ? 'ذخیره‌ی تغییرات' : 'ثبت مرکز'}
        </button>
      </div>
      <Note msg={msg} />
    </form>
  )
}

// ── بودجه‌ی مرکز ──────────────────────────────────────────────────────────────

function CenterBudget({
  token,
  center,
  accounts,
  onChanged,
}: {
  token: string
  center: CostCenterRecord
  accounts: AccountCache[]
  onChanged: () => void
}) {
  const now = isoToJalali(todayIso())
  const [lines, setLines] = useState<BudgetLineRecord[] | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [form, setForm] = useState({ accountId: '', jy: now.jy, jm: now.jm, amount: '' })

  // بودجه فقط روی حساب‌های درآمد/هزینه معنا دارد: سودِ مرکز از همین‌ها ساخته می‌شود.
  const postable = useMemo(
    () => accounts.filter((a) => !a.is_group && (a.type === 'income' || a.type === 'expense')),
    [accounts],
  )
  const years = [now.jy - 1, now.jy, now.jy + 1]

  async function refresh() {
    try {
      setLines(await fetchCostCenterBudget(token, center.id))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  useEffect(() => {
    setLines(null)
    void refresh()
  }, [token, center.id])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.accountId) {
      setMsg({ text: 'حساب را انتخاب کنید.', kind: 'err' })
      return
    }
    try {
      await setCostCenterBudget(token, center.id, {
        account_id: form.accountId,
        period_date: jalaliToIso(form.jy, form.jm, 1),
        amount: Number(form.amount || 0),
        notes: '',
      })
      setForm({ ...form, amount: '' })
      setMsg({ text: 'بودجه ثبت شد.', kind: 'ok' })
      await refresh()
      onChanged()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  const totals = useMemo(() => {
    const rows = lines ?? []
    const sum = (type: string) =>
      rows.filter((l) => l.account_type === type).reduce((s, l) => s + Number(l.amount), 0)
    return { income: sum('income'), expense: sum('expense') }
  }, [lines])

  return (
    <div className="cc-budget">
      <p className="hint">
        بودجه‌ی ماهانه‌ی این مرکز. همان جدولِ بودجه‌ی کسب‌وکار است با بُعدِ مرکز — ثبتِ دوباره‌ی یک حساب در همان
        ماه رقمِ قبلی را به‌روز می‌کند، ردیفِ دوم نمی‌سازد.
      </p>
      <form className="invoice-form form-full cc-budget-form" onSubmit={submit}>
        <label>
          حساب
          <SearchSelect
            value={form.accountId}
            onChange={(e) => setForm({ ...form, accountId: e.target.value })}
          >
            <option value="">— انتخاب حساب —</option>
            {postable.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </SearchSelect>
        </label>
        <label>
          سال
          <SearchSelect value={form.jy} onChange={(e) => setForm({ ...form, jy: Number(e.target.value) })}>
            {years.map((y) => (
              <option key={y} value={y}>
                {toFaDigits(y)}
              </option>
            ))}
          </SearchSelect>
        </label>
        <label>
          ماه
          <SearchSelect value={form.jm} onChange={(e) => setForm({ ...form, jm: Number(e.target.value) })}>
            {JALALI_MONTH_NAMES.map((m, i) => (
              <option key={m} value={i + 1}>
                {m}
              </option>
            ))}
          </SearchSelect>
        </label>
        <label>
          مبلغ
          <NumberInput value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary">
            <Save size={14} /> ثبت بودجه
          </button>
        </div>
        <Note msg={msg} />
      </form>

      <div className="cc-budget-totals">
        <StatCard label="بودجه‌ی درآمد" value={fa(totals.income)} icon={<TrendingUp size={16} />} tone="success" />
        <StatCard label="بودجه‌ی هزینه" value={fa(totals.expense)} icon={<Wallet size={16} />} tone="warning" />
      </div>

      {lines == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : lines.length === 0 ? (
        <EmptyState icon={Target} text="برای این مرکز هنوز بودجه‌ای تعریف نشده." />
      ) : (
        <div className="table-scroll ef-table-wrap">
          <table className="cards-on-mobile ef-table">
            <thead>
              <tr>
                <th>دوره</th>
                <th>حساب</th>
                <th>نوع</th>
                <th>مبلغ</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l) => (
                <tr key={l.id}>
                  <td data-label="دوره">{monthLabel(l.period_date)}</td>
                  <td className="card-title" data-label="حساب">{l.account_name}</td>
                  <td data-label="نوع">{l.account_type === 'income' ? 'درآمد' : 'هزینه'}</td>
                  <td data-label="مبلغ" className="money-cell">
                    {fa(l.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── ریزِ اسناد ────────────────────────────────────────────────────────────────

function CenterLedger({
  token,
  center,
  from,
  to,
  includeChildren,
}: {
  token: string
  center: CostCenterRecord
  from?: string
  to?: string
  includeChildren: boolean
}) {
  const [rows, setRows] = useState<CostCenterLedgerRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pg = usePagination(rows ?? [], 12, center.id)

  useEffect(() => {
    setRows(null)
    setError(null)
    void fetchCostCenterLedger(token, center.id, from, to, includeChildren, 200)
      .then(setRows)
      .catch((err) => setError(errText(err)))
  }, [token, center.id, from, to, includeChildren])

  if (error) return <div className="error">{error}</div>
  if (rows == null) return <p className="muted">در حال بارگذاری…</p>
  if (rows.length === 0)
    return <EmptyState icon={Receipt} text="در این بازه سندی به این مرکز برچسب نخورده." />

  return (
    <>
      <p className="hint">
        فقط ردیف‌های درآمد و هزینه — همان‌هایی که سودِ مرکز از آن‌ها ساخته می‌شود. سبز درآمد است و قرمز هزینه.
        سقفِ نمایش ۲۰۰ ردیفِ اخیر است.
      </p>
      <div className="table-scroll ef-table-wrap">
        <table className="cards-on-mobile cc-ledger-table">
          <thead>
            <tr>
              <th>تاریخ</th>
              <th>سند</th>
              <th>حساب</th>
              <th>شرح</th>
              {includeChildren && <th>مرکز</th>}
              <th>مبلغ</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((r) => (
              <tr key={r.line_id}>
                <td data-label="تاریخ">{formatJalali(r.entry_date)}</td>
                <td data-label="سند">{r.entry_number ? toFaDigits(r.entry_number) : '—'}</td>
                <td className="card-title cc-ledger-account" data-label="حساب">{r.account_name}</td>
                <td data-label="شرح" className="cc-ledger-desc">
                  {r.description || '—'}
                </td>
                {includeChildren && <td data-label="مرکز">{r.cost_center_name}</td>}
                {/* یک ستونِ مبلغ به‌جای بدهکار/بستانکار: در دفترِ مرکز، درآمد همیشه
                    بستانکار است و هزینه بدهکار، پس دو ستون یعنی یکی همیشه خالی. */}
                <td data-label="مبلغ" className="money-cell">
                  <span className={r.account_type === 'income' ? 'pos-in' : 'pos-out'}>
                    {fa(Number(r.debit) || Number(r.credit))}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </div>
    </>
  )
}

// ── میزکار ────────────────────────────────────────────────────────────────────

export function CostCenterWorkspace({
  token,
  accounts,
}: {
  token: string
  accounts: AccountCache[]
}) {
  const [centers, setCenters] = useState<CostCenterRecord[] | null>(null)
  const [report, setReport] = useState<CostCenterReport | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<CostCenterAnalysis | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [includeChildren, setIncludeChildren] = useState(true)
  const [showInactive, setShowInactive] = useState(false)
  const [preset, setPreset] = useState<Preset>('year')
  const [custom, setCustom] = useState({ from: '', to: '' })
  const [form, setForm] = useState<CostCenterIn>({ ...EMPTY_FORM })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formMsg, setFormMsg] = useState<Msg>(null)
  const [listMsg, setListMsg] = useState<Msg>(null)
  const [formOpen, setFormOpen] = useState(false)

  const range = preset === 'custom' ? { from: custom.from || undefined, to: custom.to || undefined } : presetRange(preset)

  async function refresh() {
    try {
      const [list, rep] = await Promise.all([
        fetchCostCenters(token),
        fetchCostCenterReport(token, range.from, range.to),
      ])
      setCenters(list)
      setReport(rep)
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
  }, [token, range.from, range.to])

  useEffect(() => {
    if (!selectedId) {
      setAnalysis(null)
      return
    }
    setAnalysis(null)
    void fetchCostCenterAnalysis(token, selectedId, range.from, range.to, includeChildren)
      .then(setAnalysis)
      .catch((err) => setListMsg({ text: errText(err), kind: 'err' }))
  }, [token, selectedId, range.from, range.to, includeChildren])

  const byId = useMemo(() => new Map((centers ?? []).map((c) => [c.id, c])), [centers])
  const statsById = useMemo(
    () => new Map((report?.rows ?? []).filter((r) => r.cost_center_id).map((r) => [r.cost_center_id!, r])),
    [report],
  )
  const untagged = report?.rows.find((r) => r.cost_center_id === null)
  const selected = selectedId ? byId.get(selectedId) ?? null : null

  const visible = useMemo(
    () => (centers ?? []).filter((c) => showInactive || c.is_active),
    [centers, showInactive],
  )

  function startCreate(parentId: string | null) {
    setEditingId(null)
    setForm({ ...EMPTY_FORM, parent_id: parentId })
    setFormMsg(null)
    setFormOpen(true)
  }

  function startEdit(c: CostCenterRecord) {
    setEditingId(c.id)
    setForm({
      code: c.code,
      name: c.name,
      name2: c.name2,
      kind: c.kind,
      parent_id: c.parent_id,
      manager: c.manager,
      start_date: c.start_date,
      end_date: c.end_date,
      is_active: c.is_active,
      notes: c.notes,
    })
    setFormMsg(null)
    setFormOpen(true)
  }

  async function submitForm(e: React.FormEvent) {
    e.preventDefault()
    setFormMsg(null)
    if (!form.name.trim()) {
      setFormMsg({ text: 'نام مرکز الزامی است.', kind: 'err' })
      return
    }
    try {
      if (editingId) await updateCostCenter(token, editingId, form)
      else await createCostCenter(token, form)
      setFormOpen(false)
      setEditingId(null)
      setForm({ ...EMPTY_FORM })
      await refresh()
    } catch (err) {
      setFormMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function remove(c: CostCenterRecord) {
    if (!window.confirm(`مرکز «${c.name}» حذف شود؟`)) return
    setListMsg(null)
    try {
      await deleteCostCenter(token, c.id)
      if (selectedId === c.id) setSelectedId(null)
      await refresh()
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
    }
  }

  const totals = report ?? null

  return (
    <>
      {/* ── نوارِ بازه و ارقامِ کل ──
          شاخص‌ها عمداً کارتِ KPIِ سطحِ صفحه نیستند: پوسته‌ی «راهنما» ردیفِ KPIِ بالای
          صفحه‌های ماژول را پنهان می‌کند و این چهار عدد باید همیشه دیده شوند. */}
      <div className="cc-head">
        <div className="cc-toolbar">
          <div className="cc-presets">
            <CalendarRange size={15} />
            {PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                className={preset === p.key ? 'is-active' : ''}
                onClick={() => setPreset(p.key)}
              >
                {p.label}
              </button>
            ))}
          </div>
          {preset === 'custom' && (
            <div className="cc-custom-range">
              <JalaliDatePicker
                value={custom.from}
                onChange={(iso) => setCustom({ ...custom, from: iso })}
                placeholder="از تاریخ"
              />
              <JalaliDatePicker
                value={custom.to}
                onChange={(iso) => setCustom({ ...custom, to: iso })}
                placeholder="تا تاریخ"
              />
            </div>
          )}
          <label className="cal-check-inline">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
            />
            نمایشِ غیرفعال‌ها
          </label>
        </div>

        <div className="cc-summary">
          <Metric
            icon={<TrendingUp size={14} />}
            label="درآمدِ برچسب‌خورده"
            value={totals ? fa(totals.total_income) : '—'}
            tone="in"
          />
          <Metric
            icon={<Wallet size={14} />}
            label="هزینه‌ی برچسب‌خورده"
            value={totals ? fa(totals.total_expense) : '—'}
            tone="out"
          />
          <Metric
            icon={<BarChart3 size={14} />}
            label="سود / زیان"
            value={totals ? fa(totals.total_profit) : '—'}
            tone={totals && Number(totals.total_profit) < 0 ? 'out' : 'in'}
          />
          <Metric
            icon={<AlertTriangle size={14} />}
            label="بدون مرکز"
            value={totals ? `${toFaDigits(totals.untagged_share_pct)}٪` : '—'}
            hint={untagged ? `${fa(untagged.income)} درآمدِ برچسب‌نخورده` : 'همه‌ی گردش برچسب خورده'}
            tone={totals && Number(totals.untagged_share_pct) > 30 ? 'out' : 'plain'}
          />
        </div>
      </div>

      <Note msg={listMsg} />

      <div className="workspace-split cc-split">
        {/* ── درختِ مراکز ── */}
        <SectionCard
          icon={FolderTree}
          title="مراکز و پروژه‌ها"
          description={
            centers ? `${faInt(visible.length)} مرکز — رقم‌ها در بازه‌ی انتخابی` : 'در حال بارگذاری…'
          }
          actions={
            <button type="button" onClick={() => startCreate(null)}>
              <Plus size={13} /> مرکز جدید
            </button>
          }
        >
          {centers == null ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : visible.length === 0 ? (
            <EmptyState
              icon={FolderTree}
              text="هنوز مرکزی تعریف نشده. با «مرکز جدید» شروع کنید — بعد فاکتورها و اسناد را به آن برچسب بزنید."
            />
          ) : (
            /* فهرست است نه جدول: ستونِ مادر باریک است و پنج ستونِ عددی در آن به
               ردیف‌های چندخطی و ناخوانا می‌شکند. رقمِ تجمیعی جلوی چشم می‌ماند و
               رقمِ مستقیم در پرونده‌ی همان مرکز دیده می‌شود. */
            <ul className="cc-tree">
              {visible.map((c) => {
                const s = statsById.get(c.id)
                const profit = Number(s?.rollup_profit ?? 0)
                const variance = s?.profit_variance
                return (
                  <li
                    key={c.id}
                    className={`cc-node ${selectedId === c.id ? 'is-selected' : ''} ${
                      c.is_active ? '' : 'is-muted'
                    }`}
                  >
                    <button
                      type="button"
                      className="cc-node-main"
                      style={{ paddingInlineStart: 10 + c.depth * 22 }}
                      onClick={() => setSelectedId(c.id)}
                    >
                      <span className="cc-node-text">
                        <span className="cc-node-title">
                          <span className="cc-kind-chip">{costCenterKindLabel(c.kind)}</span>
                          <span className="cc-tree-title">{c.name}</span>
                        </span>
                        <span className="cc-node-sub">
                          {c.code && <span className="cc-tree-code">{c.code}</span>}
                          {c.manager && <span>{c.manager}</span>}
                          {c.child_count > 0 && <span>{faInt(c.child_count)} زیرمجموعه</span>}
                          {!c.is_active && <span className="status-badge tone-warning">غیرفعال</span>}
                        </span>
                      </span>
                      <span className="cc-node-figures">
                        <span className={`cc-node-profit ${profit >= 0 ? 'pos-in' : 'pos-out'}`}>
                          {s ? fa(s.rollup_profit) : '—'}
                        </span>
                        <span className="cc-node-var">
                          {variance == null ? (
                            'بدون بودجه'
                          ) : (
                            <span className={Number(variance) >= 0 ? 'pos-in' : 'pos-out'}>
                              انحراف {Number(variance) >= 0 ? '+' : ''}
                              {fa(variance)}
                            </span>
                          )}
                        </span>
                      </span>
                    </button>
                    <span className="cc-node-actions check-actions">
                      <button type="button" onClick={() => startCreate(c.id)} aria-label="زیرمجموعه">
                        <Layers size={13} />
                      </button>
                      <button type="button" onClick={() => startEdit(c)} aria-label="ویرایش">
                        <Pencil size={13} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn-danger"
                        onClick={() => void remove(c)}
                        aria-label="حذف"
                      >
                        <Trash2 size={13} />
                      </button>
                    </span>
                  </li>
                )
              })}
            </ul>
          )}

          {formOpen && (
            <div className="cc-form-slot">
              <div className="cc-form-title">
                {editingId ? <Pencil size={14} /> : <Plus size={14} />}
                {editingId ? 'ویرایش مرکز' : 'مرکز جدید'}
                <button type="button" className="cc-form-close" onClick={() => setFormOpen(false)}>
                  <X size={14} />
                </button>
              </div>
              <CenterForm
                form={form}
                setForm={setForm}
                centers={centers ?? []}
                editingId={editingId}
                onSubmit={submitForm}
                onCancel={() => setFormOpen(false)}
                msg={formMsg}
              />
            </div>
          )}
        </SectionCard>

        {/* ── پرونده‌ی مرکزِ انتخابی ── */}
        <SectionCard
          icon={Target}
          title={selected ? selected.name : 'پرونده‌ی مرکز'}
          description={
            selected
              ? selected.path
              : 'یک مرکز را از فهرست انتخاب کنید تا ارقام، بودجه و اسنادش را ببینید.'
          }
          actions={
            selected ? (
              <label className="cal-check-inline">
                <input
                  type="checkbox"
                  checked={includeChildren}
                  onChange={(e) => setIncludeChildren(e.target.checked)}
                />
                با زیرمجموعه‌ها
              </label>
            ) : undefined
          }
        >
          {!selected ? (
            <EmptyState icon={ListTree} text="مرکزی انتخاب نشده." />
          ) : (
            <>
              <div className="cc-tabs">
                <button
                  type="button"
                  className={tab === 'overview' ? 'is-active' : ''}
                  onClick={() => setTab('overview')}
                >
                  نمای کلی
                </button>
                <button
                  type="button"
                  className={tab === 'ledger' ? 'is-active' : ''}
                  onClick={() => setTab('ledger')}
                >
                  ریز اسناد
                </button>
                <button
                  type="button"
                  className={tab === 'budget' ? 'is-active' : ''}
                  onClick={() => setTab('budget')}
                >
                  بودجه
                </button>
              </div>

              {tab === 'overview' &&
                (analysis == null ? (
                  <p className="muted">در حال بارگذاری…</p>
                ) : (
                  <div className="cc-overview">
                    <div className="cc-meta">
                      {selected.manager && (
                        <span>
                          <UserCog size={13} /> {selected.manager}
                        </span>
                      )}
                      {selected.start_date && (
                        <span>
                          <CalendarRange size={13} /> {formatJalali(selected.start_date)}
                          {selected.end_date ? ` تا ${formatJalali(selected.end_date)}` : ''}
                        </span>
                      )}
                      <span>
                        <Receipt size={13} /> {faInt(analysis.entry_count)} سند
                      </span>
                      {selected.child_count > 0 && (
                        <span>
                          <Building2 size={13} /> {faInt(selected.child_count)} زیرمجموعه
                        </span>
                      )}
                    </div>

                    <div className="stat-grid cc-inner-stats">
                      <StatCard label="درآمد" value={fa(analysis.income)} icon={<TrendingUp size={16} />} tone="success" />
                      <StatCard label="هزینه" value={fa(analysis.expense)} icon={<Wallet size={16} />} tone="warning" />
                      <StatCard
                        label="سود / زیان"
                        value={fa(analysis.profit)}
                        hint={analysis.margin_pct ? `حاشیه ${toFaDigits(analysis.margin_pct)}٪` : undefined}
                        icon={<BarChart3 size={16} />}
                        tone={Number(analysis.profit) < 0 ? 'danger' : 'default'}
                      />
                      <StatCard
                        label="انحراف از بودجه"
                        value={analysis.has_budget ? fa(analysis.profit_variance ?? 0) : '—'}
                        hint={
                          analysis.has_budget
                            ? `بودجه ${fa(analysis.budget_profit)}`
                            : 'بودجه‌ای تعریف نشده'
                        }
                        icon={<Target size={16} />}
                        tone={
                          analysis.has_budget && Number(analysis.profit_variance ?? 0) < 0
                            ? 'danger'
                            : 'default'
                        }
                      />
                    </div>

                    {analysis.has_budget && (
                      <BudgetGauge analysis={analysis} />
                    )}

                    <div className="cc-panel">
                      <h4>روند ۱۲ ماهه</h4>
                      <TrendChart points={analysis.monthly} />
                    </div>

                    <div className="cc-shares">
                      <div className="cc-panel">
                        <h4>ترکیب درآمد</h4>
                        <ShareList rows={analysis.income_accounts} tone="in" />
                      </div>
                      <div className="cc-panel">
                        <h4>ترکیب هزینه</h4>
                        <ShareList rows={analysis.expense_accounts} tone="out" />
                      </div>
                    </div>

                    {analysis.children.length > 0 && (
                      <div className="cc-panel">
                        <h4>زیرمجموعه‌ها</h4>
                        <div className="table-scroll ef-table-wrap">
                          <table className="cards-on-mobile ef-table">
                            <thead>
                              <tr>
                                <th>مرکز</th>
                                <th>درآمد</th>
                                <th>هزینه</th>
                                <th>سود</th>
                                <th />
                              </tr>
                            </thead>
                            <tbody>
                              {analysis.children.map((ch) => (
                                <tr key={ch.id}>
                                  <td className="card-title" data-label="مرکز">{ch.name}</td>
                                  <td data-label="درآمد" className="money-cell">
                                    {fa(ch.income)}
                                  </td>
                                  <td data-label="هزینه" className="money-cell">
                                    {fa(ch.expense)}
                                  </td>
                                  <td
                                    data-label="سود"
                                    className={`money-cell ${Number(ch.profit) >= 0 ? 'pos-in' : 'pos-out'}`}
                                  >
                                    {fa(ch.profit)}
                                  </td>
                                  <td className="card-actions">
                                    <button type="button" onClick={() => setSelectedId(ch.id)}>
                                      <ChevronLeft size={13} /> باز کردن
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

              {tab === 'ledger' && (
                <CenterLedger
                  token={token}
                  center={selected}
                  from={range.from}
                  to={range.to}
                  includeChildren={includeChildren}
                />
              )}

              {tab === 'budget' && (
                <CenterBudget
                  token={token}
                  center={selected}
                  accounts={accounts}
                  onChanged={() => void refresh()}
                />
              )}
            </>
          )}
        </SectionCard>
      </div>
    </>
  )
}

/**
 * مصرفِ بودجه در برابر گذشتِ زمان. تنها جایی که «۷۰٪ بودجه مصرف شده» معنا پیدا
 * می‌کند وقتی است که بدانیم چند درصد از پروژه گذشته؛ دو نوار زیرِ هم همین را می‌گویند.
 */
function BudgetGauge({ analysis }: { analysis: CostCenterAnalysis }) {
  const budget = Number(analysis.budget_expense)
  const spent = Number(analysis.expense)
  const usedPct = budget > 0 ? Math.min(200, (spent / budget) * 100) : null
  const elapsed = analysis.elapsed_pct == null ? null : Number(analysis.elapsed_pct)
  if (usedPct == null && elapsed == null) return null

  // «جلو زدن» یعنی یا از کلِ بودجه رد شده، یا از سهمِ زمانیِ خودش جلوتر است.
  const over = usedPct != null && (usedPct > 100 || (elapsed != null && usedPct > elapsed + 5))
  return (
    <div className="cc-panel cc-gauge">
      <h4>مصرف بودجه در برابر گذشتِ زمان</h4>
      {usedPct != null && (
        <div className="cc-gauge-row">
          <span className="cc-gauge-label">هزینه‌ی مصرف‌شده</span>
          <div className="cc-gauge-track">
            <span
              className={`cc-gauge-fill ${over ? 'cc-gauge-fill--over' : ''}`}
              style={{ width: `${Math.min(100, usedPct)}%` }}
            />
          </div>
          <span className="cc-gauge-pct">{toFaDigits(usedPct.toFixed(0))}٪</span>
        </div>
      )}
      {elapsed != null && (
        <div className="cc-gauge-row">
          <span className="cc-gauge-label">زمانِ سپری‌شده</span>
          <div className="cc-gauge-track">
            <span className="cc-gauge-fill cc-gauge-fill--time" style={{ width: `${elapsed}%` }} />
          </div>
          <span className="cc-gauge-pct">{toFaDigits(elapsed.toFixed(0))}٪</span>
        </div>
      )}
      {over && (
        <p className="hint cc-gauge-warn">
          <AlertTriangle size={13} />{' '}
          {usedPct != null && usedPct > 100
            ? 'هزینه از کلِ بودجه‌ی تعریف‌شده گذشته است.'
            : 'مصرفِ بودجه از پیشرفتِ زمانی جلو زده — با این آهنگ، بودجه پیش از پایانِ پروژه تمام می‌شود.'}
        </p>
      )}
    </div>
  )
}
