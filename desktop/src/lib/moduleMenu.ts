/**
 * منوی یک ماژول در **یک فهرست**: کارها و دفترها زیرِ همان دسته‌ها (۱۴۰۵/۰۷/۰۶، خواستِ آرش).
 *
 * پیش از این دو کارت بود — «عملیات» و «فهرست» — و هر کدام دسته‌های خودش را داشت. کاربر برای «فاکتور فروش» یک‌جا
 * می‌رفت و برای «فاکتورهای فروش» جای دیگر. حالا هر دفتر کنارِ کاری است که آن را می‌سازد: «اسناد حسابداری» زیرِ «ثبت
 * سند»، «عملیات چک» زیرِ «چک». ترتیبِ دسته‌ها همان ترتیبِ کارهاست؛ درونِ هر دسته اول کارها، بعد دفترها.
 *
 * - دفتری که دسته‌اش هم‌نامِ یک دسته‌ی کار است به همان می‌پیوندد.
 * - دسته‌ای که فقط دفتر دارد («موجودی»ِ انبار) پیش از دسته‌های تعریف می‌نشیند — تعریف‌ها همیشه ته‌اند.
 * - دفترِ بی‌دسته (ماژولِ کوچکِ بی‌دسته: پیمانکاری، تنظیمات) ته می‌آید و `trailing` است: رابط با یک خطِ جداکننده‌ی
 *   بی‌عنوان از کارها جدایش می‌کند.
 *
 * بی DOM و بی React تا مستقیم تست شود؛ ردیف‌ها برایش مات‌اند.
 */
export interface MenuCategory<O, L> {
  title: string | null
  ops: O[]
  lists: L[]
  /** دفترهای بی‌دسته‌ی ته — جدا از دسته‌ی بی‌عنوانِ بالای منو (مسیرِ کار، کارهای بی‌دسته). */
  trailing?: boolean
}

export function mergeMenu<O, L>(
  ops: readonly { title: string | null; items: O[] }[],
  lists: readonly { title: string | null; items: L[] }[],
  isDefinitions: (title: string) => boolean,
): MenuCategory<O, L>[] {
  const out: MenuCategory<O, L>[] = ops.map((c) => ({ title: c.title, ops: [...c.items], lists: [] }))
  const trailing: L[] = []
  for (const c of lists) {
    if (c.title === null) {
      trailing.push(...c.items)
      continue
    }
    const home = out.find((x) => x.title === c.title && !x.trailing)
    if (home) {
      home.lists.push(...c.items)
      continue
    }
    //: دسته‌ی فقط-دفتر پیش از اولین دسته‌ی تعریف؛ اگر تعریفی نیست، ته.
    const at = out.findIndex((x) => x.title !== null && isDefinitions(x.title))
    const cat: MenuCategory<O, L> = { title: c.title, ops: [], lists: [...c.items] }
    if (at === -1) out.push(cat)
    else out.splice(at, 0, cat)
  }
  if (trailing.length > 0) out.push({ title: null, ops: [], lists: trailing, trailing: true })
  return out.filter((c) => c.ops.length + c.lists.length > 0)
}

/** چند دسته‌ی عنوان‌دار دارد؟ تیترِ دسته فقط وقتی معنا دارد که بیش از یکی باشد. */
export const titledCount = (cats: readonly { title: string | null }[]) => cats.filter((c) => c.title !== null).length
