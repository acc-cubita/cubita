import { useSyncExternalStore } from 'react'

/**
 * حالتِ تجربه‌ی کاربر — «ساده» یا «حسابدار».
 *
 * **یک موتور، دو تجربه.** این ماژول هیچ منطقِ مالی‌ای ندارد و هرگز نباید داشته
 * باشد: هر دو حالت همان `useJournalEntryDraft`، همان API و همان اعتبارسنجیِ
 * سرور را مصرف می‌کنند. تفاوت فقط در **چیدمان، تراکم و رفتارِ صفحه‌کلید** است.
 *
 * **حالت ≠ مجوز.** `accountant` هیچ دسترسی‌ای اضافه نمی‌کند. آنچه کاربر می‌بیند
 * همچنان از `me.permissions` و `enabled_modules` می‌آید. اگر روزی چیزی در این
 * فایل به مجوز نگاه کرد، جایش اشتباه است.
 *
 * **حالت ≠ تم.** تمِ رنگی (`lib/theme.ts`) مستقل می‌ماند؛ هر چهار ترکیب
 * (ساده/حسابدار × روشن/تیره) معتبرند. عمداً دو صفتِ جدا روی `documentElement`
 * می‌نشینند: `data-theme` و `data-experience`.
 *
 * **چرا هم محلی هم سرور.** سرور منبعِ حقیقت است (کاربر روی دستگاهِ دیگر همان
 * حالت را می‌بیند)، ولی نوشتنِ محلی اول انجام می‌شود تا رابط بی‌درنگ عوض شود و
 * تغییرِ حالت پشتِ یک رفت‌وبرگشتِ شبکه گیر نکند. اگر سرور نپذیرد، ترجیحِ محلی
 * همین نشست را درست نگه می‌دارد و دفعه‌ی بعدِ ورود، مقدارِ سرور برمی‌گردد —
 * همان مبادله‌ای که `Membership.dashboard_cards` هم می‌کند.
 */
export type ExperienceMode = 'simple' | 'accountant'

export interface ExperienceDef {
  id: ExperienceMode
  label: string
  description: string
}

export const EXPERIENCES: ExperienceDef[] = [
  {
    id: 'simple',
    label: 'حالت ساده',
    description: 'مناسب صاحبان کسب‌وکار و کاربران غیرحسابدار',
  },
  {
    id: 'accountant',
    label: 'حالت حسابدار',
    description: 'مناسب حسابداران و کاربران حرفه‌ای',
  },
]

const KEY = 'cubita.experience'
//: پیش‌فرض در مهاجرتِ ۰۱۸۳ از `simple` به `accountant` رفت و باید با
//: `User.experience_mode`ِ بک‌اند یکی بماند: این مقدار همان چیزی است که پیش از
//: رسیدنِ پاسخِ `GET /api/auth/me` روی صفحه می‌نشیند، پس ناهمخوانی یعنی «پرشِ
//: تراکم» در اولین ثانیه‌ی هر ورود.
const DEFAULT_MODE: ExperienceMode = 'accountant'

function isMode(v: unknown): v is ExperienceMode {
  return v === 'simple' || v === 'accountant'
}

/** مقدارِ ذخیره‌شده‌ی دستگاه؛ ناشناخته یا نبودِ localStorage → پیش‌فرض. */
export function getStoredMode(): ExperienceMode {
  try {
    const v = localStorage.getItem(KEY)
    return isMode(v) ? v : DEFAULT_MODE
  } catch {
    return DEFAULT_MODE
  }
}

/**
 * صفتِ `data-experience` را روی سند می‌نشاند.
 *
 * مثلِ `applyTheme` پیش از اولین رندر در `main.tsx` صدا زده می‌شود تا صفحه بدونِ
 * «پرشِ تراکم» بالا بیاید. قواعدِ CSS به همین صفت وصل‌اند، نه به کلاسِ کامپوننت —
 * وگرنه هر کامپوننتی باید حالت را می‌خواند و prop drilling می‌شد.
 */
export function applyExperience(mode: ExperienceMode): void {
  document.documentElement.setAttribute('data-experience', mode)
  try {
    localStorage.setItem(KEY, mode)
  } catch {
    /* پنجره‌ی ناشناس یا ذخیره‌ی مسدود — همین نشست درست کار می‌کند */
  }
}

let current: ExperienceMode = getStoredMode()
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((l) => l())
}

/**
 * حالت را برای کلِ برنامه عوض می‌کند.
 *
 * `persist` تابعی است که مقدار را به سرور می‌فرستد (`PATCH /api/auth/me`).
 * تزریق می‌شود تا این ماژول به `api.ts` وابسته نشود و در تست بدونِ شبکه اجرا شود.
 * شکستِ ذخیره‌ی سرور **عمداً** حالت را برنمی‌گرداند: کاربر همین الان انتخابش را
 * دیده و پس‌گرفتنِ بی‌صدای آن بدتر از ماندنِ یک ترجیحِ ذخیره‌نشده است.
 */
export function setExperience(
  mode: ExperienceMode,
  persist?: (mode: ExperienceMode) => Promise<unknown>,
): void {
  if (mode === current) return
  applyExperience(mode)
  current = mode
  emit()
  void persist?.(mode).catch(() => {})
}

/**
 * مقدارِ سرور را می‌نشاند — هنگامِ `GET /api/auth/me` پس از ورود.
 *
 * برخلافِ `setExperience` چیزی به سرور نمی‌فرستد (وگرنه حلقه می‌شد) و اگر با
 * مقدارِ محلی یکی باشد هیچ رندری نمی‌سازد.
 */
export function adoptServerExperience(mode: string | undefined | null): void {
  if (!isMode(mode) || mode === current) return
  applyExperience(mode)
  current = mode
  emit()
}

export function useExperienceMode(): {
  mode: ExperienceMode
  isAccountant: boolean
  experiences: ExperienceDef[]
} {
  const mode = useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => current,
    () => current,
  )
  return { mode, isAccountant: mode === 'accountant', experiences: EXPERIENCES }
}

/**
 * فرمِ مرحله‌ای (ویزارد) یا فرمِ کلاسیکِ فشرده؟
 *
 * نُه فرم هر دو نسخه را دارند — فاکتور فروش، پیش‌فاکتور، برگشت از فروش، فاکتور و
 * برگشتِ خرید، تعدیل موجودی، انتقال بین انبارها، کارت دارایی و لیستینگِ پخش — و هر
 * دو نسخه از یک پیش‌نویس می‌خوانند.
 *
 * **تا UI-01 این به تم بسته بود** (`theme.content`). هر سه تم «مرحله‌ای»اند،
 * پس همه ویزارد می‌دیدند و فرم‌های کلاسیک از هیچ‌جا باز نمی‌شدند — همان قاطی‌شدنِ
 * حالت و تم که §۳۲ منع کرده بود. حالا حالت تصمیم می‌گیرد: ساده ویزارد، حسابدار فرمِ
 * فشرده. `data-structure`ِ تم همچنان چیدمانِ صفحه‌ها را تعیین می‌کند؛ این فقط انتخابِ
 * فرم است.
 */
export function useGuidedForms(): boolean {
  return useExperienceMode().mode === 'simple'
}

/** فقط برای تست — حالت را به پیش‌فرض برمی‌گرداند بی‌آنکه چیزی بفرستد. */
export function __resetExperienceForTests(): void {
  current = DEFAULT_MODE
  listeners.clear()
}
