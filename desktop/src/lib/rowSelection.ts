import { useCallback, useState } from 'react'

/**
 * انتخابِ ردیف مثلِ سرستونِ ردیفِ اکسل — برای گریدِ ثبتِ سند و فهرستِ اسناد.
 *
 * - کلیک: فقط همین ردیف (کلیکِ دوباره روی تنها ردیفِ انتخاب‌شده برش می‌دارد).
 * - Ctrl+کلیک: افزودن/برداشتنِ همین ردیف.
 * - Shift+کلیک: بازه از «لنگر» (آخرین ردیفی که بی Shift کلیک شد) تا همین؛ با Ctrl به
 *   انتخابِ قبلی افزوده می‌شود.
 *
 * کلیدها رشته‌اند نه شاخص، تا فهرستی که صفحه‌بندی و فیلتر می‌شود (اسناد) با شناسه کار کند؛
 * گرید شاخصِ ردیف را رشته می‌کند. `order` ترتیبِ فعلیِ روی صفحه است و بازه از آن ساخته می‌شود.
 */
export interface RowSelection {
  keys: ReadonlySet<string>
  anchor: string | null
}

export interface ClickMods {
  shift: boolean
  ctrl: boolean
}

export const EMPTY_SELECTION: RowSelection = { keys: new Set(), anchor: null }

export function clickRow(sel: RowSelection, order: readonly string[], key: string, mods: ClickMods): RowSelection {
  if (mods.shift && sel.anchor !== null && order.includes(sel.anchor) && order.includes(key)) {
    const a = order.indexOf(sel.anchor)
    const b = order.indexOf(key)
    const range = order.slice(Math.min(a, b), Math.max(a, b) + 1)
    return { keys: new Set(mods.ctrl ? [...sel.keys, ...range] : range), anchor: sel.anchor }
  }
  if (mods.ctrl) {
    const keys = new Set(sel.keys)
    if (keys.has(key)) keys.delete(key)
    else keys.add(key)
    return { keys, anchor: key }
  }
  if (sel.keys.size === 1 && sel.keys.has(key)) return EMPTY_SELECTION
  return { keys: new Set([key]), anchor: key }
}

/** رویدادِ ماوس → تغییردهنده‌ها. Cmd روی مک همان Ctrl است. */
export const modsOf = (e: { shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }): ClickMods => ({
  shift: e.shiftKey,
  ctrl: e.ctrlKey || e.metaKey,
})

export function useRowSelection() {
  const [sel, setSel] = useState<RowSelection>(EMPTY_SELECTION)
  const click = useCallback(
    (order: readonly string[], key: string, mods: ClickMods) => setSel((s) => clickRow(s, order, key, mods)),
    [],
  )
  const clear = useCallback(() => setSel(EMPTY_SELECTION), [])
  return { selected: sel.keys, click, clear }
}
