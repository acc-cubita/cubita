import { useLayoutEffect, useRef, type RefObject } from 'react'

/**
 * سربرگ و نوارِ پایینِ سند را **ستون‌به‌ستون** با گریدِ ردیف‌ها هم‌خط می‌کند — از دیدِ کاربر هر سه
 * یک جدول‌اند، با خطوطِ عمودیِ پیوسته.
 *
 * هر دو شبکه‌ای پنج‌خانه‌ای‌اند که مرزهایش همان مرزِ ستون‌های گرید است:
 *   ۱. ردیف + حساب (+ ستون‌های میانیِ ارز، تفصیلی، مرکز هزینه)   ۲. شرح ردیف   ۳. بدهکار
 *   ۴. بستانکار   ۵. پیگیری + آیکون‌ها
 * پس «جمع بدهکار» دقیقاً زیرِ ستونِ بدهکار است و «تاریخ سند» دقیقاً بالای آن. عرض‌ها از خودِ گرید
 * سنجیده می‌شوند — ستون‌ها کشیدنی‌اند و ستونِ مرکز هزینه گاهی می‌آید — و روی متغیرِ CSSِ `--jg-cols`ِ
 * هر دنباله‌رو می‌نشینند. خانه‌ی اول فاصله‌ی لبه‌ی دنباله‌رو تا لبه‌ی جدول را هم می‌گیرد (نوارِ پایین
 * از کارتِ گرید پهن‌تر است) و خانه‌ی آخر کشسان است تا گردکردنِ زیرپیکسلی سرریز نسازد.
 *
 * وقتی گرید خودش افقی می‌لغزد (پنجره‌ی باریک)، هم‌خطی ممکن نیست: متغیر برداشته می‌شود و CSS
 * نسبت‌های پیش‌فرضِ همان ستون‌ها را می‌دهد. مستقیم روی `style` نوشته می‌شود، نه state — کشیدنِ ستون
 * نباید کلِ فرم را دوباره رندر کند (همان الگوی `useFitText`).
 *
 * صفحه‌های هم‌سبکِ دیگر (مانده اول دوره) جدولِ خودشان (`table`) و نگاشتِ خودشان (`slots`) را می‌دهند —
 * همان پنج خانه، از ستون‌های دیگر.
 */
export const SLOT_COUNT = 5

/** عرضِ پنج خانه از عرضِ ستون‌های گرید، به ترتیبِ روی صفحه. هر ستونِ پس از «بستانکار» خانه‌ی پنجم است. خالص. */
export function slotWidths(cols: readonly { id: string; w: number }[]): number[] {
  const out = new Array<number>(SLOT_COUNT).fill(0)
  let slot = 0
  for (const c of cols) {
    if (c.id === 'description') slot = 1
    else if (c.id === 'debit') slot = 2
    else if (c.id === 'credit') slot = 3
    else if (slot === 3) slot = 4
    out[slot] += c.w
  }
  return out
}

/** ستون‌های گرید (شناسه و عرض، به ترتیبِ روی صفحه) → عرضِ پنج خانه. */
export type SlotMap = (cols: readonly { id: string; w: number }[]) => number[]

export interface AlignOptions {
  /** سلکتورِ جدولی که هم‌خطی از آن سنجیده می‌شود. پیش‌فرض: گریدِ سند. */
  table?: string
  slots?: SlotMap
}

const headsOf = (table: string) => `${table} thead tr:first-child > th[data-col]`

function align(root: HTMLElement, followers: string, table: string, slotMap: SlotMap) {
  const wrap = root.querySelector(table)?.closest<HTMLElement>('.ef-table-wrap')
  const ths = [...root.querySelectorAll<HTMLElement>(headsOf(table))]
  const els = [...root.querySelectorAll<HTMLElement>(followers)]
  //: گریدی که افقی می‌لغزد با هیچ چیزِ بیرونش هم‌خط نمی‌ماند.
  if (!wrap || ths.length === 0 || wrap.scrollWidth > wrap.clientWidth + 1) {
    for (const el of els) el.style.removeProperty('--jg-cols')
    return
  }
  const rtl = getComputedStyle(root).direction === 'rtl'
  const rects = ths.map((th) => th.getBoundingClientRect())
  const slots = slotMap(ths.map((th, i) => ({ id: th.dataset.col ?? '', w: rects[i].width })))
  const gridStart = rtl ? rects[0].right : rects[0].left
  for (const el of els) {
    const r = el.getBoundingClientRect()
    const border = parseFloat(getComputedStyle(el).borderInlineStartWidth) || 0
    const inset = rtl ? r.right - border - gridStart : gridStart - (r.left + border)
    const tracks = slots.slice(0, -1).map((w, i) => `${Math.max(0, i === 0 ? w + inset : w).toFixed(2)}px`)
    const cols = [...tracks, 'minmax(0, 1fr)'].join(' ')
    if (el.style.getPropertyValue('--jg-cols') !== cols) el.style.setProperty('--jg-cols', cols)
  }
}

/**
 * `followers` (سلکتورِ CSS درونِ `rootRef`) را با گریدِ همان ریشه هم‌خط نگه می‌دارد. با هر تغییرِ
 * اندازه‌ی سرستون‌ها، قابِ گرید یا خودِ دنباله‌روها دوباره می‌سنجد؛ بعد از هر رندر فقط فهرستِ
 * سرستون‌ها را (بی‌سنجش) نگاه می‌کند تا ستونی که آمد یا رفت زیرِ نظر برود.
 */
export function useAlignToGrid(rootRef: RefObject<HTMLElement | null>, followers: string, options: AlignOptions = {}) {
  const table = options.table ?? '.jg-table'
  const slotMap = options.slots ?? slotWidths
  const watch = useRef<{ root: HTMLElement; ro: ResizeObserver; targets: Element[] } | null>(null)

  useLayoutEffect(() => {
    const root = rootRef.current
    //: ریشه عوض شد (مثلاً رفتن از حالتِ ساده به حسابدار فرمِ دیگری می‌سازد).
    if (watch.current && watch.current.root !== root) {
      watch.current.ro.disconnect()
      watch.current = null
    }
    if (!root || typeof ResizeObserver === 'undefined') return
    if (!watch.current) {
      watch.current = { root, ro: new ResizeObserver(() => align(root, followers, table, slotMap)), targets: [] }
    }
    const w = watch.current
    const frame = root.querySelector(table)?.closest('.ef-table-wrap')
    const targets = [...(frame ? [frame] : []), ...root.querySelectorAll(`${headsOf(table)}, ${followers}`)]
    if (targets.length === w.targets.length && targets.every((t, i) => t === w.targets[i])) return
    //: `observe` خودش یک‌بار فوراً گزارش می‌دهد، پس سنجشِ اول همین‌جا انجام می‌شود.
    w.ro.disconnect()
    for (const t of targets) w.ro.observe(t)
    w.targets = targets
  })

  useLayoutEffect(
    () => () => {
      watch.current?.ro.disconnect()
      watch.current = null
    },
    [],
  )
}
