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
  Store,
  BarChart3,
  CalendarDays,
  CreditCard,
  Rocket,
  HelpCircle,
  UserCog,
  UserCircle,
  ShieldCheck,
  LogOut,
  Sun,
  Moon,
} from 'lucide-react'
import type { ReactNode } from 'react'
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
  | 'integration'
  | 'billing'
  | 'accounts'
  | 'reports'
  | 'onboarding'
  | 'calendar'
  | 'team'
  | 'profile'
  | 'help'

type NavItem = { key: PageKey; label: string; icon: ReactNode }
type NavGroup = { heading: string; items: NavItem[] }

// چیدمانِ ماژول‌ها گروه‌بندی‌شده است تا کاربر به‌جای اسکنِ یک فهرستِ تختِ بلند،
// چشمش روی «دسته» بیفتد. ترتیبِ گروه‌ها بر اساسِ گردشِ کار است: پرکاربردِ روزمره
// (فروش/خرید) بالا، مالی وسط، اطلاعات و گزارش، و ابزارِ کم‌استفاده (راه‌اندازی) ته.
const NAV_GROUPS: NavGroup[] = [
  {
    heading: 'میزکار',
    items: [{ key: 'overview', label: 'داشبورد', icon: <LayoutDashboard size={18} /> }],
  },
  {
    heading: 'فروش و مشتریان',
    items: [
      { key: 'sales', label: 'فروش', icon: <ShoppingCart size={18} /> },
      { key: 'pos', label: 'صندوق فروشگاهی', icon: <ScanLine size={18} /> },
      { key: 'installments', label: 'فروش اقساطی', icon: <CalendarClock size={18} /> },
      { key: 'crm', label: 'باشگاه مشتریان', icon: <HeartHandshake size={18} /> },
      { key: 'integration', label: 'اتصال فروشگاه', icon: <Store size={18} /> },
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
    heading: 'مالی و بانکی',
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

// این تب کنترل‌پنل فروش خودِ کوبیتاست، نه یک ویژگی برای مشتری‌ها. تا امروز فقط
// روی role_key === 'owner' شرط داشت، یعنی هر صاحب کسب‌وکاری (نه فقط خودِ کوبیتا)
// آن را در ساید‌بار می‌دید و کلیک می‌کرد تا از بک‌اند ۴۰۳ بگیرد — بک‌اند درست
// محافظت می‌کرد، ولی UI چیزی نشان می‌داد که هرگز قرار نبود مال او باشد.
const PLATFORM_ADMIN_NAV_ITEMS: NavItem[] = [
  { key: 'billing', label: 'خریدهای سایت تجاری', icon: <CreditCard size={18} /> },
]

// ماژولِ «مدیریت اکانت‌ها» فقط برای سوپرادمینِ سامانه (مالک) — سخت‌گیرانه‌تر از
// ادمینِ پلتفرم. برای هیچ کاربرِ دیگری، حتی ادمین‌های پلتفرم، دیده نمی‌شود.
const SUPER_ADMIN_NAV_ITEMS: NavItem[] = [
  { key: 'accounts', label: 'مدیریت اکانت‌ها', icon: <ShieldCheck size={18} /> },
]

const SECONDARY_NAV_ITEMS: NavItem[] = [
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
  isSuperAdmin,
  onLogout,
  open = false,
  onClose,
}: {
  active: PageKey
  onNavigate: (page: PageKey) => void
  userName: string
  roleName: string
  isPlatformAdmin: boolean
  isSuperAdmin: boolean
  onLogout: () => void
  /** فقط در وبِ باریک (موبایل) معنا دارد: نوار کناری کشوی روی‌هم می‌شود. */
  open?: boolean
  onClose?: () => void
}) {
  // آیتم‌های ادمین (مشروط) در گروهِ اختصاصیِ خودشان ته فهرست می‌آیند تا از ماژول‌های
  // عملیاتیِ کاربرِ عادی جدا باشند و فقط برای مالک/ادمین دیده شوند.
  const adminItems = [
    ...(isPlatformAdmin ? PLATFORM_ADMIN_NAV_ITEMS : []),
    ...(isSuperAdmin ? SUPER_ADMIN_NAV_ITEMS : []),
  ]
  const groups: NavGroup[] = [
    ...NAV_GROUPS,
    ...(adminItems.length ? [{ heading: 'مدیریت سامانه', items: adminItems }] : []),
  ]
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
        <span className="sidebar-brand-mark">C</span>
        <span className="sidebar-brand-name">کوبیتا</span>
      </div>

      <nav className="sidebar-nav">
        {groups.map((group) => (
          <div className="sidebar-nav-group" key={group.heading}>
            <div className="sidebar-nav-heading">{group.heading}</div>
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
