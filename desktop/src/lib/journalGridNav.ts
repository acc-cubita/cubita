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
  | 'costCenter'
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
  //: از گرید بیرون برو (Tab در انتهای سندِ کامل) — مقصد را فراخوان تعیین می‌کند.
  | { kind: 'exit' }

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
 * چپ/راست در `onHorizontal` است، با قاعده‌ی لبه‌ی مکان‌نما (`arrowLeavesField`) — تا
 * اصلاحِ وسطِ عدد ممکن بماند (همان تعارضی که §۱۲ از آن می‌ترسید).
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

/**
 * Tab / Shift+Tab: خانه‌ی فعالِ بعد/قبل، **با** مرکزِ هزینه (برخلافِ Enter، §۱۵)، و
 * پیچیدن به ردیفِ بعد/قبل — دکمه‌های کنشِ ردیف (تکرار/کپی/حذف) در مسیر نیستند؛ میان‌بر
 * دارند (Ctrl+D، Ctrl+Shift+C، Ctrl+Delete) و بی این هر ردیف سه Tabِ اضافه می‌خواست.
 *
 * در آخرین خانه‌ی آخرین ردیف: ردیفِ تازه — **مگر ردیفِ آخر خالی باشد**؛ آن‌وقت
 * `exit`، تا کاربری که سند را تمام کرده با Tab به «ثبت سند» برسد و در گرید زندانی نشود.
 * Shift+Tab در اولین خانه‌ی ردیفِ اول هم `exit` است (به سربرگ).
 */
export function onTab(
  shape: GridShape,
  at: CellRef,
  dir: 1 | -1,
  enabled: CellEnabled,
  lastRowHasContent: boolean,
): Move {
  const inRow = stepInRow(shape, at, dir, enabled)
  if (inRow) return { kind: 'move', to: inRow }
  if (dir === 1) {
    for (let r = at.row + 1; r < shape.rowCount; r++) {
      const head = firstInRow(shape, r, enabled)
      if (head) return { kind: 'move', to: head }
    }
    return lastRowHasContent ? { kind: 'appendRow' } : { kind: 'exit' }
  }
  for (let r = at.row - 1; r >= 0; r--) {
    const tail = lastInRow(shape, r, enabled)
    if (tail) return { kind: 'move', to: tail }
  }
  return { kind: 'exit' }
}

/**
 * ← / →: خانه‌ی مجاور در همان ردیف.
 *
 * **در رابطِ راست‌به‌چپ «بعدی» چپ است** (§۳۷): ستون‌ها از راست شروع می‌شوند، پس ←
 * یعنی ستونِ منطقیِ بعد. در لبه‌ی ردیف نمی‌پیچد (مثلِ Excel) — ردیف عوض‌کردن کارِ ↑/↓
 * و Enter/Tab است.
 */
export function onHorizontal(
  shape: GridShape,
  at: CellRef,
  key: 'ArrowLeft' | 'ArrowRight',
  rtl: boolean,
  enabled: CellEnabled,
): Move {
  const dir: 1 | -1 = (key === 'ArrowLeft') === rtl ? 1 : -1
  const to = stepInRow(shape, at, dir, enabled)
  return to ? { kind: 'move', to } : { kind: 'none' }
}

/**
 * آیا ← / → باید از این فیلد به خانه‌ی مجاور برود، یا مکان‌نما را داخلِ متن جابه‌جا کند؟
 *
 * همان دو حالتِ Excel: وقتی تازه به خانه رسیده‌ای (کلِ مقدار انتخاب‌شده — `focusCell`
 * همین را می‌کند) یا خانه خالی است، پیکان **حرکت** است. وقتی مکان‌نما داخلِ متن است
 * (کلیک یا F2)، پیکان مکان‌نما را می‌برد و فقط در لبه‌ی متن از خانه بیرون می‌زند —
 * پس اصلاحِ وسطِ عدد همیشه ممکن است.
 *
 * «لبه» به جهتِ خودِ فیلد بسته است: در فیلدِ راست‌به‌چپ ← مکان‌نما را به **انتهای**
 * متن می‌برد، در فیلدِ عددیِ چپ‌به‌راست به ابتدای آن. `start === null` یعنی کنترلی
 * بی‌مکان‌نما (دکمه‌ی انتخاب‌گر، `select`) — همیشه حرکت.
 */
export function arrowLeavesField(
  f: { start: number | null; end: number | null; length: number; rtl: boolean },
  key: 'ArrowLeft' | 'ArrowRight',
): boolean {
  if (f.start === null || f.end === null || f.length === 0) return true
  if (f.start === 0 && f.end === f.length) return true
  if (f.start !== f.end) return false
  const towardEnd = (key === 'ArrowLeft') === f.rtl
  return towardEnd ? f.end === f.length : f.start === 0
}
