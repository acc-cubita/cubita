import {
  Archive,
  ArrowLeftRight,
  BarChart3,
  BellRing,
  BookMarked,
  BookOpen,
  BookOpenCheck,
  Boxes,
  Building,
  Building2,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ClipboardCheck,
  ClipboardList,
  Coins,
  Combine,
  CreditCard,
  DatabaseBackup,
  Factory,
  FileSpreadsheet,
  FolderPlus,
  HandCoins,
  HardHat,
  Hash,
  HeartHandshake,
  HelpCircle,
  KeyRound,
  Landmark,
  Layers,
  LayoutDashboard,
  ListTree,
  Lock,
  MapPin,
  PackagePlus,
  Palette,
  Percent,
  PlayCircle,
  Scale,
  ScanLine,
  Settings,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  SlidersHorizontal,
  Store,
  Tag,
  Tags,
  Target,
  Truck,
  UserCircle,
  UserCog,
  UserPlus,
  Users,
  UsersRound,
  Wallet,
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
  //: ماژولِ «شرکت» — عملیاتِ سطحِ شرکت.
  | 'contactnew'
  | 'contactgroup'
  | 'geo'
  | 'costcenter'
  | 'openingops'
  | 'yearendops'
  | 'yearendreminder'
  //: صفحه‌های فهرست — از کارتِ «فهرست» باز می‌شوند، نه از منو.
  | 'backuplist'
  | 'userlist'
  | 'fiscalyearlist'
  | 'dataexport'
  | 'dataimport'
  | 'reportbuilder'
  | 'dynamicreports'
  | 'dayactivity'
  | 'mgmtreports'
  | 'usagereport'
  | 'contactlist'
  | 'relatedpeople'
  | 'installmentplans'
  | 'allinstallments'
  | 'costcenterlist'
  //: فهرستِ «سامانه مؤدیان» — از کارتِ «فهرست» باز می‌شود، نه از منوی عملیات.
  | 'moadianhistory'
  //: ماژولِ «حسابداری» — هجده عملیاتِ دفترداری. کلیدِ ماژولِ گیت‌کننده‌شان
  //: `accounting` است (نگاشتِ PAGE_MODULE_KEY پایین)، نه خودشان.
  | 'acctchart'
  | 'journalentry'
  | 'renumber'
  | 'mergeentries'
  | 'finalizeentries'
  | 'fxrevaluation'
  | 'generaldoc'
  | 'entrycartable'
  | 'closingopening'
  | 'vat'
  | 'ebooks'
  | 'reclassify'
  | 'closepnl'
  | 'analytics'
  | 'newaccount'
  | 'openingbalance'
  | 'accountbrowse'
  | 'balancereport'
  | 'ledgerreport'
  //: فهرست‌های حسابداری — از کارتِ «فهرست» باز می‌شوند.
  | 'entrylist'
  | 'accountlist'
  | 'recurringlist'
  | 'budgetlist'
  | 'currencylist'
  | 'periodcloselist'

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
    //: «حسابداری» = دفترداری، از ساختِ چارت تا بستنِ سال. ترتیب عمدی است و مسیرِ
    //: کارِ واقعی را دنبال می‌کند: اول ساختار (چارت، سرفصل)، بعد ثبت و بازبینیِ
    //: سند، بعد اصلاح و مرتب‌سازی، بعد عملیاتِ پایانِ دوره، و آخر گزارش‌ها.
    heading: 'حسابداری',
    icon: <BookOpen size={17} />,
    items: [
      { key: 'acctchart', label: 'درختواره حساب‌ها', icon: <ListTree size={18} /> },
      { key: 'newaccount', label: 'سرفصل جدید', icon: <FolderPlus size={18} /> },
      { key: 'openingbalance', label: 'مانده اول دوره', icon: <Wallet size={18} /> },
      { key: 'journalentry', label: 'سند حسابداری', icon: <BookOpen size={18} /> },
      { key: 'entrycartable', label: 'کارتابل صدور سند حسابداری', icon: <ClipboardCheck size={18} /> },
      { key: 'finalizeentries', label: 'تبدیل اسناد موقت به دائم', icon: <Lock size={18} /> },
      { key: 'renumber', label: 'شماره‌گذاری مجدد اسناد', icon: <Hash size={18} /> },
      { key: 'mergeentries', label: 'ادغام اسناد', icon: <Combine size={18} /> },
      { key: 'reclassify', label: 'اصلاح طبقه‌بندی حساب‌ها', icon: <ArrowLeftRight size={18} /> },
      { key: 'analytics', label: 'تفصیلی سایر', icon: <Tag size={18} /> },
      { key: 'fxrevaluation', label: 'صدور سند تسعیر ارز', icon: <Coins size={18} /> },
      { key: 'generaldoc', label: 'صدور سند کل', icon: <FileSpreadsheet size={18} /> },
      { key: 'closepnl', label: 'بستن حساب‌های سود و زیان', icon: <CalendarCheck size={18} /> },
      { key: 'closingopening', label: 'صدور سند اختتامیه و افتتاحیه', icon: <Archive size={18} /> },
      { key: 'vat', label: 'مالیات بر ارزش افزوده', icon: <Percent size={18} /> },
      { key: 'ebooks', label: 'دفاتر تجارت الکترونیک', icon: <BookMarked size={18} /> },
      { key: 'accountbrowse', label: 'مرور حساب‌ها', icon: <Layers size={18} /> },
      { key: 'balancereport', label: 'گزارش ترازها', icon: <Scale size={18} /> },
      { key: 'ledgerreport', label: 'گزارش دفتر', icon: <BookOpenCheck size={18} /> },
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
    //: «شرکت» = کارهای سطحِ سازمان: شناسنامه‌ی طرف‌حساب‌ها، فروشِ اقساطی، و عملیاتِ
    //: ابتدا/انتهای دوره. ترتیب عمدی است — از ساختِ داده‌ی پایه تا بستنِ سال.
    heading: 'شرکت',
    icon: <Building size={17} />,
    items: [
      { key: 'contactnew', label: 'طرف حساب جدید', icon: <UserPlus size={18} /> },
      { key: 'installments', label: 'فروش اقساطی', icon: <CalendarClock size={18} /> },
      { key: 'costcenter', label: 'مرکز هزینه', icon: <Target size={18} /> },
      { key: 'geo', label: 'محل‌های جغرافیایی', icon: <MapPin size={18} /> },
      { key: 'contactgroup', label: 'گروه جدید', icon: <Tags size={18} /> },
      { key: 'openingops', label: 'عملیات اول دوره', icon: <PlayCircle size={18} /> },
      { key: 'yearendops', label: 'عملیات پایان سال', icon: <Archive size={18} /> },
      { key: 'yearendreminder', label: 'یادآوری عملیات پایان سال', icon: <BellRing size={18} /> },
      { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} /> },
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
//: صفحه‌هایی که خودشان کلیدِ ماژول نیستند ولی زیرِ چترِ یک ماژول گیت می‌شوند.
//: بدونِ این نگاشت، خاموش‌کردنِ «حسابداری» در شخصی‌سازیِ پنل هجده ورودی را روشن
//: می‌گذاشت — و بدتر، گرنت‌نداشتنِ ماژول هم جلویشان را نمی‌گرفت.
const PAGE_MODULE_KEY: Partial<Record<PageKey, string>> = Object.fromEntries(
  (
    [
      'acctchart', 'newaccount', 'openingbalance', 'journalentry', 'entrycartable', 'finalizeentries',
      'renumber', 'mergeentries', 'reclassify', 'analytics', 'fxrevaluation',
      'generaldoc', 'closepnl', 'closingopening', 'vat', 'ebooks', 'accountbrowse',
      'balancereport', 'ledgerreport',
      'entrylist', 'accountlist', 'recurringlist', 'budgetlist', 'currencylist', 'periodcloselist',
    ] as PageKey[]
  ).map((key) => [key, 'accounting']),
) as Partial<Record<PageKey, string>>

const GATED_MODULE_KEYS = new Set<PageKey>([
  'overview', 'sales', 'pos', 'installments', 'crm', 'purchases', 'inventory',
  'manufacturing', 'accounting', 'banking', 'fixedassets', 'payroll',
  'integration', 'calendar', 'contacts', 'reports',
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
  const isVisible = (key: PageKey) => {
    if (!filterModules) return true
    const moduleKey = PAGE_MODULE_KEY[key]
    if (moduleKey) return visible.has(moduleKey)
    return !GATED_MODULE_KEYS.has(key) || visible.has(key)
  }

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
