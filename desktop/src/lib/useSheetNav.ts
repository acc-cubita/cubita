import { useCallback, type KeyboardEvent, type RefObject } from 'react'

import {
  arrowLeavesField,
  firstInRow,
  onEnter,
  onHorizontal,
  onShiftEnter,
  onTab,
  onVertical,
  type CellEnabled,
  type GridShape,
  type Move,
} from './journalGridNav'

const always = () => true
const isRtl = (el: Element) => getComputedStyle(el).direction === 'rtl'

/**
 * صفحه‌کلیدِ گریدهای ورودِ داده‌ی هم‌سبکِ گریدِ سند (مانده اول دوره و صفحه‌های بعدی) — همان حرکت‌ها با
 * همان منطقِ خالصِ `journalGridNav`:
 *
 * - Enter / Shift+Enter: خانه‌ی بعد / قبل در مسیرِ Enter (`enterPath`)؛ بعد از آخرین خانه‌ی آخرین ردیف،
 *   ردیفِ تازه. روی انتخاب‌گرِ بسته‌ی خالی، Enter بازش می‌کند (پیش‌فرضِ دکمه) و رد نمی‌شود.
 * - Tab / Shift+Tab: خانه‌به‌خانه؛ در انتهای ردیفِ آخرِ پُر، ردیفِ تازه، وگرنه بیرون از گرید.
 * - ←/→ با قاعده‌ی لبه‌ی مکان‌نما (اصلاحِ وسطِ عدد ممکن می‌ماند)، ↑/↓ هم‌ستون، F2 مکان‌نما به انتها.
 * - Ctrl+Enter ردیفِ تازه، Ctrl+Delete حذفِ همین ردیف (`onDeleteRow`؛ `false` یعنی حذف نشد).
 *
 * خانه‌ها `data-cell="ردیف-ستون"` دارند و `onKeyDown` روی ظرفِ گرید می‌نشیند. گریدِ سند (`JournalGrid`)
 * سیم‌کشیِ خودش را دارد چون ده‌ها میان‌برِ ویژه‌ی سند رویش است (مبلغِ باقی‌مانده، تکرارِ ردیف، رفتن به
 * ردیف)؛ منطقِ حرکت اما همین است.
 */
export function useSheetNav<C extends string>({
  gridRef,
  cols,
  rowCount,
  enabled = always,
  enterPath,
  onAppendRow,
  onDeleteRow,
  rowHasContent,
}: {
  gridRef: RefObject<HTMLElement | null>
  cols: C[]
  rowCount: number
  enabled?: CellEnabled<C>
  /** خانه‌هایی که Enter رویشان می‌ایستد (پیش‌فرض: همه‌ی خانه‌های فعال). */
  enterPath?: CellEnabled<C>
  /** ردیفِ تازه بساز. اگر شاخصی برگرداند، فوکوس به همان ردیف می‌رود (برگه‌ای که همیشه یک ردیفِ
   *  خالیِ ته دارد، ردیف نمی‌سازد — به همان خالی می‌رود). */
  onAppendRow: () => number | void
  onDeleteRow?: (row: number) => boolean
  /** Tab در انتهای گرید فقط وقتی ردیفِ آخر چیزی دارد ردیفِ تازه می‌سازد. */
  rowHasContent?: (row: number) => boolean
}) {
  const shape: GridShape<C> = { cols, rowCount }
  const onPath = enterPath ?? enabled

  /** عنصرِ قابلِ فوکوسِ یک خانه؛ عددِ موجود کامل انتخاب می‌شود تا تایپ جایگزینش کند (مثلِ اکسل). */
  const focusCell = useCallback(
    (row: number, col: number) => {
      const cell = gridRef.current?.querySelector<HTMLElement>(`[data-cell="${row}-${col}"]`)
      const target = cell?.querySelector<HTMLElement>('input:not([disabled]), select:not([disabled]), button:not([disabled])')
      if (!target) return
      target.focus()
      if (target instanceof HTMLInputElement && target.type !== 'checkbox') target.select?.()
    },
    [gridRef],
  )

  function apply(move: Move) {
    if (move.kind === 'move') {
      focusCell(move.to.row, move.to.col)
    } else if (move.kind === 'appendRow') {
      const target = onAppendRow()
      const row = typeof target === 'number' ? target : rowCount
      //: ردیفِ تازه هنوز رندر نشده؛ فوکوس بعد از آن.
      requestAnimationFrame(() => {
        const head = firstInRow<C>({ cols, rowCount: row + 1 }, row, always)
        if (head) focusCell(head.row, head.col)
      })
    }
  }

  /** بعد از انتخاب در کادرِ ترکیبی (`AccountCombo`): همان حرکتِ Enter/Tab از همان خانه. */
  function commit(row: number, col: C, how: 'enter' | 'tab') {
    const at = { row, col: cols.indexOf(col) }
    //: بعد از بسته‌شدنِ فهرست و نشستنِ مقدار — وگرنه کادر فوکوس را پس می‌گرفت.
    requestAnimationFrame(() => {
      const move = how === 'enter' ? onEnter(shape, at, onPath) : onTab(shape, at, 1, enabled, true)
      if (move.kind !== 'exit') apply(move)
    })
  }

  function onKeyDown(e: KeyboardEvent<HTMLElement>) {
    const cellEl = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]')
    const coords = cellEl?.dataset.cell?.split('-').map(Number)
    if (!coords || coords.length !== 2) return
    const at = { row: coords[0], col: coords[1] }

    if (e.ctrlKey || e.metaKey) {
      if (e.code === 'Enter' || e.code === 'NumpadEnter') {
        e.preventDefault()
        apply({ kind: 'appendRow' })
      } else if ((e.code === 'Delete' || e.code === 'NumpadDecimal') && onDeleteRow) {
        e.preventDefault()
        if (onDeleteRow(at.row)) requestAnimationFrame(() => focusCell(Math.max(0, at.row - 1), at.col))
      }
      return
    }

    if (e.code === 'F2') {
      const el = e.target
      if (el instanceof HTMLInputElement && !el.disabled) {
        e.preventDefault()
        el.setSelectionRange(el.value.length, el.value.length)
      }
      return
    }

    if (e.code === 'Tab' && !e.altKey) {
      const move = onTab(shape, at, e.shiftKey ? -1 : 1, enabled, rowHasContent?.(rowCount - 1) ?? true)
      //: بیرون از گرید: رفتارِ پیش‌فرضِ مرورگر.
      if (move.kind === 'exit') return
      e.preventDefault()
      apply(move)
      return
    }

    if ((e.code === 'ArrowLeft' || e.code === 'ArrowRight') && !e.shiftKey && !e.altKey) {
      const el = e.target as HTMLElement
      if (el.closest('.item-picker-pop, .jalali-date-popover')) return
      if (el instanceof HTMLInputElement) {
        const field = { start: el.selectionStart, end: el.selectionEnd, length: el.value.length, rtl: isRtl(el) }
        if (!arrowLeavesField(field, e.code)) return
      }
      e.preventDefault()
      apply(onHorizontal(shape, at, e.code, isRtl(gridRef.current ?? el), enabled))
      return
    }

    if ((e.code === 'ArrowDown' || e.code === 'ArrowUp') && !e.altKey) {
      //: داخلِ پاپ‌آورِ بازِ انتخاب‌گر، پیکان مالِ خودِ فهرست است.
      if ((e.target as HTMLElement).closest('.item-picker-pop')) return
      e.preventDefault()
      apply(onVertical(shape, at, e.code === 'ArrowDown' ? 1 : -1, enabled))
      return
    }

    if (e.code === 'Enter' || e.code === 'NumpadEnter') {
      //: انتخاب‌گرِ بسته‌ای که هنوز چیزی ندارد با Enter **باز** می‌شود (کلیکِ پیش‌فرضِ دکمه) — وگرنه
      //: با صفحه‌کلید راهی برای بازکردنش نبود و ردیف بی‌صدا خالی می‌ماند.
      const trigger = (e.target as HTMLElement).closest('.item-picker-trigger')
      if (!e.shiftKey && trigger?.querySelector('.item-picker-placeholder')) return
      e.preventDefault()
      apply(e.shiftKey ? onShiftEnter(shape, at, onPath) : onEnter(shape, at, onPath))
    }
  }

  return { onKeyDown, focusCell, commit }
}
