import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Copy, CopyPlus, Trash2 } from 'lucide-react'

import { SearchSelect } from './SearchSelect'
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
export function JournalGrid({ d }: { d: JournalEntryDraft }) {
  const gridRef = useRef<HTMLDivElement>(null)
  const jumpRef = useRef<HTMLInputElement>(null)
  const [jump, setJump] = useState('')
  const [jumpMsg, setJumpMsg] = useState<string | null>(null)

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
  //: **مسیرِ Enter از مرکزِ هزینه می‌پرد** (§۱۵): در سندِ دستی اجباری نیست، و خانه‌ای
  //: که بیشترِ ردیف‌ها خالی می‌گذارند هر ردیف را یک Enterِ اضافه کند می‌کرد. Tab و موس
  //: به آن می‌رسند و ↑/↓ داخلِ همان ستون کار می‌کند (آن‌ها `enabled` را می‌خوانند).
  const onEnterPath = useCallback(
    (row: number, col: ColId) => col !== 'costCenter' && enabled(row, col),
    [enabled],
  )

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
    const first = gridRef.current?.querySelector<HTMLElement>('[data-cell="0-0"] button, [data-cell="0-0"] select')
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
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    const cellEl = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]')
    const coords = cellEl?.dataset.cell?.split('-').map(Number)
    if (!coords || coords.length !== 2) return
    const at = { row: coords[0], col: coords[1] }

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
        jumpRef.current?.focus()
        jumpRef.current?.select()
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
      if (!e.shiftKey && (col === 'account' || col === 'tafsili')) {
        const emptyPick = col === 'account' ? !line?.accountId : !line?.analyticId
        if (emptyPick && (e.target as HTMLElement).closest('.item-picker-trigger')) return
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
    <>
    <div className="jg-toolbar">
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
          title="Ctrl + G از هر خانه‌ی گرید"
          onChange={(e) => {
            setJump(e.target.value)
            setJumpMsg(null)
          }}
          onKeyDown={(e) => {
            //: Enter این‌جا فرمِ سند را ثبت نمی‌کند — فقط می‌پرد.
            if (e.key === 'Enter') {
              e.preventDefault()
              jumpTo()
            }
          }}
        />
      </label>
      <span className="jg-count">{fa(d.lines.length)} ردیف</span>
      {jumpMsg && (
        <span className="jg-jump-msg" id="jg-jump-msg" role="status">
          {jumpMsg}
        </span>
      )}
    </div>
    <div
      ref={gridRef}
      className="table-scroll ef-table-wrap jg-wrap"
      onKeyDown={onKeyDown}
      role="grid"
      aria-label="ردیف‌های سند"
    >
      <table className="ef-table ef-table--edit jg-table table-plain">
        <thead>
          <tr>
            <th className="ef-col-min">ردیف</th>
            <th>حساب</th>
            {showFx && <th>مبلغ ارزی</th>}
            {showTafsili && <th>تفصیلی</th>}
            {showCostCenter && <th>مرکز هزینه</th>}
            <th>شرح ردیف</th>
            <th>بدهکار</th>
            <th>بستانکار</th>
            {showTracking && <th>شماره پیگیری</th>}
            {showTracking && <th>تاریخ پیگیری</th>}
            <th className="ef-col-min" aria-label="کنش‌ها" />
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
              accounts={d.postableAccounts}
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
            />
          ))}
        </tbody>
      </table>
    </div>
    </>
  )
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
  accounts,
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
  accounts: JournalEntryDraft['postableAccounts']
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
}) {
  const col = (id: ColId) => cols.indexOf(id)

  return (
    <tr>
      {/* `card-title` و `card-actions` دو کلاسِ معافِ قرارداد صفحه‌اند: در نمای
          کارتی سرِ کارت و نوارِ کنش می‌شوند و برچسب نمی‌خواهند. */}
      <td className="ef-col-min jg-num card-title">{fa(i + 1)}</td>

      <td className="ef-col-wide" data-cell={`${i}-${col('account')}`}>
        <SearchSelect
          aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
          value={line.accountId}
          onChange={(e) => onUpdate(i, { accountId: e.target.value })}
        >
          <option value="">— انتخاب حساب —</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} — {a.name}
            </option>
          ))}
        </SearchSelect>
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
