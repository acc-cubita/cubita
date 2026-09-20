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
