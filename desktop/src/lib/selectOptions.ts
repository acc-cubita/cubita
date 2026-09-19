import { Children, isValidElement, type ReactNode } from 'react'

/**
 * منطقِ خالصِ `SearchSelect` — جدا از کامپوننت تا هم سنجیدنی باشد و هم
 * fast-refresh فایلِ کامپوننت را ترک نکند.
 */

/** از این تعداد گزینه به بالا، جست‌وجو. پایین‌تر، `<select>`ِ بومی. */
export const SEARCH_THRESHOLD = 8

export interface Opt {
  value: string
  label: string
  disabled?: boolean
}

/**
 * فرزندانِ `<option>` (و `<optgroup>`) را به فهرستِ ساده تبدیل می‌کند.
 *
 * اگر شکلی از فرزند فهمیده نشود، آن فهرست **بی‌صدا خالی** می‌شود — نه خطا
 * می‌دهد و نه به چشم می‌آید. برای همین `optgroup` صریح باز می‌شود و تست دارد.
 */
export function flatten(children: ReactNode): Opt[] {
  const out: Opt[] = []
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return
    const props = child.props as {
      value?: string | number
      children?: ReactNode
      disabled?: boolean
    }
    if (child.type === 'optgroup') {
      out.push(...flatten(props.children))
      return
    }
    if (child.type !== 'option') return
    const label =
      typeof props.children === 'string' ? props.children : String(props.children ?? '')
    out.push({ value: String(props.value ?? ''), label, disabled: props.disabled })
  })
  return out
}

/**
 * آیا این فهرست جست‌وجو می‌خواهد؟
 *
 * `multiple` و `size` رفتارِ کاملاً دیگری دارند و `SearchSelect` ادعایشان را
 * نمی‌کند؛ آن‌ها همیشه `<select>`ِ بومی می‌مانند.
 */
export function shouldSearch(
  optionCount: number,
  opts: { multiple?: boolean; size?: number } = {},
): boolean {
  if (opts.multiple || opts.size) return false
  return optionCount >= SEARCH_THRESHOLD
}
