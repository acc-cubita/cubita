/**
 * ناوبریِ صفحه‌کلید در گریدِ سندِ حسابداری — منطقِ خالص، بی DOM و بی React.
 *
 * **چرا جدا از کامپوننت.** محیطِ تستِ این پروژه `node` است و DOM ندارد
 * (`desktop/vitest.config.ts`). اگر «کدام سلولِ بعدی» داخلِ کامپوننت می‌ماند،
 * تنها راهِ سنجشش رندرِ واقعی بود — یعنی عملاً سنجیده نمی‌شد. این‌جا یک تابعِ
 * خالص است و مستقیم تست می‌شود.
 *
 * **مدلِ ستون‌ها پویاست.** ستونِ ارزی، تفصیلی و پیگیری فقط وقتی رندر می‌شوند که
 * لازم باشند (همان قاعده‌ی فرمِ کلاسیک). پس ناوبری نمی‌تواند شماره‌ی ستونِ ثابت
 * فرض کند — فهرستِ ستون‌ها ورودیِ این ماژول است.
 */

/** شناسه‌ی ستون‌های قابلِ ویرایش. ترتیبِ آرایه = ترتیبِ حرکتِ منطقی. */
export type ColId =
  | 'account'
  | 'fx'
  | 'tafsili'
  | 'description'
  | 'debit'
  | 'credit'
  | 'trackingNo'
  | 'trackingDate'

export interface GridShape {
  /** ستون‌های رندرشده، به ترتیبِ چپ‌به‌راستِ منطقی (نه بصری). */
  cols: ColId[]
  rowCount: number
}

export interface CellRef {
  row: number
  col: number
}

/**
 * آیا این سلول در این ردیف قابلِ ورود است؟
 *
 * تفصیلی و پیگیری ستون دارند ولی در ردیفی که حسابش آن‌ها را نمی‌پذیرد
 * **غیرفعال**‌اند. ناوبری باید از رویشان بپرد، وگرنه کاربر به یک input قفل‌شده
 * می‌رسد و فکر می‌کند گرید گیر کرده. (§۱۴ — «مرحله غیرضروری Skip شود».)
 */
export type CellEnabled = (row: number, col: ColId) => boolean

/**
 * سلولِ بعدی/قبلی در همان ردیف، با پرش از سلول‌های غیرفعال.
 *
 * `null` یعنی به لبه‌ی ردیف رسیدیم — تصمیمِ «ردیفِ بعد» با فراخوان است، نه این‌جا،
 * چون آن تصمیم می‌تواند ردیفِ تازه بسازد و ساختنِ ردیف کارِ یک تابعِ ناوبری نیست.
 */
export function stepInRow(
  shape: GridShape,
  at: CellRef,
  dir: 1 | -1,
  enabled: CellEnabled,
): CellRef | null {
  for (let c = at.col + dir; c >= 0 && c < shape.cols.length; c += dir) {
    if (enabled(at.row, shape.cols[c])) return { row: at.row, col: c }
  }
  return null
}

/** اولین سلولِ فعالِ یک ردیف (از چپِ منطقی). `null` = ردیف هیچ سلولِ فعالی ندارد. */
export function firstInRow(shape: GridShape, row: number, enabled: CellEnabled): CellRef | null {
  for (let c = 0; c < shape.cols.length; c++) {
    if (enabled(row, shape.cols[c])) return { row, col: c }
  }
  return null
}

/** آخرین سلولِ فعالِ یک ردیف. */
export function lastInRow(shape: GridShape, row: number, enabled: CellEnabled): CellRef | null {
  for (let c = shape.cols.length - 1; c >= 0; c--) {
    if (enabled(row, shape.cols[c])) return { row, col: c }
  }
  return null
}

/** نتیجه‌ی یک حرکت: یا برو به سلول، یا اول ردیف بساز و بعد برو. */
export type Move =
  | { kind: 'move'; to: CellRef }
  | { kind: 'appendRow' }
  | { kind: 'none' }

/**
 * Enter: «این مقدار تمام شد، بعدی».
 *
 * در آخرین ستونِ فعالِ ردیف → اولین ستونِ ردیفِ بعد.
 * در آخرین ستونِ **آخرین** ردیف → ردیفِ تازه ساخته شود (§۲۱).
 */
export function onEnter(shape: GridShape, at: CellRef, enabled: CellEnabled): Move {
  const next = stepInRow(shape, at, 1, enabled)
  if (next) return { kind: 'move', to: next }
  if (at.row + 1 < shape.rowCount) {
    const head = firstInRow(shape, at.row + 1, enabled)
    return head ? { kind: 'move', to: head } : { kind: 'none' }
  }
  return { kind: 'appendRow' }
}

/**
 * Shift+Enter: حرکتِ معکوس.
 *
 * در اولین ستونِ ردیف → آخرین ستونِ ردیفِ قبل. در ردیفِ اول هیچ — عمداً ردیف
 * نمی‌سازد، چون «بالا رفتن» هرگز نباید داده اضافه کند.
 */
export function onShiftEnter(shape: GridShape, at: CellRef, enabled: CellEnabled): Move {
  const prev = stepInRow(shape, at, -1, enabled)
  if (prev) return { kind: 'move', to: prev }
  if (at.row === 0) return { kind: 'none' }
  const tail = lastInRow(shape, at.row - 1, enabled)
  return tail ? { kind: 'move', to: tail } : { kind: 'none' }
}

/**
 * پیکانِ بالا/پایین: همان ستون، ردیفِ مجاور.
 *
 * **چرا فقط بالا/پایین و نه چپ/راست.** §۱۲ خودش راهِ خروج را داده: «اگر تعارضِ
 * UX دارد، فقط Up/Down پیاده شود». و تعارض واقعی است — چپ/راست داخلِ یک input
 * مکان‌نما را جابه‌جا می‌کند و گرفتنشان یعنی کاربر نتواند وسطِ عدد را اصلاح کند.
 * به‌علاوه در رابطِ راست‌به‌چپ «بعدی» بصری، *چپ* است نه راست؛ کپی‌کردنِ بی‌فکرِ
 * گریدهای LTR دقیقاً همان دامی است که §۳۷ هشدارش را داده. پس چپ/راست دست‌نخورده
 * می‌مانند و حرکتِ افقی فقط با Enter/Tab است — که در هر دو جهتِ نوشتار یکسان‌اند.
 *
 * اگر سلولِ هم‌ستون در ردیفِ مقصد غیرفعال باشد، نزدیک‌ترین سلولِ فعالِ همان ردیف
 * انتخاب می‌شود تا حرکت هرگز بی‌اثر نماند.
 */
export function onVertical(
  shape: GridShape,
  at: CellRef,
  dir: 1 | -1,
  enabled: CellEnabled,
): Move {
  const row = at.row + dir
  if (row < 0 || row >= shape.rowCount) return { kind: 'none' }
  if (enabled(row, shape.cols[at.col])) return { kind: 'move', to: { row, col: at.col } }
  const near =
    stepInRow(shape, { row, col: at.col }, 1, enabled) ??
    stepInRow(shape, { row, col: at.col }, -1, enabled)
  return near ? { kind: 'move', to: near } : { kind: 'none' }
}
