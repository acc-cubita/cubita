import type { ReactNode } from 'react'
import { Check } from 'lucide-react'

import { FormStatus } from './form/FormKit'
import { FitText } from './FitText'

export interface FooterStat {
  label: string
  value: string
  /** جای خانه در چیدمانِ ستونی (`jb-stat--debit`/`--credit` یا `--a`/`--b`). */
  className: string
}

/**
 * نوارِ چسبنده‌ی پایینِ صفحه‌های هم‌سبکِ «سند حسابداری» — پایه‌ی مشترکِ نوارِ سند ([BalanceFooter])،
 * برگه‌های ویرایشِ درجا ([SheetFooter]) و پیش‌نمایشِ سندهای خودکار (تسعیرِ ارز).
 *
 * **راست** دکمه‌ی اصلی، بعد یک خانه‌ی وضعیت و دو خانه‌ی عدد — هر کدام با سرستونِ خاکستری، مثلِ خانه‌های
 * گرید. رنگِ وضعیت (`tone`: `ok` سبز، `err` قرمز، `warn` زرد، `auto` accent، `empty` خاکستری) روی خانه‌ی
 * وضعیت و لبه‌ی بالای کلِ نوار می‌نشیند. عددی که در خانه جا نشود کوچک می‌شود، نه خانه بزرگ (`FitText`).
 *
 * `columns` نوار را ستون‌به‌ستون با گریدِ بالایش هم‌خط می‌کند (`useAlignToGrid`): دکمه در خانه‌ی اول، وضعیت
 * در دوم، دو عدد در سوم و چهارم؛ `statusEnd` وضعیت را به خانه‌ی پنجم می‌برد (وقتی ستونِ آخرِ گرید خودش
 * «اختلاف» است — تسعیر).
 *
 * **چرا دو لایه (`jf-dock` و `jf-foot`).** لایه‌ی بیرونی می‌چسبد و ظرفِ `scroll-state` است؛ لایه‌ی
 * درونی ظاهر است و وقتی نوار واقعاً چسبیده، گوشه‌های پایینش صاف می‌شود. پرس‌وجوی `scroll-state` فقط
 * فرزندان را می‌تواند رنگ کند، نه خودِ ظرف را.
 */
export function DocFooter({
  tone,
  columns = false,
  statusEnd = false,
  submitting,
  submitLabel,
  submittingLabel = 'در حال ثبت…',
  submitDisabled = false,
  shortcut = false,
  message,
  groupLabel,
  statusLabel,
  status,
  statusKey,
  sub,
  stats,
}: {
  tone: string
  columns?: boolean
  statusEnd?: boolean
  submitting: boolean
  submitLabel: string
  submittingLabel?: string
  submitDisabled?: boolean
  shortcut?: boolean
  message: { text: string; kind: 'ok' | 'err' } | null
  groupLabel: string
  statusLabel: string
  /** متنِ وضعیت با آیکونش. */
  status: ReactNode
  /** کلیدِ سنجشِ دوباره‌ی اندازه‌ی متنِ وضعیت. */
  statusKey: string
  /** خطِ دومِ وضعیت؛ `side` در موبایل پنهان می‌شود (خانه‌ی باریک). */
  sub?: { main: string; side?: string }
  stats: [FooterStat, FooterStat]
}) {
  const cls = ['jf-foot', `jf-foot--${tone}`, columns && 'jf-foot--cols', statusEnd && 'jf-foot--status-end']
  return (
    <div className="jf-dock">
      <div className={cls.filter(Boolean).join(' ')}>
        <button
          type="submit"
          className="btn-primary jf-submit"
          disabled={submitting || submitDisabled}
          aria-keyshortcuts={shortcut ? 'Control+S' : undefined}
        >
          <Check size={18} aria-hidden="true" />
          {submitting ? submittingLabel : submitLabel}
          {shortcut && !submitting && <span className="jf-submit-hint">(Ctrl+S)</span>}
        </button>
        <div className="jf-msg">
          <FormStatus msg={message} />
        </div>
        <div className={`jb-sum jb-sum--${tone}`} role="group" aria-label={groupLabel}>
          {stats.map((s) => (
            <div key={s.className} className={`jb-stat ${s.className}`}>
              <span className="jb-k">{s.label}</span>
              <div className="jb-body">
                <FitText className="jb-v" text={s.value} />
              </div>
            </div>
          ))}
          <div className="jb-stat jb-stat--diff" aria-live="polite">
            <span className="jb-k">{statusLabel}</span>
            <div className="jb-body">
              <FitText className="jb-v" min={0.6} text={statusKey}>
                {status}
              </FitText>
              {sub && (
                <FitText className="jb-sub" min={0.75} text={`${sub.main} ${sub.side ?? ''}`}>
                  {sub.main}
                  {sub.side && <span className="jb-sub-side"> {sub.side}</span>}
                </FitText>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
