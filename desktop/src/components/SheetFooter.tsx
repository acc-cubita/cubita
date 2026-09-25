import { AlertTriangle, CheckCircle2, PencilLine } from 'lucide-react'

import { DocFooter } from './DocFooter'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** `clean` همه ذخیره شده، `dirty` تغییرِ ذخیره‌نشده هست، `err` ردیفی ذخیره نشد. */
export type SheetState = 'clean' | 'dirty' | 'err'

//: همان رنگ‌های نوارِ سند: سبز، زرد (تازه)، قرمز.
const TONE: Record<SheetState, string> = { clean: 'ok', dirty: 'warn', err: 'err' }

/**
 * نوارِ پایینِ برگه‌های ویرایشِ درجا (تفصیلی سایر و بعدی‌ها) — [DocFooter] با دکمه‌ی ذخیره، شمارِ
 * ردیف‌های تازه و ویرایش‌شده، و وضعیت: سبز همه ذخیره شده، زرد تغییرِ ذخیره‌نشده، قرمز ردیفی که سرور
 * نپذیرفت.
 */
export function SheetFooter({
  state,
  fresh,
  edited,
  submitting,
  message,
  submitLabel = 'ذخیره تغییرات',
  columns = false,
  labels = ['ردیفِ تازه', 'ویرایش‌شده'],
}: {
  state: SheetState
  fresh: number
  edited: number
  submitting: boolean
  message: { text: string; kind: 'ok' | 'err' } | null
  submitLabel?: string
  columns?: boolean
  /** برچسبِ دو عدد — برگه‌ای که خانه می‌شمارد نه ردیف (بودجه) «خانه‌ی تازه» می‌گوید. */
  labels?: [string, string]
}) {
  const pending = fresh + edited
  return (
    <DocFooter
      tone={TONE[state]}
      columns={columns}
      submitting={submitting}
      submitLabel={submitLabel}
      submittingLabel="در حال ذخیره…"
      shortcut
      message={message}
      groupLabel="وضعیتِ برگه"
      statusLabel="وضعیت"
      statusKey={`${state}-${pending}`}
      status={
        state === 'clean' ? (
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
        )
      }
      sub={state === 'clean' ? undefined : { main: state === 'err' ? 'ردیفِ قرمز را ببینید' : 'ذخیره‌نشده' }}
      stats={[
        { label: labels[0], value: fa(fresh), className: 'jb-stat--a' },
        { label: labels[1], value: fa(edited), className: 'jb-stat--b' },
      ]}
    />
  )
}
