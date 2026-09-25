import type { PointerEvent, ReactNode } from 'react'
import { X } from 'lucide-react'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * قطعه‌های مشترکِ جدولِ اکسل‌مانند (`.xl-grid`) — گریدِ ثبتِ سند و فهرستِ اسناد.
 *
 * ظاهر همه در CSS است (سرستونِ خاکستری، خطوطِ ظریفِ افقی و عمودی، hover و انتخابِ ردیف)؛
 * این‌جا فقط دو تکه‌ی رفتاری: لبه‌ی کشیدنیِ عرضِ ستون، و نوارِ وضعیتِ انتخاب.
 */

/** لبه‌ی کشیدنیِ سرستون. ماوس‌محور است؛ دوبار کلیک همه‌ی عرض‌ها را به پیش‌فرض برمی‌گرداند. */
export function ColResizer({
  onBegin,
  onReset,
}: {
  onBegin: (e: PointerEvent<HTMLElement>) => void
  onReset: () => void
}) {
  return (
    <span
      className="xl-resize"
      aria-hidden="true"
      title="کشیدن: عرضِ ستون — دوبار کلیک: عرضِ پیش‌فرضِ همه"
      onPointerDown={onBegin}
      onDoubleClick={onReset}
    />
  )
}

/**
 * نوارِ وضعیتِ انتخاب — همان «جمع / تعداد»ِ پایینِ پنجره‌ی اکسل: چند ردیف انتخاب شده و
 * جمعِ مبالغشان، با کنش‌های همان انتخاب. فقط وقتی چیزی انتخاب شده.
 */
export function SelectionBar({
  count,
  unit,
  onClear,
  children,
}: {
  count: number
  unit: string
  onClear: () => void
  children?: ReactNode
}) {
  return (
    <div className="xl-selbar" role="status">
      <strong>
        {fa(count)} {unit} انتخاب شد
      </strong>
      {children}
      <button type="button" className="xl-selbar-clear" onClick={onClear} title="لغوِ انتخاب (Esc)">
        <X size={14} aria-hidden="true" /> لغوِ انتخاب
      </button>
    </div>
  )
}
