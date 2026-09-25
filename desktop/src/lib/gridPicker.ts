/**
 * بازکردنِ انتخاب‌گرِ یک خانه‌ی گرید از صفحه‌کلید (F4 و Alt+↓).
 *
 * سه شکل: کادرِ جست‌وجوی درجای حساب (`AccountCombo`)، و دو شکلِ `SearchSelect` — برای
 * فهرستِ کوتاه `<select>`ِ بومی، برای بلند دکمه‌ی پاپ‌آور (`.item-picker-trigger`). همه
 * این‌جا یکی می‌شوند تا گرید و سربرگ لازم نباشد بدانند کدام رندر شده. `true` یعنی
 * انتخاب‌گری پیدا و باز شد.
 */
export function openCellPicker(cell: Element | null | undefined): boolean {
  if (!cell) return false
  //: خانه‌ی حساب کادرِ جست‌وجوی درجاست (`AccountCombo`): کلیک فهرستِ کاملش را باز می‌کند.
  const combo = cell.querySelector<HTMLInputElement>('input[role="combobox"]:not([disabled])')
  if (combo) {
    combo.focus()
    if (combo.getAttribute('aria-expanded') !== 'true') combo.click()
    return true
  }
  const trigger = cell.querySelector<HTMLButtonElement>('.item-picker-trigger:not([disabled])')
  if (trigger) {
    trigger.focus()
    if (trigger.getAttribute('aria-expanded') !== 'true') trigger.click()
    return true
  }
  const select = cell.querySelector<HTMLSelectElement>('select:not([disabled])')
  if (select) {
    select.focus()
    try {
      //: `showPicker` در Chromium هست؛ بی کنشِ مستقیمِ کاربر ممکن است خطا بدهد — آن‌وقت
      //: فوکوس کافی است و Alt+↓ِ بومی همان را باز می‌کند.
      select.showPicker?.()
    } catch {
      /* فوکوس ماند */
    }
    return true
  }
  return false
}
