import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Copy, CopyPlus, Trash2 } from 'lucide-react'

import { SearchSelect } from './SearchSelect'
import { AccountCombo, type ComboCommit, type ComboOption } from './AccountCombo'
import { ColResizer, SelectionBar } from './XlGrid'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { RowAction } from './form/FormKit'
import { DescriptionInput } from './DescriptionInput'
import type { JournalEntryDraft, JournalDraftLine } from '../lib/journalEntryDraft'
import {
  arrowLeavesField,
  firstInRow,
  onEnter,
  onHorizontal,
  onShiftEnter,
  onTab,
  onVertical,
  type ColId,
  type GridShape,
} from '../lib/journalGridNav'
import { openCellPicker } from '../lib/gridPicker'
import { poolFor } from '../lib/descriptionMemory'
import { normalizeFa } from '../lib/faText'
import { modsOf, useRowSelection, type ClickMods } from '../lib/rowSelection'
import { useColumnWidths } from '../lib/useColumnWidths'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * جهتِ نوشتار از صفتِ `dir` (نزدیک‌ترین جد، وگرنه `<html>`). `NumberInput` خودش
 * `dir="ltr"` دارد و شرح از `<html dir="rtl">` می‌گیرد. صفت و نه `getComputedStyle`:
 * جهتِ این برنامه همیشه با صفت تعیین می‌شود، و jsdom جهتِ محاسبه‌شده ندارد.
 */
function isRtl(el: Element): boolean {
  return (el.closest('[dir]')?.getAttribute('dir') ?? document.documentElement.dir) === 'rtl'
}

/**
 * گریدِ ثبتِ سند برای **حالت حسابدار** — فشرده و صفحه‌کلیدمحور.
 *
 * **همان موتور، تجربه‌ی دیگر.** این کامپوننت هیچ منطقِ مالی ندارد: همان
 * `useJournalEntryDraft` را می‌گیرد که فرمِ ساده می‌گیرد، همان `submit` را صدا
 * می‌زند و همان payload را می‌فرستد. تفاوت فقط در چیدمان، تراکم و رفتارِ کلید
 * است. اگر روزی محاسبه‌ای این‌جا نوشته شود، جایش اشتباه است.
 *
 * **چرا focus با `data-cell` و نه ماتریسِ ref.** ردیف‌ها اضافه و حذف می‌شوند و
 * ستون‌ها شرطی‌اند؛ ماتریسِ ref باید با هر تغییر هم‌گام می‌ماند و اولین باری که
 * نماند، focus بی‌صدا می‌پرد. صفتِ داده روی DOM همیشه درست است چون خودِ رندر
 * تولیدش می‌کند. به‌علاوه این‌طور `SearchSelect` و `NumberInput` دست‌نخورده
 * می‌مانند — هیچ‌کدام لازم نیست ref بپذیرند.
 */
//: عرضِ پیش‌فرضِ هر ستون، وقتی کاربر عرضی را کشیده و بقیه باید پیکسلی شوند (`useColumnWidths`).
const COL_FALLBACK: Record<string, number> = {
  num: 44,
  account: 320,
  fx: 130,
  tafsili: 150,
  costCenter: 150,
  description: 140,
  debit: 170,
  credit: 170,
  trackingNo: 130,
  trackingDate: 130,
  actions: 104,
}

export function JournalGrid({
  d,
  highlight = null,
  current,
}: {
  d: JournalEntryDraft
  /** ردیف‌هایی که جست‌وجوی سریعِ سرِ کارت پیدا کرده؛ `null` یعنی جست‌وجویی نیست. */
  highlight?: readonly number[] | null
  /** ردیفی که Enterِ کادرِ جست‌وجو رویش ایستاده. */
  current?: number
}) {
  const gridRef = useRef<HTMLDivElement>(null)
  const jumpRef = useRef<HTMLInputElement>(null)
  const [jump, setJump] = useState('')
  const [jumpMsg, setJumpMsg] = useState<string | null>(null)
  //: «رفتن به ردیف» فقط با Ctrl+G پیدا می‌شود — نوارِ همیشگی‌اش بالای گرید جا می‌گرفت و
  //: شمارِ ردیف‌هایش همان نشانِ «ردیف معتبر»ِ کارت بود. Esc فوکوس را به خانه‌ی مبدأ برمی‌گرداند.
  const [jumpOpen, setJumpOpen] = useState(false)
  const jumpFrom = useRef<{ row: number; col: number } | null>(null)
  //: جلو رفتن بعد از انتخابِ حساب با Enter/Tab — در اثرِ پایین، **بعد از** رندرِ وضعیتِ تازه.
  const [advance, setAdvance] = useState<{ row: number; how: ComboCommit } | null>(null)
  //: انتخابِ ردیف با سرستونِ ردیف (شماره)، مثلِ اکسل — برای حذفِ دسته‌ای و جمعِ انتخاب.
  const { selected, click: clickRowHead, clear: clearSelection } = useRowSelection()
  //: ستونِ کنش‌ها (آخرین) کشسان است: جای خالیِ باریک‌کردنِ یک ستون ته جدول می‌ماند و ستون‌های دیگر
  //: جابه‌جا نمی‌شوند.
  const cw = useColumnWidths('cubita.journalGrid.widths', COL_FALLBACK, 'actions')

  //: مخزنِ حافظه‌ی شرح از `ref` خوانده می‌شود، نه از `d.lines`: تابعی که به ردیف‌ها
  //: می‌رسد باید پایدار بماند، وگرنه `memo`ِ هر ۳۰۰ ردیف با هر کلید می‌شکست.
  const linesRef = useRef(d.lines)
  linesRef.current = d.lines
  const descriptionPool = useCallback(
    (row: number) => poolFor(linesRef.current.map((l) => l.description ?? ''), row),
    [],
  )

  const showFx = Boolean(d.currencyCode)
  const showTafsili = d.lines.some((l) => d.tafsiliRequired.has(l.accountId))
  const showTracking = d.lines.some((l) => d.trackingAllowed.has(l.accountId))
  //: مرکزِ هزینه‌ی ردیف فقط وقتی ستون دارد که کسب‌وکار مرکزی تعریف کرده باشد.
  const showCostCenter = d.costCenters.length > 0

  //: `useMemo` حیاتی است، نه آرایش: `cols` به **هر** ردیف پاس داده می‌شود، و
  //: آرایه‌ی تازه در هر رندر یعنی مقایسه‌ی `memo`ِ همه‌ی ۳۰۰ ردیف شکست می‌خورد.
  //: سنجیده شد — بدونِ این، تایپ در سندِ ۳۰۰ ردیفی ۲۵۰ms برای هر کلید می‌گرفت
  //: حتی وقتی بقیه‌ی propها پایدار بودند.
  const cols: ColId[] = useMemo(
    () => [
      'account',
      ...(showFx ? (['fx'] as ColId[]) : []),
      ...(showTafsili ? (['tafsili'] as ColId[]) : []),
      ...(showCostCenter ? (['costCenter'] as ColId[]) : []),
      'description',
      'debit',
      'credit',
      ...(showTracking ? (['trackingNo', 'trackingDate'] as ColId[]) : []),
    ],
    [showFx, showTafsili, showTracking, showCostCenter],
  )
  const shape: GridShape = { cols, rowCount: d.lines.length }

  /** سلولی که حسابش آن را نمی‌پذیرد، غیرفعال است و ناوبری از رویش می‌پرد. */
  const enabled = useCallback(
    (row: number, col: ColId) => {
      const line = d.lines[row]
      if (!line) return false
      if (col === 'tafsili') return d.tafsiliRequired.has(line.accountId)
      if (col === 'trackingNo' || col === 'trackingDate') return d.trackingAllowed.has(line.accountId)
      return true
    },
    [d.lines, d.tafsiliRequired, d.trackingAllowed],
  )
  //: **مسیرِ Enter از مرکزِ هزینه و شرحِ ردیف می‌پرد** (§۱۵): هیچ‌کدام در سندِ دستی اجباری
  //: نیست، و خانه‌ای که بیشترِ ردیف‌ها خالی می‌گذارند هر ردیف را یک Enterِ اضافه کند می‌کرد.
  //: حسابدار با Enter از حساب مستقیم به مبلغ می‌رسد (خواسته‌ی آرش، ۱۴۰۵/۰۷/۰۳). Tab، ←/→ و
  //: موس به هر دو می‌رسند و ↑/↓ داخلِ همان ستون کار می‌کند (آن‌ها `enabled` را می‌خوانند).
  const onEnterPath = useCallback(
    (row: number, col: ColId) => col !== 'costCenter' && col !== 'description' && enabled(row, col),
    [enabled],
  )

  //: گزینه‌های حساب یک‌بار برای همه‌ی ردیف‌ها — آرایه‌ی تازه در هر رندر `memo`ِ ردیف‌ها را می‌شکست.
  const accountOptions: ComboOption[] = useMemo(
    () => d.postableAccounts.map((a) => ({ value: a.id, label: `${a.code} — ${a.name}` })),
    [d.postableAccounts],
  )
  const commitAccount = useCallback((row: number, how: ComboCommit) => setAdvance({ row, how }), [])

  //: ترتیبِ ردیف‌ها برای بازه‌ی Shift+کلیک، از ref تا تابعِ پاس‌داده به ردیف‌ها پایدار بماند.
  const rowOrder = useRef<string[]>([])
  rowOrder.current = d.lines.map((_, i) => String(i))
  const onRowHead = useCallback((row: number, mods: ClickMods) => clickRowHead(rowOrder.current, String(row), mods), [clickRowHead])
  //: با افزودن/حذف/تکرارِ ردیف شاخص‌ها جابه‌جا می‌شوند؛ انتخابِ کهنه ردیفِ اشتباه را پاک می‌کرد.
  useEffect(() => clearSelection(), [d.lines.length, clearSelection])
  const hitSet = useMemo(() => (highlight ? new Set(highlight) : null), [highlight])
  const selectedRows = useMemo(() => [...selected].map(Number).sort((a, b) => a - b), [selected])

  function deleteSelected() {
    if (selectedRows.length === 0) return
    const first = selectedRows[0]
    d.removeLines(selectedRows)
    clearSelection()
    requestAnimationFrame(() => focusCell(Math.max(0, Math.min(first, d.lines.length - selectedRows.length) - 1), 0))
  }

  /** عنصرِ قابلِ فوکوسِ درونِ یک سلول را پیدا و فوکوس می‌کند. */
  const focusCell = useCallback((row: number, col: number) => {
    const cell = gridRef.current?.querySelector<HTMLElement>(`[data-cell="${row}-${col}"]`)
    const target = cell?.querySelector<HTMLElement>('input:not([disabled]), select:not([disabled]), button:not([disabled])')
    if (!target) return
    target.focus()
    //: عددِ موجود کامل انتخاب می‌شود تا تایپِ بعدی جایگزینش کند، نه اینکه به
    //: دنبالش بچسبد — همان رفتاری که حسابدار از Excel انتظار دارد.
    if (target instanceof HTMLInputElement && target.type !== 'checkbox') target.select?.()
  }, [])

  //: فوکوسِ خودکار روی اولین سلولِ عملیاتی (§۴۴) — کاربر نباید اول داخلِ گرید
  //: کلیک کند. فقط یک‌بار موقعِ سوارشدن. اگر کاربر از سربرگِ **همین فرم** شروع کرده
  //: (تاریخ/شرح)، فوکوسش دزدیده نمی‌شود.
  //:
  //: فوکوسِ بیرون از فرم اما کارِ کاربر روی این سند نیست، باقی‌مانده‌ی ناوبری است:
  //: دکمه‌ی «حسابداری»ِ نوارِ بالا که با آن آمده، یا پالتِ فرمان. شرطِ قبلی هر فوکوسی
  //: بیرون از گرید را محترم می‌شمرد، پس کسی که با کلیک روی نوار آمده بود فوکوسی
  //: نمی‌گرفت و باید با Tab از کلِ سربرگ رد می‌شد — E2E همین را پیدا کرد.
  useEffect(() => {
    const active = document.activeElement
    const grid = gridRef.current
    const inOwnHeader = Boolean(active && grid?.closest('form')?.contains(active) && !grid.contains(active))
    if (inOwnHeader) return
    const first = gridRef.current?.querySelector<HTMLElement>(
      '[data-cell="0-0"] input, [data-cell="0-0"] button, [data-cell="0-0"] select',
    )
    first?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** یک حرکتِ محاسبه‌شده را اجرا می‌کند؛ `appendRow` اول ردیف می‌سازد. */
  const apply = useCallback(
    (move: ReturnType<typeof onEnter>) => {
      if (move.kind === 'move') {
        focusCell(move.to.row, move.to.col)
      } else if (move.kind === 'appendRow') {
        const row = d.lines.length
        d.addLine()
        //: رندرِ ردیفِ تازه هنوز نیفتاده؛ فوکوس باید بعد از آن باشد.
        requestAnimationFrame(() => {
          const head = firstInRow({ ...shape, rowCount: row + 1 }, row, () => true)
          if (head) focusCell(head.row, head.col)
        })
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [d, focusCell, cols.length],
  )

  /**
   * کلیدهای گرید.
   *
   * **میان‌برهای حرفی با `e.code` سنجیده می‌شوند، نه `e.key`** — درسی که پروژه
   * با `Ctrl+K` گرفت و در `lib/shortcuts.ts` نوشته: روی چیدمانِ فارسی
   * `e.key` می‌شود «ن» و میان‌بر بی‌صدا از کار می‌افتد. `e.code` جای فیزیکیِ
   * کلید است.
   *
   * **تعارضی با میان‌برهای کاربر نیست:** `useShortcuts` با `isTypingTarget`
   * داخلِ هر input/select/button از کار می‌افتد، و این کلیدها دقیقاً همان‌جا
   * اجرا می‌شوند. دو فضای مکمل.
   */
  /**
   * رفتن به ردیفِ n (UI-01 §۴۲): اسکرول، و فوکوس روی اولین خانه‌ی فعالِ همان ردیف.
   * رقمِ فارسی هم پذیرفته می‌شود — کاربر روی چیدمانِ فارسی تایپ می‌کند.
   */
  function jumpTo() {
    const raw = normalizeFa(jump)
    const n = Number(raw)
    if (!raw || !Number.isInteger(n) || n < 1 || n > d.lines.length) {
      setJumpMsg(`ردیفِ ${raw ? fa(Number(raw) || 0) : '؟'} نیست — سند ${fa(d.lines.length)} ردیف دارد.`)
      return
    }
    setJumpMsg(null)
    const head = firstInRow(shape, n - 1, onEnterPath)
    if (!head) return
    gridRef.current
      ?.querySelector(`[data-cell="${head.row}-${head.col}"]`)
      ?.scrollIntoView?.({ block: 'center' })
    focusCell(head.row, head.col)
    setJumpOpen(false)
    setJump('')
  }

  function closeJump(restoreFocus: boolean) {
    setJumpOpen(false)
    setJump('')
    setJumpMsg(null)
    const from = jumpFrom.current
    jumpFrom.current = null
    if (restoreFocus && from) focusCell(from.row, from.col)
  }

  useEffect(() => {
    if (!jumpOpen) return
    jumpRef.current?.focus()
    jumpRef.current?.select()
  }, [jumpOpen])

  //: بعد از انتخابِ حساب: همان حرکتِ Enter/Tab، ولی با `shape`/`enabled`ِ **این** رندر — حسابِ
  //: تازه ممکن است ستونِ تفصیلیِ اجباری را تازه پیدا کرده باشد (`AccountCombo`).
  useEffect(() => {
    if (!advance) return
    setAdvance(null)
    const at = { row: advance.row, col: cols.indexOf('account') }
    if (advance.how === 'enter') {
      apply(onEnter(shape, at, onEnterPath))
      return
    }
    const move = onTab(shape, at, 1, enabled, true)
    if (move.kind !== 'exit') apply(move)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [advance])

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    const cellEl = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]')
    const coords = cellEl?.dataset.cell?.split('-').map(Number)
    if (!coords || coords.length !== 2) return
    const at = { row: coords[0], col: coords[1] }

    //: Esc انتخابِ ردیف‌ها را برمی‌دارد — فهرست‌های باز (حساب، شرح) Esc را خودشان می‌گیرند.
    if (e.key === 'Escape' && selectedRows.length > 0) {
      clearSelection()
      return
    }

    // ── میان‌برهای ردیف و سند ──
    if (e.ctrlKey || e.metaKey) {
      if (e.code === 'Enter' || e.code === 'NumpadEnter') {
        e.preventDefault()
        apply({ kind: 'appendRow' })
        return
      }
      if (e.code === 'KeyD') {
        e.preventDefault()
        const at2 = d.duplicateLine(at.row)
        requestAnimationFrame(() => focusCell(at2, at.col))
        return
      }
      if (e.code === 'KeyC' && e.shiftKey) {
        e.preventDefault()
        d.copyPreviousInto(at.row)
        return
      }
      if (e.code === 'Delete' || e.code === 'NumpadDecimal') {
        e.preventDefault()
        //: با ردیف‌های انتخاب‌شده، همان‌ها با هم حذف می‌شوند (نوارِ انتخاب هم همین را دارد).
        if (selectedRows.length > 0) {
          deleteSelected()
          return
        }
        if (d.lines.length <= 2) return
        d.removeLine(at.row)
        requestAnimationFrame(() => focusCell(Math.max(0, at.row - 1), at.col))
        return
      }
      if (e.code === 'KeyS') {
        e.preventDefault()
        if (!d.submitting) void d.submit()
        return
      }
      //: «رفتن به ردیف» — Ctrl+G در مرورگر «یافتنِ بعدی» است، ولی فقط وقتی نوارِ
      //: یافتن باز است؛ داخلِ خانه‌ی گرید معنای دیگری ندارد.
      if (e.code === 'KeyG') {
        e.preventDefault()
        jumpFrom.current = at
        if (jumpOpen) {
          jumpRef.current?.focus()
          jumpRef.current?.select()
        } else {
          setJumpOpen(true)
        }
        return
      }
      return
    }

    // ── F2: حالتِ ویرایش ──
    //: خانه با کلِ مقدارِ انتخاب‌شده باز می‌شود (تایپ جایگزین می‌کند و ←/→ حرکت‌اند).
    //: F2 مکان‌نما را به انتهای متن می‌برد تا بشود وسطِ عدد را اصلاح کرد — همان Excel.
    if (e.code === 'F2') {
      const el = e.target
      if (el instanceof HTMLInputElement && !el.disabled) {
        e.preventDefault()
        const n = el.value.length
        el.setSelectionRange(n, n)
      }
      return
    }

    // ── F4 / Alt+↓: فهرستِ انتخاب ──
    //: F4 همیشه فهرستِ **حساب‌های** همین ردیف است — «بازکردنِ سریعِ فهرستِ حساب‌ها» از
    //: هر خانه‌ی ردیف. Alt+↓ انتخاب‌گرِ خودِ همین خانه را باز می‌کند (تفصیلی، مرکز)، و
    //: اگر خانه انتخاب‌گر ندارد همان حساب.
    if (e.code === 'F4' || (e.altKey && e.code === 'ArrowDown')) {
      e.preventDefault()
      const cellOf = (c: number) => gridRef.current?.querySelector(`[data-cell="${at.row}-${c}"]`)
      if (e.code === 'ArrowDown' && openCellPicker(cellOf(at.col))) return
      openCellPicker(cellOf(cols.indexOf('account')))
      return
    }

    // ── Tab / Shift+Tab ──
    //: خانه‌به‌خانه، بی دکمه‌های کنشِ ردیف؛ در انتهای سند ردیفِ تازه، مگر ردیفِ آخر خالی
    //: باشد — آن‌وقت به «ثبت سند» (`onTab` در `journalGridNav`).
    if (e.code === 'Tab' && !e.ctrlKey && !e.altKey) {
      const last = d.lines[d.lines.length - 1]
      const lastHasContent = Boolean(last && (last.accountId || last.debit || last.credit || last.description?.trim()))
      const move = onTab(shape, at, e.shiftKey ? -1 : 1, enabled, lastHasContent)
      if (move.kind === 'exit') {
        if (e.shiftKey) return //: رفتارِ پیش‌فرض: به «رفتن به ردیف» و سربرگ
        e.preventDefault()
        gridRef.current?.closest('form')?.querySelector<HTMLElement>('button[type="submit"]')?.focus()
        return
      }
      e.preventDefault()
      apply(move)
      return
    }

    // ── ← / → ──
    //: در رابطِ راست‌به‌چپ ← خانه‌ی بعد است. داخلِ متن، پیکان مالِ مکان‌نماست تا لبه
    //: (`arrowLeavesField`)؛ Shift+پیکان انتخابِ متن است و دست نمی‌خورد.
    if ((e.code === 'ArrowLeft' || e.code === 'ArrowRight') && !e.shiftKey && !e.altKey) {
      const el = e.target as HTMLElement
      if (el.closest('.item-picker-pop, .jalali-date-popover')) return
      if (el instanceof HTMLInputElement) {
        const field = {
          start: el.selectionStart,
          end: el.selectionEnd,
          length: el.value.length,
          rtl: isRtl(el),
        }
        if (!arrowLeavesField(field, e.code)) return
      }
      e.preventDefault()
      apply(onHorizontal(shape, at, e.code, isRtl(gridRef.current ?? el), enabled))
      return
    }

    // ── پذیرشِ مبلغِ باقی‌مانده ──
    //: در ستونِ بدهکار/بستانکارِ خالی، Enter عددی را می‌نشاند که سند را متوازن
    //: می‌کند و **در همان ضربه** جلو می‌رود — از جایی که انگار Enter روی ستونِ
    //: بستانکار خورده: مبالغِ ردیف با همین کامل شد و طرفِ دیگرش باید خالی بماند،
    //: پس ایستادن روی آن فقط یک Enterِ اضافه بود. اگر ردیف از قبل عدد دارد، یا
    //: سند متوازن است، دست نمی‌خورد و Enterِ عادی اجرا می‌شود — وگرنه مبلغِ کاربر
    //: بازنویسی می‌شد.
    if (e.code === 'Enter' || e.code === 'NumpadEnter') {
      const col = cols[at.col]
      const line = d.lines[at.row]
      const emptyAmount = line && !line.debit && !line.credit

      // ── بازکردنِ انتخاب‌گرِ خالی ──
      //: روی انتخاب‌گرِ بسته‌ای که هنوز چیزی انتخاب نشده، Enter باید **بازش
      //: کند**، نه از آن رد شود — وگرنه با صفحه‌کلید هیچ راهی برای بازکردنش با
      //: Enter نیست و کاربر بی‌آنکه بفهمد ردیف را با حسابِ خالی رها می‌کند.
      //:
      //: اگر از قبل مقدار دارد، Enter مثلِ هر ستونِ دیگری جلو می‌برد. عمدی است:
      //: چون `SearchSelect` بعد از انتخاب فوکوس را به همین دکمه برمی‌گرداند،
      //: «همیشه باز کن» یک حلقه می‌ساخت که کاربر با Enter هرگز از سلول بیرون
      //: نمی‌آمد. برای عوض‌کردنِ مقدارِ موجود کافی است شروع به تایپ کند.
      //:
      //: `preventDefault` صدا زده **نمی‌شود** تا کلیکِ پیش‌فرضِ Enter روی دکمه
      //: خودش پاپ‌آور را باز کند.
      //: (خانه‌ی حساب این را خودش می‌کند — `AccountCombo`؛ این‌جا فقط تفصیلی.)
      if (!e.shiftKey && col === 'tafsili') {
        if (!line?.analyticId && (e.target as HTMLElement).closest('.item-picker-trigger')) return
      }

      if (!e.shiftKey && (col === 'debit' || col === 'credit') && emptyAmount && d.remaining) {
        e.preventDefault()
        if (d.applyRemaining(at.row)) {
          apply(onEnter(shape, { row: at.row, col: cols.indexOf('credit') }, onEnterPath))
        }
        return
      }
      e.preventDefault()
      apply(e.shiftKey ? onShiftEnter(shape, at, onEnterPath) : onEnter(shape, at, onEnterPath))
      return
    }

    if (e.code === 'ArrowDown' || e.code === 'ArrowUp') {
      //: داخلِ پاپ‌آورِ بازِ انتخاب‌گر، پیکان مالِ خودِ فهرست است.
      if ((e.target as HTMLElement).closest('.item-picker-pop')) return
      e.preventDefault()
      apply(onVertical(shape, at, e.code === 'ArrowDown' ? 1 : -1, enabled))
    }
  }

  return (
    <div className="jg">
      {jumpOpen && (
        <div className="jg-jump-pop">
          <label className="jg-jump">
            رفتن به ردیف
            <input
              ref={jumpRef}
              type="text"
              inputMode="numeric"
              dir="ltr"
              size={5}
              value={jump}
              aria-describedby={jumpMsg ? 'jg-jump-msg' : undefined}
              onChange={(e) => {
                setJump(e.target.value)
                setJumpMsg(null)
              }}
              onKeyDown={(e) => {
                //: Enter این‌جا فرمِ سند را ثبت نمی‌کند — فقط می‌پرد.
                if (e.key === 'Enter') {
                  e.preventDefault()
                  jumpTo()
                } else if (e.key === 'Escape') {
                  e.preventDefault()
                  closeJump(true)
                }
              }}
              onBlur={() => closeJump(false)}
            />
          </label>
          <span className="jg-count">از {fa(d.lines.length)}</span>
          {jumpMsg && (
            <span className="jg-jump-msg" id="jg-jump-msg" role="status">
              {jumpMsg}
            </span>
          )}
        </div>
      )}
    <div
      ref={gridRef}
      className="table-scroll ef-table-wrap jg-wrap"
      onKeyDown={onKeyDown}
      role="grid"
      aria-label="ردیف‌های سند"
    >
      <table
        className={`ef-table ef-table--edit jg-table xl-grid table-plain${cw.customized ? ' xl-custom' : ''}`}
        style={cw.table(['num', ...cols, 'actions'])}
      >
        {/* عرضِ ستون‌ها (`table-layout: fixed`): حساب هرچه بماند می‌گیرد؛ شماره و شرح باریک،
            مبلغ‌ها پهن تا عددِ میلیاردی بی‌برش دیده شود. کاربر با کشیدنِ لبه‌ی سرستون عوضشان
            می‌کند (`useColumnWidths`). */}
        <colgroup>
          <col className="jg-c-num" style={cw.col('num')} />
          <col className="jg-c-account" style={cw.col('account')} />
          {showFx && <col className="jg-c-fx" style={cw.col('fx')} />}
          {showTafsili && <col className="jg-c-pick" style={cw.col('tafsili')} />}
          {showCostCenter && <col className="jg-c-pick" style={cw.col('costCenter')} />}
          <col className="jg-c-desc" style={cw.col('description')} />
          <col className="jg-c-amount" style={cw.col('debit')} />
          <col className="jg-c-amount" style={cw.col('credit')} />
          {showTracking && <col className="jg-c-track" style={cw.col('trackingNo')} />}
          {showTracking && <col className="jg-c-track" style={cw.col('trackingDate')} />}
          <col className="jg-c-actions" style={cw.col('actions')} />
        </colgroup>
        <thead>
          <tr>
            <th className="ef-col-min xl-rowhead" data-col="num">ردیف</th>
            {(
              [
                ['account', 'حساب'],
                ...(showFx ? [['fx', 'مبلغ ارزی']] : []),
                ...(showTafsili ? [['tafsili', 'تفصیلی']] : []),
                ...(showCostCenter ? [['costCenter', 'مرکز هزینه']] : []),
                ['description', 'شرح ردیف'],
                ['debit', 'بدهکار'],
                ['credit', 'بستانکار'],
                ...(showTracking ? [['trackingNo', 'شماره پیگیری'], ['trackingDate', 'تاریخ پیگیری']] : []),
              ] as [string, string][]
            ).map(([id, label]) => (
              <th key={id} data-col={id}>
                {label}
                <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />
              </th>
            ))}
            <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
          </tr>
        </thead>
        <tbody>
          {d.lines.map((line, i) => (
            <GridRow
              key={i}
              i={i}
              line={line}
              cols={cols}
              showFx={showFx}
              showTafsili={showTafsili}
              showTracking={showTracking}
              //: **هر prop باید پایدار باشد وگرنه `memo` بی‌اثر است.** خودِ `d`
              //: هر رندر شیءِ تازه‌ای است، پس عمداً پاس داده نمی‌شود — سنجیده
              //: شد که با پاس‌دادنش، هر کلیدفشار در سندِ ۳۰۰ ردیفی ۱۷۰ms
              //: می‌گرفت چون همه‌ی ردیف‌ها دوباره رندر می‌شدند.
              hasTafsili={d.tafsiliRequired.has(line.accountId)}
              hasTracking={d.trackingAllowed.has(line.accountId)}
              tafsiliRequired={d.tafsiliMode !== 'floating'}
              accountOptions={accountOptions}
              onAccountCommit={commitAccount}
              analytics={d.analytics}
              hasHeaderAnalytic={Boolean(d.analyticId)}
              showCostCenter={showCostCenter}
              costCenters={d.costCenters}
              hasHeaderCenter={Boolean(d.costCenterId)}
              canRemove={d.lines.length > 2}
              onUpdate={d.updateLine}
              onFx={d.setLineFx}
              onDuplicate={d.duplicateLine}
              onCopyPrev={d.copyPreviousInto}
              onRemove={d.removeLine}
              getDescriptionPool={descriptionPool}
              selected={selected.has(String(i))}
              mark={hitSet ? (i === current ? 'current' : hitSet.has(i) ? 'hit' : 'dim') : undefined}
              onRowHead={onRowHead}
            />
          ))}
        </tbody>
      </table>
    </div>
      {selectedRows.length > 0 && (
        <SelectionBar count={selectedRows.length} unit="ردیف" onClear={clearSelection}>
          <span>
            جمع بدهکار <b className="num">{fa(sumOf(d.lines, selectedRows, 'debit'))}</b>
          </span>
          <span>
            جمع بستانکار <b className="num">{fa(sumOf(d.lines, selectedRows, 'credit'))}</b>
          </span>
          <button type="button" className="xl-selbar-danger" onClick={deleteSelected}>
            <Trash2 size={14} aria-hidden="true" /> حذفِ ردیف‌ها (Ctrl+Delete)
          </button>
        </SelectionBar>
      )}
    </div>
  )
}

//: جمعِ یک طرفِ ردیف‌های انتخاب‌شده — همان «جمع»ِ نوارِ وضعیتِ اکسل.
function sumOf(lines: JournalDraftLine[], rows: number[], side: 'debit' | 'credit'): number {
  return rows.reduce((s, r) => s + (Number(lines[r]?.[side]) || 0), 0)
}

/**
 * یک ردیفِ گرید.
 *
 * `memo` این‌جا برای ادعای زیبایی نیست: سندِ ۳۰۰ ردیفی بدونِ آن، با هر کلیدفشاری
 * ۳۰۰ ردیف را دوباره رندر می‌کند. مقایسه‌ی سطحیِ props کافی است چون `line` با
 * `updateLine` **جایگزین** می‌شود (شیءِ تازه) نه ویرایش در جا.
 */
const GridRow = memo(function GridRow({
  i,
  line,
  cols,
  showFx,
  showTafsili,
  showTracking,
  hasTafsili,
  hasTracking,
  tafsiliRequired,
  accountOptions,
  onAccountCommit,
  analytics,
  hasHeaderAnalytic,
  showCostCenter,
  costCenters,
  hasHeaderCenter,
  canRemove,
  onUpdate,
  onFx,
  onDuplicate,
  onCopyPrev,
  onRemove,
  getDescriptionPool,
  selected,
  mark,
  onRowHead,
}: {
  i: number
  line: JournalDraftLine
  cols: ColId[]
  showFx: boolean
  showTafsili: boolean
  showTracking: boolean
  hasTafsili: boolean
  hasTracking: boolean
  tafsiliRequired: boolean
  accountOptions: ComboOption[]
  onAccountCommit: (row: number, how: ComboCommit) => void
  analytics: JournalEntryDraft['analytics']
  hasHeaderAnalytic: boolean
  showCostCenter: boolean
  costCenters: JournalEntryDraft['costCenters']
  hasHeaderCenter: boolean
  canRemove: boolean
  onUpdate: JournalEntryDraft['updateLine']
  onFx: JournalEntryDraft['setLineFx']
  onDuplicate: JournalEntryDraft['duplicateLine']
  onCopyPrev: JournalEntryDraft['copyPreviousInto']
  onRemove: JournalEntryDraft['removeLine']
  getDescriptionPool: (row: number) => string[]
  selected: boolean
  /** نتیجه‌ی جست‌وجوی سریع: `current` همانی که Enter رویش است، `hit` پیدا شد، `dim` نه. */
  mark: 'current' | 'hit' | 'dim' | undefined
  onRowHead: (row: number, mods: ClickMods) => void
}) {
  const col = (id: ColId) => cols.indexOf(id)

  return (
    <tr className={[selected && 'is-selected', mark && `is-${mark}`].filter(Boolean).join(' ') || undefined}>
      {/* `card-title` و `card-actions` دو کلاسِ معافِ قرارداد صفحه‌اند: در نمای
          کارتی سرِ کارت و نوارِ کنش می‌شوند و برچسب نمی‌خواهند. */}
      <td className="ef-col-min jg-num xl-rowhead card-title">
        {/* سرستونِ ردیف مثلِ اکسل: کلیک انتخاب، Ctrl+کلیک افزودن، Shift+کلیک بازه. از Tabِ گرید
            بیرون است (`tabIndex=-1`) — ناوبریِ صفحه‌کلید خانه‌به‌خانه است. */}
        <button
          type="button"
          tabIndex={-1}
          className="xl-rowhead-btn"
          aria-pressed={selected}
          aria-label={`انتخابِ ردیفِ ${fa(i + 1)}`}
          onClick={(e) => onRowHead(i, modsOf(e))}
        >
          {fa(i + 1)}
        </button>
      </td>

      <td className="ef-col-wide" data-cell={`${i}-${col('account')}`}>
        <AccountCombo
          aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
          value={line.accountId}
          options={accountOptions}
          onChange={(v) => onUpdate(i, { accountId: v })}
          onCommit={(how) => onAccountCommit(i, how)}
        />
      </td>

      {showFx && (
        <td data-cell={`${i}-${col('fx')}`}>
          <NumberInput
            aria-label={`مبلغِ ارزیِ ردیفِ ${fa(i + 1)}`}
            value={line.fxAmount ?? ''}
            onChange={(v) => onFx(i, v)}
            allowDecimal
          />
        </td>
      )}

      {showTafsili && (
        <td data-cell={`${i}-${col('tafsili')}`}>
          {hasTafsili ? (
            <SearchSelect
              aria-label={`تفصیلیِ ردیفِ ${fa(i + 1)}`}
              value={line.analyticId ?? ''}
              onChange={(e) => onUpdate(i, { analyticId: e.target.value })}
              required={tafsiliRequired}
            >
              <option value="">{hasHeaderAnalytic ? '— تفصیلیِ سند —' : '— انتخاب کنید —'}</option>
              {analytics.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name}
                </option>
              ))}
            </SearchSelect>
          ) : (
            <input type="text" value="" disabled readOnly placeholder="—" aria-label="بدونِ تفصیلی" />
          )}
        </td>
      )}

      {showCostCenter && (
        <td data-cell={`${i}-${col('costCenter')}`}>
          <SearchSelect
            aria-label={`مرکزِ هزینه‌ی ردیفِ ${fa(i + 1)}`}
            value={line.costCenterId ?? ''}
            onChange={(e) => onUpdate(i, { costCenterId: e.target.value })}
          >
            {/* خالی یعنی «همان مرکزِ سند» اگر سند مرکز دارد — متنِ گزینه همین را می‌گوید. */}
            <option value="">{hasHeaderCenter ? '— مرکزِ سند —' : '— بدون مرکز —'}</option>
            {costCenters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} — ${c.name}` : c.name}
              </option>
            ))}
          </SearchSelect>
        </td>
      )}

      <td data-cell={`${i}-${col('description')}`}>
        <DescriptionInput
          aria-label={`شرحِ ردیفِ ${fa(i + 1)}`}
          value={line.description ?? ''}
          row={i}
          onUpdate={onUpdate}
          getDescriptionPool={getDescriptionPool}
          placeholder="اختیاری"
        />
      </td>

      <td data-cell={`${i}-${col('debit')}`}>
        <NumberInput
          aria-label={`بدهکارِ ردیفِ ${fa(i + 1)}`}
          value={line.debit}
          onChange={(v) => onUpdate(i, { debit: v, credit: '' })}
        />
      </td>

      <td data-cell={`${i}-${col('credit')}`}>
        <NumberInput
          aria-label={`بستانکارِ ردیفِ ${fa(i + 1)}`}
          value={line.credit}
          onChange={(v) => onUpdate(i, { credit: v, debit: '' })}
        />
      </td>

      {showTracking && (
        <td data-cell={`${i}-${col('trackingNo')}`}>
          <input
            type="text"
            aria-label={`شماره پیگیریِ ردیفِ ${fa(i + 1)}`}
            value={line.trackingNo ?? ''}
            onChange={(e) => onUpdate(i, { trackingNo: e.target.value })}
            disabled={!hasTracking}
            maxLength={50}
            placeholder={hasTracking ? 'حواله/نامه' : '—'}
          />
        </td>
      )}

      {showTracking && (
        <td data-cell={`${i}-${col('trackingDate')}`}>
          {hasTracking ? (
            <JalaliDatePicker
              value={line.trackingDate ?? ''}
              onChange={(v) => onUpdate(i, { trackingDate: v })}
            />
          ) : (
            <input type="text" value="" disabled readOnly placeholder="—" aria-label="بدونِ پیگیری" />
          )}
        </td>
      )}

      {/* فلکس روی `.row-actions`ِ داخلی می‌نشیند و **نه روی خودِ `<td>`** — همان
          الگویی که بقیه‌ی جدول‌های این برنامه دارند. `display:flex` روی یک
          `<td>` سلول را از چیدمانِ جدول بیرون می‌اندازد: عرضش به ستون گوش
          نمی‌دهد، به ۱۷px جمع می‌شود و دکمه‌ها بیرون می‌زنند روی کادرِ بستانکار. */}
      <td className="ef-col-min jg-actions card-actions">
        <div className="row-actions">
          <RowAction
            icon={CopyPlus}
            label="تکرار ردیف"
            title="تکرار ردیف (Ctrl+D)"
            onClick={() => onDuplicate(i)}
          />
          <RowAction
            icon={Copy}
            label="کپی از ردیف قبل"
            title="کپیِ حساب و تفصیلی از ردیف قبل (Ctrl+Shift+C)"
            disabled={i === 0}
            onClick={() => onCopyPrev(i)}
          />
          <RowAction
            icon={Trash2}
            label="حذف ردیف"
            danger
            disabled={!canRemove}
            title={!canRemove ? 'سند دست‌کم دو ردیف می‌خواهد.' : 'حذف ردیف (Ctrl+Delete)'}
            onClick={() => onRemove(i)}
          />
        </div>
      </td>
    </tr>
  )
})
