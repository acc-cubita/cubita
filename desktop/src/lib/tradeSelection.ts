/**
 * انتخابِ چندتاییِ صنف — منطقِ خالصش، جدا از رندر.
 *
 * دو جا همین را می‌خواهند: اصنافِ کلیِ پخش‌کننده (تبِ تنظیمات) و اصنافِ اضافه‌ی یک
 * قلمِ کاتالوگ (فرمِ لیستینگ و ویزاردش). چون محیطِ vitest در این پروژه `node` است و
 * DOM ندارد، منطق این‌جا می‌ماند تا تست‌پذیر باشد — همان قراردادِ `topnavFit` و
 * `popover`.
 */

/** یک صنف را برمی‌دارد یا می‌گذارد. ترتیبِ بقیه دست نمی‌خورد. */
export function toggleTrade(current: string[], key: string): string[] {
  return current.includes(key) ? current.filter((k) => k !== key) : [...current, key]
}

/**
 * «کلِ این گروه» — اگر **همه‌ی** اصنافِ گروه انتخاب باشند برمی‌دارد، وگرنه همه را
 * می‌گذارد. حالتِ نیمه‌انتخاب عمداً به «همه» می‌رود نه «هیچ»: کاربری که سه‌تا از ده‌تا
 * را زده و دکمه را می‌زند، منظورش گسترش است نه پاک‌کردنِ کارِ خودش.
 */
export function toggleGroup(current: string[], keys: string[]): string[] {
  const set = new Set(current)
  const allOn = keys.every((k) => set.has(k))
  if (allOn) return current.filter((k) => !keys.includes(k))
  return [...new Set([...current, ...keys])]
}

/** یک گروه پس از فیلترِ جست‌وجو، به‌همراه چیزهایی که سرِ گروه باید نشان دهد. */
export interface GroupView {
  key: string
  label: string
  /** اصنافی که باید رندر شوند — با جست‌وجو باریک می‌شود. */
  trades: { key: string; label: string }[]
  /** از **کلِ** گروه (نه فقط نتایج) چندتا انتخاب شده. */
  chosen: number
  /** اندازه‌ی کلِ گروه، برای «۳ از ۲۰». */
  total: number
  /** باز باشد یا جمع. */
  open: boolean
}

/**
 * گروه‌ها را برای رندر آماده می‌کند: فیلترِ جست‌وجو، شمارشِ انتخاب‌شده‌ها، و
 * تصمیمِ باز/بسته.
 *
 * **چرا شمارنده از کلِ گروه است نه از نتایج.** گروهِ جمع‌شده انتخاب‌هایش را پنهان
 * می‌کند؛ اگر شمارنده هم فقط نتایجِ جست‌وجو را بشمارد، پخش‌کننده‌ای که «یدک» را
 * جست‌وجو کرده می‌بیند «۱ از ۲۰» و فکر می‌کند بقیه‌ی انتخاب‌هایش پاک شده‌اند.
 *
 * **چرا جست‌وجو گروه را باز می‌کند.** با ۶۴ گروهِ جمع‌شده، نتیجه‌ی جست‌وجویی که
 * داخلِ یک گروهِ بسته بماند اصلاً دیده نمی‌شود — یعنی جست‌وجو کار نمی‌کند.
 */
export function viewGroups(
  groups: { key: string; label: string; trades: { key: string; label: string }[] }[],
  chosen: string[],
  query: string,
  expanded: Set<string>,
  matches: (label: string, q: string) => boolean,
): GroupView[] {
  const picked = new Set(chosen)
  const q = query.trim()
  const out: GroupView[] = []
  for (const g of groups) {
    const hits = q ? g.trades.filter((t) => matches(t.label, q)) : g.trades
    //: گروهِ بی‌نتیجه هنگامِ جست‌وجو اصلاً نمایش داده نمی‌شود — وگرنه کاربر ۶۴ سرِ
    //: گروهِ خالی را اسکرول می‌کند تا به دوتا نتیجه برسد.
    if (q && hits.length === 0) continue
    out.push({
      key: g.key,
      label: g.label,
      trades: hits,
      chosen: g.trades.filter((t) => picked.has(t.key)).length,
      total: g.trades.length,
      open: q ? true : expanded.has(g.key),
    })
  }
  return out
}

/** گروه را باز/جمع می‌کند. */
export function toggleExpanded(expanded: Set<string>, key: string): Set<string> {
  const next = new Set(expanded)
  if (!next.delete(key)) next.add(key)
  return next
}
