import {
  LayoutDashboard,
  ShoppingCart,
  ScanLine,
  CalendarClock,
  PackagePlus,
  Warehouse,
  UsersRound,
  BookOpen,
  Landmark,
  Users,
  HeartHandshake,
  Factory,
  BarChart3,
  CalendarDays,
  Rocket,
  HelpCircle,
  UserCircle,
  LogOut,
  Sun,
  Moon,
} from 'lucide-react'
import { type ReactNode } from 'react'
import { useTheme } from '../lib/theme'

export type PageKey =
  | 'overview'
  | 'sales'
  | 'pos'
  | 'installments'
  | 'purchases'
  | 'contacts'
  | 'crm'
  | 'inventory'
  | 'manufacturing'
  | 'accounting'
  | 'banking'
  | 'payroll'
  | 'reports'
  | 'onboarding'
  | 'calendar'
  | 'profile'
  | 'help'

type NavItem = { key: PageKey; label: string; icon: ReactNode }
type NavGroup = { heading: string; items: NavItem[] }

// طراحیِ «دفترِ آرام»: فهرستِ گروه‌بندی‌شده‌ی همیشه‌باز (بدونِ آکاردئون و زیرمنوی شلوغ).
// هر گروه یک برچسبِ کوچک دارد و آیتم‌ها جادار با «قرصِ» نرمِ فعال. زیرِناوبریِ هر ماژول
// با تب‌های داخلِ صفحه انجام می‌شود، نه در سایدبار — تا نوار تمیز بماند.
const NAV_GROUPS: NavGroup[] = [
  {
    heading: 'میزکار',
    items: [{ key: 'overview', label: 'میزِ کار', icon: <LayoutDashboard size={18} /> }],
  },
  {
    heading: 'فروش و مشتریان',
    items: [
      { key: 'sales', label: 'فروش', icon: <ShoppingCart size={18} /> },
      { key: 'pos', label: 'صندوق فروشگاهی', icon: <ScanLine size={18} /> },
      { key: 'installments', label: 'فروش اقساطی', icon: <CalendarClock size={18} /> },
      { key: 'crm', label: 'باشگاه مشتریان', icon: <HeartHandshake size={18} /> },
    ],
  },
  {
    heading: 'خرید و انبار',
    items: [
      { key: 'purchases', label: 'خرید', icon: <PackagePlus size={18} /> },
      { key: 'inventory', label: 'انبار', icon: <Warehouse size={18} /> },
      { key: 'manufacturing', label: 'تولید', icon: <Factory size={18} /> },
    ],
  },
  {
    heading: 'مالی',
    items: [
      { key: 'accounting', label: 'حسابداری', icon: <BookOpen size={18} /> },
      { key: 'banking', label: 'چک و بانک', icon: <Landmark size={18} /> },
      { key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} /> },
    ],
  },
  {
    heading: 'اطلاعات و گزارش',
    items: [
      { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} /> },
      { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} /> },
    ],
  },
  {
    heading: 'ابزار',
    items: [
      { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} /> },
      { key: 'onboarding', label: 'راه‌اندازی', icon: <Rocket size={18} /> },
    ],
  },
]

const SECONDARY_NAV_ITEMS: NavItem[] = [
  { key: 'profile', label: 'پروفایل من', icon: <UserCircle size={18} /> },
  { key: 'help', label: 'راهنما', icon: <HelpCircle size={18} /> },
]

export function Sidebar({
  active,
  onNavigate,
  userName,
  roleName,
  onLogout,
  open = false,
  onClose,
}: {
  active: PageKey
  /** تبِ فعالِ صفحه؛ در این چیدمان استفاده نمی‌شود (زیرِناوبری داخلِ صفحه است). */
  activeSection?: string | null
  onNavigate: (page: PageKey, section?: string) => void
  userName: string
  roleName: string
  onLogout: () => void
  /** فقط در وبِ باریک (موبایل) معنا دارد: نوار کناری کشوی روی‌هم می‌شود. */
  open?: boolean
  onClose?: () => void
}) {
  const { theme, toggle } = useTheme()

  const renderItem = (item: NavItem) => (
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
  )

  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
        <div className="sidebar-brand">
          <span className="sidebar-brand-mark">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 5h16M4 5v14M4 19h16M8 9h8M8 13h5" />
            </svg>
          </span>
          <span className="sidebar-brand-name">
            حسابداری
            <small>نسخه‌ی محلی</small>
          </span>
        </div>

        <nav className="sidebar-nav">
          {NAV_GROUPS.map((group) => (
            <div className="sidebar-nav-group" key={group.heading}>
              {group.items.length > 1 && <p className="sidebar-nav-heading">{group.heading}</p>}
              {group.items.map(renderItem)}
            </div>
          ))}
          <div className="sidebar-nav-divider" />
          <div className="sidebar-nav-group">{SECONDARY_NAV_ITEMS.map(renderItem)}</div>
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
