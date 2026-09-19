import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { HelpCircle, Plus, X } from 'lucide-react'

/**
 * اجزای فرمِ سازمانی (`ef-*`) — برچسب، راهنمای شناور، انتخاب با دکمه‌ی «+»، تب و نوارِ
 * عملیات. اولین مصرف‌کننده «قرارداد جدید» است؛ هر فرمِ بلندِ دیگری هم می‌تواند همین‌ها را
 * بگیرد تا ارتفاعِ فیلدها، جای راهنما و ترتیبِ دکمه‌ها در همه‌جا یکی شود.
 *
 * قاعده‌ها:
 * * راهنمای طولانی زیرِ فیلد نمی‌نشیند؛ آیکونِ «؟» کنارِ برچسب است و با hover، فوکوسِ
 *   کیبورد یا لمس باز می‌شود. متنِ زیرِ فیلد فقط برای پیامی است که همین حالا لازم است.
 * * هر برچسب با `htmlFor` به کنترلش وصل است، نه با پیچیدنِ کنترل در `<label>`: برچسبی که
 *   دکمه‌ی «؟» هم دارد، اولین کنترلِ درونش را هدف می‌گرفت و کلیک روی متن راهنما را باز می‌کرد.
 */

/** آیکونِ «؟» با راهنمای شناور. */
export function InfoTip({ text }: { text: string }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  return (
    <span className="ef-tip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="ef-tip-btn"
        aria-label="راهنما"
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
      >
        <HelpCircle size={14} />
      </button>
      {open && (
        <span role="tooltip" id={id} className="ef-tip-bubble">
          {text}
        </span>
      )}
    </span>
  )
}

/**
 * یک خانه‌ی گریدِ فرم: برچسب (+ ستاره‌ی الزامی + «؟») و کنترل.
 * `children` اگر تابع باشد، شناسه‌ی کنترل را می‌گیرد تا برچسب به آن وصل شود.
 */
export function FormField({
  id: fixedId,
  label,
  required,
  tip,
  message,
  span,
  children,
}: {
  /** شناسه‌ی ثابتِ کنترل، وقتی صفحه باید خودش به آن برسد (مثلاً فوکوس بعد از خطا). */
  id?: string
  label: string
  required?: boolean
  tip?: string
  /** پیامِ لحظه‌ای زیرِ فیلد (هشدار یا نتیجه‌ی جست‌وجو) — نه راهنمای ثابت. */
  message?: ReactNode
  /** تمامِ ردیف را بگیرد. پهنای دوستونه عمداً نیست: گریدِ یک‌ستونه‌ی موبایل را سرریز می‌کرد. */
  span?: 'full'
  children: ReactNode | ((id: string) => ReactNode)
}) {
  const autoId = useId()
  const id = fixedId ?? autoId
  return (
    <div className={`ef-field${span === 'full' ? ' ef-span-full' : ''}`}>
      <div className="ef-label">
        <label htmlFor={id}>
          {label}
          {required && (
            <span className="ef-req" aria-hidden="true">
              *
            </span>
          )}
        </label>
        {tip && <InfoTip text={tip} />}
      </div>
      {typeof children === 'function' ? children(id) : children}
      {message && (
        <p className="ef-message" role="status">
          {message}
        </p>
      )}
    </div>
  )
}

/** گریدِ منظمِ فرم: سه ستون در عرضِ کافی، دو ستون در عرضِ متوسط، یک ستون در موبایل. */
export function FormGrid({ children }: { children: ReactNode }) {
  return <div className="ef-grid">{children}</div>
}

/**
 * انتخاب از فهرست با دکمه‌ی «+» کنارش، به‌جای دکمه‌ی متنیِ زیرِ فیلد. دکمه فقط پنلِ
 * ساختِ درجا را باز و بسته می‌کند؛ خودِ پنل را صفحه نشان می‌دهد.
 */
export function SelectWithAdd({
  id,
  value,
  onChange,
  options,
  addLabel,
  adding,
  onToggleAdd,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  /** متنِ دسترس‌پذیرِ دکمه، مثلِ «افزودن شغل تازه». */
  addLabel: string
  adding: boolean
  onToggleAdd: () => void
}) {
  return (
    <div className="ef-select-add">
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">— انتخاب کنید —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        className={`ef-icon-btn${adding ? ' is-on' : ''}`}
        onClick={onToggleAdd}
        aria-label={adding ? 'بستنِ فرمِ ساخت' : addLabel}
        aria-expanded={adding}
        title={adding ? 'انصراف' : addLabel}
      >
        {adding ? <X size={16} /> : <Plus size={16} />}
      </button>
    </div>
  )
}

export type FormTab = { key: string; label: string; badge?: string }

/**
 * نوارِ تب با نقش‌های ARIA و کلیدهای جهت‌نما. در راست‌به‌چپ «چپ» یعنی تبِ بعدی —
 * همان جهتی که چشم در نوار جلو می‌رود.
 */
export function FormTabs({
  tabs,
  active,
  onChange,
  label,
  children,
}: {
  tabs: FormTab[]
  active: string
  onChange: (key: string) => void
  label: string
  /** محتوای تبِ فعال. */
  children: ReactNode
}) {
  const base = useId()
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const index = Math.max(0, tabs.findIndex((t) => t.key === active))

  function onKeyDown(e: KeyboardEvent) {
    const step = ({ ArrowLeft: 1, ArrowRight: -1 } as Record<string, number>)[e.key]
    let next = index
    if (step) next = (index + step + tabs.length) % tabs.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = tabs.length - 1
    else return
    e.preventDefault()
    onChange(tabs[next].key)
    refs.current[next]?.focus()
  }

  return (
    <>
      <div className="ef-tabs" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
        {tabs.map((t, i) => {
          const selected = i === index
          return (
            <button
              key={t.key}
              ref={(el) => {
                refs.current[i] = el
              }}
              type="button"
              role="tab"
              id={`${base}-tab-${t.key}`}
              aria-controls={`${base}-panel`}
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              className="ef-tab"
              onClick={() => onChange(t.key)}
            >
              {t.label}
              {t.badge && <span className="ef-tab-badge">{t.badge}</span>}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${tabs[index]?.key}`} className="ef-tab-panel">
        {children}
      </div>
    </>
  )
}

/** سرِ هر تب: عنوان و «؟» در یک سو، دکمه‌های همان تب در سوی دیگر. */
export function TabHead({ title, tip, actions }: { title: string; tip?: string; actions?: ReactNode }) {
  return (
    <div className="ef-tab-head">
      <div className="ef-tab-title">
        <h3>{title}</h3>
        {tip && <InfoTip text={tip} />}
      </div>
      {actions && <div className="ef-tab-actions">{actions}</div>}
    </div>
  )
}

/** نوارِ عملیاتِ چسبیده به پایینِ فرم: وضعیت در یک سو، دکمه‌ها در سوی دیگر. */
export function ActionBar({ status, children }: { status?: ReactNode; children: ReactNode }) {
  return (
    <div className="ef-actions">
      <div className="ef-actions-status">{status}</div>
      <div className="ef-actions-buttons">{children}</div>
    </div>
  )
}
