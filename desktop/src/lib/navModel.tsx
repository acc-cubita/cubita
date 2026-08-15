import {
  LayoutDashboard,
  ShoppingCart,
  ScanLine,
  CalendarClock,
  Warehouse,
  UsersRound,
  BookOpen,
  Landmark,
  Building2,
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
  PackagePlus,
  ShoppingBag,
  Boxes,
  Wallet,
  Database,
  Wrench,
  Settings,
  Truck,
  Percent,
  Palette,
} from 'lucide-react'
import type { ReactNode } from 'react'

// شناسه‌ی هر صفحه‌ی برنامه. منبعِ واحد؛ Sidebar و TopNav هر دو از همین می‌خوانند.
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
  | 'fixedassets'
  | 'distributor'
  | 'marketplace'
  | 'payroll'
  | 'integration'
  | 'billing'
  | 'accounts'
  | 'mpcommission'
  | 'reports'
  | 'onboarding'
  | 'calendar'
  | 'team'
  | 'profile'
  | 'help'
  | 'theme'

export type NavItem = { key: PageKey; label: string; icon: ReactNode }
export type NavGroup = { heading: string; icon?: ReactNode; items: NavItem[] }

// چیدمانِ ماژول‌ها گروه‌بندی‌شده تا کاربر به‌جای اسکنِ فهرستِ تخت، روی «دسته» تمرکز کند.
// ترتیبِ گروه‌ها بر اساسِ گردشِ کار: پرکاربردِ روزمره بالا، مالی وسط، اطلاعات/گزارش، ابزارِ کم‌استفاده ته.
export const NAV_GROUPS: NavGroup[] = [
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
      { key: 'fixedassets', label: 'دارایی ثابت', icon: <Building2 size={18} /> },
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
      { key: 'integration', label: 'اتصال فروشگاه', icon: <Store size={18} /> },
      { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} /> },
      { key: 'onboarding', label: 'راه‌اندازی', icon: <Rocket size={18} /> },
    ],
  },
]

// تبِ کنترل‌پنلِ فروشِ خودِ کوبیتا (نه فیچرِ مشتری) — فقط برای ادمینِ پلتفرم.
export const PLATFORM_ADMIN_NAV_ITEMS: NavItem[] = [
  { key: 'billing', label: 'خریدهای سایت تجاری', icon: <CreditCard size={18} /> },
]

// «مدیریت اکانت‌ها» فقط برای سوپرادمینِ سامانه (مالک) — سخت‌گیرانه‌تر از ادمینِ پلتفرم.
export const SUPER_ADMIN_NAV_ITEMS: NavItem[] = [
  { key: 'accounts', label: 'مدیریت اکانت‌ها', icon: <ShieldCheck size={18} /> },
  { key: 'mpcommission', label: 'کمیسیونِ بازار', icon: <Percent size={18} /> },
]

export const SECONDARY_NAV_ITEMS: NavItem[] = [
  { key: 'profile', label: 'پروفایل من', icon: <UserCircle size={18} /> },
  { key: 'team', label: 'کاربران', icon: <UserCog size={18} /> },
  { key: 'theme', label: 'ظاهر و پوسته', icon: <Palette size={18} /> },
  { key: 'help', label: 'راهنما', icon: <HelpCircle size={18} /> },
]

/** فهرستِ گروه‌ها و آیتم‌های ثانویه را با گیتِ نقش/نوعِ حساب می‌سازد. Sidebar و TopNav
 *  هر دو همین را صدا می‌زنند تا ناوبری یکسان بماند. */
export function buildNav({
  isPlatformAdmin,
  isSuperAdmin,
  tenantKind,
}: {
  isPlatformAdmin: boolean
  isSuperAdmin: boolean
  tenantKind: string
}): { groups: NavGroup[]; secondary: NavItem[] } {
  const adminItems = [
    ...(isPlatformAdmin ? PLATFORM_ADMIN_NAV_ITEMS : []),
    ...(isSuperAdmin ? SUPER_ADMIN_NAV_ITEMS : []),
  ]
  // ماژول‌های بازارِ عمده‌فروشی — فقط برای حسابِ متناظر (انحصاری). standard هیچ‌کدام را نمی‌بیند.
  const marketplaceItems: NavItem[] = [
    ...(tenantKind === 'distributor'
      ? [{ key: 'distributor' as PageKey, label: 'پخشِ من', icon: <Truck size={18} /> }]
      : []),
    ...(tenantKind === 'retailer'
      ? [{ key: 'marketplace' as PageKey, label: 'بازارِ خرید', icon: <Store size={18} /> }]
      : []),
  ]
  const groups: NavGroup[] = [
    ...NAV_GROUPS,
    ...(marketplaceItems.length
      ? [{ heading: 'بازارِ عمده‌فروشی', icon: <Truck size={17} />, items: marketplaceItems }]
      : []),
    ...(adminItems.length ? [{ heading: 'مدیریت سامانه', icon: <Settings size={17} />, items: adminItems }] : []),
  ]
  return { groups, secondary: SECONDARY_NAV_ITEMS }
}
