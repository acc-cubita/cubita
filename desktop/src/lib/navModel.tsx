import {
  BarChart3,
  BookOpen,
  Boxes,
  Building,
  Building2,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ClipboardList,
  CreditCard,
  DatabaseBackup,
  Factory,
  FileSpreadsheet,
  HandCoins,
  HardHat,
  Hash,
  HeartHandshake,
  HelpCircle,
  KeyRound,
  Landmark,
  LayoutDashboard,
  PackagePlus,
  Palette,
  Percent,
  Rocket,
  ScanLine,
  Settings,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  SlidersHorizontal,
  Store,
  Truck,
  UserCircle,
  UserCog,
  Users,
  UsersRound,
  Warehouse,
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
  | 'contracting'
  | 'moadian'
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
  | 'modules'
  | 'profile'
  | 'help'
  | 'theme'
  | 'fiscalyear'
  | 'password'
  | 'backup'
  | 'numbering'
  //: صفحه‌های فهرست — از کارتِ «فهرست» باز می‌شوند، نه از منو.
  | 'backuplist'
  | 'userlist'
  | 'fiscalyearlist'

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
    heading: 'مشتریان و فروش',
    icon: <ShoppingBag size={17} />,
    items: [
      { key: 'sales', label: 'فروش', icon: <ShoppingCart size={18} /> },
      { key: 'pos', label: 'صندوق فروشگاهی', icon: <ScanLine size={18} /> },
      { key: 'installments', label: 'فروش اقساطی', icon: <CalendarClock size={18} /> },
      { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} /> },
      { key: 'crm', label: 'باشگاه مشتریان', icon: <HeartHandshake size={18} /> },
    ],
  },
  {
    //: کانالِ فروشِ آنلاین — کنارِ کانالِ حضوری می‌نشیند، نه لای تنظیمات: راه‌اندازیِ
    //: فروشگاه یک ماژولِ کاری است (کاتالوگ، سفارش، درگاه)، نه یک گزینه‌ی پیکربندی.
    //: پیش‌فرض خاموش است و فقط با گرنتِ سوپرادمین دیده می‌شود (RESTRICTED_MODULES).
    heading: 'اتصال فروشگاه',
    icon: <Store size={17} />,
    items: [{ key: 'integration', label: 'اتصال فروشگاه', icon: <Store size={18} /> }],
  },
  {
    heading: 'تامین‌کنندگان و انبار',
    icon: <Boxes size={17} />,
    items: [
      { key: 'purchases', label: 'خرید', icon: <PackagePlus size={18} /> },
      { key: 'inventory', label: 'انبار', icon: <Warehouse size={18} /> },
    ],
  },
  {
    heading: 'سفارش کار',
    icon: <ClipboardList size={17} />,
    items: [{ key: 'manufacturing', label: 'تولید', icon: <Factory size={18} /> }],
  },
  {
    heading: 'دریافت و پرداخت',
    icon: <HandCoins size={17} />,
    items: [{ key: 'banking', label: 'چک و بانک', icon: <Landmark size={18} /> }],
  },
  {
    heading: 'دارایی ثابت',
    icon: <Building2 size={17} />,
    items: [{ key: 'fixedassets', label: 'دارایی ثابت', icon: <Building2 size={18} /> }],
  },
  {
    heading: 'حسابداری',
    icon: <BookOpen size={17} />,
    items: [
      { key: 'accounting', label: 'حسابداری', icon: <BookOpen size={18} /> },
      { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} /> },
    ],
  },
  {
    heading: 'حقوق و دستمزد',
    icon: <Users size={17} />,
    items: [{ key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} /> }],
  },
  {
    heading: 'پیمانکاری',
    icon: <HardHat size={17} />,
    items: [{ key: 'contracting', label: 'پیمانکاری', icon: <HardHat size={18} /> }],
  },
  {
    heading: 'سامانه مؤدیان',
    icon: <FileSpreadsheet size={17} />,
    items: [{ key: 'moadian', label: 'سامانه مؤدیان', icon: <FileSpreadsheet size={18} /> }],
  },
  {
    heading: 'شرکت',
    icon: <Building size={17} />,
    items: [
      { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} /> },
      { key: 'onboarding', label: 'راه‌اندازی', icon: <Rocket size={18} /> },
    ],
  },
  {
    heading: 'تنظیمات',
    icon: <Settings size={17} />,
    items: [
      { key: 'fiscalyear', label: 'سال مالی', icon: <CalendarRange size={18} /> },
      { key: 'numbering', label: 'روش‌های شماره‌گذاری', icon: <Hash size={18} /> },
      { key: 'team', label: 'کاربر جدید', icon: <UserCog size={18} /> },
      { key: 'password', label: 'تغییر کلمه عبور', icon: <KeyRound size={18} /> },
      { key: 'backup', label: 'پشتیبان‌گیری خودکار', icon: <DatabaseBackup size={18} /> },
      { key: 'theme', label: 'ظاهر و پوسته', icon: <Palette size={18} /> },
      { key: 'help', label: 'راهنما', icon: <HelpCircle size={18} /> },
    ],
  },
]

//: کلیدهایی که با سیستمِ شخصی‌سازیِ ماژول گیت می‌شوند. بقیه‌ی ورودی‌های منو (کاربران،
//: تنظیمات، راهنما، ماژول‌های تازه‌ای که هنوز در رجیستریِ بک‌اند نیستند) همیشه دیده
//: می‌شوند — وگرنه با روشنِ‌شدن فیلتر، ناوبریِ سیستمی هم ناپدید می‌شد.
const GATED_MODULE_KEYS = new Set<PageKey>([
  'overview', 'sales', 'pos', 'installments', 'crm', 'purchases', 'inventory',
  'manufacturing', 'accounting', 'banking', 'fixedassets', 'payroll',
  'integration', 'calendar', 'onboarding', 'contacts', 'reports',
])

// تبِ کنترل‌پنلِ فروشِ خودِ کوبیتا (نه فیچرِ مشتری) — فقط برای ادمینِ پلتفرم.
export const PLATFORM_ADMIN_NAV_ITEMS: NavItem[] = [
  { key: 'billing', label: 'خریدهای سایت تجاری', icon: <CreditCard size={18} /> },
]

// «مدیریت اکانت‌ها» فقط برای سوپرادمینِ سامانه (مالک) — سخت‌گیرانه‌تر از ادمینِ پلتفرم.
export const SUPER_ADMIN_NAV_ITEMS: NavItem[] = [
  { key: 'accounts', label: 'مدیریت اکانت‌ها', icon: <ShieldCheck size={18} /> },
  { key: 'mpcommission', label: 'کمیسیونِ بازار', icon: <Percent size={18} /> },
]

//: ورودی‌های پایینِ سایدبار/منوی کاربر. «ظاهر» و «راهنما» به گروهِ «تنظیمات» منتقل
//: شدند تا در ساختارِ تازه‌ی ماژول‌ها یک‌جا جمع باشند.
export const SECONDARY_NAV_ITEMS: NavItem[] = [
  { key: 'profile', label: 'پروفایل من', icon: <UserCircle size={18} /> },
]

//: ورودیِ «شخصی‌سازیِ پنل» — فقط برای مالک (روشن/خاموش‌کردنِ ماژول‌ها).
const MODULES_SETTINGS_ITEM: NavItem = {
  key: 'modules',
  label: 'شخصی‌سازیِ پنل',
  icon: <SlidersHorizontal size={18} />,
}

/** فهرستِ گروه‌ها و آیتم‌های ثانویه را با گیتِ نقش/نوعِ حساب و شخصی‌سازیِ ماژول می‌سازد.
 *  Sidebar و TopNav هر دو همین را صدا می‌زنند تا ناوبری یکسان بماند. */
export function buildNav({
  isPlatformAdmin,
  isSuperAdmin,
  tenantKind,
  enabledModules = [],
  allowedModules = [],
  isOwner = false,
}: {
  isPlatformAdmin: boolean
  isSuperAdmin: boolean
  tenantKind: string
  //: کلیدِ ماژول‌های روشن/مجازِ کسب‌وکار (از MeResponse). خالی = فیلتر نکن (fail-open).
  enabledModules?: string[]
  allowedModules?: string[]
  //: مالکِ کسب‌وکار — گیتِ ورودیِ «شخصی‌سازیِ پنل».
  isOwner?: boolean
}): { groups: NavGroup[]; secondary: NavItem[] } {
  // نمایشِ نهاییِ یک ماژولِ کسب‌وکار = روشن ∩ مجاز. اگر داده نیامده باشد فیلتر نمی‌کنیم (fail-open).
  const filterModules = enabledModules.length > 0 && allowedModules.length > 0
  const allowed = new Set(allowedModules)
  const visible = new Set(enabledModules.filter((k) => allowed.has(k)))
  const isVisible = (key: PageKey) =>
    !filterModules || !GATED_MODULE_KEYS.has(key) || visible.has(key)

  const businessGroups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => isVisible(i.key)),
  })).filter((g) => g.items.length > 0)

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
    ...businessGroups,
    ...(marketplaceItems.length
      ? [{ heading: 'بازارِ عمده‌فروشی', icon: <Truck size={17} />, items: marketplaceItems }]
      : []),
    ...(adminItems.length ? [{ heading: 'مدیریت سامانه', icon: <Settings size={17} />, items: adminItems }] : []),
  ]

  // «شخصی‌سازیِ پنل» (فقط مالک) به انتهای گروهِ «تنظیمات» اضافه می‌شود.
  if (isOwner) {
    const settings = groups.find((g) => g.heading === 'تنظیمات')
    if (settings) settings.items = [...settings.items, MODULES_SETTINGS_ITEM]
  }

  return { groups, secondary: [...SECONDARY_NAV_ITEMS] }
}
