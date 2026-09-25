import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'

/** کمینه‌ی عرضِ ستون — کمتر از این، برچسب و عدد هر دو خوانده نمی‌شوند. */
export const MIN_COL_WIDTH = 48

/** کمینه‌ی پیش‌فرضِ ستونِ کشسان (`ColumnLayout.autoMin`). */
const AUTO_MIN = 160

/**
 * عرضِ ستون‌های جدولِ اکسل‌مانند، در حالتِ **«جا در قاب»**: جدول همیشه دقیقاً هم‌عرضِ قابِ خودش
 * است و کشیدنِ ستون هرگز اسکرولِ افقی نمی‌سازد.
 *
 * سه جور ستون:
 * - **ثابت** (`fixed` — شماره‌ی ردیف و ستونِ آیکون‌های کنش): عرضِ پیکسلیِ خودشان را از CSS دارند
 *   و هیچ‌وقت عوض نمی‌شوند.
 * - **کشسان** (`auto`، یکی — حسابِ سند، شرحِ فهرست): عرضِ صریح ندارد و باقیِ عرض را می‌گیرد، پس با
 *   بزرگ و کوچک‌شدنِ پنجره هم جدول پر می‌ماند.
 * - **بقیه**: درصدی از عرضِ جدول.
 *
 * **کشیدنِ لبه‌ی میانِ دو ستون فقط همان دو را عوض می‌کند** — یکی پهن‌تر، هم‌سایه‌اش به همان اندازه
 * باریک‌تر؛ ستون‌های دیگر و عرضِ کلِ جدول دست نمی‌خورند (اگر یکی از آن دو کشسان باشد، سهمِ او خودکار
 * عوض می‌شود). نسخه‌های قبل جدول را به جمعِ ستون‌ها می‌رساندند: باریک‌کردن فضای سفید می‌گذاشت،
 * پهن‌کردن اسکرولِ افقی، و پرکردنِ جای خالی با ستونی دیگر همه را جابه‌جا می‌کرد — کاربر گفت «همه‌ی
 * جدول به‌هم می‌ریزد» و «ردیف و ستونِ آیکون‌ها باید ثابت باشند تا اسکرولِ افقی ایجاد نشود». لبه‌ی
 * کنارِ ستونِ ثابت کشیدنی نیست (`canResize`).
 *
 * تا کاربر دست نزده، هیچ عرضی نوشته نمی‌شود و چیدمانِ پیش‌فرضِ CSS می‌ماند. روی همین دستگاه ذخیره
 * می‌شود؛ دوبار کلیک روی هر لبه همه را به پیش‌فرض برمی‌گرداند.
 *
 * **کفِ ستونِ کشسان در زمانِ نمایش هم پابرجاست** (`fitShares`)، نه فقط هنگامِ کشیدن. درصدها
 * نسبت به عرضِ جدول‌اند ولی ستون‌های ثابت پیکسلی: سهم‌هایی که در پنجره‌ی پهن جا می‌شدند، در پنجره‌ی
 * باریک‌تر همه‌ی جا را می‌گرفتند و «حساب» صفر می‌شد — ستونش ناپدید و فلشِ کادرش روی شماره‌ی ردیف.
 * حالا اگر جا کم باشد، ستون‌های درصدی به یک نسبت کوچک می‌شوند تا کشسان کمینه‌اش را داشته باشد.
 * برای این، جدول با `frame` (ref) سنجیده می‌شود.
 */
export interface ColumnLayout {
  /** ستون‌هایی که هیچ‌وقت عوض نمی‌شوند. */
  fixed: readonly string[]
  /** تنها ستونِ بی‌عرضِ صریح که باقی را می‌گیرد. */
  auto: string
  /** کمینه‌ی ستونِ کشسان — تا کشیدنِ بقیه آن را از بین نبرد. */
  autoMin?: number
}

/** درصدِ هر ستون از عرضِ جدول. */
export type Shares = Record<string, number>

/**
 * حرکتِ لبه‌ی میانِ `col` و ستونِ بعدی‌اش به اندازه‌ی `dPx` (مثبت = `col` پهن‌تر). خالص و آزمون‌پذیر.
 * `px` عرضِ فعلیِ همه‌ی ستون‌ها و `ids` ترتیبشان روی صفحه است. خروجی سهمِ درصدیِ ستون‌های غیرثابت و
 * غیرکشسان — با رعایتِ کمینه‌ها؛ `null` اگر این لبه کشیدنی نیست.
 */
export function dragBoundary(
  px: Record<string, number>,
  ids: readonly string[],
  col: string,
  dPx: number,
  layout: ColumnLayout,
): Shares | null {
  const next = ids[ids.indexOf(col) + 1]
  if (!next || layout.fixed.includes(col) || layout.fixed.includes(next)) return null
  const total = ids.reduce((s, id) => s + (px[id] ?? 0), 0)
  if (total <= 0) return null
  const autoMin = layout.autoMin ?? AUTO_MIN
  const minOf = (id: string) => (id === layout.auto ? autoMin : MIN_COL_WIDTH)
  //: جمعِ دو ستون ثابت است؛ `d` محدود می‌شود تا هیچ‌کدام زیرِ کمینه‌اش نرود.
  const d = Math.max(minOf(col) - px[col], Math.min(dPx, px[next] - minOf(next)))
  const out: Record<string, number> = { ...px, [col]: px[col] + d, [next]: px[next] - d }
  const shares: Shares = {}
  for (const id of ids) {
    if (layout.fixed.includes(id) || id === layout.auto) continue
    shares[id] = Math.round((out[id] / total) * 10000) / 100
  }
  return shares
}

/**
 * سهم‌های درصدیِ `flex` را به یک نسبت کوچک می‌کند تا در جدولی به عرضِ `tableW` — که `reservedPx`ش
 * مالِ ستون‌های بی‌سهم است (ثابت‌ها و ستونِ تازه‌ای که هنوز درصد ندارد) — دستِ‌کم `autoMin` برای
 * ستونِ کشسان بماند. اگر جا هست، همان ورودی برمی‌گردد. هیچ ستونی زیرِ `MIN_COL_WIDTH` نمی‌رود. خالص.
 */
export function fitShares(
  shares: Shares,
  flex: readonly string[],
  tableW: number,
  reservedPx: number,
  autoMin: number = AUTO_MIN,
): Shares {
  const used = flex.reduce((s, id) => s + ((shares[id] ?? 0) / 100) * tableW, 0)
  const room = tableW - reservedPx - autoMin
  if (tableW <= 0 || used <= room) return shares
  const k = Math.max(room, 0) / used
  const floor = (MIN_COL_WIDTH / tableW) * 100
  const out: Shares = { ...shares }
  for (const id of flex) {
    if (shares[id] !== undefined) out[id] = Math.max(floor, Math.round(shares[id] * k * 100) / 100)
  }
  return out
}

/** اندازه‌ی جدولِ روی صفحه: عرضش، پیکسلِ ستون‌های بی‌سهم، و ستون‌های درصدیِ نمایان. */
interface Frame {
  w: number
  reserved: number
  flex: string[]
}

export function useColumnWidths(storageKey: string, layout: ColumnLayout) {
  const [shares, setShares] = useState<Shares | null>(() => load(storageKey, layout))
  const [frame, setFrame] = useState<Frame | null>(null)
  const tableRef = useRef<HTMLTableElement | null>(null)
  const measureRef = useRef<() => void>(() => {})

  //: بعد از **هر** رندر دوباره سنجیده می‌شود، نه فقط با تغییرِ اندازه: ستونی که تازه پیدا می‌شود
  //: (مرکز هزینه، ارز) عرضِ جدول را عوض نمی‌کند ولی جا می‌گیرد. `setFrame` فقط با تغییرِ واقعی
  //: رندرِ دوباره می‌سازد، پس حلقه نمی‌شود.
  useLayoutEffect(() => {
    measureRef.current = () => {
      const table = tableRef.current
      if (!table || !shares) {
        setFrame(null)
        return
      }
      let reserved = 0
      const flex: string[] = []
      for (const th of table.querySelectorAll<HTMLElement>('thead tr:first-child > th[data-col]')) {
        const id = th.dataset.col!
        if (id === layout.auto) continue
        if (!layout.fixed.includes(id) && shares[id] !== undefined) flex.push(id)
        else reserved += th.getBoundingClientRect().width
      }
      const w = table.getBoundingClientRect().width
      setFrame((f) =>
        f && Math.abs(f.w - w) < 1 && Math.abs(f.reserved - reserved) < 1 && f.flex.join() === flex.join()
          ? f
          : { w, reserved, flex },
      )
    }
    measureRef.current()
  })

  /** روی `<table>` بگذار — تا کفِ ستونِ کشسان با عرضِ واقعیِ جدول سنجیده شود. */
  const frameRef = useCallback((table: HTMLTableElement | null) => {
    tableRef.current = table
    if (!table || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => measureRef.current())
    ro.observe(table)
    return () => {
      ro.disconnect()
      tableRef.current = null
    }
  }, [])

  const fitted = shares && frame ? fitShares(shares, frame.flex, frame.w, frame.reserved, layout.autoMin) : shares

  function persist(next: Shares | null) {
    try {
      if (next) localStorage.setItem(storageKey, JSON.stringify(next))
      else localStorage.removeItem(storageKey)
    } catch {
      //: ذخیره‌نشدن فقط یعنی عرض با بستنِ برنامه برمی‌گردد.
    }
  }

  function begin(e: PointerEvent<HTMLElement>, col: string) {
    if (e.button !== 0) return
    const handle = e.currentTarget
    const table = handle.closest('table')
    if (!table) return
    e.preventDefault()
    const ths = [...table.querySelectorAll<HTMLElement>('thead tr:first-child > th[data-col]')]
    const ids = ths.map((th) => th.dataset.col!)
    const px: Record<string, number> = {}
    for (const th of ths) px[th.dataset.col!] = th.getBoundingClientRect().width
    const rtl = getComputedStyle(table).direction === 'rtl'
    const x0 = e.clientX
    let latest: Shares | null = shares
    handle.setPointerCapture?.(e.pointerId)
    handle.classList.add('is-resizing')
    const move = (ev: globalThis.PointerEvent) => {
      const dx = ev.clientX - x0
      const next = dragBoundary(px, ids, col, rtl ? -dx : dx, layout)
      if (!next) return
      latest = { ...(shares ?? {}), ...next }
      setShares(latest)
    }
    const up = () => {
      handle.removeEventListener('pointermove', move)
      handle.removeEventListener('pointerup', up)
      handle.removeEventListener('pointercancel', up)
      handle.classList.remove('is-resizing')
      persist(latest)
    }
    handle.addEventListener('pointermove', move)
    handle.addEventListener('pointerup', up)
    handle.addEventListener('pointercancel', up)
  }

  function reset() {
    setShares(null)
    persist(null)
  }

  return {
    customized: shares !== null,
    frame: frameRef,
    begin,
    reset,
    /** لبه‌ی میانِ `col` و `next` کشیدنی است؟ (هیچ‌کدام ثابت نباشند.) */
    canResize: (col: string, next: string | undefined): boolean =>
      next !== undefined && !layout.fixed.includes(col) && !layout.fixed.includes(next),
    /** سبکِ `<col>`؛ تا کاربر دست نزده، هیچ. ستونِ ثابت هیچ‌وقت (عرضش مالِ CSS است)، ستونِ کشسان
     *  صریحاً `auto` (تا عرضِ پیش‌فرضِ کلاسش نماند)، بقیه درصدِ ذخیره‌شده — و ستونی که تازه پیدا
     *  شده و درصدی ندارد، همان پیش‌فرضِ CSS. */
    col: (id: string): CSSProperties | undefined => {
      if (!fitted || layout.fixed.includes(id)) return undefined
      if (id === layout.auto) return { width: 'auto' }
      return fitted[id] !== undefined ? { width: `${fitted[id]}%` } : undefined
    },
  }
}

function load(key: string, layout: ColumnLayout): Shares | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    //: سهمی برای ستونِ ثابت یا کشسان یعنی قالبِ نسخه‌های پیش از «جا در قاب» (که شماره و حساب را هم
    //: می‌نوشتند، گاهی پیکسلی) — کلش کنار می‌رود و چیدمانِ پیش‌فرض برمی‌گردد.
    if (Object.keys(parsed).some((k) => k === layout.auto || layout.fixed.includes(k))) return null
    const out: Shares = {}
    //: فقط درصدِ معقول: عرض‌های پیکسلیِ نسخه‌ی قبل (بزرگ‌تر از ۱۰۰) کنار گذاشته می‌شوند.
    for (const [k, v] of Object.entries(parsed)) if (typeof v === 'number' && v > 0 && v < 100) out[k] = v
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}
