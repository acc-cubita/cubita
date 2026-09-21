import { useMemo, useState } from 'react'
import {
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  PlayCircle,
  RefreshCcw,
  ShieldCheck,
  UserCheck,
  X,
} from 'lucide-react'

import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { CountBadge, FormField, FormGrid, FormStatus, RowAction } from '../components/form/FormKit'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { NumberInput } from '../components/NumberInput'
import { formatJalali } from '../lib/jalali'
import {
  approveAssuranceRequest,
  assignAssuranceAuditor,
  closeAssuranceEngagement,
  extendAssuranceAccess,
  fetchAssuranceRequests,
  rejectAssuranceRequest,
  runAssuranceSnapshot,
  type StaffAssuranceEngagement,
} from '../api'

const fa = (n: number | string | null | undefined) =>
  n === null || n === undefined ? '—' : Number(n).toLocaleString('fa-IR')

const STATUS_LABELS: Record<string, string> = {
  requested: 'در انتظارِ بررسی',
  approved: 'تأییدشده',
  active: 'در جریان',
  rejected: 'رد شده',
  closed: 'بسته‌شده',
}

const STATUS_TONE: Record<string, string> = {
  requested: 'tone-warning',
  approved: 'tone-info',
  active: 'tone-success',
  rejected: 'tone-danger',
  closed: 'tone-muted',
}

//: ترتیبِ کارت‌ها = ترتیبِ کارِ واقعیِ ستاد: اول چیزی که منتظرِ تصمیم است.
const BUCKETS: { key: string; title: string; statuses: string[]; hint: string }[] = [
  {
    key: 'inbox',
    title: 'در انتظارِ تصمیم',
    statuses: ['requested'],
    hint: 'درخواست‌هایی که هنوز تأیید یا رد نشده‌اند.',
  },
  {
    key: 'open',
    title: 'پرونده‌های باز',
    statuses: ['approved', 'active'],
    hint: 'حسابرس دسترسی دارد و بررسی‌ها اجرا می‌شوند.',
  },
  {
    key: 'done',
    title: 'بسته‌شده و ردشده',
    statuses: ['closed', 'rejected'],
    hint: 'تاریخچه — برای حسابرسیِ دوره‌ی تازه، مشتری درخواستِ جدید ثبت می‌کند.',
  },
]

type Msg = { text: string; kind: 'ok' | 'err' } | null

function daysLeft(iso: string | null): number | null {
  if (!iso) return null
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000)
}

/**
 * کارتابلِ حسابرسیِ ستاد — صفحه‌ی مستقل، نه تبی در «مدیریت اکانت‌ها».
 *
 * آن صفحه **حساب‌محور** است (یک کارت به‌ازای هر مشتری) و این **صف‌محور**: کارِ
 * روزمره‌اش «کدام درخواست منتظرِ من است؟» و کنارِ هم گذاشتنِ درخواست‌های چند
 * مشتری. نشاندنِ یک صف داخلِ فهرستی که به حساب مرتب شده، همان کار را سخت می‌کرد.
 */
export function AssuranceAdminPage({ token }: { token: string }) {
  const [rows, setRows] = useState<StaffAssuranceEngagement[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [dialog, setDialog] = useState<{ row: StaffAssuranceEngagement; mode: 'approve' | 'assign' } | null>(
    null,
  )

  async function load() {
    try {
      setRows(await fetchAssuranceRequests(token))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useMemo(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(true)
    setMsg(null)
    try {
      await fn()
      await load()
      setMsg({ text: `${label} انجام شد.`, kind: 'ok' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : `${label} ناموفق بود`, kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const all = rows ?? []
  const waiting = all.filter((r) => r.status === 'requested').length
  const open = all.filter((r) => r.status === 'approved' || r.status === 'active').length
  const expiring = all.filter((r) => {
    const left = daysLeft(r.access_expires_at)
    return (r.status === 'approved' || r.status === 'active') && left !== null && left <= 7
  }).length

  return (
    <div className="page panels">
      <PageHeader
        icon={ClipboardCheck}
        title="کارتابل حسابرسی"
        description="درخواست‌های حسابرسیِ همه‌ی کسب‌وکارها — تأیید، گمارشِ حسابرس، تمدید و بستنِ پرونده."
      />

      {error && <p className="ef-message ef-message--warn">{error}</p>}

      {/* داخلِ `section`، وگرنه پوسته‌ی «راهنما» ردیفِ KPIِ فرزندِ مستقیمِ صفحه را
          پنهان می‌کند — همان تله‌ای که قراردادِ صفحه‌ها هشدارش را می‌دهد. */}
      <section className="as-kpi">
        <div className="stat-grid">
          <StatCard
            icon={<Clock size={18} />}
            label="در انتظارِ تصمیم"
            value={fa(waiting)}
            tone={waiting > 0 ? 'warning' : 'default'}
          />
          <StatCard icon={<ShieldCheck size={18} />} label="پرونده‌های باز" value={fa(open)} />
          <StatCard
            icon={<CalendarClock size={18} />}
            label="دسترسیِ رو به انقضا (۷ روز)"
            value={fa(expiring)}
            tone={expiring > 0 ? 'warning' : 'default'}
          />
        </div>
      </section>

      {msg && (
        <p className={msg.kind === 'ok' ? 'ef-message' : 'ef-message ef-message--warn'}>{msg.text}</p>
      )}

      {BUCKETS.map((bucket) => {
        const items = all.filter((r) => bucket.statuses.includes(r.status))
        return (
          <SectionCard
            key={bucket.key}
            icon={ClipboardCheck}
            title={bucket.title}
            description={bucket.hint}
            badge={items.length > 0 ? <CountBadge accent>{fa(items.length)}</CountBadge> : undefined}
          >
            {items.length === 0 ? (
              <EmptyState icon={ClipboardCheck} text="چیزی در این دسته نیست." />
            ) : (
              <div className="table-scroll ef-table-wrap">
                <table className="cards-on-mobile ef-table">
                  <thead>
                    <tr>
                      <th>کسب‌وکار</th>
                      <th>دوره</th>
                      <th className="ef-col-min">وضعیت</th>
                      <th>حسابرس</th>
                      <th className="num ef-col-min">نمره</th>
                      <th className="ef-col-min">مهلت</th>
                      <th className="ef-col-min">عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => {
                      const left = daysLeft(row.access_expires_at)
                      return (
                        <tr key={row.id}>
                          <td className="card-title ef-cell-title" data-label="کسب‌وکار">
                            {row.tenant_name || '—'}
                            <span className="lp-item-parent">{row.owner_email}</span>
                          </td>
                          <td data-label="دوره">
                            {row.period_from && row.period_to
                              ? `${formatJalali(row.period_from)} تا ${formatJalali(row.period_to)}`
                              : '—'}
                          </td>
                          <td data-label="وضعیت">
                            <span className={`status-badge ${STATUS_TONE[row.status] ?? 'tone-info'}`}>
                              {STATUS_LABELS[row.status] ?? row.status}
                            </span>
                          </td>
                          <td data-label="حسابرس">{row.auditor_name || '—'}</td>
                          <td className="num" data-label="نمره">
                            {row.last_run_at ? fa(row.last_score) : 'هنوز بررسی نشده'}
                          </td>
                          <td data-label="مهلت">
                            {left === null ? '—' : left > 0 ? `${fa(left)} روز` : 'تمام شده'}
                          </td>
                          <td className="card-actions ef-col-min">
                            <div className="row-actions ef-row-actions">
                              {row.status === 'requested' && (
                                <>
                                  <RowAction
                                    icon={CheckCircle2}
                                    label="تأیید"
                                    disabled={busy}
                                    onClick={() => setDialog({ row, mode: 'approve' })}
                                  />
                                  <RowAction
                                    icon={X}
                                    label="رد"
                                    danger
                                    disabled={busy}
                                    onClick={() => {
                                      const reason = window.prompt('دلیلِ رد؟') ?? ''
                                      void act('رد درخواست', () =>
                                        rejectAssuranceRequest(token, row.id, reason),
                                      )
                                    }}
                                  />
                                </>
                              )}
                              {(row.status === 'approved' || row.status === 'active') && (
                                <>
                                  <RowAction
                                    icon={PlayCircle}
                                    label="اجرای بررسی"
                                    disabled={busy}
                                    onClick={() =>
                                      void act('اجرای بررسی', () => runAssuranceSnapshot(token, row.id))
                                    }
                                  />
                                  <RowAction
                                    icon={CalendarClock}
                                    label="تمدید ۳۰ روز"
                                    disabled={busy}
                                    onClick={() =>
                                      void act('تمدید', () => extendAssuranceAccess(token, row.id, 30))
                                    }
                                  />
                                  <RowAction
                                    icon={UserCheck}
                                    label="تعویضِ حسابرس"
                                    disabled={busy}
                                    onClick={() => setDialog({ row, mode: 'assign' })}
                                  />
                                  <RowAction
                                    icon={X}
                                    label="بستنِ پرونده"
                                    danger
                                    disabled={busy}
                                    onClick={() => {
                                      const note = window.prompt('یادداشتِ پایان؟') ?? ''
                                      void act('بستنِ پرونده', () =>
                                        closeAssuranceEngagement(token, row.id, note),
                                      )
                                    }}
                                  />
                                </>
                              )}
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
        )
      })}

      {dialog && (
        <AuditorDialog
          row={dialog.row}
          mode={dialog.mode}
          busy={busy}
          onCancel={() => setDialog(null)}
          onSubmit={(body) => {
            const label = dialog.mode === 'approve' ? 'تأیید' : 'گمارشِ حسابرس'
            void act(label, () =>
              dialog.mode === 'approve'
                ? approveAssuranceRequest(token, dialog.row.id, body)
                : assignAssuranceAuditor(token, dialog.row.id, {
                    auditor_email: body.auditor_email,
                    days: body.days,
                  }),
            ).then(() => setDialog(null))
          }}
        />
      )}
    </div>
  )
}

/** گفت‌وگوی تأیید/گمارش — ایمیلِ حسابرس، مهلت، و در تأیید، دوره‌ی حسابرسی. */
function AuditorDialog({
  row,
  mode,
  busy,
  onCancel,
  onSubmit,
}: {
  row: StaffAssuranceEngagement
  mode: 'approve' | 'assign'
  busy: boolean
  onCancel: () => void
  onSubmit: (body: {
    auditor_email: string
    days: number
    period_from?: string | null
    period_to?: string | null
  }) => void
}) {
  const [email, setEmail] = useState(row.auditor_email)
  const [days, setDays] = useState('90')
  const [from, setFrom] = useState(row.period_from ?? '')
  const [to, setTo] = useState(row.period_to ?? '')

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span>
            <UserCheck size={16} /> {mode === 'approve' ? 'تأییدِ درخواست' : 'تعویضِ حسابرس'}
          </span>
          <button type="button" onClick={onCancel} aria-label="بستن">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">
          <p className="ef-message">
            {row.tenant_name} — حسابرس باید کاربرِ موجودِ کوبیتا باشد و نباید از قبل عضوِ این
            کسب‌وکار باشد.
          </p>
          <FormGrid cols={2}>
            <FormField label="ایمیلِ حسابرس" required span="full">
              {(id) => (
                <input
                  id={id}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  dir="ltr"
                  type="email"
                />
              )}
            </FormField>
            <FormField label="مهلتِ دسترسی" tip="از همین حالا شمرده می‌شود.">
              {(id) => <NumberInput id={id} value={days} onChange={setDays} group={false} />}
            </FormField>
            {mode === 'approve' && (
              <>
                <FormField label="آغازِ دوره">
                  {(id) => <JalaliDatePicker id={id} value={from} onChange={setFrom} />}
                </FormField>
                <FormField label="پایانِ دوره">
                  {(id) => <JalaliDatePicker id={id} value={to} onChange={setTo} />}
                </FormField>
              </>
            )}
          </FormGrid>
        </div>
        <div className="modal-foot">
          <FormStatus msg={null} />
          <button type="button" className="ef-btn-secondary" onClick={onCancel} disabled={busy}>
            <X size={15} /> انصراف
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={busy || !email.trim()}
            onClick={() =>
              onSubmit({
                auditor_email: email.trim(),
                days: Number(days) || 90,
                period_from: from || null,
                period_to: to || null,
              })
            }
          >
            {mode === 'approve' ? <CheckCircle2 size={16} /> : <RefreshCcw size={16} />}{' '}
            {mode === 'approve' ? 'تأیید و بازکردنِ دسترسی' : 'گمارش'}
          </button>
        </div>
      </div>
    </div>
  )
}
