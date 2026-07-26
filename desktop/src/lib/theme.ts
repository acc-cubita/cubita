import { useState } from 'react'

/** پوسته‌ی برنامه — تیره (پیش‌فرض) یا روشن. روی `data-theme` ریشه‌ی سند می‌نشیند و
 *  CSS بقیه را از روی متغیرها می‌سازد. انتخابِ کاربر در localStorage می‌ماند. */
export type Theme = 'dark' | 'light'

const KEY = 'cubita-theme'

export function getStoredTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

/** پوسته را روی سند اعمال و ذخیره می‌کند. در main.tsx قبل از render صدا زده می‌شود
 *  تا صفحه بدونِ «پرش» با پوسته‌ی درست بالا بیاید. */
export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* localStorage ممکن است در دسترس نباشد؛ همان جلسه اعمال می‌شود */
  }
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(getStoredTheme)
  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    setTheme(next)
  }
  return { theme, toggle }
}
