import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowDownUp,
  CheckCircle2,
  LayoutList,
  Pin,
  Play,
  Save,
  Trash2,
  Wrench,
  X,
} from 'lucide-react'
import {
  createSavedReport,
  deleteSavedReport,
  fetchSavedReports,
  updateSavedReport,
  type SavedReportRecord,
} from '../../api'
import { MODULE_LISTS } from '../../components/moduleLists'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { EmptyState } from '../../components/EmptyState'
import { Pager, usePagination } from '../../components/Pager'
import type { PageKey } from '../../lib/navModel'

/**
 * گزارش‌ساز و گزارش‌های پویا.
 *
 * **منابعِ داده از رجیستریِ فهرست‌ها می‌آیند** (`MODULE_LISTS`) نه از یک فهرستِ
 * دستیِ موازی: همان‌جا برای هر ماژول یک بارگذارِ واقعی تعریف شده، و هر منبعِ تازه‌ای
 * که به برنامه اضافه شود خودکار این‌جا هم پیدا می‌شود. فهرستِ دوم دیر یا زود از
 * اولی عقب می‌ماند.
 *
 * **ستون‌ها از خودِ داده کشف می‌شوند.** نگاشتِ دستیِ ستون‌ها یعنی هر فیلدِ تازه‌ای در
 * بک‌اند باید این‌جا هم اضافه شود وگرنه نامرئی می‌ماند؛ کشف از روی کلیدهای ردیف
 * این هزینه را حذف می‌کند.
 *
 * **فقط تعریف ذخیره می‌شود، نه نتیجه.** گزارشِ ذخیره‌شده هر بار زنده اجرا می‌شود؛
 * خروجیِ ذخیره‌شده گزارشی است که با گذشتِ زمان دروغ می‌گوید.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

type Msg = { text: string; kind: 'ok' | 'err' } | null

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return (
    <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
      {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <div>{msg.text}</div>
    </div>
  )
}

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

/** یک منبعِ داده: کلیدِ یکتا، برچسبِ فارسی و بارگذار. */
type Source = {
  key: string
  label: string
  load: (token: string) => Promise<Record<string, unknown>[]>
}

/** همه‌ی منابعِ موجود، تختِ‌شده از رجیستریِ فهرست‌های ماژول‌ها. */
const SOURCES: Source[] = Object.entries(MODULE_LISTS).flatMap(([page, defs]) =>
  Object.entries(defs ?? {}).map(([section, def]) => ({
    key: `${page}.${section}`,
    label: def.label,
    load: def.fetch as (token: string) => Promise<Record<string, unknown>[]>,
  })),
)

const SOURCE_BY_KEY = new Map(SOURCES.map((s) => [s.key, s]))

/**
 * برچسبِ فارسیِ نام‌های پرتکرارِ ستون‌ها.
 *
 * کشفِ خودکارِ ستون‌ها نامِ خامِ فیلد را می‌دهد (`total_amount`) که برای کاربرِ فارسی
 * خوانا نیست. نگاشتِ *کامل* هم شدنی نیست — هر منبع فیلدهای خودش را دارد و فهرست
 * دیر یا زود عقب می‌ماند. پس فقط نام‌های مشترکِ بینِ منابع ترجمه می‌شوند و بقیه
 * همان نامِ خام را نگه می‌دارند: خوانا برای اکثریت، بی‌آنکه چیزی نامرئی شود.
 */
const FIELD_LABELS: Record<string, string> = {
  id: 'شناسه',
  number: 'شماره',
  serial: 'سریال',
  code: 'کد',
  name: 'نام',
  title: 'عنوان',
  description: 'شرح',
  notes: 'توضیحات',
  status: 'وضعیت',
  type: 'نوع',
  category: 'دسته',
  is_active: 'فعال',
  created_at: 'تاریخ ایجاد',
  updated_at: 'آخرین تغییر',
  created_by_name: 'ثبت‌کننده',
  // مبالغ و تاریخ‌های سند
  total_amount: 'مبلغ کل',
  total_discount: 'تخفیف',
  total_cost: 'بهای تمام‌شده',
  tax_amount: 'مالیات',
  tax_rate: 'نرخ مالیات',
  invoice_date: 'تاریخ فاکتور',
  invoice_discount: 'تخفیف فاکتور',
  due_date: 'سررسید',
  entry_date: 'تاریخ سند',
  quotation_date: 'تاریخ پیش‌فاکتور',
  return_date: 'تاریخ برگشت',
  amount: 'مبلغ',
  paid_amount: 'پرداخت‌شده',
  remaining: 'مانده',
  currency_code: 'ارز',
  exchange_rate: 'نرخ ارز',
  // طرف‌حساب، کالا، انبار
  contact_id: 'طرف حساب',
  contact_name: 'طرف حساب',
  customer_name: 'مشتری',
  supplier_name: 'تأمین‌کننده',
  item_id: 'کالا',
  item_name: 'کالا',
  sku: 'کد کالا',
  barcode: 'بارکد',
  quantity: 'تعداد',
  unit: 'واحد',
  warehouse_id: 'انبار',
  warehouse_name: 'انبار',
  cost_center_id: 'مرکز هزینه',
  phone: 'تلفن',
  email: 'ایمیل',
  address: 'نشانی',
  national_id: 'کد/شناسه ملی',
  economic_code: 'کد اقتصادی',
  postal_code: 'کد پستی',
  // ابطال
  voided_at: 'تاریخ ابطال',
  void_reason: 'دلیل ابطال',
  lines: 'ردیف‌ها',
}

const fieldLabel = (key: string) => FIELD_LABELS[key] ?? key

/** عملگرهای فیلتر — عمداً کم و قابلِ‌فهم، نه یک زبانِ کوئریِ کامل. */
const OPERATORS = [
  { key: 'contains', label: 'شامل' },
  { key: 'equals', label: 'برابر با' },
  { key: 'gt', label: 'بزرگ‌تر از' },
  { key: 'lt', label: 'کوچک‌تر از' },
  { key: 'nonempty', label: 'خالی نباشد' },
] as const

type Filter = { column: string; op: string; value: string }

export type ReportConfig = {
  columns: string[]
  filters: Filter[]
  sortBy: string
  sortDir: 'asc' | 'desc'
  limit: number
}

const EMPTY_CONFIG: ReportConfig = {
  columns: [],
  filters: [],
  sortBy: '',
  sortDir: 'asc',
  limit: 200,
}

function readConfig(raw: unknown): ReportConfig {
  const c = (raw ?? {}) as Partial<ReportConfig>
  return {
    columns: Array.isArray(c.columns) ? c.columns : [],
    filters: Array.isArray(c.filters) ? c.filters : [],
    sortBy: typeof c.sortBy === 'string' ? c.sortBy : '',
    sortDir: c.sortDir === 'desc' ? 'desc' : 'asc',
    limit: typeof c.limit === 'number' ? c.limit : 200,
  }
}

/** مقدارِ سلول به متنِ خوانا — بی‌آنکه بخواهیم شکلِ هر منبع را از پیش بدانیم. */
function cell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر'
  if (typeof value === 'number') return value.toLocaleString('fa-IR')
  if (typeof value === 'string') {
    // تاریخِ ISO و عددِ متنی، دو حالتِ رایجِ داده‌ی این برنامه‌اند.
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10)
    if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value).toLocaleString('fa-IR')
    return value
  }
  if (Array.isArray(value)) return `${fa(value.length)} مورد`
  return '—'
}

function passes(row: Record<string, unknown>, f: Filter): boolean {
  const raw = row[f.column]
  const text = raw === null || raw === undefined ? '' : String(raw)
  switch (f.op) {
    case 'contains':
      return text.includes(f.value)
    case 'equals':
      return text === f.value
    case 'gt':
      return Number(raw) > Number(f.value)
    case 'lt':
      return Number(raw) < Number(f.value)
    case 'nonempty':
      return text !== ''
    default:
      return true
  }
}

/** اجرای تعریف روی ردیف‌های خام. */
export function runReport(
  rows: Record<string, unknown>[],
  config: ReportConfig,
): Record<string, unknown>[] {
  let out = rows.filter((r) => config.filters.every((f) => passes(r, f)))
  if (config.sortBy) {
    const dir = config.sortDir === 'desc' ? -1 : 1
    out = [...out].sort((a, b) => {
      const av = a[config.sortBy]
      const bv = b[config.sortBy]
      const an = Number(av)
      const bn = Number(bv)
      if (!Number.isNaN(an) && !Number.isNaN(bn) && av !== '' && bv !== '') return (an - bn) * dir
      return String(av ?? '').localeCompare(String(bv ?? ''), 'fa') * dir
    })
  }
  return out.slice(0, Math.max(1, config.limit))
}

/** جدولِ نتیجه — مشترکِ گزارش‌ساز و گزارش‌های پویا. */
export function ResultTable({
  rows,
  columns,
}: {
  rows: Record<string, unknown>[]
  columns: string[]
}) {
  const pg = usePagination(rows, 10, columns.join('|'))
  if (columns.length === 0) {
    return <p className="muted">هنوز ستونی انتخاب نشده است.</p>
  }
  if (rows.length === 0) {
    return <EmptyState icon={LayoutList} text="هیچ ردیفی با این فیلترها پیدا نشد." />
  }
  return (
    <>
      <div className="table-scroll">
        <table className="cards-on-mobile">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{fieldLabel(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((row, i) => (
              <tr key={String(row.id ?? i)}>
                {columns.map((c) => (
                  <td key={c} data-label={fieldLabel(c)}>
                    {cell(row[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </>
  )
}

// ── گزارش‌ساز ────────────────────────────────────────────────────────────────

export function ReportBuilderPage({ token }: { token: string }) {
  const [sourceKey, setSourceKey] = useState(SOURCES[0]?.key ?? '')
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null)
  const [config, setConfig] = useState<ReportConfig>(EMPTY_CONFIG)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)

  const load = useCallback(
    async (key: string) => {
      const src = SOURCE_BY_KEY.get(key)
      if (!src) return
      setRows(null)
      setMsg(null)
      try {
        const data = await src.load(token)
        setRows(data)
      } catch (err) {
        setRows([])
        setMsg({ text: errText(err), kind: 'err' })
      }
    },
    [token],
  )

  useEffect(() => {
    void load(sourceKey)
  }, [sourceKey, load])

  //: ستون‌ها از چند ردیفِ اول کشف می‌شوند — یک ردیف کافی نیست چون فیلدهای اختیاری
  //: ممکن است در ردیفِ اول خالی و در بقیه پر باشند.
  const columns = useMemo(() => {
    const keys = new Set<string>()
    for (const row of (rows ?? []).slice(0, 25)) {
      for (const k of Object.keys(row)) keys.add(k)
    }
    return [...keys]
  }, [rows])

  // با عوض‌شدنِ منبع، ستون‌های انتخاب‌شده‌ی قبلی بی‌معنا می‌شوند.
  useEffect(() => {
    setConfig((c) => ({
      ...c,
      columns: c.columns.filter((x) => columns.includes(x)),
      filters: c.filters.filter((f) => columns.includes(f.column)),
      sortBy: columns.includes(c.sortBy) ? c.sortBy : '',
    }))
  }, [columns])

  const result = useMemo(() => runReport(rows ?? [], config), [rows, config])

  function toggleColumn(col: string) {
    setConfig((c) => ({
      ...c,
      columns: c.columns.includes(col) ? c.columns.filter((x) => x !== col) : [...c.columns, col],
    }))
  }

  async function save() {
    if (!name.trim() || config.columns.length === 0) return
    setBusy(true)
    setMsg(null)
    try {
      const payload = {
        name: name.trim(),
        description,
        source: sourceKey,
        config: config as unknown as Record<string, unknown>,
        is_pinned: false,
      }
      if (editingId) await updateSavedReport(token, editingId, payload)
      else await createSavedReport(token, payload)
      setMsg({
        text: `گزارشِ «${name.trim()}» ذخیره شد و در «گزارش‌های پویا» در دسترس است.`,
        kind: 'ok',
      })
      setEditingId(null)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const source = SOURCE_BY_KEY.get(sourceKey)

  return (
    <div className="page panels">
      <PageHeader
        icon={Wrench}
        title="گزارش‌ساز"
        description="منبعِ داده را انتخاب کنید، ستون‌ها و فیلترها را بچینید، و نتیجه را همان‌جا ببینید. آنچه ذخیره می‌شود *تعریفِ* گزارش است، پس هر بار تازه اجرا می‌شود."
      />
      <Note msg={msg} />

      <SectionCard
        icon={Wrench}
        title="۱. منبعِ داده"
        description={
          rows == null
            ? 'در حال بارگذاری…'
            : `${fa(rows.length)} ردیف خوانده شد؛ ${fa(columns.length)} ستون در دسترس است.`
        }
        actions={
          <select value={sourceKey} onChange={(e) => setSourceKey(e.target.value)}>
            {SOURCES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        }
      >
        <p className="bk-hint">
          منابع همان فهرست‌های ماژول‌های برنامه‌اند؛ هر فهرستِ تازه‌ای که اضافه شود خودکار این‌جا هم می‌آید.
        </p>
      </SectionCard>

      <SectionCard
        icon={LayoutList}
        title="۲. ستون‌ها"
        description="ترتیبِ انتخاب همان ترتیبِ ستون‌ها در خروجی است."
        actions={
          config.columns.length > 0 ? (
            <button type="button" onClick={() => setConfig((c) => ({ ...c, columns: [] }))}>
              <X size={13} /> پاک‌کردن
            </button>
          ) : undefined
        }
      >
        {columns.length === 0 ? (
          <p className="muted">این منبع فعلاً داده‌ای ندارد، پس ستونی برای انتخاب نیست.</p>
        ) : (
          <div className="rb-cols">
            {columns.map((c) => (
              <label key={c} className={`rb-col${config.columns.includes(c) ? ' is-on' : ''}`}>
                <input
                  type="checkbox"
                  checked={config.columns.includes(c)}
                  onChange={() => toggleColumn(c)}
                />
                <span title={c}>{fieldLabel(c)}</span>
              </label>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard
        icon={ArrowDownUp}
        title="۳. فیلتر و مرتب‌سازی"
        actions={
          <button
            type="button"
            disabled={columns.length === 0}
            onClick={() =>
              setConfig((c) => ({
                ...c,
                filters: [...c.filters, { column: columns[0], op: 'contains', value: '' }],
              }))
            }
          >
            افزودنِ فیلتر
          </button>
        }
      >
        {config.filters.length === 0 ? (
          <p className="muted">فیلتری تعریف نشده — همه‌ی ردیف‌ها می‌آیند.</p>
        ) : (
          <div className="rb-filters">
            {config.filters.map((f, i) => (
              <div key={i} className="rb-filter">
                <select
                  value={f.column}
                  onChange={(e) =>
                    setConfig((c) => ({
                      ...c,
                      filters: c.filters.map((x, j) => (j === i ? { ...x, column: e.target.value } : x)),
                    }))
                  }
                >
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {fieldLabel(c)}
                    </option>
                  ))}
                </select>
                <select
                  value={f.op}
                  onChange={(e) =>
                    setConfig((c) => ({
                      ...c,
                      filters: c.filters.map((x, j) => (j === i ? { ...x, op: e.target.value } : x)),
                    }))
                  }
                >
                  {OPERATORS.map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <input
                  value={f.value}
                  disabled={f.op === 'nonempty'}
                  onChange={(e) =>
                    setConfig((c) => ({
                      ...c,
                      filters: c.filters.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)),
                    }))
                  }
                />
                <button
                  type="button"
                  className="icon-btn-danger"
                  onClick={() =>
                    setConfig((c) => ({ ...c, filters: c.filters.filter((_, j) => j !== i) }))
                  }
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="rb-sort">
          <label>
            <span>مرتب بر اساسِ</span>
            <select
              value={config.sortBy}
              onChange={(e) => setConfig((c) => ({ ...c, sortBy: e.target.value }))}
            >
              <option value="">— بدون مرتب‌سازی —</option>
              {columns.map((c) => (
                <option key={c} value={c}>
                  {fieldLabel(c)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>جهت</span>
            <select
              value={config.sortDir}
              onChange={(e) =>
                setConfig((c) => ({ ...c, sortDir: e.target.value as 'asc' | 'desc' }))
              }
            >
              <option value="asc">صعودی</option>
              <option value="desc">نزولی</option>
            </select>
          </label>
          <label>
            <span>حداکثر ردیف</span>
            <input
              type="number"
              min={1}
              value={config.limit}
              onChange={(e) => setConfig((c) => ({ ...c, limit: Number(e.target.value) || 1 }))}
            />
          </label>
        </div>
      </SectionCard>

      <SectionCard
        icon={Play}
        title="۴. پیش‌نمایش"
        description={`${fa(result.length)} ردیف از ${fa(rows?.length ?? 0)} ردیفِ منبع`}
      >
        <ResultTable rows={result} columns={config.columns} />
      </SectionCard>

      <SectionCard
        icon={Save}
        title="۵. ذخیره"
        description={`این تعریف روی منبعِ «${source?.label ?? '—'}» ذخیره می‌شود و برای همه‌ی کاربرانِ کسب‌وکار دیده خواهد شد.`}
      >
        <div className="cmp-form">
          <label className="cmp-form-wide">
            <span>نامِ گزارش</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} />
          </label>
          <label className="cmp-form-wide">
            <span>توضیح</span>
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
        </div>
        <div className="invoice-form-footer">
          <button
            type="button"
            className="btn-primary"
            disabled={busy || !name.trim() || config.columns.length === 0}
            onClick={() => void save()}
          >
            <Save size={13} /> ذخیره‌ی گزارش
          </button>
        </div>
        {config.columns.length === 0 && (
          <p className="bk-hint">برای ذخیره، دستِ‌کم یک ستون انتخاب کنید.</p>
        )}
      </SectionCard>
    </div>
  )
}

// ── گزارش‌های پویا ───────────────────────────────────────────────────────────

export function DynamicReportsPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey) => void
}) {
  const [reports, setReports] = useState<SavedReportRecord[] | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try {
      //: `saved_reports` را دو قابلیت به‌اشتراک می‌گذارند و ردیف‌هاشان مجموعه‌های
      //: جدا هستند: این‌جا گزارش‌های ساخته‌شده، و با پیشوندِ `view:` نماهای
      //: ذخیره‌شده‌ی گزارش‌های حسابداری. کلیدهای این صفحه از `MODULE_LISTS` می‌آیند
      //: و هرگز دونقطه ندارند، پس فیلترِ زیر دقیق است — بدونِ آن، نماها این‌جا
      //: «منبعِ ناموجود» دیده می‌شدند.
      const all = await fetchSavedReports(token)
      setReports(all.filter((r) => !r.source.startsWith('view:')))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const open = useMemo(
    () => (reports ?? []).find((r) => r.id === openId) ?? null,
    [reports, openId],
  )

  async function run(report: SavedReportRecord) {
    setOpenId(report.id)
    setRows(null)
    setMsg(null)
    const src = SOURCE_BY_KEY.get(report.source)
    if (!src) {
      setMsg({
        text: `منبعِ «${report.source}» دیگر در برنامه وجود ندارد؛ این گزارش را دوباره بسازید.`,
        kind: 'err',
      })
      setRows([])
      return
    }
    try {
      setRows(await src.load(token))
    } catch (err) {
      setRows([])
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function togglePin(report: SavedReportRecord) {
    setBusy(true)
    try {
      await updateSavedReport(token, report.id, {
        name: report.name,
        description: report.description,
        source: report.source,
        config: report.config,
        is_pinned: !report.is_pinned,
      })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(report: SavedReportRecord) {
    if (!window.confirm(`گزارشِ «${report.name}» حذف شود؟`)) return
    setBusy(true)
    try {
      await deleteSavedReport(token, report.id)
      if (openId === report.id) {
        setOpenId(null)
        setRows(null)
      }
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const config = open ? readConfig(open.config) : EMPTY_CONFIG
  const result = useMemo(
    () => (rows ? runReport(rows, config) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, open],
  )

  return (
    <div className="page panels">
      <PageHeader
        icon={LayoutList}
        title="گزارش‌های پویا"
        description="گزارش‌هایی که خودتان ساخته‌اید. هر بار که بازشان کنید روی داده‌ی امروز اجرا می‌شوند."
      />
      <Note msg={msg} />

      <SectionCard
        icon={LayoutList}
        title={reports ? `${fa(reports.length)} گزارشِ ذخیره‌شده` : 'در حال بارگذاری…'}
        actions={
          <button type="button" onClick={() => onNavigate('reportbuilder')}>
            <Wrench size={13} /> گزارشِ تازه
          </button>
        }
      >
        {reports == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : reports.length === 0 ? (
          <EmptyState
            icon={LayoutList}
            text="هنوز گزارشی نساخته‌اید — از «گزارش‌ساز» اولین گزارش را بسازید."
          />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>منبع</th>
                  <th>ستون‌ها</th>
                  <th>توضیح</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => {
                  const cfg = readConfig(r.config)
                  const src = SOURCE_BY_KEY.get(r.source)
                  return (
                    <tr key={r.id} className={openId === r.id ? 'row-active' : undefined}>
                      <td className="card-title" data-label="نام">
                        {r.is_pinned && <Pin size={12} className="cmp-star" />} {r.name}
                      </td>
                      <td data-label="منبع">{src?.label ?? <span className="muted">{r.source} (ناموجود)</span>}</td>
                      <td data-label="ستون‌ها">{fa(cfg.columns.length)}</td>
                      <td data-label="توضیح">{r.description || '—'}</td>
                      <td className="card-actions">
                        <div className="rb-row-actions">
                          <button type="button" className="btn-primary" onClick={() => void run(r)}>
                            <Play size={13} /> اجرا
                          </button>
                          <button type="button" disabled={busy} onClick={() => void togglePin(r)}>
                            <Pin size={13} /> {r.is_pinned ? 'برداشتن نشان' : 'نشان‌کردن'}
                          </button>
                          <button
                            type="button"
                            className="icon-btn-danger"
                            disabled={busy}
                            onClick={() => void remove(r)}
                          >
                            <Trash2 size={13} /> حذف
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {open && (
        <SectionCard
          icon={Play}
          title={open.name}
          description={
            rows == null
              ? 'در حال اجرا…'
              : `${fa(result.length)} ردیف از ${fa(rows.length)} ردیفِ منبع — ${new Date().toLocaleString('fa-IR')}`
          }
          actions={
            <button type="button" onClick={() => { setOpenId(null); setRows(null) }}>
              <X size={13} /> بستن
            </button>
          }
        >
          {rows == null ? (
            <p className="muted">در حال اجرا…</p>
          ) : (
            <ResultTable rows={result} columns={config.columns} />
          )}
        </SectionCard>
      )}
    </div>
  )
}
