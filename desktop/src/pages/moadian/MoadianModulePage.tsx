import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Download,
  FileCheck2,
  FileSpreadsheet,
  Landmark,
  ListChecks,
  Loader2,
  PlugZap,
  RefreshCw,
  Save,
  Send,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import {
  deleteMoadianUnitMap,
  fetchMoadianUnitMaps,
  fetchMoadianUnmappedUnits,
  saveMoadianUnitMap,
  type MeResponse,
  type MoadianUnitMap,
} from '../../api'
import type { PageKey } from '../../lib/navModel'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { StatCard } from '../../components/StatCard'
import { EmptyState } from '../../components/EmptyState'
import { FeatureUpsell } from '../../components/FeatureUpsell'
import { Pager, usePagination } from '../../components/Pager'
import { Tabs } from '../../components/Tabs'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, toFaDigits } from '../../lib/jalali'
import {
  useMoadianPanel,
  MOADIAN_STATUS_LABEL,
  MOADIAN_STATUS_TONE,
  type MoadianPanelState,
} from '../../lib/moadianPanel'
import { FormField } from '../../components/form/FormKit'

/**
 * ماژولِ «سامانه مؤدیان» — چهار بخش به‌ترتیبِ کارِ واقعی: وضعیت، ارسال، تاریخچه، تنظیمات.
 *
 * **چرا چهار بخش و نه یک صفحه‌ی دوستونی:** پیش‌تر فرمِ اعتبارنامه و کادرِ ارسال کنارِ هم
 * در دو ستون می‌نشستند. فرم هفت فیلد دارد که دوتایشان PEMِ چندخطی‌اند و کادرِ ارسال فقط
 * یک انتخابگر — نتیجه‌اش ستونی فشرده با textareaهای غیرقابلِ استفاده کنارِ ستونی تقریباً
 * خالی بود. تنظیمات کاری است که یک‌بار انجام می‌شود و ارسال کاری است که هر روز؛ این دو
 * نباید هم‌زمان روی صفحه جا بگیرند.
 *
 * ارقامِ فارسی و تاریخِ شمسی همه‌جا؛ ولی PEM و آدرس و شناسه‌ی حافظه عمداً `dir="ltr"`اند —
 * متنِ لاتین در جریانِ راست‌به‌چپ به‌هم می‌ریزد و کاربر کدِ درست را غلط می‌بیند.
 */

const fa = (v: string | number | null | undefined) => Number(v ?? 0).toLocaleString('fa-IR')
const faNum = (n: number | null) => (n === null ? '—' : n.toLocaleString('fa-IR', { useGrouping: false }))

/** جمله‌ی اولِ پیامِ سرور برای سلولِ جدول؛ ادامه‌اش راهنماست و در tooltip می‌ماند. */
const shortReason = (text: string) => text.split('؛')[0]

/** باکسِ «خرید پلن» به‌جای صفحه، وقتی این امکان روی پلنِ حساب قفل است.
 *
 *  پیش از هر درخواستی سنجیده می‌شود: بدونِ آن، صفحه چند فراخوانیِ ۴۰۲ می‌زد و
 *  به‌جای پیشنهادِ ارتقا چند پیامِ خطا نشان می‌داد. */
function LockedPage({ title }: { title: string }) {
  return (
    <div className="page panels">
      <PageHeader
        icon={FileSpreadsheet}
        title={title}
        description="ارسالِ صورتحساب الکترونیکی به کارپوشه‌ی سازمان امور مالیاتی."
      />
      <section>
        <FeatureUpsell feature="moadian" />
      </section>
    </div>
  )
}

const isLocked = (me: MeResponse) => (me.locked_features ?? []).includes('moadian')

export function MoadianModulePage({
  token,
  me,
  onNavigate,
}: {
  token: string
  me: MeResponse
  onNavigate: (page: PageKey) => void
}) {
  if (isLocked(me)) return <LockedPage title="سامانه مؤدیان" />
  return <MoadianModule token={token} onNavigate={onNavigate} />
}

/** «تاریخچه ارسال‌ها» — صفحه‌ی فهرستِ ماژول، از کارتِ «فهرست» باز می‌شود.
 *
 *  تبِ درونِ ماژول نیست چون دفترِ ارسال‌ها یک *داده‌ی ذخیره‌شده* است نه یک عملیات؛
 *  همان تفکیکی که در بقیه‌ی ماژول‌ها بینِ کارتِ «عملیات» و کارتِ «فهرست» برقرار است. */
export function MoadianHistoryPage({ token, me }: { token: string; me: MeResponse }) {
  if (isLocked(me)) return <LockedPage title="تاریخچه ارسال‌ها" />
  return <MoadianHistory token={token} />
}

function MoadianHistory({ token }: { token: string }) {
  const m = useMoadianPanel({ token })
  return (
    <div className="page panels">
      <PageHeader
        icon={FileCheck2}
        title="تاریخچه ارسال‌ها"
        description="هر صورتحسابی که به سامانه رفته، با شناسه‌ی مالیاتی، سریال و وضعیتِ کارپوشه."
      />
      <HistoryTab m={m} />
    </div>
  )
}

function MoadianModule({ token, onNavigate }: { token: string; onNavigate: (page: PageKey) => void }) {
  const m = useMoadianPanel({ token })

  return (
    <div className="page panels">
      <PageHeader
        icon={FileSpreadsheet}
        title="سامانه مؤدیان"
        description="ارسالِ صورتحساب الکترونیکی به کارپوشه‌ی سازمان امور مالیاتی و پیگیریِ وضعیتِ آن‌ها."
      />
      <Tabs
        syncPage="moadian"
        tabs={[
          {
            key: 'status',
            label: 'وضعیت و آمادگی',
            icon: ListChecks,
            content: <StatusTab m={m} onNavigate={onNavigate} />,
          },
          { key: 'send', label: 'ارسال صورتحساب', icon: Send, content: <SendTab m={m} /> },
          { key: 'settings', label: 'تنظیمات و اعتبارنامه', icon: Landmark, content: <SettingsTab m={m} token={token} /> },
        ]}
      />
    </div>
  )
}

// ── نوارِ محیط ────────────────────────────────────────────────────────────────

/** محیطِ مؤثر. «واقعی» عمداً پررنگ است: تفاوتش با سندباکس یک صورتحسابِ قانونیِ
 *  برگشت‌ناپذیر است، نه یک تنظیمِ ساده. */
function EnvironmentBar({ m }: { m: MoadianPanelState }) {
  const s = m.settings
  if (!s) return null
  const live = !s.is_sandbox
  return (
    <div className={`mdn-env ${live ? 'is-live' : ''}`}>
      {live ? <AlertTriangle size={16} /> : <ShieldCheck size={16} />}
      <div>
        <strong>{live ? 'محیط واقعی' : 'محیط سندباکس (آزمایشی)'}</strong>
        <span>
          {live
            ? 'صورتحساب‌ها به سامانه‌ی رسمیِ سازمان امور مالیاتی می‌روند و برگشت‌پذیر نیستند.'
            : 'ارسال‌ها آزمایشی‌اند و اثرِ قانونی ندارند.'}
        </span>
      </div>
      <span className="mdn-env-serial">آخرین سریال: {fa(s.last_serial)}</span>
      <code dir="ltr">{s.effective_base_url}</code>
    </div>
  )
}

// ── وضعیت و آمادگی ──────────────────────────────────────────────────────────

function StatusTab({ m, onNavigate }: { m: MoadianPanelState; onNavigate: (page: PageKey) => void }) {
  const r = m.readiness
  const s = m.settings

  if (m.loading) {
    return (
      <p className="hint mdn-loading">
        <Loader2 size={15} className="spin" /> در حال بارگذاری…
      </p>
    )
  }

  return (
    <>
      <EnvironmentBar m={m} />

      <div className="stat-grid">
        <StatCard
          icon={s?.is_active ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
          label="وضعیت ارسال"
          value={s?.is_active ? 'فعال' : 'غیرفعال'}
          tone={s?.is_active ? 'success' : 'warning'}
          hint={s?.is_sandbox ? 'محیط سندباکس' : 'محیط واقعی'}
        />
        <StatCard
          icon={<Send size={18} />}
          label="در صفِ ارسال"
          value={fa(r?.pending_count ?? 0)}
          tone={(r?.blocked_count ?? 0) > 0 ? 'warning' : 'default'}
          hint={(r?.blocked_count ?? 0) > 0 ? `${fa(r?.blocked_count ?? 0)} فاکتور مسدود` : 'همه قابلِ ارسال'}
        />
        <StatCard
          icon={<FileCheck2 size={18} />}
          label="ارسال موفق"
          value={fa(m.sentCount)}
          tone="success"
          hint="ارسال‌شده یا تأییدشده"
        />
        <StatCard
          icon={<ShieldAlert size={18} />}
          label="ردشده / خطا"
          value={fa(m.failedCount)}
          tone={m.failedCount ? 'danger' : 'default'}
          hint="نیازمندِ بررسی"
        />
      </div>

      <SectionCard
        icon={ListChecks}
        title="آمادگیِ ارسال"
        description="همان شرط‌هایی که سرور پیش از مصرفِ سریال می‌سنجد — نه یک توصیه‌ی جداگانه."
        actions={
          <>
            <button type="button" onClick={() => onNavigate('moadianhistory')}>
              <FileCheck2 size={13} /> تاریخچه ارسال‌ها
            </button>
            <button type="button" onClick={() => void m.refresh()}>
              <RefreshCw size={13} /> بازخوانی
            </button>
          </>
        }
      >
        <div className={`mdn-verdict ${r?.ready ? 'is-ok' : 'is-todo'}`}>
          {r?.ready ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>
            {r?.ready
              ? 'همه‌چیز آماده است — می‌توانید صورتحساب بفرستید.'
              : `${fa((r?.checks ?? []).filter((c) => !c.ok).length)} شرط باقی مانده است.`}
          </span>
        </div>

        <ul className="mdn-checks">
          {(r?.checks ?? []).map((c) => (
            <li key={c.key} className={c.ok ? 'is-ok' : 'is-todo'}>
              {c.ok ? <CheckCircle2 size={16} /> : <Circle size={16} />}
              <div>
                <strong>{c.title}</strong>
                <p>{toFaDigits(c.detail)}</p>
              </div>
            </li>
          ))}
        </ul>

        <div className="mdn-actions">
          <button type="button" onClick={() => void m.testConnection()} disabled={m.testing}>
            <PlugZap size={14} /> {m.testing ? 'در حالِ آزمایش…' : 'تستِ اتصال'}
          </button>
        </div>
        {m.testMsg && (
          <p className={`hint mdn-note mdn-note--${m.testMsg.ok ? 'ok' : 'err'}`}>
            {m.testMsg.ok ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
            {m.testMsg.text}
          </p>
        )}
        {m.msg && <p className="hint">{m.msg}</p>}
      </SectionCard>
    </>
  )
}

// ── ارسال صورتحساب ──────────────────────────────────────────────────────────

function SendTab({ m }: { m: MoadianPanelState }) {
  const pg = usePagination(m.pending, 12)
  const selectedCount = m.sendable.filter((r) => m.selected.has(r.id)).length
  const blockedCount = m.pending.length - m.sendable.length
  const ready = m.readiness?.ready ?? false

  return (
    <SectionCard
      icon={Send}
      title="صفِ ارسال"
      description="فاکتورهای فروشی که هنوز ارسالِ موفق ندارند. هر فاکتور فقط یک‌بار ارسال می‌شود."
      actions={
        <button type="button" onClick={() => void m.refresh()}>
          <RefreshCw size={13} /> بازخوانی
        </button>
      }
    >
      {!ready && (
        <p className="hint mdn-note mdn-note--warn">
          <AlertTriangle size={14} />
          تا وقتی شرط‌های بخشِ «وضعیت و آمادگی» کامل نشده، ارسال انجام نمی‌شود.
        </p>
      )}

      {m.pending.length === 0 ? (
        <EmptyState icon={FileCheck2} text="فاکتورِ ارسال‌نشده‌ای نیست." />
      ) : (
        <>
          <div className="mdn-toolbar">
            <span>
              {fa(m.pending.length)} فاکتور در صف
              {blockedCount > 0 && <> — {fa(blockedCount)} مسدود</>}
            </span>
            <div className="mdn-toolbar-actions">
              <button type="button" onClick={m.toggleAll} disabled={m.sendable.length === 0}>
                {selectedCount >= m.sendable.length && m.sendable.length > 0 ? 'لغوِ انتخاب' : 'انتخابِ همه‌ی قابلِ ارسال'}
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => void m.submitSelected()}
                disabled={m.sending || selectedCount === 0 || !ready}
              >
                <Send size={14} />{' '}
                {m.sending
                  ? 'در حالِ ارسال…'
                  : selectedCount === 0
                    ? 'ارسالِ گروهی'
                    : `ارسالِ ${fa(selectedCount)} فاکتور`}
              </button>
            </div>
          </div>

          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th className="mdn-check-col"></th>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>خریدار</th>
                  <th>خالص</th>
                  <th>مالیات</th>
                  <th>قابل پرداخت</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((row) => (
                  <tr key={row.id} className={row.blocked_reason ? 'mdn-row-blocked' : ''}>
                    <td className="mdn-check-col" data-label="انتخاب">
                      <input
                        type="checkbox"
                        checked={m.selected.has(row.id)}
                        disabled={Boolean(row.blocked_reason)}
                        onChange={() => m.toggle(row.id)}
                        aria-label={`انتخاب فاکتور ${row.number ?? ''}`}
                      />
                    </td>
                    <td className="card-title" data-label="شماره">{faNum(row.number)}</td>
                    <td data-label="تاریخ">{formatJalali(row.invoice_date)}</td>
                    <td className="card-wide" data-label="خریدار">
                      <span className="mdn-buyer">
                        <span>{row.buyer_name}</span>
                        <span className="mdn-buyer-kind">{row.buyer_is_legal ? 'حقوقی' : 'حقیقی'}</span>
                      </span>
                    </td>
                    <td className="money-cell" data-label="خالص">{fa(row.net_amount)}</td>
                    <td className="money-cell" data-label="مالیات">{fa(row.tax_amount)}</td>
                    <td className="money-cell" data-label="قابل پرداخت">{fa(row.payable)}</td>
                    <td className="card-wide" data-label="وضعیت">
                      {row.blocked_reason ? (
                        <span className="mdn-blocked" title={row.blocked_reason}>
                          <XCircle size={14} /> {shortReason(row.blocked_reason)}
                        </span>
                      ) : (
                        <span className="status-badge tone-success">آماده</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </>
      )}

      {m.sendMsg && <p className="hint">{m.sendMsg}</p>}

      {m.batchResults && m.batchResults.length > 0 && (
        <div className="mdn-results">
          <h4>نتیجه‌ی ارسال</h4>
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>وضعیت</th>
                  <th>شناسه مالیاتی</th>
                  <th>شماره مرجع</th>
                  <th>توضیح</th>
                </tr>
              </thead>
              <tbody>
                {m.batchResults.map((r) => (
                  <tr key={r.invoice_id}>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${MOADIAN_STATUS_TONE[r.status] ?? ''}`}>
                        {MOADIAN_STATUS_LABEL[r.status] ?? r.status}
                      </span>
                    </td>
                    <td className="card-wide" data-label="شناسه مالیاتی"><code dir="ltr">{r.tax_id || '—'}</code></td>
                    <td className="card-wide" data-label="شماره مرجع">
                      {r.reference_number ? <span className="mdn-ref" dir="ltr">{r.reference_number}</span> : '—'}
                    </td>
                    <td className="card-wide" data-label="توضیح">{r.error_message || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SectionCard>
  )
}

// ── تاریخچه ─────────────────────────────────────────────────────────────────

const HISTORY_FILTERS: { key: string; label: string }[] = [
  { key: 'all', label: 'همه' },
  { key: 'ok', label: 'موفق' },
  { key: 'bad', label: 'ردشده و خطا' },
  { key: 'pending', label: 'در انتظار' },
]

function HistoryTab({ m }: { m: MoadianPanelState }) {
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    const term = q.trim()
    return m.submissions.filter((s) => {
      if (filter === 'ok' && !['sent', 'confirmed'].includes(s.status)) return false
      if (filter === 'bad' && !['rejected', 'failed'].includes(s.status)) return false
      if (filter === 'pending' && s.status !== 'pending') return false
      if (!term) return true
      return (
        s.tax_id.includes(term) ||
        s.reference_number.includes(term) ||
        s.buyer_name.includes(term) ||
        String(s.invoice_number ?? '').includes(term)
      )
    })
  }, [m.submissions, filter, q])

  const pg = usePagination(rows, 10, `${filter}|${q}`)

  function exportCsv() {
    downloadCsv(
      'تاریخچه-مؤدیان',
      ['تاریخ فاکتور', 'شماره فاکتور', 'خریدار', 'شناسه مالیاتی', 'سریال', 'وضعیت', 'شماره مرجع', 'توضیح'],
      rows.map((s) => [
        formatJalali(s.invoice_date),
        s.invoice_number ?? '',
        s.buyer_name,
        s.tax_id,
        s.serial,
        MOADIAN_STATUS_LABEL[s.status] ?? s.status,
        s.reference_number,
        s.error_message,
      ]),
    )
  }

  return (
    <SectionCard
      icon={FileCheck2}
      title="تاریخچه ارسال‌ها"
      description={`${fa(m.submissions.length)} ارسال — هر ردیف یک صورتحسابِ قانونی است.`}
      actions={
        <button type="button" onClick={exportCsv} disabled={rows.length === 0}>
          <Download size={13} /> خروجی CSV
        </button>
      }
    >
      {m.submissions.length === 0 ? (
        <EmptyState icon={FileCheck2} text="هنوز صورتحسابی ارسال نشده." />
      ) : (
        <>
          <div className="mdn-filters">
            <div className="mdn-chips">
              {HISTORY_FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  className={`mdn-chip ${filter === f.key ? 'is-active' : ''}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جست‌وجو: شناسه مالیاتی، مرجع، خریدار، شماره فاکتور"
            />
          </div>

          {rows.length === 0 ? (
            <EmptyState icon={FileCheck2} text="با این فیلتر چیزی پیدا نشد." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ فاکتور</th>
                    <th>فاکتور</th>
                    <th>خریدار</th>
                    <th>شناسه مالیاتی</th>
                    <th>سریال</th>
                    <th>وضعیت</th>
                    <th>شماره مرجع</th>
                    <th>توضیح</th>
                    <th>استعلام</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((s) => (
                    <tr key={s.id}>
                      <td className="card-title" data-label="تاریخ فاکتور">{formatJalali(s.invoice_date)}</td>
                      <td data-label="فاکتور">{faNum(s.invoice_number)}</td>
                      <td className="card-wide" data-label="خریدار">{s.buyer_name || '—'}</td>
                      <td className="card-wide" data-label="شناسه مالیاتی"><code dir="ltr">{s.tax_id}</code></td>
                      <td data-label="سریال">{fa(s.serial)}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${MOADIAN_STATUS_TONE[s.status] ?? ''}`}>
                          {MOADIAN_STATUS_LABEL[s.status] ?? s.status}
                        </span>
                      </td>
                      <td className="card-wide" data-label="شماره مرجع">
                        {s.reference_number ? <span className="mdn-ref" dir="ltr">{s.reference_number}</span> : '—'}
                      </td>
                      <td className="card-wide" data-label="توضیح">{s.error_message || '—'}</td>
                      <td className="card-actions" data-label="استعلام">
                        {s.reference_number ? (
                          <button type="button" className="btn-ghost btn-sm" onClick={() => void m.inquire(s.id)}>
                            استعلام وضعیت
                          </button>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          )}
        </>
      )}
      {m.sendMsg && <p className="hint">{m.sendMsg}</p>}
    </SectionCard>
  )
}

// ── تنظیمات و اعتبارنامه ────────────────────────────────────────────────────

function SettingsTab({ m, token }: { m: MoadianPanelState; token: string }) {
  const { form, setForm, settings } = m

  return (
    <>
      <EnvironmentBar m={m} />

      <SectionCard
        icon={Landmark}
        title="اعتبارنامه‌ی کارپوشه"
        description="این اطلاعات از کارپوشه‌ی سازمان امور مالیاتی گرفته می‌شود. کلید خصوصی فقط یک‌بار وارد می‌شود و هرگز از سرور برنمی‌گردد."
      >
        <form
          className="mdn-form"
          onSubmit={(e) => {
            e.preventDefault()
            void m.save()
          }}
        >
          <div className="mdn-grid">
            <FormField label="شناسه یکتای حافظه مالیاتی" tip="دقیقاً ۶ کاراکتر، از کارپوشه.">
              {(id) => (
                <input
                  id={id}
                  dir="ltr"
                  value={form.memory_id}
                  onChange={(e) => setForm({ ...form, memory_id: e.target.value })}
                  maxLength={6}
                  placeholder="A1B2C3"
                />
              )}
            </FormField>
            <label>
              شناسه ملی / کد ملی مؤدی
              <input dir="ltr" value={form.national_id} onChange={(e) => setForm({ ...form, national_id: e.target.value })} />
            </label>
            <label>
              شماره اقتصادی
              <input dir="ltr" value={form.economic_code} onChange={(e) => setForm({ ...form, economic_code: e.target.value })} />
            </label>
            <FormField
              label="شناسه‌ی پیش‌فرضِ کالا/خدمت"
              tip="۱۳ رقم، اختیاری. هر کالا می‌تواند کدِ خودش را داشته باشد؛ این کد فقط جایگزینِ کالاهای بدونِ کد است."
            >
              {(id) => (
                <input
                  id={id}
                  dir="ltr"
                  value={form.default_stuff_id}
                  onChange={(e) => setForm({ ...form, default_stuff_id: e.target.value })}
                  inputMode="numeric"
                />
              )}
            </FormField>
          </div>

          <FormField
            label="کلید خصوصی (PEM)"
            span="full"
            message={settings?.has_private_key ? 'کلید ثبت شده است — خالی بگذارید تا دست‌نخورده بماند، یا کلیدِ تازه را بچسبانید.' : null}
          >
            {(id) => (
              <textarea
                id={id}
                dir="ltr"
                rows={6}
                className="mdn-pem"
                value={form.private_key_pem}
                onChange={(e) => setForm({ ...form, private_key_pem: e.target.value })}
                placeholder="-----BEGIN PRIVATE KEY-----"
              />
            )}
          </FormField>

          <FormField
            label="گواهیِ امضا — Certificate (PEM)"
            span="full"
            message={settings?.has_certificate ? 'گواهی ثبت شده است — خالی بگذارید تا دست‌نخورده بماند، یا گواهیِ تازه را بچسبانید.' : null}
          >
            {(id) => (
              <textarea
                id={id}
                dir="ltr"
                rows={6}
                className="mdn-pem"
                value={form.certificate_pem}
                onChange={(e) => setForm({ ...form, certificate_pem: e.target.value })}
                placeholder="-----BEGIN CERTIFICATE-----"
              />
            )}
          </FormField>

          <FormField label="آدرس پایه (اختیاری)" span="full" tip="خالی یعنی آدرسِ پیش‌فرضِ همان محیط.">
            {(id) => (
              <input
                id={id}
                dir="ltr"
                value={form.base_url_override}
                onChange={(e) => setForm({ ...form, base_url_override: e.target.value })}
                placeholder={settings?.effective_base_url ?? ''}
              />
            )}
          </FormField>

          <div className="mdn-toggles">
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={form.is_sandbox}
                onChange={(e) => setForm({ ...form, is_sandbox: e.target.checked })}
              />
              محیط سندباکس (آزمایشی)
            </label>
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              ارسال فعال باشد
            </label>
          </div>

          {!form.is_sandbox && (
            <p className="hint mdn-note mdn-note--warn">
              <AlertTriangle size={14} />
              محیط واقعی انتخاب شده — صورتحساب‌ها به سامانه‌ی رسمی سازمان امور مالیاتی ارسال می‌شوند.
            </p>
          )}

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={m.saving}>
              <Save size={14} /> ذخیره تنظیمات
            </button>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => void m.testConnection()}
              disabled={m.testing}
              title="فقط احراز هویت با سامانه را می‌سنجد — بدونِ مصرفِ سریال یا ارسالِ فاکتور"
            >
              <PlugZap size={14} /> {m.testing ? 'در حالِ آزمایش…' : 'تستِ اتصال'}
            </button>
          </div>

          {m.testMsg && (
            <p className={`hint mdn-note mdn-note--${m.testMsg.ok ? 'ok' : 'err'}`}>
              {m.testMsg.ok ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              {m.testMsg.text}
            </p>
          )}
          {settings && (!settings.has_private_key || !settings.has_certificate) && (
            <p className="hint">
              برای ارسال، هم «کلید خصوصی» و هم «گواهیِ امضا» لازم است
              {settings.has_private_key ? '' : ' — کلید هنوز ثبت نشده'}
              {settings.has_certificate ? '' : ' — گواهی هنوز ثبت نشده'}.
            </p>
          )}
          {m.msg && <p className="hint">{m.msg}</p>}
        </form>
      </SectionCard>

      <UnitMapCard token={token} />
    </>
  )
}

/**
 * نگاشتِ واحدِ سنجش به کدِ رسمیِ سامانه.
 *
 * تا پیش از این، کدِ واحدِ **هر** ردیفی ثابت «۱۶۴» (عدد) ارسال می‌شد — فروشِ ۵۰
 * کیلوگرم به‌صورتِ ۵۰ عدد به سازمان اظهار می‌شد. کدها عمداً از پیش پُر نشده‌اند:
 * جدولِ رسمی ده‌ها ردیف دارد و کدِ اشتباه از نفرستادن بدتر است.
 */
function UnitMapCard({ token }: { token: string }) {
  const [rows, setRows] = useState<MoadianUnitMap[]>([])
  const [missing, setMissing] = useState<string[]>([])
  const [unit, setUnit] = useState('')
  const [code, setCode] = useState('')
  const [msg, setMsg] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const [maps, unmapped] = await Promise.all([
      fetchMoadianUnitMaps(token),
      fetchMoadianUnmappedUnits(token),
    ])
    setRows(maps)
    setMissing(unmapped)
  }, [token])

  useEffect(() => {
    void refresh().catch(() => undefined)
  }, [refresh])

  async function save(u: string, c: string) {
    setMsg(null)
    try {
      await saveMoadianUnitMap(token, u, c)
      setUnit('')
      setCode('')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard
      icon={Landmark}
      title="نگاشتِ واحدهای سنجش"
      description="کدِ واحد را از جدولِ رسمیِ سامانه وارد کنید. «عدد» از پیش کدِ ۱۶۴ دارد؛ بقیه تا نگاشت نشوند، فاکتورشان ارسال نمی‌شود."
    >
      {missing.length > 0 && (
        <p className="hint">
          واحدهای بدونِ کد: {missing.join('، ')}
        </p>
      )}

      <div className="mdn-form">
        <label className="form-field">
          واحد
          <input
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            list="mdn-unit-suggestions"
            placeholder="کیلوگرم"
          />
          <datalist id="mdn-unit-suggestions">
            {missing.map((u) => (
              <option key={u} value={u} />
            ))}
          </datalist>
        </label>
        <FormField label="کدِ سامانه" tip="از جدولِ رسمیِ واحدهای سامانه مؤدیان.">
          {(id) => <input id={id} value={code} onChange={(e) => setCode(e.target.value)} dir="ltr" />}
        </FormField>
        <button
          type="button"
          className="btn-primary"
          disabled={!unit.trim() || !code.trim()}
          onClick={() => void save(unit, code)}
        >
          ثبتِ نگاشت
        </button>
      </div>

      {rows.length > 0 && (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>واحد</th>
                <th>کد</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="card-title" data-label="واحد">{r.unit}</td>
                  <td data-label="کد" dir="ltr">{r.code}</td>
                  <td className="card-actions">
                    <button
                      type="button"
                      onClick={() => {
                        void deleteMoadianUnitMap(token, r.id).then(refresh).catch(() => undefined)
                      }}
                    >
                      حذف
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {msg && <p className="hint">{msg}</p>}
    </SectionCard>
  )
}
