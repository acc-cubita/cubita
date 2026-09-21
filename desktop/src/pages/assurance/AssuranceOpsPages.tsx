import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  ClipboardCheck,
  FileSignature,
  Gauge,
  RefreshCcw,
  ShieldCheck,
  UserCheck,
} from 'lucide-react'

import { SectionCard } from '../../components/SectionCard'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import {
  ActionBar,
  FormField,
  FormGrid,
  FormStatus,
  InfoTip,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { formatJalali } from '../../lib/jalali'
import {
  fetchAssuranceEngagement,
  fetchLatestAssuranceRun,
  refreshAssuranceRun,
  submitAssuranceRequest,
  type AssuranceEngagementRecord,
  type AssuranceRunRecord,
  type MeResponse,
} from '../../api'
import { AsyncBlock, Metric, OpsPage, faInt, useAsync, type Msg } from '../accounting/kit'
import type { PageKey } from '../../lib/navModel'

const fa = (v: number | string | null | undefined) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString('fa-IR')

const STATUS_LABELS: Record<string, string> = {
  requested: 'در انتظارِ بررسی',
  approved: 'تأییدشده',
  active: 'در جریان',
  rejected: 'رد شده',
  closed: 'بسته‌شده',
}

const GRADE_LABELS: Record<string, string> = {
  healthy: 'سالم',
  warning: 'نیازمندِ رسیدگی',
  critical: 'بحرانی',
}

const GRADE_TONE: Record<string, string> = {
  healthy: 'tone-success',
  warning: 'tone-warning',
  critical: 'tone-danger',
}

/** روزهای مانده تا پایانِ دسترسی — عددی که حسابرس و مشتری هر دو می‌پرسند. */
function daysLeft(iso: string | null): number | null {
  if (!iso) return null
  const ms = new Date(iso).getTime() - Date.now()
  return Math.ceil(ms / 86_400_000)
}

/**
 * «درخواست حسابرسی» — تنها صفحه‌ی این ماژول که پیش از تأییدِ ما هم دیده می‌شود.
 *
 * چهار حالت دارد و هر کدام چیزِ متفاوتی نشان می‌دهد؛ فرم فقط در حالتِ اول و در
 * حالتِ «رد شده» ظاهر می‌شود، چون در بقیه‌ی حالت‌ها کاری برای انجام‌دادن نیست و
 * فرمِ بی‌اثر فقط کاربر را دوباره می‌فرستد سراغِ دکمه‌ای که چیزی عوض نمی‌کند.
 */
export function AssuranceRequestPage({ token, me }: { token: string; me: MeResponse }) {
  const engagement = useAsync<AssuranceEngagementRecord | null>(
    () => fetchAssuranceEngagement(token),
    [token],
  )
  const [periodFrom, setPeriodFrom] = useState('')
  const [periodTo, setPeriodTo] = useState('')
  const [phone, setPhone] = useState(me.phone ?? '')
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  const record = engagement.data
  const showForm = record === null || record?.status === 'rejected'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const missing = firstMissing([
      [periodFrom, 'asr-from', 'آغازِ دوره‌ی موردِ حسابرسی را انتخاب کنید.'],
      [periodTo, 'asr-to', 'پایانِ دوره‌ی موردِ حسابرسی را انتخاب کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      await submitAssuranceRequest(token, {
        period_from: periodFrom,
        period_to: periodTo,
        contact_phone: phone,
        note,
      })
      engagement.reload()
      setMsg({ text: 'درخواستِ شما ثبت شد؛ کارشناسِ ما تماس می‌گیرد.', kind: 'ok' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'ثبتِ درخواست ناموفق بود', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      canvas
      icon={FileSignature}
      title="درخواست حسابرسی"
      description="حسابرسیِ دفاتر توسطِ تیمِ حسابرسانِ کوبیتا — از این‌جا درخواست بدهید."
    >
      <AsyncBlock loading={engagement.loading} error={engagement.error}>
        {record !== null && <StatusPanel record={record} />}

        {showForm && (
          <form noValidate onSubmit={submit}>
            <SectionCard
              icon={FileSignature}
              title={record === null ? 'درخواستِ تازه' : 'درخواستِ دوباره'}
              description="دوره‌ای را که می‌خواهید حسابرسی شود مشخص کنید."
            >
              <FormGrid cols={2}>
                <FormField id="asr-from" label="آغازِ دوره" required>
                  {(id) => <JalaliDatePicker id={id} value={periodFrom} onChange={setPeriodFrom} />}
                </FormField>
                <FormField id="asr-to" label="پایانِ دوره" required>
                  {(id) => <JalaliDatePicker id={id} value={periodTo} onChange={setPeriodTo} />}
                </FormField>
                <FormField
                  label="تلفنِ تماس"
                  optional
                  tip="کارشناسِ ما برای هماهنگیِ شروعِ کار با همین شماره تماس می‌گیرد."
                >
                  {(id) => (
                    <input
                      id={id}
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      dir="ltr"
                      inputMode="tel"
                    />
                  )}
                </FormField>
                <FormField label="توضیح" optional span="full">
                  {(id) => (
                    <input
                      id={id}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="اگر نکته‌ی خاصی هست بنویسید"
                    />
                  )}
                </FormField>
              </FormGrid>
            </SectionCard>

            <ScopeCard />

            <ActionBar status={<FormStatus msg={msg} />}>
              <button type="submit" className="btn-primary" disabled={busy}>
                <CheckCircle2 size={16} /> {busy ? 'در حال ثبت…' : 'ثبتِ درخواست'}
              </button>
            </ActionBar>
          </form>
        )}
      </AsyncBlock>
    </OpsPage>
  )
}

/** وضعیتِ پرونده — همان چیزی که مشتری بعد از ثبتِ درخواست می‌خواهد بداند. */
function StatusPanel({ record }: { record: AssuranceEngagementRecord }) {
  const left = daysLeft(record.access_expires_at)
  return (
    <SectionCard
      icon={ClipboardCheck}
      title="وضعیتِ پرونده"
      badge={
        <span className={`status-badge ${record.status === 'rejected' ? 'tone-danger' : 'tone-info'}`}>
          {STATUS_LABELS[record.status] ?? record.status}
        </span>
      }
    >
      <div className="cc-summary">
        <Metric
          icon={<CalendarRange size={15} />}
          label="دوره‌ی موردِ حسابرسی"
          value={
            record.period_from && record.period_to
              ? `${formatJalali(record.period_from)} تا ${formatJalali(record.period_to)}`
              : '—'
          }
        />
        <Metric
          icon={<ClipboardCheck size={15} />}
          label="تاریخِ درخواست"
          value={formatJalali(record.requested_at.slice(0, 10))}
        />
        {record.auditor_name && (
          <Metric icon={<UserCheck size={15} />} label="حسابرسِ پرونده" value={record.auditor_name} />
        )}
        {left !== null && (
          <Metric
            icon={<ShieldCheck size={15} />}
            label="مهلتِ دسترسیِ حسابرس"
            value={left > 0 ? `${faInt(left)} روز` : 'تمام شده'}
            tone={left > 0 ? 'plain' : 'out'}
          />
        )}
      </div>

      {record.status === 'requested' && (
        <p className="ef-message">درخواستِ شما ثبت شده است؛ کارشناسِ ما برای هماهنگی تماس می‌گیرد.</p>
      )}
      {record.status === 'rejected' && record.reject_reason && (
        <p className="ef-message ef-message--warn">
          <AlertTriangle size={15} /> دلیلِ رد: {record.reject_reason}
        </p>
      )}
      {(record.status === 'approved' || record.status === 'active') && (
        <p className="ef-message">
          پرونده باز است. کارنامه‌ی سلامتِ دفتر و یافته‌ها را از منوی «حسابرسی» ببینید.
        </p>
      )}
      {record.status === 'closed' && (
        <p className="ef-message">
          پرونده بسته شده است{record.close_note ? ` — ${record.close_note}` : ''}. برای حسابرسیِ دوره‌ی
          تازه، درخواستِ جدید ثبت کنید.
        </p>
      )}
    </SectionCard>
  )
}

/** صریح گفتنِ اینکه حسابرس چه چیزی خواهد دید — پیش از اینکه کاربر تأیید کند. */
function ScopeCard() {
  return (
    <SectionCard icon={ShieldCheck} title="حسابرس چه چیزی خواهد دید؟">
      <ul className="ef-bullets">
        <li>
          با تأییدِ ما، یک <strong>دسترسیِ موقتِ فقط‌خواندنی</strong> برای حسابرس در همین کسب‌وکار
          ساخته می‌شود. مهلتش مشخص است و با بسته‌شدنِ پرونده خودکار قطع می‌شود.
        </li>
        <li>
          حسابرس می‌تواند دفاتر، اسناد، انبار، دارایی و <strong>اطلاعاتِ حقوق و دستمزد</strong> را
          ببیند — حسابرسیِ واقعی بدونِ اینها ممکن نیست.
        </li>
        <li>
          حسابرس <strong>هیچ چیزی نمی‌تواند ثبت، ویرایش یا حذف کند</strong>، پشتیبان نمی‌گیرد و به
          مدیریتِ کاربرانِ شما دسترسی ندارد.
        </li>
        <li>
          نامش با نقشِ «حسابرس» در صفحه‌ی «کاربران» دیده می‌شود و هر کاری که بکند در «ردِ تغییرات»
          ثبت است. هر وقت بخواهید می‌توانید غیرفعالش کنید.
        </li>
      </ul>
    </SectionCard>
  )
}

/**
 * «کارنامه سلامت دفتر» — نمره، و **جدولی که نمره را توضیح می‌دهد**.
 *
 * عددِ تنها فقط دعوا می‌سازد. جدولِ «بررسی · شدت · تعداد · امتیازِ ازدست‌رفته»
 * همان چیزی است که نمره از آن ساخته شده، پس همیشه کنارش می‌آید.
 */
export function AssuranceHealthPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey, section?: string | null) => void
}) {
  const engagement = useAsync<AssuranceEngagementRecord | null>(
    () => fetchAssuranceEngagement(token),
    [token],
  )
  const run = useAsync<AssuranceRunRecord | null>(() => fetchLatestAssuranceRun(token), [token])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)

  const rows = useMemo(
    () => (run.data?.summary ?? []).slice().sort((a, b) => b.lost - a.lost),
    [run.data],
  )
  const available = rows.reduce((sum, row) => sum + row.weight, 0)

  async function refresh() {
    setBusy(true)
    setMsg(null)
    try {
      await refreshAssuranceRun(token)
      run.reload()
      engagement.reload()
      setMsg({ text: 'بررسی دوباره اجرا شد.', kind: 'ok' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'اجرای بررسی ناموفق بود', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const record = run.data

  return (
    <OpsPage
      canvas
      icon={Gauge}
      title="کارنامه سلامت دفتر"
      description="نتیجه‌ی بررسی‌های خودکار روی دفترِ شما، در تاریخی که اجرا شده است."
    >
      <AsyncBlock
        loading={run.loading}
        error={run.error}
        empty={record === null}
        emptyText="هنوز بررسی‌ای اجرا نشده است. با «بررسی دوباره» اولین کارنامه ساخته می‌شود."
      >
        {record && (
          <>
            {/* داخلِ section، وگرنه پوسته‌ی «راهنما» ردیفِ ارقامِ فرزندِ مستقیم را پنهان می‌کند. */}
            <SectionCard
              icon={Gauge}
              title="نمره‌ی سلامت"
              badge={
                <span className={`status-badge ${GRADE_TONE[record.grade] ?? 'tone-info'}`}>
                  {GRADE_LABELS[record.grade] ?? record.grade}
                </span>
              }
              description={`بررسیِ شماره‌ی ${faInt(record.number)} — ${formatJalali(record.ran_at.slice(0, 10))}`}
            >
              <div className="cc-summary">
                <Metric
                  icon={<Gauge size={15} />}
                  label="نمره از ۱۰۰"
                  value={fa(record.score)}
                  tone={record.grade === 'healthy' ? 'in' : record.grade === 'critical' ? 'out' : 'plain'}
                />
                <Metric
                  icon={<AlertTriangle size={15} />}
                  label="یافته‌های خطا"
                  value={faInt(record.error_count)}
                  tone={record.error_count > 0 ? 'out' : 'plain'}
                />
                <Metric
                  icon={<AlertTriangle size={15} />}
                  label="یافته‌های هشدار"
                  value={faInt(record.warning_count)}
                />
                <Metric
                  icon={<CalendarRange size={15} />}
                  label="بازه"
                  value={
                    record.date_from && record.date_to
                      ? `${formatJalali(record.date_from)} تا ${formatJalali(record.date_to)}`
                      : 'همه‌ی دوره'
                  }
                />
              </div>
              <p className="ef-message">
                ۱۰۰ یعنی هیچ‌کدام از بررسی‌ها چیزی پیدا نکرد — نه اینکه دفتر بی‌خطاست، بلکه اینکه
                چیزی از آنچه بلدیم بگردیم پیدا نشد.
              </p>
            </SectionCard>

            <SectionCard
              icon={ClipboardCheck}
              title="نمره از کجا آمد"
              tip="هر بررسی امتیازِ ثابتی دارد؛ کلِ آن امتیاز وقتی کم می‌شود که مشکل فراگیر باشد، نه با یک مورد."
              description={`مجموعِ امتیازِ قابلِ‌کسب: ${faInt(available)}`}
            >
              <div className="table-scroll ef-table-wrap">
                <table className="cards-on-mobile ef-table">
                  <thead>
                    <tr>
                      <th>بررسی</th>
                      <th className="ef-col-min">شدت</th>
                      <th className="num ef-col-min">تعداد</th>
                      <th className="num ef-col-min">امتیازِ ازدست‌رفته</th>
                      <th className="num ef-col-min">از</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.key}>
                        <td className="card-title ef-cell-title" data-label="بررسی">
                          {row.title}
                          {row.description && <InfoTip text={row.description} />}
                        </td>
                        <td data-label="شدت">
                          <span
                            className={`status-badge ${row.severity === 'error' ? 'tone-danger' : 'tone-warning'}`}
                          >
                            {row.severity === 'error' ? 'خطا' : 'هشدار'}
                          </span>
                        </td>
                        <td className="num" data-label="تعداد">
                          {row.count ? faInt(row.count) : '—'}
                        </td>
                        <td className="num" data-label="امتیازِ ازدست‌رفته">
                          {row.lost ? fa(row.lost.toFixed(2)) : '—'}
                        </td>
                        <td className="num" data-label="از">
                          {faInt(row.weight)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </>
        )}
      </AsyncBlock>

      <ActionBar status={<FormStatus msg={msg} />}>
        {onNavigate && record && (
          <button
            type="button"
            className="ef-btn-secondary"
            onClick={() => onNavigate('assurancefindinglist')}
          >
            <ClipboardCheck size={15} /> دیدنِ یافته‌ها
          </button>
        )}
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void refresh()}>
          <RefreshCcw size={16} /> {busy ? 'در حال اجرا…' : 'بررسی دوباره'}
        </button>
      </ActionBar>
    </OpsPage>
  )
}
