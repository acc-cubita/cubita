/**
 * اجزای مشترکِ اپِ ستاد.
 *
 * قرینه‌ی `desktop/src/pages/accounting/kit.tsx` ولی بسیار کوچک‌تر: اپِ ستاد
 * نه بازه‌ی تاریخ می‌خواهد نه جمع‌های دفتری. هر چه اینجاست در دستِ‌کم دو صفحه
 * استفاده می‌شود؛ چیزی که یک مصرف‌کننده دارد در خودِ صفحه می‌ماند.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

import { toFaDigits } from '../lib/jalali'

/** عدد با ارقامِ فارسی و جداکننده. `toLocaleString()` بدونِ زبان روی ویندوزِ
 *  انگلیسی رقمِ لاتین می‌دهد — همان باگی که بارها برگشته. */
export const fa = (n: number | null | undefined): string =>
  n == null ? '—' : Math.round(n).toLocaleString('fa-IR')

/** مبلغ؛ صفر خط تیره می‌شود تا چشم از ارقامِ واقعی منحرف نشود. */
export const faAmount = (n: number | null | undefined): string => (!n ? '—' : fa(n))

export const faInt = (n: number | null | undefined): string =>
  n == null ? '—' : toFaDigits(String(Math.round(n)))

export function PageHeader({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon: LucideIcon
  title: string
  description: string
  actions?: ReactNode
}) {
  return (
    <header className="ad-head">
      <div className="ad-head-icon">
        <Icon size={20} />
      </div>
      <div className="ad-head-text">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions ? <div className="ad-head-actions">{actions}</div> : null}
    </header>
  )
}

export function Card({
  title,
  description,
  actions,
  children,
}: {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="ad-card">
      {title ? (
        <div className="ad-card-head">
          <div>
            <h2>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          {actions ? <div className="ad-card-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  )
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint?: string
  tone?: 'ok' | 'warn' | 'bad'
}) {
  return (
    <div className={`ad-stat${tone ? ` tone-${tone}` : ''}`}>
      <span className="ad-stat-label">{label}</span>
      <strong className="ad-stat-value">{value}</strong>
      {hint ? <span className="ad-stat-hint">{hint}</span> : null}
    </div>
  )
}

export function Chip({ text, tone }: { text: string; tone: 'ok' | 'warn' | 'bad' | 'mute' }) {
  return <span className={`ad-chip tone-${tone}`}>{text}</span>
}

export function EmptyState({ text }: { text: string }) {
  return <p className="ad-empty">{text}</p>
}

/** پیامِ نتیجه — خطا یا موفقیت. */
export function Note({ msg }: { msg: { kind: 'ok' | 'bad'; text: string } | null }) {
  if (!msg) return null
  return <p className={`ad-note tone-${msg.kind === 'ok' ? 'ok' : 'bad'}`}>{msg.text}</p>
}

/**
 * هر چهار حالت، نه فقط «داده هست».
 *
 * خطا **پیامِ سرور** را نشان می‌دهد نه «خطایی رخ داد»: `detail`ِ فارسیِ بک‌اند
 * تنها چیزی است که می‌گوید چه کار باید کرد.
 */
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
  if (loading) return <p className="ad-muted">در حال بارگذاری…</p>
  if (error) return <p className="ad-note tone-bad">{error}</p>
  if (empty) return <EmptyState text={emptyText ?? 'چیزی برای نمایش نیست.'} />
  return <>{children}</>
}

/** بارگذاریِ ناهمگام با گاردِ پاسخِ کهنه (پاسخِ درخواستِ قبلی نباید تازه را بازنویسی کند). */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const run = useRef(0)

  const reload = useCallback(() => {
    const id = ++run.current
    setLoading(true)
    setError(null)
    fn()
      .then((d) => {
        if (id === run.current) setData(d)
      })
      .catch((e: unknown) => {
        if (id === run.current) setError(e instanceof Error ? e.message : 'خطای ناشناخته')
      })
      .finally(() => {
        if (id === run.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(reload, [reload])
  return { data, loading, error, reload, setData }
}

/**
 * جدول با قراردادِ نمای کارتی.
 *
 * `cards-on-mobile` و `data-label` روی هر سلول اجباری‌اند: زیرِ ۷۶۰px سرستون‌ها
 * ناپدید می‌شوند و بدونِ برچسب، هر سلول یک عددِ بی‌عنوان است. `audit-admin.mjs`
 * نبودشان را خطا می‌دهد.
 */
export function TableScroll({ children }: { children: ReactNode }) {
  return <div className="ad-table-scroll">{children}</div>
}

/** دکمه‌ی کنشِ داخلِ ردیف. */
export function RowAction({
  icon: Icon,
  label,
  onClick,
  danger,
  disabled,
}: {
  icon: LucideIcon
  label: string
  onClick: () => void
  danger?: boolean
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      className={`ad-row-action${danger ? ' danger' : ''}`}
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
    >
      <Icon size={15} />
      <span>{label}</span>
    </button>
  )
}

/** پنجره‌ی گفت‌وگو. `onClose` با Escape و کلیکِ بیرون هم صدا زده می‌شود. */
export function Dialog({
  title,
  onClose,
  children,
  footer,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="ad-overlay" onMouseDown={onClose}>
      <div className="ad-dialog" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal>
        <div className="ad-dialog-head">
          <h3>{title}</h3>
          <button type="button" className="ad-x" onClick={onClose} aria-label="بستن">
            ×
          </button>
        </div>
        <div className="ad-dialog-body">{children}</div>
        {footer ? <div className="ad-dialog-foot">{footer}</div> : null}
      </div>
    </div>
  )
}

/** فیلدِ فرم با برچسب و راهنمای **زیرِ** فیلد (نه placeholderِ فارسی روی dir=ltr). */
export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="ad-field">
      <span className="ad-field-label">{label}</span>
      {children}
      {hint ? <span className="ad-field-hint">{hint}</span> : null}
    </label>
  )
}

export function FieldGrid({ children }: { children: ReactNode }) {
  return <div className="ad-field-grid">{children}</div>
}
