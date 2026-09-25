import { AlertTriangle, CheckCircle2, Scale } from 'lucide-react'

import { DocFooter } from './DocFooter'
import type { BalanceState } from '../lib/balanceState'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * نوارِ پایینِ هر سندِ بدهکار/بستانکار — گریدِ «سند حسابداری» و هر صفحه‌ی هم‌سبکش (مانده اول دوره):
 * دکمه‌ی ثبت، جمعِ بدهکار، جمعِ بستانکار، و وضعیتِ توازن ([DocFooter]).
 *
 * سبز = متوازن، قرمز = نامتوازن (با مبلغِ اختلاف و اینکه کدام طرف بیشتر است، تا حسابدار بداند ردیفِ بعد
 * بدهکار است یا بستانکار)، accent = اختلافی که خودکار بسته می‌شود (`auto` — «به سرمایه»)، خاکستری = هنوز
 * مبلغی نیست. وضعیت `aria-live` دارد تا صفحه‌خوان هم بشنودش. `columns` در گریدِ سند: دکمه زیرِ
 * «ردیف + حساب»، وضعیت زیرِ «شرح ردیف»، و هر جمع دقیقاً زیرِ ستونِ خودش.
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
  const diff = Math.abs(totalDebit - totalCredit)
  const side = state === 'auto' && autoNote ? autoNote : totalDebit > totalCredit ? 'بدهکار بیشتر' : 'بستانکار بیشتر'
  return (
    <DocFooter
      tone={state}
      columns={columns}
      submitting={submitting}
      submitLabel={submitLabel}
      shortcut={shortcut}
      message={message}
      groupLabel="جمعِ سند"
      statusLabel="وضعیتِ توازن"
      statusKey={state}
      status={
        state === 'empty' ? (
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
        )
      }
      //: در موبایل فقط مبلغ: خانه‌ی ۱۰۰ پیکسلی جای «بدهکار بیشتر» را ندارد، و طرفِ بزرگ‌تر از دو جمعِ کنارش پیداست.
      sub={state === 'err' || state === 'auto' ? { main: fa(diff), side } : undefined}
      stats={[
        { label: 'جمع بدهکار', value: fa(totalDebit), className: 'jb-stat--debit' },
        { label: 'جمع بستانکار', value: fa(totalCredit), className: 'jb-stat--credit' },
      ]}
    />
  )
}
