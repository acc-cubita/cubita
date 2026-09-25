import { AlertTriangle, Check, CheckCircle2, Scale } from 'lucide-react'

import { FormStatus } from './form/FormKit'
import { FitText } from './FitText'
import type { BalanceState } from '../lib/balanceState'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * نوارِ چسبنده‌ی پایینِ هر سندِ بدهکار/بستانکار — گریدِ «سند حسابداری» و هر صفحه‌ی هم‌سبکش (مانده اول
 * دوره): **راست** دکمه‌ی ثبت، **چپ** وضعیتِ توازن و جمع‌ها.
 *
 * جای `ActionBar`ِ عمومی، چون این‌جا نوار خودش محتوای اصلی است: رنگِ توازن روی لبه‌ی بالای کلِ نوار
 * می‌نشیند و دکمه‌ی ثبت بزرگ‌تر از دکمه‌ی فرم‌های دیگر است. ظاهرش هم‌خانواده‌ی جدولِ اکسلیِ ردیف‌هاست:
 * جمع‌ها خانه‌های یک جدول‌اند، هر کدام با سرستونِ خاکستری. `shortcut` «(Ctrl+S)» را روی دکمه می‌نویسد —
 * فقط جایی که آن میان‌بر واقعاً هست.
 *
 * `columns` نوار را ستون‌به‌ستون با گریدِ بالایش هم‌خط می‌کند (`useAlignToGrid`، کلاسِ `jf-foot--cols`):
 * دکمه زیرِ «ردیف + حساب» و هر جمع دقیقاً زیرِ ستونِ خودش.
 *
 * **چرا دو لایه (`jf-dock` و `jf-foot`).** لایه‌ی بیرونی می‌چسبد و ظرفِ `scroll-state`
 * است؛ لایه‌ی درونی ظاهر است و وقتی نوار واقعاً چسبیده، گوشه‌های پایینش صاف می‌شود.
 * پرس‌وجوی `scroll-state` فقط فرزندان را می‌تواند رنگ کند، نه خودِ ظرف را.
 */
export function BalanceFooter({
  totalDebit,
  totalCredit,
  state,
  submitting,
  message,
  submitLabel = 'ثبت سند',
  shortcut = false,
  columns = false,
  autoNote,
}: {
  totalDebit: number
  totalCredit: number
  state: BalanceState
  submitting: boolean
  message: { text: string; kind: 'ok' | 'err' } | null
  submitLabel?: string
  shortcut?: boolean
  columns?: boolean
  /** در وضعیتِ `auto`: اختلاف کجا بسته می‌شود — «به سرمایه». */
  autoNote?: string
}) {
  return (
    <div className="jf-dock">
      <div className={`jf-foot jf-foot--${state}${columns ? ' jf-foot--cols' : ''}`}>
        <button
          type="submit"
          className="btn-primary jf-submit"
          disabled={submitting}
          aria-keyshortcuts={shortcut ? 'Control+S' : undefined}
        >
          <Check size={18} aria-hidden="true" />
          {submitting ? 'در حال ثبت…' : submitLabel}
          {shortcut && !submitting && <span className="jf-submit-hint">(Ctrl+S)</span>}
        </button>
        <div className="jf-msg">
          <FormStatus msg={message} />
        </div>
        <BalanceSummary totalDebit={totalDebit} totalCredit={totalCredit} state={state} autoNote={autoNote} />
      </div>
    </div>
  )
}

/**
 * جمع‌ها و وضعیتِ توازن: جمعِ بدهکار، جمعِ بستانکار، و «متوازن / نامتوازن».
 *
 * سبز = متوازن، قرمز = نامتوازن (با مبلغِ اختلاف و اینکه کدام طرف بیشتر است، تا حسابدار
 * بداند ردیفِ بعد بدهکار است یا بستانکار)، رنگِ accent = اختلافی که خودکار بسته می‌شود،
 * خاکستری = هنوز مبلغی نیست. وضعیت `aria-live` دارد تا صفحه‌خوان هم بشنودش.
 *
 * **سه خانه اندازه‌ی ثابت دارند** (CSS) و با تایپِ هر رقم بزرگ و کوچک نمی‌شوند — نوار
 * جلوی چشمِ حسابدار است و هر لرزشش حواس را می‌بَرد. عددی که در خانه جا نشود به‌جای
 * پهن‌کردنِ خانه، به نسبت کوچک می‌شود (`FitText`).
 */
function BalanceSummary({
  totalDebit,
  totalCredit,
  state,
  autoNote,
}: {
  totalDebit: number
  totalCredit: number
  state: BalanceState
  autoNote?: string
}) {
  const diff = Math.abs(totalDebit - totalCredit)
  const side = state === 'auto' && autoNote ? autoNote : totalDebit > totalCredit ? 'بدهکار بیشتر' : 'بستانکار بیشتر'
  return (
    <div className={`jb-sum jb-sum--${state}`} role="group" aria-label="جمعِ سند">
      <div className="jb-stat jb-stat--debit">
        <span className="jb-k">جمع بدهکار</span>
        <div className="jb-body">
          <FitText className="jb-v" text={fa(totalDebit)} />
        </div>
      </div>
      <div className="jb-stat jb-stat--credit">
        <span className="jb-k">جمع بستانکار</span>
        <div className="jb-body">
          <FitText className="jb-v" text={fa(totalCredit)} />
        </div>
      </div>
      <div className="jb-stat jb-stat--diff" aria-live="polite">
        <span className="jb-k">وضعیتِ توازن</span>
        <div className="jb-body">
          {/* این خانه گاهی باریک است (زیرِ «شرح ردیف») — وضعیت هم مثلِ عددها کوچک می‌شود. */}
          <FitText className="jb-v" min={0.6} text={state}>
            {state === 'empty' ? (
              'مبلغی وارد نشده'
            ) : state === 'ok' ? (
              <>
                <CheckCircle2 aria-hidden="true" /> متوازن
              </>
            ) : state === 'auto' ? (
              <>
                <Scale aria-hidden="true" /> تراز خودکار
              </>
            ) : (
              <>
                <AlertTriangle aria-hidden="true" /> نامتوازن
              </>
            )}
          </FitText>
          {/* در موبایل فقط مبلغ: خانه‌ی ۱۰۰ پیکسلی جای «بدهکار بیشتر» را ندارد، و طرفِ بزرگ‌تر از دو
              جمعِ کنارش پیداست. */}
          {(state === 'err' || state === 'auto') && (
            <FitText className="jb-sub" min={0.75} text={`${fa(diff)} ${side}`}>
              {fa(diff)}
              <span className="jb-sub-side"> {side}</span>
            </FitText>
          )}
        </div>
      </div>
    </div>
  )
}
