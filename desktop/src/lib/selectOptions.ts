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
 * متنِ یک گره‌ی React را همان‌طور که کاربر می‌بیند بیرون می‌کشد.
 *
 * **چرا `String(children)` کافی نیست.** الگوی رایجِ این مخزن
 * `<option>{a.code} — {a.name}</option>` است و ۵۴ جا تکرار شده. آنجا
 * `props.children` یک **آرایه** است (`['1007', ' — ', 'بانک صادرات']`) و
 * `String()` رویش `Array.prototype.toString` را صدا می‌زند، یعنی اعضا را با
 * **ویرگول** می‌چسباند: `«1007, — ,بانک صادرات»`. همین رشته هم در دکمه‌ی
 * انتخاب‌گر دیده می‌شد و هم چیزی بود که `textMatches` رویش جست‌وجو می‌کرد.
 *
 * عنصرِ تودرتو (مثلِ `<b>`) هم باز می‌شود تا برچسب هرگز `[object Object]` نشود.
 */
function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement(node)) return textOf((node.props as { children?: ReactNode }).children)
  return ''
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
    out.push({ value: String(props.value ?? ''), label: textOf(props.children), disabled: props.disabled })
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
