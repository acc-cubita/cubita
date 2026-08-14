import { useEffect, useState, type ReactNode } from 'react'
import { Check, ChevronLeft, ChevronRight } from 'lucide-react'

/** یک مرحله‌ی ویزارد. بدنه‌ی مرحله معمولاً روی state مشترکِ بیرونی (هوکِ draft) رندر
 *  می‌شود، پس جابه‌جایی بین مراحل داده را از دست نمی‌دهد. */
export interface WizardStep {
  key: string
  title: string
  subtitle?: string
  body: ReactNode
  /** اگر false باشد، «تایید و ادامه» غیرفعال است (اعتبارسنجیِ مرحله). پیش‌فرض true. */
  canAdvance?: boolean
  /** راهنمای درون‌خطی وقتی نمی‌شود جلو رفت. */
  blockHint?: string
}

/** چارچوبِ کارِ مرحله‌ای (ویزارد) برای «نسخه‌ی جدید». استپرِ شماره‌دار + بدنه‌ی مرحله‌ی
 *  فعال + پنلِ پیش‌نمایشِ کناری + فوترِ ناوبری. فقط مرحله‌ی فعال به DOM می‌رود؛ بازگشت به
 *  مراحلِ گذشته آزاد است، پرش به جلو نه (باید هر مرحله را تایید کنی). قابل‌استفاده برای هر
 *  کاری؛ اولین مصرف‌کننده SalesInvoiceWizard است. */
export function TaskFlow({
  title,
  steps,
  preview,
  onSubmit,
  submitLabel = 'ثبت',
  submitting,
  message,
  resetKey,
  allowJump = false,
}: {
  title: string
  steps: WizardStep[]
  preview?: ReactNode
  onSubmit: () => void
  submitLabel?: string
  submitting?: boolean
  message?: ReactNode
  /** با تغییرِ این مقدار، ویزارد به مرحله‌ی اول برمی‌گردد (مثلاً بعد از ثبتِ موفق). */
  resetKey?: unknown
  /** پرشِ آزاد بین مراحل (برای کارهای غیرترتیبی مثلِ مؤدیان: تنظیمات/تست/ارسالِ مستقل). */
  allowJump?: boolean
}) {
  const [active, setActive] = useState(0)
  useEffect(() => {
    setActive(0)
  }, [resetKey])

  const step = steps[active]
  const isLast = active === steps.length - 1
  const canNext = step.canAdvance !== false

  function next() {
    if (isLast) {
      onSubmit()
      return
    }
    if (canNext) setActive((i) => Math.min(i + 1, steps.length - 1))
  }
  function back() {
    setActive((i) => Math.max(i - 1, 0))
  }
  function goto(i: number) {
    // به‌طورِ پیش‌فرض فقط بازگشت (یا ماندن) آزاد است — نه پرش به مرحله‌ی تاییدنشده‌ی جلوتر.
    // در حالتِ allowJump (کارهای غیرترتیبی) پرش به هر مرحله آزاد است.
    if (allowJump || i <= active) setActive(i)
  }

  return (
    <section className="taskflow">
      <div className="taskflow-head">
        <h2 className="taskflow-title">{title}</h2>
        <ol className="taskflow-steps">
          {steps.map((s, i) => {
            const state = i < active ? 'done' : i === active ? 'active' : 'todo'
            return (
              <li key={s.key} className={`taskflow-step is-${state}`}>
                <button
                  type="button"
                  className="taskflow-step-btn"
                  onClick={() => goto(i)}
                  disabled={!allowJump && i > active}
                  aria-current={i === active ? 'step' : undefined}
                >
                  <span className="taskflow-step-num">
                    {state === 'done' ? <Check size={15} /> : toFa(i + 1)}
                  </span>
                  <span className="taskflow-step-label">{s.title}</span>
                </button>
              </li>
            )
          })}
        </ol>
        <div className="taskflow-step-mobile">
          مرحله {toFa(active + 1)} از {toFa(steps.length)} — {step.title}
        </div>
      </div>

      <div className="taskflow-main">
        <div className="taskflow-body">
          {step.subtitle && <p className="taskflow-step-sub">{step.subtitle}</p>}
          {step.body}
          {!canNext && step.blockHint && <p className="taskflow-block-hint">{step.blockHint}</p>}
          {message && <div className="taskflow-message">{message}</div>}
        </div>
        {preview && <aside className="taskflow-preview">{preview}</aside>}
      </div>

      <div className="taskflow-footer">
        <button type="button" className="taskflow-back" onClick={back} disabled={active === 0}>
          <ChevronRight size={16} /> قبلی
        </button>
        <div className="taskflow-footer-spacer" />
        <button
          type="button"
          className="btn-primary taskflow-next"
          onClick={next}
          disabled={(!isLast && !canNext) || !!submitting}
        >
          {isLast ? (
            submitLabel
          ) : (
            <>
              تایید و ادامه <ChevronLeft size={16} />
            </>
          )}
        </button>
      </div>
    </section>
  )
}

function toFa(n: number): string {
  return n.toLocaleString('fa-IR')
}
