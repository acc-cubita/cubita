import type { Item, StockCountLine } from '../api/types'

/**
 * بارکد → ردیفِ جلسه‌ی انبارگردانی.
 *
 * **چرا محلی و نه `GET /api/items/by-barcode`:** انبارِ فلزی آنتن ندارد. اسکنی
 * که برای هر کالا یک درخواست بزند، دقیقاً جایی که لازم است کار نمی‌کند. فهرستِ
 * کالاها از قبل در کشِ روی دیسک هست (همان کشی که فازِ ۳ ساخت)، پس تطبیق آفلاین
 * انجام می‌شود.
 *
 * سه نتیجه‌ی متفاوت، چون سه کارِ متفاوت از کاربر می‌خواهند — و ادغامشان در یک
 * «پیدا نشد» انباردار را گمراه می‌کند:
 *
 * - `unknown` — این بارکد به هیچ کالایی وصل نیست. یعنی کالا در سیستم بارکد
 *   ندارد یا اصلاً تعریف نشده. کارِ لازم: تعریفِ کالا/بارکد.
 * - `notInSession` — کالا هست، ولی در این جلسه نیست. یعنی یا خدماتی است یا
 *   **بعد از عکس‌برداریِ جلسه ساخته شده**. کارِ لازم: جلسه‌ی تازه، وگرنه این
 *   کالا در انبارگردانی شمرده نمی‌شود و کسی هم متوجه نمی‌شود.
 * - `line` — پیدا شد.
 */
export type ScanResolution =
  | { kind: 'unknown'; code: string }
  | { kind: 'notInSession'; item: Item }
  | { kind: 'line'; item: Item; line: StockCountLine }

/** نگاشتِ بارکد → کالا. بارکدها با فاصله‌ی اضافه ذخیره شده‌اند یا نه — هر دو حالت. */
export function barcodeIndex(items: Item[]): Map<string, Item> {
  const map = new Map<string, Item>()
  for (const it of items) {
    const code = (it.barcode ?? '').trim()
    // اولین کالا برنده است: بک‌اند ایندکسِ یکتا روی بارکد دارد، پس تکراری فقط از
    // داده‌ی کهنه‌ی کش می‌آید و بازنویسی‌اش چیزی را بهتر نمی‌کند.
    if (code && !map.has(code)) map.set(code, it)
  }
  return map
}

export function resolveScan(
  code: string,
  index: Map<string, Item>,
  lines: StockCountLine[],
): ScanResolution {
  const clean = code.trim()
  const item = index.get(clean)
  if (!item) return { kind: 'unknown', code: clean }
  const line = lines.find((l) => l.item_id === item.id)
  return line ? { kind: 'line', item, line } : { kind: 'notInSession', item }
}
