import {
  LayoutDashboard,
  ShoppingCart,
  PackagePlus,
  Warehouse,
  UsersRound,
  BookOpen,
  Landmark,
  Users,
  HeartHandshake,
  Store,
  BarChart3,
  CalendarDays,
  CreditCard,
  HelpCircle,
  UserCog,
  UserCircle,
  LogOut,
  Sun,
  Moon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useTheme } from '../lib/theme'

export type PageKey =
  | 'overview'
  | 'sales'
  | 'purchases'
  | 'contacts'
  | 'crm'
  | 'inventory'
  | 'accounting'
  | 'banking'
  | 'payroll'
  | 'integration'
  | 'billing'
  | 'reports'
  | 'calendar'
  | 'team'
  | 'profile'
  | 'help'

const NAV_ITEMS: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: 'overview', label: 'داشبورد', icon: <LayoutDashboard size={18} /> },
  { key: 'sales', label: 'فروش', icon: <ShoppingCart size={18} /> },
  { key: 'purchases', label: 'خرید', icon: <PackagePlus size={18} /> },
  { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} /> },
  { key: 'crm', label: 'باشگاه مشتریان', icon: <HeartHandshake size={18} /> },
  { key: 'inventory', label: 'انبار', icon: <Warehouse size={18} /> },
  { key: 'accounting', label: 'حسابداری', icon: <BookOpen size={18} /> },
  { key: 'banking', label: 'چک و بانک', icon: <Landmark size={18} /> },
  { key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} /> },
  { key: 'integration', label: 'اتصال فروشگاه', icon: <Store size={18} /> },
  { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} /> },
  { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} /> },
]

// این تب کنترل‌پنل فروش خودِ کوبیتاست، نه یک ویژگی برای مشتری‌ها. تا امروز فقط
// روی role_key === 'owner' شرط داشت، یعنی هر صاحب کسب‌وکاری (نه فقط خودِ کوبیتا)
// آن را در ساید‌بار می‌دید و کلیک می‌کرد تا از بک‌اند ۴۰۳ بگیرد — بک‌اند درست
// محافظت می‌کرد، ولی UI چیزی نشان می‌داد که هرگز قرار نبود مال او باشد.
const PLATFORM_ADMIN_NAV_ITEMS: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: 'billing', label: 'خریدهای سایت تجاری', icon: <CreditCard size={18} /> },
]

const SECONDARY_NAV_ITEMS: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: 'profile', label: 'پروفایل من', icon: <UserCircle size={18} /> },
  { key: 'team', label: 'کاربران', icon: <UserCog size={18} /> },
  { key: 'help', label: 'راهنما', icon: <HelpCircle size={18} /> },
]

export function Sidebar({
  active,
  onNavigate,
  userName,
  roleName,
  isPlatformAdmin,
  onLogout,
  open = false,
  onClose,
}: {
  active: PageKey
  onNavigate: (page: PageKey) => void
  userName: string
  roleName: string
  isPlatformAdmin: boolean
  onLogout: () => void
  /** فقط در وبِ باریک (موبایل) معنا دارد: نوار کناری کشوی روی‌هم می‌شود. */
  open?: boolean
  onClose?: () => void
}) {
  const navItems = isPlatformAdmin ? [...NAV_ITEMS, ...PLATFORM_ADMIN_NAV_ITEMS] : NAV_ITEMS
  const { theme, toggle } = useTheme()

  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">C</span>
        <span className="sidebar-brand-name">کوبیتا</span>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`sidebar-nav-item${active === item.key ? ' active' : ''}`}
            onClick={() => {
              onNavigate(item.key)
              onClose?.()
            }}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
        <div className="sidebar-nav-divider" />
        {SECONDARY_NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`sidebar-nav-item${active === item.key ? ' active' : ''}`}
            onClick={() => {
              onNavigate(item.key)
              onClose?.()
            }}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">{userName.charAt(0)}</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">{userName}</div>
            <div className="sidebar-user-role">{roleName}</div>
          </div>
        </div>
        <button
          type="button"
          className="sidebar-icon-btn"
          onClick={toggle}
          title={theme === 'dark' ? 'پوسته‌ی روشن' : 'پوسته‌ی تیره'}
          aria-label="تغییر پوسته"
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <button type="button" className="sidebar-logout" onClick={onLogout} title="خروج">
          <LogOut size={17} />
        </button>
      </div>
      </aside>
    </>
  )
}
