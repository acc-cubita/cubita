import {
  LayoutDashboard,
  ShoppingCart,
  PackagePlus,
  Warehouse,
  UsersRound,
  BookOpen,
  Landmark,
  Users,
  Store,
  BarChart3,
  CreditCard,
  HelpCircle,
  UserCog,
  LogOut,
} from 'lucide-react'
import type { ReactNode } from 'react'

export type PageKey =
  | 'overview'
  | 'sales'
  | 'purchases'
  | 'contacts'
  | 'inventory'
  | 'accounting'
  | 'banking'
  | 'payroll'
  | 'integration'
  | 'billing'
  | 'reports'
  | 'team'
  | 'help'

const NAV_ITEMS: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: 'overview', label: 'داشبورد', icon: <LayoutDashboard size={18} /> },
  { key: 'sales', label: 'فروش', icon: <ShoppingCart size={18} /> },
  { key: 'purchases', label: 'خرید', icon: <PackagePlus size={18} /> },
  { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} /> },
  { key: 'inventory', label: 'انبار', icon: <Warehouse size={18} /> },
  { key: 'accounting', label: 'حسابداری', icon: <BookOpen size={18} /> },
  { key: 'banking', label: 'چک و بانک', icon: <Landmark size={18} /> },
  { key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} /> },
  { key: 'integration', label: 'اتصال فروشگاه', icon: <Store size={18} /> },
  { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} /> },
]

const OWNER_ONLY_NAV_ITEMS: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: 'billing', label: 'خریدهای سایت تجاری', icon: <CreditCard size={18} /> },
]

const SECONDARY_NAV_ITEMS: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: 'team', label: 'کاربران', icon: <UserCog size={18} /> },
  { key: 'help', label: 'راهنما', icon: <HelpCircle size={18} /> },
]

export function Sidebar({
  active,
  onNavigate,
  userName,
  roleName,
  roleKey,
  onLogout,
}: {
  active: PageKey
  onNavigate: (page: PageKey) => void
  userName: string
  roleName: string
  roleKey: string
  onLogout: () => void
}) {
  const navItems = roleKey === 'owner' ? [...NAV_ITEMS, ...OWNER_ONLY_NAV_ITEMS] : NAV_ITEMS

  return (
    <aside className="sidebar">
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
            onClick={() => onNavigate(item.key)}
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
            onClick={() => onNavigate(item.key)}
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
        <button type="button" className="sidebar-logout" onClick={onLogout} title="خروج">
          <LogOut size={17} />
        </button>
      </div>
    </aside>
  )
}
