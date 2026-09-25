import { useState, type CSSProperties, type PointerEvent } from 'react'

/** کمینه‌ی عرضِ ستون — کمتر از این، برچسب و عدد هر دو خوانده نمی‌شوند. */
export const MIN_COL_WIDTH = 48

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
  const autoMin = layout.autoMin ?? 160
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

export function useColumnWidths(storageKey: string, layout: ColumnLayout) {
  const [shares, setShares] = useState<Shares | null>(() => load(storageKey))

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
    begin,
    reset,
    /** لبه‌ی میانِ `col` و `next` کشیدنی است؟ (هیچ‌کدام ثابت نباشند.) */
    canResize: (col: string, next: string | undefined): boolean =>
      next !== undefined && !layout.fixed.includes(col) && !layout.fixed.includes(next),
    /** سبکِ `<col>`؛ تا کاربر دست نزده، هیچ. ستونِ ثابت هیچ‌وقت (عرضش مالِ CSS است)، ستونِ کشسان
     *  صریحاً `auto` (تا عرضِ پیش‌فرضِ کلاسش نماند)، بقیه درصدِ ذخیره‌شده — و ستونی که تازه پیدا
     *  شده و درصدی ندارد، همان پیش‌فرضِ CSS. */
    col: (id: string): CSSProperties | undefined => {
      if (!shares || layout.fixed.includes(id)) return undefined
      if (id === layout.auto) return { width: 'auto' }
      return shares[id] !== undefined ? { width: `${shares[id]}%` } : undefined
    },
  }
}

function load(key: string): Shares | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    const out: Shares = {}
    //: فقط درصدِ معقول: عرض‌های پیکسلیِ نسخه‌ی قبل (بزرگ‌تر از ۱۰۰) کنار گذاشته می‌شوند.
    for (const [k, v] of Object.entries(parsed)) if (typeof v === 'number' && v > 0 && v < 100) out[k] = v
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}
