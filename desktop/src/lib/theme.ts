import { useSyncExternalStore } from 'react'

/** یک تمِ ثبت‌شده در برنامه. افزودنِ تمِ تازه = یک رکورد اینجا + یک بلوکِ توکنِ
 *  `:root[data-theme='<id>']` در index.css. `shell` تعیین می‌کند چیدمانِ برنامه
 *  نوارِ کناری باشد یا نوارِ افقیِ بالا. */
export interface ThemeDef {
  id: string
  label: string
  kind: 'dark' | 'light'
  shell: 'sidebar' | 'topnav'
  /** حالتِ محتوای مرکزیِ صفحه‌ها. 'classic' = فرم‌های تک‌صفحه‌ایِ فعلی؛ 'guided' =
   *  «نسخه‌ی جدید» با داشبوردِ اقدام‌محور و کارهای مرحله‌ای (ویزارد). تنها Tipalti
   *  فعلاً 'guided' است، پس پوسته‌های کلاسیک دقیقاً مثلِ قبل رندر می‌شوند. */
  content: 'classic' | 'guided'
  /** سه رنگِ نمونه برای کارتِ پیش‌نمایش در گالریِ پوسته (نوار، تأکید، سطح). */
  swatches: [string, string, string]
}

/** رجیستریِ تم‌ها. ترتیبِ نمایش در گالری همین است.
 *  هر سه تم اکنون «ساختارِ جدید» را دارند (shell=topnav + content=guided): همان منوها،
 *  صفحه‌ها و کارهای مرحله‌ایِ تمِ Tipalti. تنها تفاوتِ سه تم، «پالتِ رنگ» است که از بلوکِ
 *  توکنِ متناظر در index.css می‌آید؛ مقیاسِ هوادار (فونت/فاصله/گِردی) مشترک است و در
 *  `:root[data-structure='guided']` تعریف شده. */
export const THEMES: ThemeDef[] = [
  {
    id: 'tipalti',
    label: 'Tipalti — سرمه‌ای/طلایی (پیش‌فرض)',
    kind: 'light',
    shell: 'topnav',
    content: 'guided',
    swatches: ['#16223d', '#ffc72c', '#ffffff'],
  },
  {
    id: 'dark',
    label: 'تیره',
    kind: 'dark',
    shell: 'topnav',
    content: 'guided',
    swatches: ['#181818', '#0078d4', '#252526'],
  },
  {
    id: 'light',
    label: 'روشن',
    kind: 'light',
    shell: 'topnav',
    content: 'guided',
    swatches: ['#f8f8f8', '#005fb8', '#ffffff'],
  },
]

const KEY = 'cubita-theme'
const DEFAULT_ID = 'tipalti'

export function getTheme(id: string): ThemeDef {
  return THEMES.find((t) => t.id === id) ?? THEMES[0]
}

/** id ذخیره‌شده را با رجیستری اعتبارسنجی می‌کند؛ ناشناخته → پیش‌فرض. سازگارِ عقب:
 *  مقادیرِ قدیمیِ 'dark'/'light' همان id معتبرند. */
export function getStoredThemeId(): string {
  try {
    const id = localStorage.getItem(KEY)
    return id && THEMES.some((t) => t.id === id) ? id : DEFAULT_ID
  } catch {
    return DEFAULT_ID
  }
}

/** تم را روی سند اعمال و ذخیره می‌کند. در main.tsx پیش از render صدا زده می‌شود تا
 *  صفحه بدونِ «پرش» با تمِ درست بالا بیاید. */
export function applyTheme(id: string): void {
  const theme = getTheme(id)
  document.documentElement.setAttribute('data-theme', id)
  // `data-structure` جدا از رنگ است: قواعدِ ساختاریِ «نسخه‌ی جدید» (App.css) به این
  // صفت وصل‌اند، نه به id تم. پس هر تمی با content='guided' همان ساختار را می‌گیرد و فقط
  // پالتِ رنگش (از data-theme) فرق می‌کند.
  document.documentElement.setAttribute('data-structure', theme.content)
  try {
    localStorage.setItem(KEY, id)
  } catch {
    /* localStorage ممکن است در دسترس نباشد؛ همان جلسه اعمال می‌شود */
  }
}

// حالتِ تم سراسری و مشترک است: چند کامپوننت (Dashboard/Sidebar/TopNav/ThemeGallery)
// هم‌زمان useTheme صدا می‌زنند و باید همه با تغییرِ تم re-render شوند — وگرنه تعویضِ تم
// در گالری فقط رنگ‌ها را عوض می‌کرد ولی چیدمان (shell) تا reload جابه‌جا نمی‌شد.
let currentThemeId = getStoredThemeId()
const listeners = new Set<() => void>()

/** تم را برای کلِ برنامه عوض می‌کند: اعمال روی سند + ذخیره + آگاه‌سازیِ همه‌ی مصرف‌کننده‌ها. */
export function setThemeId(id: string): void {
  applyTheme(id)
  currentThemeId = id
  listeners.forEach((l) => l())
}

export function useTheme(): { theme: ThemeDef; themes: ThemeDef[]; setThemeId: (id: string) => void } {
  const id = useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => currentThemeId,
    () => currentThemeId,
  )
  return { theme: getTheme(id), themes: THEMES, setThemeId }
}
