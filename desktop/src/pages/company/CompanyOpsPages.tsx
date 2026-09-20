import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Archive,
  BellRing,
  PlayCircle,
} from 'lucide-react'
import {
  createCalendarEvent,
  fetchCalendarEvents,
  fetchChartSetup,
  fetchFiscalYears,
  type CalendarEventRecord,
  type ChartSetup,
  type FiscalYearRecord,
} from '../../api'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { ActionBar, CountBadge, FormStatus } from '../../components/form/FormKit'
import { EmptyState } from '../../components/EmptyState'
import { formatJalali, toFaDigits, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'

/**
 * عملیاتِ سطحِ شرکت: ساختِ طرف‌حساب، و کارهای ابتدا/انتهای دوره.
 *
 * «عملیات اول دوره» و «عملیات پایان سال» عمداً *صفحه‌ی کار* نیستند بلکه **راهنمای
 * مسیر**اند: هر کدام چند کارِ واقعی دارند که هرکدام صفحه‌ی خودش را از قبل داشت
 * (راه‌اندازی، سال مالی، انبارگردانی…). چیزی که نبود، ترتیب و وضعیت بود — کاربر
 * نمی‌دانست چه کاری مانده. پس این‌جا وضعیتِ واقعی از سرور خوانده و کنارِ هر گام
 * نشان داده می‌شود، و دکمه کاربر را به همان صفحه می‌برد؛ نه تکرارِ فرم‌ها.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

type Msg = { text: string; kind: 'ok' | 'err' } | null

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

/** یک گامِ راهنما — عنوان، توضیح، وضعیتِ واقعی و دکمه‌ی رفتن به همان صفحه. */
function Step({
  index,
  title,
  description,
  state,
  action,
  onGo,
}: {
  index: number
  title: string
  description: string
  state: { label: string; tone: 'ok' | 'todo' | 'warn' }
  action: string
  onGo: () => void
}) {
  return (
    <div className={`ops-step is-${state.tone}`}>
      <span className="ops-step-num">{fa(index)}</span>
      <div className="ops-step-body">
        <div className="ops-step-head">
          <strong>{title}</strong>
          <span className={`badge ${state.tone === 'ok' ? 'success' : state.tone === 'warn' ? 'warning' : ''}`}>
            {state.label}
          </span>
        </div>
        <p className="ops-step-desc">{description}</p>
      </div>
      <button type="button" onClick={onGo}>
        {action}
      </button>
    </div>
  )
}

// ── طرف حساب جدید ────────────────────────────────────────────────────────────

// ── عملیات اول دوره ──────────────────────────────────────────────────────────

export function OpeningOpsPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey, section?: string | null) => void
}) {
  const [years, setYears] = useState<FiscalYearRecord[] | null>(null)
  const [chart, setChart] = useState<ChartSetup | null>(null)

  useEffect(() => {
    void fetchFiscalYears(token)
      .then(setYears)
      .catch(() => setYears([]))
    // نشانِ گامِ «کدینگ حساب‌ها» باید از وضعیتِ واقعیِ چارت بیاید، نه یک برچسبِ ثابت.
    void fetchChartSetup(token)
      .then(setChart)
      .catch(() => setChart(null))
  }, [token])

  const active = useMemo(() => (years ?? []).find((y) => y.is_active) ?? null, [years])
  const hasOpening = Boolean(active?.opening_entry_id)
  //: «انجام شده» یعنی چارت گسترش یافته — با درجِ قالبِ صنفی یا با ساختنِ حسابِ خودی.
  //: صرفِ داشتنِ حساب معیار نیست: چارتِ پایه از لحظه‌ی ساختِ کسب‌وکار وجود دارد.
  const chartReady = Boolean(chart && (chart.custom > 0 || chart.applied_template))

  return (
    <div className="page panels">
      <PageHeader
        icon={PlayCircle}
        title="عملیات اول دوره"
        description="کارهایی که یک‌بار در ابتدای دوره انجام می‌شوند تا دفترها از نقطه‌ی درست شروع کنند."
      />
      <div className="ef-form">
      <SectionCard
        icon={PlayCircle}
        title="مسیرِ شروعِ دوره"
        description={
          active
            ? `سالِ مالیِ جاری: «${active.title}» (${formatJalali(active.start_date)} تا ${formatJalali(active.end_date)})`
            : 'هنوز سالِ مالیِ فعالی تعریف نشده — گامِ اول همین است.'
        }
      >
        <div className="ops-steps">
          <Step
            index={1}
            title="تعریفِ سال مالی"
            description="بازه‌ی دوره را مشخص کنید. تا وقتی سالِ مالی تعریف نشده باشد، هیچ محدودیتی روی تاریخِ اسناد اعمال نمی‌شود."
            state={active ? { label: 'انجام شده', tone: 'ok' } : { label: 'انجام نشده', tone: 'todo' }}
            action="سال مالی"
            onGo={() => onNavigate('fiscalyear')}
          />
          <Step
            index={2}
            title="کدینگ حساب‌ها"
            description="درختواره‌ی حساب‌ها را بسازید یا یکی از قالب‌های صنفی (بازرگانی، خدماتی، تولیدی، پیمانکاری) را درج کنید."
            state={
              chart === null
                ? { label: 'هر وقت لازم شد', tone: 'warn' }
                : chartReady
                  ? {
                      label: chart.applied_template
                        ? 'قالبِ صنفی درج شده'
                        : `${toFaDigits(chart.custom)} حسابِ افزوده`,
                      tone: 'ok',
                    }
                  : { label: 'انجام نشده', tone: 'todo' }
            }
            action="درختواره"
            onGo={() => onNavigate('acctchart')}
          />
          <Step
            index={3}
            title="مانده‌های اول دوره"
            description="مانده‌ی حساب‌ها، موجودیِ انبار و مانده‌ی طرف‌حساب‌ها در لحظه‌ی شروع. سندِ افتتاحیه از همین‌جا ساخته می‌شود."
            state={
              hasOpening
                ? { label: 'سندِ افتتاحیه ثبت شده', tone: 'ok' }
                : { label: 'انجام نشده', tone: 'todo' }
            }
            action="مانده اول دوره"
            onGo={() => onNavigate('openingbalance')}
          />
          <Step
            index={4}
            title="روش‌های شماره‌گذاری"
            description="اگر از سیستمِ قبلی می‌آیید، شماره‌ی شروعِ اسناد را تنظیم کنید تا سریِ شماره‌ها نشکند."
            state={{ label: 'اختیاری', tone: 'warn' }}
            action="شماره‌گذاری"
            onGo={() => onNavigate('numbering')}
          />
        </div>
      </SectionCard>
      </div>
    </div>
  )
}

// ── عملیات پایان سال ─────────────────────────────────────────────────────────

export function YearEndOpsPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey, section?: string | null) => void
}) {
  const [years, setYears] = useState<FiscalYearRecord[] | null>(null)

  useEffect(() => {
    void fetchFiscalYears(token)
      .then(setYears)
      .catch(() => setYears([]))
  }, [token])

  const active = useMemo(() => (years ?? []).find((y) => y.is_active) ?? null, [years])
  const closed = active?.status === 'closed'
  const daysLeft = useMemo(() => {
    if (!active) return null
    const end = new Date(active.end_date).getTime()
    return Math.ceil((end - Date.now()) / 86_400_000)
  }, [active])

  return (
    <div className="page panels">
      <PageHeader
        icon={Archive}
        title="عملیات پایان سال"
        description="بستنِ دوره کارِ برگشت‌ناپذیری است؛ ترتیبِ زیر تضمین می‌کند چیزی جا نماند."
      />
      <div className="ef-form">
      {active && daysLeft !== null && daysLeft <= 60 && !closed && (
        <div className="ef-callout ef-callout--warn">
          <AlertTriangle size={16} />
          <div>
            {daysLeft >= 0
              ? `تا پایانِ سالِ مالیِ «${active.title}» ${fa(daysLeft)} روز مانده است.`
              : `سالِ مالیِ «${active.title}» ${fa(Math.abs(daysLeft))} روز است که تمام شده و هنوز بسته نشده.`}
          </div>
        </div>
      )}

      <SectionCard
        icon={Archive}
        title="مسیرِ بستنِ سال"
        description={
          active
            ? `سالِ مالیِ جاری: «${active.title}» — وضعیت: ${closed ? 'بسته' : 'باز'}`
            : 'سالِ مالیِ فعالی تعریف نشده است.'
        }
      >
        <div className="ops-steps">
          <Step
            index={1}
            title="انبارگردانی و تعدیلِ موجودی"
            description="شمارشِ فیزیکیِ انبار و ثبتِ اختلاف‌ها، پیش از آنکه دفترها بسته شوند."
            state={{ label: 'پیش‌نیاز', tone: 'warn' }}
            action="انبارگردانی"
            onGo={() => onNavigate('inventory', 'count')}
          />
          <Step
            index={2}
            title="تطبیقِ بانک و صندوق"
            description="مانده‌ی دفترها با صورت‌حسابِ بانکی و شمارشِ صندوق یکی شود."
            state={{ label: 'پیش‌نیاز', tone: 'warn' }}
            action="چک و بانک"
            onGo={() => onNavigate('banking')}
          />
          <Step
            index={3}
            title="بررسیِ تراز آزمایشی"
            description="تراز باید تراز باشد و حسابِ معلق نماند. اینجا آخرین فرصتِ اصلاحِ سندهاست."
            state={{ label: 'بررسی کنید', tone: 'warn' }}
            action="گزارش‌ها"
            onGo={() => onNavigate('reports')}
          />
          <Step
            index={4}
            title="بستنِ سال و سندِ اختتامیه"
            description="حساب‌های موقت صفر و مانده‌های دائمی به دوره‌ی بعد منتقل می‌شوند. پس از بستن، ثبتِ سند در این بازه ممکن نیست."
            state={closed ? { label: 'بسته شده', tone: 'ok' } : { label: 'انجام نشده', tone: 'todo' }}
            action="سال مالی"
            onGo={() => onNavigate('fiscalyear')}
          />
          <Step
            index={5}
            title="پشتیبانِ پایانِ دوره"
            description="یک نسخه‌ی کاملِ داده پیش از شروعِ دوره‌ی تازه بگیرید و بیرون از این دستگاه نگه دارید."
            state={{ label: 'توصیه‌ی جدی', tone: 'warn' }}
            action="پشتیبان‌گیری"
            onGo={() => onNavigate('backup')}
          />
        </div>
      </SectionCard>
      </div>
    </div>
  )
}

// ── یادآوری عملیات پایان سال ─────────────────────────────────────────────────

/** پیش‌فرضِ فاصله‌ی یادآوری تا پایانِ سال (روز). */
const REMINDER_OFFSETS = [60, 30, 14, 7, 1]

export function YearEndReminderPage({ token }: { token: string }) {
  const [years, setYears] = useState<FiscalYearRecord[] | null>(null)
  const [events, setEvents] = useState<CalendarEventRecord[]>([])
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [picked, setPicked] = useState<number[]>([30, 7])

  async function refresh() {
    try {
      setEvents(await fetchCalendarEvents(token))
    } catch {
      /* تقویم اختیاری است؛ نبودنش این صفحه را نباید بشکند */
    }
  }

  useEffect(() => {
    void fetchFiscalYears(token)
      .then(setYears)
      .catch(() => setYears([]))
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const active = useMemo(() => (years ?? []).find((y) => y.is_active) ?? null, [years])

  //: یادآوری‌های ساخته‌شده‌ی همین سال — با پیشوندِ عنوان شناسایی می‌شوند.
  const mine = useMemo(
    () => events.filter((e) => e.title.startsWith('پایان سال مالی')),
    [events],
  )

  function dateFor(offset: number): string | null {
    if (!active) return null
    const d = new Date(active.end_date)
    d.setDate(d.getDate() - offset)
    return d.toISOString().slice(0, 10)
  }

  async function create() {
    if (picked.length === 0) {
      setMsg({ text: 'دست‌کم یک فاصله‌ی یادآوری را علامت بزنید.', kind: 'err' })
      return
    }
    if (!active) return
    setBusy(true)
    setMsg(null)
    try {
      let made = 0
      for (const offset of picked) {
        const date = dateFor(offset)
        if (!date || date < todayIso()) continue
        await createCalendarEvent(token, {
          title: `پایان سال مالی «${active.title}» — ${offset} روز مانده`,
          description:
            'عملیات پایان سال: انبارگردانی، تطبیقِ بانک، بررسیِ تراز آزمایشی، بستنِ سال و پشتیبان‌گیری.',
          event_date: date,
          start_time: null,
          end_time: null,
          category: 'reminder',
          is_done: false,
        })
        made += 1
      }
      setMsg(
        made
          ? { text: `${fa(made)} یادآوری در تقویم ثبت شد.`, kind: 'ok' }
          : { text: 'همه‌ی تاریخ‌های انتخاب‌شده گذشته‌اند؛ یادآوری‌ای ساخته نشد.', kind: 'err' },
      )
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={BellRing}
        title="یادآوری عملیات پایان سال"
        description="بستنِ سال کارِ یک‌روزه نیست. این‌جا چند یادآوری روی تقویمِ برنامه می‌نشیند تا انبارگردانی و تطبیق‌ها به روزهای آخر نیفتند."
      />
      <div className="ef-form">
      {!active ? (
        <EmptyState icon={BellRing} text="سالِ مالیِ فعالی نیست — اول در «سال مالی» یک دوره تعریف و فعال کنید تا تاریخِ پایانش مشخص باشد." />
      ) : (
        <>
          <SectionCard
            icon={BellRing}
            title="ساختِ یادآوری"
            tip="یادآوری‌ها به‌صورتِ رویدادِ تقویم ثبت می‌شوند و در «کارهای امروز» و مرکزِ هشدارها دیده می‌شوند."
            description={`پایانِ سالِ مالیِ «${active.title}»: ${formatJalali(active.end_date)}`}
          >
            <div className="cd-levels">
              {REMINDER_OFFSETS.map((offset) => {
                const date = dateFor(offset)
                const past = date !== null && date < todayIso()
                const on = picked.includes(offset)
                return (
                  <label key={offset} className={`ef-check-tip${past ? ' is-past' : ''}`}>
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={past}
                      onChange={(e) =>
                        setPicked((prev) =>
                          e.target.checked ? [...prev, offset] : prev.filter((o) => o !== offset),
                        )
                      }
                    />
                    <span>
                      {fa(offset)} روز مانده
                      {date && <em className="cmp-hint"> — {formatJalali(date)}</em>}
                      {past && <em className="cmp-hint"> (گذشته)</em>}
                    </span>
                  </label>
                )
              })}
            </div>

          </SectionCard>
          <ActionBar
            status={
              <FormStatus
                msg={msg}
                idle={
                  picked.length > 0
                    ? `${fa(picked.length)} یادآوری ثبت می‌شود.`
                    : 'فاصله‌های موردِنظر را علامت بزنید.'
                }
              />
            }
          >
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void create()}>
              <BellRing size={16} /> ثبت در تقویم
            </button>
          </ActionBar>

          <SectionCard
            icon={BellRing}
            title="یادآوری‌های ثبت‌شده"
            badge={mine.length > 0 ? <CountBadge accent>{fa(mine.length)} یادآوری</CountBadge> : undefined}
          >
            {mine.length === 0 ? (
              <EmptyState icon={BellRing} text="هنوز یادآوری‌ای ثبت نشده — از بالا فاصله‌های موردِنظر را انتخاب و ثبت کنید." />
            ) : (
              <div className="table-scroll ef-table-wrap">
                <table className="cards-on-mobile ef-table">
                  <thead>
                    <tr>
                      <th>تاریخ</th>
                      <th>عنوان</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mine.map((e) => (
                      <tr key={e.id}>
                        <td data-label="تاریخ">{formatJalali(e.event_date)}</td>
                        <td className="card-title" data-label="عنوان">{e.title}</td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${e.is_done ? 'tone-success' : 'tone-muted'}`}>
                            {e.is_done ? 'انجام شده' : 'در انتظار'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>
        </>
      )}
      </div>
    </div>
  )
}
