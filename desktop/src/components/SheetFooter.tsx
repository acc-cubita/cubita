import { AlertTriangle, Check, CheckCircle2, PencilLine } from 'lucide-react'

import { FormStatus } from './form/FormKit'
import { FitText } from './FitText'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** `clean` همه ذخیره شده، `dirty` تغییرِ ذخیره‌نشده هست، `err` ردیفی ذخیره نشد. */
export type SheetState = 'clean' | 'dirty' | 'err'

/**
 * نوارِ چسبنده‌ی پایینِ برگه‌های ویرایشِ درجا (تفصیلی سایر و بعدی‌ها) — هم‌خانواده‌ی نوارِ سند
 * ([BalanceFooter])، همان کلاس‌ها و همان چیدمان: **راست** دکمه‌ی ذخیره، بعد خانه‌ی وضعیت و دو شمارش
 * (ردیف‌های تازه، ردیف‌های ویرایش‌شده)، هر کدام با سرستونِ خاکستری.
 *
 * رنگِ وضعیت مثلِ سند روی لبه‌ی بالای نوار هم می‌نشیند: سبز همه ذخیره شده، زرد تغییرِ ذخیره‌نشده، قرمز
 * ردیفی که سرور نپذیرفت. `columns` نوار را ستون‌به‌ستون با برگه‌ی بالایش هم‌خط می‌کند (`useAlignToGrid`).
 */
export function SheetFooter({
  state,
  fresh,
  edited,
  submitting,
  message,
  submitLabel = 'ذخیره تغییرات',
  columns = false,
}: {
  state: SheetState
  fresh: number
  edited: number
  submitting: boolean
  message: { text: string; kind: 'ok' | 'err' } | null
  submitLabel?: string
  columns?: boolean
}) {
  const pending = fresh + edited
  return (
    <div className="jf-dock">
      <div className={`jf-foot jf-foot--${TONE[state]}${columns ? ' jf-foot--cols' : ''}`}>
        <button type="submit" className="btn-primary jf-submit" disabled={submitting} aria-keyshortcuts="Control+S">
          <Check size={18} aria-hidden="true" />
          {submitting ? 'در حال ذخیره…' : submitLabel}
          {!submitting && <span className="jf-submit-hint">(Ctrl+S)</span>}
        </button>
        <div className="jf-msg">
          <FormStatus msg={message} />
        </div>
        <div className={`jb-sum jb-sum--${TONE[state]}`} role="group" aria-label="وضعیتِ برگه">
          <div className="jb-stat jb-stat--a">
            <span className="jb-k">ردیفِ تازه</span>
            <div className="jb-body">
              <FitText className="jb-v" text={fa(fresh)} />
            </div>
          </div>
          <div className="jb-stat jb-stat--b">
            <span className="jb-k">ویرایش‌شده</span>
            <div className="jb-body">
              <FitText className="jb-v" text={fa(edited)} />
            </div>
          </div>
          <div className="jb-stat jb-stat--diff" aria-live="polite">
            <span className="jb-k">وضعیت</span>
            <div className="jb-body">
              <FitText className="jb-v" min={0.6} text={`${state}-${pending}`}>
                {state === 'clean' ? (
                  <>
                    <CheckCircle2 aria-hidden="true" /> همه ذخیره شده
                  </>
                ) : state === 'err' ? (
                  <>
                    <AlertTriangle aria-hidden="true" /> ذخیره نشد
                  </>
                ) : (
                  <>
                    <PencilLine aria-hidden="true" /> {fa(pending)} تغییر
                  </>
                )}
              </FitText>
              {state !== 'clean' && (
                <FitText className="jb-sub" min={0.75} text={state}>
                  {state === 'err' ? 'ردیفِ قرمز را ببینید' : 'ذخیره‌نشده'}
                </FitText>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

//: همان کلاس‌های رنگِ نوارِ سند: سبز، زرد (تازه)، قرمز.
const TONE: Record<SheetState, string> = { clean: 'ok', dirty: 'warn', err: 'err' }
