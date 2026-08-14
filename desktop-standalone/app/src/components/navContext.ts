import { createContext, useContext } from 'react'
import type { PageKey } from './Sidebar'

/**
 * وضعیتِ «تبِ فعالِ صفحه» را از سایدبار تا نوارِ تبِ داخلِ صفحه مشترک می‌کند.
 *
 * Dashboard این را فراهم می‌کند و `<Tabs syncPage="...">` آن را مصرف می‌کند، پس
 * زیرمنوی سایدبار و نوارِ تبِ صفحه دوطرفه هم‌گام می‌مانند: کلیک روی هرکدام، دیگری را
 * هم به‌روز می‌کند. `section === null` یعنی «تبِ پیش‌فرض (اولین)».
 */
export type NavSectionValue = {
  activePage: PageKey
  section: string | null
  setSection: (key: string | null) => void
}

export const NavSectionContext = createContext<NavSectionValue | null>(null)

export function useNavSection(): NavSectionValue | null {
  return useContext(NavSectionContext)
}
