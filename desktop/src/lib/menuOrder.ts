import { useState } from 'react'

/**
 * ترتیبِ دلخواهِ کاربر برای منوهای کارت‌های «عملیات» و «فهرست» (`ModulePanels`).
 *
 * **روی دستگاه، نه سرور** — همان تصمیمِ میان‌برهای کاربر و جمع‌بودنِ همین کارت‌ها: ترجیحِ
 * چیدمان است، نه قاعده‌ی کسب‌وکار. هر فهرستِ منو یک «دامنه» دارد (مثلاً `ops:حسابداری`) و
 * ترتیبش فهرستی از کلیدهای ورودی‌هاست.
 *
 * **ترتیبِ پیش‌فرض همیشه پایه است.** ورودی‌ای که در ترتیبِ ذخیره‌شده نیست — منوی تازه در
 * نسخه‌ی بعد، یا ماژولی که تازه روشن شده — ته فهرست می‌نشیند و ناپدید نمی‌شود. کلیدِ ذخیره‌شده‌ای
 * که الان دیده نمی‌شود (ماژولِ خاموش) با جابه‌جایی پاک نمی‌شود تا با روشن‌شدنِ دوباره جایش بماند.
 */
export type MenuOrders = Record<string, string[]>

const STORAGE_KEY = 'cubita.menuOrder'

/** مرتب‌سازیِ پایدار: کلیدهای ذخیره‌شده به ترتیبِ خودشان، بقیه به ترتیبِ پیش‌فرض در انتها. */
export function applyOrder<T>(items: T[], keyOf: (item: T) => string, saved?: string[]): T[] {
  if (!saved || saved.length === 0) return items
  const pos = new Map(saved.map((k, i) => [k, i]))
  return items
    .map((item, i) => ({ item, i, p: pos.get(keyOf(item)) ?? Number.MAX_SAFE_INTEGER }))
    .sort((a, b) => a.p - b.p || a.i - b.i)
    .map((x) => x.item)
}

/**
 * ورودیِ `key` را یک خانه بالا (`-1`) یا پایین (`1`) می‌برد. `visible` ترتیبِ فعلیِ آنچه روی
 * صفحه است؛ خروجی ترتیبِ تازه برای ذخیره، یا `null` اگر حرکتی ممکن نیست (لبه‌ی فهرست).
 */
export function moveInOrder(visible: string[], saved: string[] | undefined, key: string, dir: -1 | 1): string[] | null {
  const i = visible.indexOf(key)
  const j = i + dir
  if (i < 0 || j < 0 || j >= visible.length) return null
  const next = [...visible]
  ;[next[i], next[j]] = [next[j], next[i]]
  const shown = new Set(next)
  return [...next, ...(saved ?? []).filter((k) => !shown.has(k))]
}

function load(): MenuOrders {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    //: فقط دامنه‌هایی که واقعاً فهرستِ رشته‌اند — ذخیره‌ی خراب نباید منو را بشکند.
    return Object.fromEntries(
      Object.entries(parsed).filter(([, v]) => Array.isArray(v) && v.every((k) => typeof k === 'string')),
    ) as MenuOrders
  } catch {
    return {}
  }
}

export interface MenuOrderApi {
  sort<T>(scope: string, items: T[], keyOf: (item: T) => string): T[]
  /** `true` اگر جابه‌جا شد. */
  move(scope: string, visible: string[], key: string, dir: -1 | 1): boolean
  reset(scopes: string[]): void
  customized(scopes: string[]): boolean
}

export function useMenuOrder(): MenuOrderApi {
  const [orders, setOrders] = useState<MenuOrders>(load)
  const save = (next: MenuOrders) => {
    setOrders(next)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      //: ذخیره‌نشدن فقط یعنی ترتیب با بستنِ برنامه برمی‌گردد؛ منو باید کار کند.
    }
  }
  return {
    sort: (scope, items, keyOf) => applyOrder(items, keyOf, orders[scope]),
    move: (scope, visible, key, dir) => {
      const next = moveInOrder(visible, orders[scope], key, dir)
      if (!next) return false
      save({ ...orders, [scope]: next })
      return true
    },
    reset: (scopes) => {
      const next = { ...orders }
      for (const s of scopes) delete next[s]
      save(next)
    },
    customized: (scopes) => scopes.some((s) => (orders[s]?.length ?? 0) > 0),
  }
}
