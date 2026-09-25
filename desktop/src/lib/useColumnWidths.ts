import { useState, type CSSProperties, type PointerEvent } from 'react'

/** کمینه‌ی عرضِ ستون — کمتر از این، برچسب و عدد هر دو خوانده نمی‌شوند. */
export const MIN_COL_WIDTH = 48

/**
 * عرضِ ستون‌های یک جدولِ اکسل‌مانند که کاربر با کشیدنِ لبه‌ی سرستون عوض می‌کند.
 *
 * **تا کاربر دست نزده، جدول چیدمانِ پیش‌فرضِ خودش را دارد** (درصدی یا خودکار) و این هوک
 * هیچ عرضی نمی‌نویسد. با اولین کشیدن، عرضِ **همه‌ی** ستون‌ها از سرستون‌ها سنجیده و پیکسلی
 * می‌شود (`data-col` روی `<th>`)؛ وگرنه بزرگ‌کردنِ یکی بقیه‌ی ستون‌های درصدی را جابه‌جا
 * می‌کرد. از آن به بعد جدول به اندازه‌ی جمعِ ستون‌هاست و اگر از قاب پهن‌تر شد، افقی می‌لغزد.
 *
 * روی همین دستگاه می‌ماند (مثلِ ترتیبِ منوها و میان‌برها). دوبار کلیک روی هر لبه همه را به
 * پیش‌فرض برمی‌گرداند. جهت از خودِ جدول خوانده می‌شود: در راست‌به‌چپ لبه‌ی کشیدنی سمتِ چپِ
 * ستون است و کشیدن به چپ پهن‌ترش می‌کند.
 */
export function useColumnWidths(storageKey: string, fallback: Record<string, number>) {
  const [widths, setWidths] = useState<Record<string, number> | null>(() => load(storageKey))

  function persist(next: Record<string, number> | null) {
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
    const snapshot: Record<string, number> = { ...(widths ?? {}) }
    table.querySelectorAll<HTMLElement>('thead tr:first-child > th[data-col]').forEach((th) => {
      snapshot[th.dataset.col!] = Math.round(th.getBoundingClientRect().width)
    })
    const start = snapshot[col] ?? fallback[col] ?? 120
    const rtl = getComputedStyle(table).direction === 'rtl'
    const x0 = e.clientX
    let latest = snapshot
    handle.setPointerCapture?.(e.pointerId)
    handle.classList.add('is-resizing')
    const move = (ev: globalThis.PointerEvent) => {
      const dx = ev.clientX - x0
      latest = { ...snapshot, [col]: Math.max(MIN_COL_WIDTH, Math.round(start + (rtl ? -dx : dx))) }
      setWidths(latest)
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
    setWidths(null)
    persist(null)
  }

  return {
    customized: widths !== null,
    begin,
    reset,
    /** سبکِ `<col>`؛ تا کاربر دست نزده، هیچ — چیدمانِ پیش‌فرض می‌ماند. */
    col: (id: string): CSSProperties | undefined => (widths ? { width: widths[id] ?? fallback[id] ?? 120 } : undefined),
    /** سبکِ `<table>` برای ستون‌هایی که الان دیده می‌شوند. */
    table: (ids: readonly string[]): CSSProperties | undefined =>
      widths ? { width: ids.reduce((s, id) => s + (widths[id] ?? fallback[id] ?? 120), 0), minInlineSize: 0 } : undefined,
  }
}

function load(key: string): Record<string, number> | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    const out: Record<string, number> = {}
    for (const [k, v] of Object.entries(parsed)) if (typeof v === 'number' && v >= MIN_COL_WIDTH) out[k] = v
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}
