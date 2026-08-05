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
  ChevronDown,
  ShoppingBag,
  Boxes,
  Wallet,
  Database,
  Wrench,
  Settings,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTheme } from '../lib/theme'
import { MODULE_SECTIONS } from './moduleSections'

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
type NavGroup = { heading: string; icon?: ReactNode; items: NavItem[] }

// چیدمانِ ماژول‌ها گروه‌بندی‌شده است تا کاربر به‌جای اسکنِ یک فهرستِ تختِ بلند،
// چشمش روی «دسته» بیفتد. هر گروه یک آکاردئونِ کشویی است: سرتیتر همیشه دیده می‌شود و
// با کلیک، ماژول‌هایش باز/بسته می‌شوند. ترتیبِ گروه‌ها بر اساسِ گردشِ کار است: پرکاربردِ
// روزمره (فروش/خرید) بالا، مالی وسط، اطلاعات و گزارش، و ابزارِ کم‌استفاده ته.
const NAV_GROUPS: NavGroup[] = [
  {
    heading: 'میزکار',
    items: [{ key: 'overview', label: 'داشبورد', icon: <LayoutDashboard size={18} /> }],
  },
  {
    heading: 'فروش و مشتریان',
    icon: <ShoppingBag size={17} />,
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
    icon: <Boxes size={17} />,
    items: [
      { key: 'purchases', label: 'خرید', icon: <PackagePlus size={18} /> },
      { key: 'inventory', label: 'انبار', icon: <Warehouse size={18} /> },
      { key: 'manufacturing', label: 'تولید', icon: <Factory size={18} /> },
    ],
  },
  {
    heading: 'مالی و بانکی',
    icon: <Wallet size={17} />,
    items: [
      { key: 'accounting', label: 'حسابداری', icon: <BookOpen size={18} /> },
      { key: 'banking', label: 'چک و بانک', icon: <Landmark size={18} /> },
      { key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} /> },
    ],
  },
  {
    heading: 'اطلاعات و گزارش',
    icon: <Database size={17} />,
    items: [
      { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} /> },
      { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} /> },
    ],
  },
  {
    heading: 'ابزار',
    icon: <Wrench size={17} />,
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
  activeSection,
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
  /** تبِ فعالِ صفحه (زیرمنوی سطح‌سوم)؛ null یعنی تبِ پیش‌فرض (اولین). */
  activeSection: string | null
  onNavigate: (page: PageKey, section?: string) => void
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
    ...(adminItems.length
      ? [{ heading: 'مدیریت سامانه', icon: <Settings size={17} />, items: adminItems }]
      : []),
  ]
  const { theme, toggle } = useTheme()

  // آکاردئون: فقط یک گروه هم‌زمان باز است تا نوار کوتاه بماند. به‌صورتِ پیش‌فرض،
  // گروهی که صفحه‌ی فعال در آن است باز می‌شود؛ و با تغییرِ صفحه‌ی فعال هم‌گام می‌ماند.
  const activeGroup = groups.find((g) => g.items.some((i) => i.key === active))?.heading ?? null
  const [openGroup, setOpenGroup] = useState<string | null>(activeGroup)
  useEffect(() => {
    if (activeGroup) setOpenGroup(activeGroup)
  }, [activeGroup])

  // سطح‌سوم: کدام ماژول زیرمنوی تب‌هایش باز است. فقط یکی هم‌زمان، و ماژولِ فعال
  // (اگر تب‌دار باشد) خودکار باز می‌شود.
  const [openModule, setOpenModule] = useState<PageKey | null>(
    MODULE_SECTIONS[active] ? active : null,
  )
  useEffect(() => {
    // ماژولِ فعالِ تب‌دار باز می‌شود؛ رفتن به یک صفحه‌ی بدونِ تب، زیرمنوی بازِ قبلی را می‌بندد.
    setOpenModule(MODULE_SECTIONS[active] ? active : null)
  }, [active])

  // برگِ ساده (بدونِ زیرمنو): داشبورد، صندوق، گزارش‌ها، آیتم‌های ثانویه و مدیریتی.
  const renderLeaf = (item: NavItem) => (
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

  // ماژول: اگر تب‌دار باشد، یک آکاردئونِ سطح‌دوم با زیرمنوی تب‌ها (سطح‌سوم)؛ وگرنه برگِ ساده.
  const renderModule = (item: NavItem) => {
    const sections = MODULE_SECTIONS[item.key]
    if (!sections) return renderLeaf(item)
    const isCurrent = active === item.key
    const isOpen = openModule === item.key
    // تبِ فعال: صریح، وگرنه (وقتی هنوز تبی انتخاب نشده) اولین تب.
    const activeSecKey = isCurrent ? activeSection ?? sections[0]?.key : null
    return (
      <div className={`sidebar-mod${isOpen ? ' open' : ''}`} key={item.key}>
        {/* سرتیترِ ماژول دو ناحیه‌ی کلیک دارد: نامِ ماژول → رفتن به تبِ اول + بازکردن؛
            فلش → فقط باز/بستنِ زیرمنو (بدونِ جابه‌جایی). دو دکمه‌ی مجزا چون دکمه در
            دکمه HTML معتبر نیست. درِ کشوی موبایل باز می‌ماند تا کاربر تب را انتخاب کند. */}
        <div className={`sidebar-mod-header${isCurrent ? ' current' : ''}`}>
          <button
            type="button"
            className="sidebar-mod-main"
            onClick={() => {
              onNavigate(item.key)
              setOpenModule(item.key)
            }}
          >
            {item.icon}
            <span className="mod-label">{item.label}</span>
            {isCurrent && !isOpen && <span className="acc-dot" aria-hidden="true" />}
          </button>
          <button
            type="button"
            className="sidebar-mod-toggle"
            aria-label={isOpen ? 'بستنِ زیرمنو' : 'بازکردنِ زیرمنو'}
            aria-expanded={isOpen}
            onClick={() => setOpenModule((m) => (m === item.key ? null : item.key))}
          >
            <ChevronDown className="mod-chev" size={15} />
          </button>
        </div>
        <div className="sidebar-mod-panel">
          <div className="mod-inner">
            {sections.map((s) => {
              const Icon = s.icon
              return (
                <button
                  key={s.key}
                  type="button"
                  className={`sidebar-subitem${activeSecKey === s.key ? ' active' : ''}`}
                  onClick={() => {
                    onNavigate(item.key, s.key)
                    onClose?.()
                  }}
                >
                  <Icon size={15} />
                  <span>{s.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  const renderGroup = (group: NavGroup) => {
    // گروهِ تک‌آیتم (مثلِ داشبورد) نیازی به آکاردئون ندارد؛ مستقیم دیده می‌شود.
    if (group.items.length === 1) {
      return (
        <div className="sidebar-nav-solo" key={group.heading}>
          {renderModule(group.items[0])}
        </div>
      )
    }
    const isOpen = openGroup === group.heading
    const hasActive = group.items.some((i) => i.key === active)
    return (
      <div className={`sidebar-acc${isOpen ? ' open' : ''}`} key={group.heading}>
        <button
          type="button"
          className={`sidebar-acc-header${hasActive ? ' has-active' : ''}`}
          aria-expanded={isOpen}
          onClick={() => setOpenGroup((h) => (h === group.heading ? null : group.heading))}
        >
          <span className="acc-ico">{group.icon}</span>
          <span className="acc-label">{group.heading}</span>
          {hasActive && !isOpen && <span className="acc-dot" aria-hidden="true" />}
          <ChevronDown className="acc-chev" size={16} />
        </button>
        <div className="sidebar-acc-panel">
          <div className="acc-inner">{group.items.map(renderModule)}</div>
        </div>
      </div>
    )
  }

  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">C</span>
        <span className="sidebar-brand-name">کوبیتا</span>
      </div>

      <nav className="sidebar-nav">
        {groups.map(renderGroup)}
        <div className="sidebar-nav-divider" />
        <div className="sidebar-nav-group">{SECONDARY_NAV_ITEMS.map(renderLeaf)}</div>
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
