/**
 * جاگذاریِ پاپ‌آورِ فهرست‌های انتخاب — منطقِ خالصش، جدا از DOM.
 *
 * **یک پیاده‌سازی برای هر دو.** `ItemPicker` و `SearchSelect` تا امروز دو رونوشتِ
 * کلمه‌به‌کلمه از همین حساب داشتند، با هر سه اشکالِ زیر در هر دو.
 *
 * **اشکالی که این‌جا درست می‌شود:** حسابِ قبلی برای ارتفاعِ فهرست کفِ ۱۴۰px
 * می‌گذاشت، حتی وقتی زیرِ فیلد اصلاً ۱۴۰px نبود. چون پاپ‌آور `position: fixed`
 * است، آن قسمت نه دیده می‌شد و نه با اسکرول به آن می‌رسیدی — یعنی فهرستِ یک فیلدِ
 * نزدیکِ پایینِ پنجره عملاً بی‌استفاده بود. حالا اگر پایین جا نباشد، پاپ‌آور
 * **بالای** فیلد باز می‌شود، و اگر هیچ‌کدام جا نباشد به ویوپورت چسبانده می‌شود.
 *
 * برای بازشدن به بالا `bottom` برمی‌گردد نه `top`: لبه‌ی پایینِ پاپ‌آور به بالای
 * فیلد می‌چسبد، پس برای جاگذاری نیازی به دانستنِ ارتفاعِ رندرشده‌اش نیست.
 */

/** مستطیلِ فیلدی که پاپ‌آور به آن لنگر می‌اندازد (از `getBoundingClientRect`). */
export interface Anchor {
  top: number
  bottom: number
  right: number
  width: number
}

export interface Viewport {
  width: number
  height: number
}

/** خروجی: همیشه دقیقاً یکی از `top` یا `bottom` ست می‌شود. */
export interface Placement {
  left: number
  width: number
  /** سقفِ ارتفاعِ **فهرست** (نه کلِ پاپ‌آور) — روی `<ul>` می‌نشیند. */
  maxH: number
  top?: number
  bottom?: number
}

export interface PopoverOpts {
  /** کمینه‌ی عرض، تا پاپ‌آورِ یک فیلدِ باریک هم خواندنی بماند. */
  minWidth?: number
  /** فاصله تا لبه‌های ویوپورت. */
  margin?: number
  /** فاصله‌ی پاپ‌آور تا خودِ فیلد. */
  gap?: number
  /**
   * ارتفاعی که بالای فهرست خرج می‌شود: نوارِ جست‌وجو (`.item-picker-search`،
   * ~۳۶px) به‌علاوه‌ی قابِ پاپ‌آور. کمی دست‌ودل‌بازتر از عددِ واقعی است تا خطای
   * چند پیکسلی به سرریز نرسد.
   */
  chrome?: number
  /** سقفِ ارتفاعِ فهرست وقتی جا هست. */
  maxH?: number
  /** کف — زیرِ این مقدار، آن سمت «جا ندارد» حساب می‌شود. */
  minH?: number
}

export function placePopover(anchor: Anchor, vp: Viewport, opts: PopoverOpts = {}): Placement {
  const {
    minWidth = 240,
    margin = 8,
    gap = 4,
    chrome = 44,
    maxH: want = 320,
    minH = 96,
  } = opts

  const width = Math.min(Math.max(anchor.width, minWidth), Math.max(0, vp.width - margin * 2))
  //: لبه‌ی راست به فیلد می‌چسبد — طبیعیِ راست‌به‌چپ.
  let left = anchor.right - width
  if (left + width > vp.width - margin) left = vp.width - margin - width
  if (left < margin) left = margin

  //: فضای واقعیِ **فهرست** در هر سمت: فضای آن سمت منهای نوارِ جست‌وجو.
  const listBelow = vp.height - anchor.bottom - gap - margin - chrome
  const listAbove = anchor.top - gap - margin - chrome

  //: پنجره‌ی خیلی کوتاه (یا فیلدی که خودش تمامِ ارتفاع را گرفته): هیچ سمتی جا
  //: ندارد، پس به‌جای بیرون‌زدن، پاپ‌آور به بالای ویوپورت می‌چسبد.
  if (listBelow < minH && listAbove < minH) {
    return { left, width, top: margin, maxH: Math.max(0, vp.height - margin * 2 - chrome) }
  }

  //: به بالا فقط وقتی می‌پرد که پایین کم آورده باشد **و** بالا واقعاً بهتر باشد.
  if (listBelow < minH) {
    return { left, width, maxH: Math.min(want, listAbove), bottom: vp.height - anchor.top + gap }
  }
  return { left, width, maxH: Math.min(want, listBelow), top: anchor.bottom + gap }
}
