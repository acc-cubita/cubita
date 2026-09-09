import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, CalendarRange, CheckCircle2, Loader2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { PageHeader } from '../../components/PageHeader'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { isoToJalali, jalaliToIso, toFaDigits, todayIso } from '../../lib/jalali'
import type { EntrySource } from '../../api'

/**
 * قطعاتِ مشترکِ هجده صفحه‌ی ماژولِ حسابداری.
 *
 * هر عملیاتِ حسابداری تقریباً یک شکل دارد: یک بازه یا تاریخ انتخاب کن، پیش‌نمایش را
 * ببین، تأیید کن. اگر هر صفحه این اسکلت را از نو می‌نوشت، هجده نسخه‌ی کمی‌متفاوت از
 * «در حال بارگذاری…» و «تاریخ» و «تأیید» می‌داشتیم که هیچ‌کدام دقیقاً مثل هم رفتار
 * نمی‌کردند. پس اسکلت یک‌جاست و صفحه‌ها فقط *محتوای* پیش‌نمایش و کنشِ صدور را می‌دهند.
 */

export const fa = (v: string | number | null | undefined) => Number(v || 0).toLocaleString('fa-IR')
export const faInt = (n: number) => n.toLocaleString('fa-IR')

/** مبلغِ صفر در ستونِ بدهکار/بستانکار عمداً خط تیره می‌شود — صفرهای ردیف‌به‌ردیف
 *  چشم را از ارقامِ واقعی منحرف می‌کنند. */
export const faAmount = (v: string | number | null | undefined) =>
  Number(v || 0) === 0 ? '—' : fa(v)

export type Msg = { text: string; kind: 'ok' | 'err' } | null

export function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return (
    <p className={`hint acc-note acc-note--${msg.kind}`}>
      {msg.kind === 'ok' ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
      {msg.text}
    </p>
  )
}

/** برچسبِ فارسیِ منشأِ سند. کلیدِ ناشناخته خودش نمایش داده می‌شود تا ماژولِ تازه
 *  بی‌صدا «نامشخص» نشود. */
export const SOURCE_LABELS: Record<string, string> = {
  manual: 'دستی',
  sales_invoice: 'فاکتور فروش',
  purchase_invoice: 'فاکتور خرید',
  sales_return: 'برگشت از فروش',
  purchase_return: 'برگشت از خرید',
  treasury: 'دریافت و پرداخت',
  treasury_receipt: 'دریافت از مشتری',
  treasury_payment: 'پرداخت به تأمین‌کننده',
  bank: 'عملیات بانکی',
  check_clear: 'وصول چک',
  petty_cash_settle: 'تسویه تنخواه',
  payroll: 'حقوق و دستمزد',
  payroll_benefit: 'مزایای حقوق',
  payslip: 'فیش حقوقی',
  check: 'چک',
  petty_cash: 'تنخواه',
  depreciation: 'استهلاک',
  asset_acquisition: 'خرید دارایی ثابت',
  production: 'تولید',
  production_order: 'سفارشِ تولید',
  stock_adjustment: 'تعدیل انبار',
  stock_count: 'انبارگردانی',
  adjustment: 'تعدیل',
  transfer_in: 'ورود از انتقال',
  transfer_out: 'خروج برای انتقال',
  period_close: 'بستن حساب‌های سود و زیان',
  closing_entry: 'سند اختتامیه',
  opening_entry: 'سند افتتاحیه',
  fx_revaluation: 'تسعیر ارز',
  reclassification: 'اصلاح طبقه‌بندی مانده',
  recurring: 'سند تکرارشونده',
  void: 'ابطال',
  opening_balance: 'مانده اول دوره',
  opening: 'افتتاحیه',
  installment: 'اقساط',
}

export const sourceLabel = (key: string) => SOURCE_LABELS[key] ?? key

/**
 * منشأِ سند با هویتش — «فاکتور فروش ۱۲۵»، نه فقط «فاکتور فروش».
 *
 * وقتی چند عملیات به یک سند می‌رسند (حقوق و دستمزد یک سند برای کلِ دوره می‌زند)
 * شماره نمی‌آید و شمارش جایش را می‌گیرد: شماره‌ی *یکی* از بیست‌وسه فیش، سند را
 * غلط توصیف می‌کند.
 */
export function sourceText(entry: { source_type: string; source?: EntrySource | null }): string {
  const label = sourceLabel(entry.source_type)
  const src = entry.source
  if (!src) return label
  if (src.number) return `${label} ${toFaDigits(src.number)}`
  if (src.count > 1) return `${label} — ${faInt(src.count)} مورد`
  return label
}

export const STATUS_LABELS: Record<string, string> = { temporary: 'موقت', permanent: 'دائم' }

export function StatusChip({ status, voided }: { status: string; voided?: boolean }) {
  if (voided) return <span className="acc-chip acc-chip--void">باطل</span>
  return (
    <span className={`acc-chip acc-chip--${status === 'permanent' ? 'final' : 'draft'}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

/** یک عددِ سرصفحه. همان ظاهرِ «مرکز هزینه» را دارد تا دو ماژول یک زبان داشته باشند. */
export function Metric({
  icon,
  label,
  value,
  hint,
  tone = 'plain',
}: {
  icon: ReactNode
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
      <span
        className={`cc-metric-value ${tone === 'plain' ? '' : tone === 'in' ? 'pos-in' : 'pos-out'}`}
      >
        {value}
      </span>
      {hint && <span className="cc-metric-hint">{hint}</span>}
    </div>
  )
}

/**
 * پوسته‌ی هر صفحه‌ی عملیات.
 *
 * `.page.panels` هر فرزندِ مستقیم را یک پنلِ جدا می‌کند، پس سرصفحه و نوارِ ارقام و
 * هر `<section>` خودبه‌خود کارتِ خودشان را می‌گیرند. صفحه‌ها فقط باید فرزندانشان را
 * صاف نگه دارند — یک `<div>`ِ اضافی همه‌ی کارت‌ها را داخلِ یک کارت می‌بُرد.
 */
export function OpsPage({
  icon,
  title,
  description,
  head,
  children,
}: {
  icon: LucideIcon
  title: string
  description: string
  /** نوارِ ابزار/ارقامِ همیشه‌دیده — بیرون از پوسته‌ی «راهنما» که سرصفحه را پنهان می‌کند. */
  head?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="page panels">
      <PageHeader icon={icon} title={title} description={description} />
      {head}
      {children}
    </div>
  )
}

/** بارگذاری/خطا/خالی — یک زبانِ واحد برای هر سه حالت. */
export function AsyncBlock({
  loading,
  error,
  empty,
  emptyText,
  children,
}: {
  loading: boolean
  error: string | null
  empty?: boolean
  emptyText?: string
  children: ReactNode
}) {
  if (loading)
    return (
      <p className="hint acc-loading">
        <Loader2 size={15} className="spin" /> در حال بارگذاری…
      </p>
    )
  if (error) return <p className="hint acc-note acc-note--err">{error}</p>
  if (empty) return <p className="hint">{emptyText ?? 'چیزی برای نمایش نیست.'}</p>
  return <>{children}</>
}

/** `useAsync` — یک fetch با کلیدِ وابستگی، بدونِ نشتِ پاسخِ کهنه روی حالتِ تازه.
 *
 *  شمارنده‌ی `runRef` لازم است چون کاربر بازه را سریع عوض می‌کند: بدونِ آن، پاسخِ
 *  کندِ درخواستِ قبلی می‌توانست بعد از پاسخِ سریعِ درخواستِ فعلی بنشیند و صفحه
 *  داده‌ی بازه‌ی اشتباه را نشان بدهد. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const runRef = useRef(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  const reload = useCallback(() => {
    const run = ++runRef.current
    setLoading(true)
    setError(null)
    loaderRef.current()
      .then((result) => {
        if (run === runRef.current) {
          setData(result)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (run === runRef.current) {
          setError(err instanceof Error ? err.message : 'خطای ناشناخته')
          setLoading(false)
        }
      })
  }, [])

  useEffect(reload, deps) // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error, reload, setData }
}

// ──────────────────────────── بازه‌ی تاریخ ────────────────────────────

export type Preset = 'all' | 'year' | 'quarter' | 'month' | 'custom'

const PRESETS: { key: Preset; label: string }[] = [
  { key: 'all', label: 'از ابتدا' },
  { key: 'year', label: 'امسال' },
  { key: 'quarter', label: 'این فصل' },
  { key: 'month', label: 'این ماه' },
  { key: 'custom', label: 'دلخواه' },
]

/** بازه‌ی میلادیِ هر پیش‌تنظیم از تقویمِ **شمسی** — «امسال» یعنی سالِ شمسی نه ژانویه. */
export function presetRange(preset: Preset): { from?: string; to?: string } {
  if (preset === 'all' || preset === 'custom') return {}
  const { jy, jm } = isoToJalali(todayIso())
  if (preset === 'year') return { from: jalaliToIso(jy, 1, 1), to: todayIso() }
  if (preset === 'month') return { from: jalaliToIso(jy, jm, 1), to: todayIso() }
  const qStart = jm <= 3 ? 1 : jm <= 6 ? 4 : jm <= 9 ? 7 : 10
  return { from: jalaliToIso(jy, qStart, 1), to: todayIso() }
}

/** اولین روزِ سالِ شمسیِ جاری — پیش‌فرضِ منطقی برای عملیاتِ سالانه. */
export function jalaliYearStart(): string {
  const { jy } = isoToJalali(todayIso())
  return jalaliToIso(jy, 1, 1)
}

export interface RangeState {
  preset: Preset
  setPreset: (p: Preset) => void
  custom: { from: string; to: string }
  setCustom: (c: { from: string; to: string }) => void
  from?: string
  to?: string
}

export function useRange(initial: Preset = 'year'): RangeState {
  const [preset, setPreset] = useState<Preset>(initial)
  const [custom, setCustom] = useState({ from: jalaliYearStart(), to: todayIso() })
  const range = preset === 'custom' ? { from: custom.from, to: custom.to } : presetRange(preset)
  return { preset, setPreset, custom, setCustom, from: range.from, to: range.to }
}

export function RangeBar({ range, extra }: { range: RangeState; extra?: ReactNode }) {
  return (
    <div className="cc-toolbar">
      <div className="cc-presets">
        <CalendarRange size={15} />
        {PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            className={range.preset === p.key ? 'is-active' : ''}
            onClick={() => range.setPreset(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>
      {range.preset === 'custom' && (
        <div className="cc-custom-range">
          <JalaliDatePicker
            value={range.custom.from}
            onChange={(iso) => range.setCustom({ ...range.custom, from: iso })}
            placeholder="از تاریخ"
          />
          <JalaliDatePicker
            value={range.custom.to}
            onChange={(iso) => range.setCustom({ ...range.custom, to: iso })}
            placeholder="تا تاریخ"
          />
        </div>
      )}
      {extra}
    </div>
  )
}

/** جمعِ بدهکار/بستانکارِ یک پیش‌نمایش، با نشانِ توازن. سندی که جمعش نمی‌خواند
 *  هرگز نباید صادر شود، پس عدم‌توازن باید *پیش* از دکمه دیده شود. */
export function BalanceFooter({ debit, credit }: { debit: number; credit: number }) {
  const balanced = debit === credit
  return (
    <div className={`acc-balance${balanced ? '' : ' acc-balance--off'}`}>
      <span>
        جمعِ بدهکار: <b>{fa(debit)}</b>
      </span>
      <span>
        جمعِ بستانکار: <b>{fa(credit)}</b>
      </span>
      <span className="acc-balance-state">
        {balanced ? (
          <>
            <CheckCircle2 size={14} /> متوازن
          </>
        ) : (
          <>
            <AlertTriangle size={14} /> اختلاف {fa(Math.abs(debit - credit))}
          </>
        )}
      </span>
    </div>
  )
}
