import { type InputHTMLAttributes } from 'react'

/**
 * ورودیِ عددی با نمایشِ رقمِ فارسی و جداکننده‌ی سه‌رقمی — تا خواندنِ مبالغِ بزرگ آسان شود.
 *
 * چرا `type="text"` و نه `type="number"`: مرورگر روی input عددی نه رقمِ فارسی نشان
 * می‌دهد و نه اجازه‌ی ویرگولِ هزارگان می‌دهد. پس متن است، ولی فقط رقم (و در صورتِ نیاز
 * ممیز/منفی) می‌پذیرد و مقدارِ خام (لاتین، بدونِ ویرگول) را به بیرون می‌دهد — دقیقاً مثلِ
 * `e.target.value` قبلی، تا هندلرهای موجود با کمترین تغییر کار کنند.
 */
const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

function toLatin(s: string): string {
  return s
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
}

function toFa(s: string): string {
  return s.replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)])
}

/** رشته‌ی خام را برای نمایش گروه‌بندی و فارسی می‌کند (بدونِ تغییرِ خودِ مقدار). */
function formatDisplay(raw: string, group: boolean): string {
  if (raw === '' || raw === '-' || raw === '.') return toFa(raw)
  const neg = raw.startsWith('-')
  const body = neg ? raw.slice(1) : raw
  const dot = body.indexOf('.')
  const intPart = dot === -1 ? body : body.slice(0, dot)
  const decPart = dot === -1 ? '' : body.slice(dot) // شاملِ خودِ نقطه
  const groupedInt = group ? intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '،') : intPart
  return (neg ? '−' : '') + toFa(groupedInt + decPart)
}

/** ورودیِ کاربر را به رشته‌ی خامِ لاتین (فقط رقم/ممیز/منفی) تمیز می‌کند. */
function sanitize(input: string, allowDecimal: boolean, allowNegative: boolean): string {
  let s = toLatin(input).replace(/[،,]/g, '')
  const neg = allowNegative && /^\s*[-−]/.test(s)
  s = s.replace(/[^0-9.]/g, '')
  if (!allowDecimal) {
    s = s.replace(/\./g, '')
  } else {
    const i = s.indexOf('.')
    if (i !== -1) s = s.slice(0, i + 1) + s.slice(i + 1).replace(/\./g, '')
  }
  return (neg ? '-' : '') + s
}

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'type'> & {
  value: string | number | null | undefined
  /** مقدارِ خام (لاتین، بدونِ ویرگول) — همان چیزی که قبلاً از e.target.value می‌گرفتید. */
  onChange: (raw: string) => void
  /** جداکردنِ سه‌رقمی. برای سال یا شناسه‌ها false کنید تا ویرگول نخورد. */
  group?: boolean
  allowDecimal?: boolean
  allowNegative?: boolean
}

export function NumberInput({
  value,
  onChange,
  group = true,
  allowDecimal = false,
  allowNegative = false,
  inputMode,
  className,
  ...rest
}: Props) {
  const raw = value === null || value === undefined ? '' : String(value)
  return (
    <input
      {...rest}
      // کلاسِ num-input عدد را راست‌چین می‌کند (RTL)؛ کلاسِ فراخوان هم حفظ می‌شود.
      className={className ? `num-input ${className}` : 'num-input'}
      type="text"
      dir="ltr"
      inputMode={inputMode ?? (allowDecimal ? 'decimal' : 'numeric')}
      value={formatDisplay(raw, group)}
      onChange={(e) => onChange(sanitize(e.target.value, allowDecimal, allowNegative))}
    />
  )
}
