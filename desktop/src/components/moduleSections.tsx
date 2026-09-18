import {
  BadgeDollarSign,
  ScanSearch,
  AlertTriangle,
  ArrowLeftRight,
  Briefcase,
  BellRing,
  Cake,
  Calculator,
  CalendarClock,
  CalendarDays,
  CalendarPlus,
  ClipboardCheck,
  ClipboardList,
  FileText,
  FileUp,
  FlaskConical,
  Gift,
  History,
  Landmark,
  Layers,
  Link2,
  ListChecks,
  Medal,
  Package,
  PackageCheck,
  PackageMinus,
  PackagePlus,
  PackageSearch,
  PackageX,
  Percent,
  PieChart,
  Receipt,
  Send,
  SlidersHorizontal,
  Wrench,
  Settings,
  Store,
  Tags,
  Target,
  Ticket,
  Undo2,
  UserCheck,
  TrendingDown,
  Users,
  UsersRound,
  Warehouse,
  type LucideIcon,
  FileStack,
  FolderTree,
  RotateCcw,
  Ruler,
  Tag,
} from 'lucide-react'
import type { PageKey } from './Sidebar'

/** یک تبِ درون‌ماژولی — کلید و برچسب و آیکنش باید دقیقاً با تعریفِ `<Tabs>` همان
 *  صفحه یکی باشد، چون سایدبار با همین کلید تبِ صفحه را کنترل می‌کند. */
export type SectionDef = {
  key: string
  label: string
  icon: LucideIcon
  /** بخشی که دفترِ داده‌ی ذخیره‌شده است نه کاری که کاربر انجام می‌دهد. در ستونِ
   *  «فهرست» می‌نشیند نه «عملیات» — هرچند مثلِ بقیه یک تبِ همان صفحه است. */
  kind?: 'list'
}

/** بخش‌های «عملیات» و «فهرست»ِ یک ماژولِ تب‌دار، با همان ترتیبِ تعریف. */
export const opsSections = (sections: SectionDef[]) => sections.filter((s) => s.kind !== 'list')
export const listSections = (sections: SectionDef[]) => sections.filter((s) => s.kind === 'list')

/**
 * فهرستِ تب‌های هر ماژولِ تب‌دار — منبعِ زیرمنوی سطح‌سومِ سایدبار.
 *
 * **چرا این‌جا و نه داخلِ صفحه:** سایدبار باید تب‌های هر ماژول را بشناسد تا آن‌ها را
 * به‌صورتِ زیرمنو نشان دهد و با کلیک، تبِ صفحه را باز کند. کلیدها همان کلیدهای
 * `<Tabs>` آن صفحه‌اند؛ اگر روزی تبی اضافه/حذف شد، همین‌جا هم به‌روز شود. (اگر کلیدی
 * ناهم‌خوان بماند، صفحه به تبِ اول برمی‌گردد — نه خطا، ولی زیرمنو ناقص می‌شود.)
 */
export const MODULE_SECTIONS: Partial<Record<PageKey, SectionDef[]>> = {
  //: «سامانه مؤدیان» — ترتیب همان مسیرِ کار است: اول ببین آماده‌ای یا نه، بعد بفرست،
  //: بعد پیگیری کن؛ تنظیمات آخر است چون یک‌بار انجام می‌شود.
  moadian: [
    { key: 'status', label: 'وضعیت و آمادگی', icon: ListChecks },
    { key: 'send', label: 'ارسال صورتحساب', icon: Send },
    { key: 'settings', label: 'تنظیمات و اعتبارنامه', icon: Landmark },
  ],
  //: تب‌های دو صفحه‌ی «خرید» و «انبار». منوی گروهِ «تامین‌کنندگان و انبار» از این‌ها
  //: ساخته نمی‌شود — از `OPS_MENUS`/`LIST_MENUS` می‌آید که بینِ دو صفحه تخت است. این‌جا
  //: فقط باید با `<Tabs>`ِ هر صفحه یکی بماند (تبِ پیش‌فرض و نوارِ تبِ زیرِ ۱۰۲۴px).
  purchases: [
    { key: 'invoices', label: 'فاکتور خرید', icon: PackagePlus },
    { key: 'services', label: 'فاکتور خرید خدمات', icon: Briefcase },
    { key: 'receipts', label: 'رسید انبار', icon: PackageCheck },
    { key: 'returns', label: 'برگشت از خرید', icon: Undo2 },
    { key: 'deductions', label: 'انواع کسورات', icon: Percent },
    { key: 'invoice-list', label: 'فاکتورهای خرید', icon: ClipboardList, kind: 'list' },
    { key: 'service-list', label: 'فاکتورهای خرید خدمات', icon: FileText, kind: 'list' },
  ],
  inventory: [
    { key: 'products', label: 'کالاها', icon: Package },
    { key: 'warehouses', label: 'انبارها', icon: Warehouse },
    { key: 'units', label: 'واحدها', icon: Ruler },
    { key: 'taxonomy', label: 'گروه و مشخصات', icon: FolderTree },
    { key: 'count-tags', label: 'تگ انبارگردانی', icon: Tag },
    { key: 'count', label: 'ثبت مغایرت انبارگردانی', icon: ClipboardCheck },
    { key: 'adjust', label: 'تعدیل دستی', icon: ClipboardList },
    { key: 'issues', label: 'حواله انبار', icon: PackageMinus },
    { key: 'issue-returns', label: 'برگشت خروج انبار', icon: RotateCcw },
    { key: 'transfer', label: 'رسید/حواله انتقال بین انبارها', icon: ArrowLeftRight },
    { key: 'unpriced', label: 'قیمت‌گذاری ورودی‌ها', icon: BadgeDollarSign },
    { key: 'valuation', label: 'قیمت‌گذاری اسناد انبار', icon: Calculator },
    { key: 'pricelists', label: 'لیست قیمت', icon: Tags },
    { key: 'import', label: 'ورود گروهی کالا', icon: FileUp },
    { key: 'documents', label: 'فهرست رسیدها و حواله‌های انبار', icon: FileStack, kind: 'list' },
    { key: 'kardex', label: 'کاردکس کالا', icon: History, kind: 'list' },
    { key: 'stock', label: 'مرور انبار / موجودی کالا', icon: PackageSearch, kind: 'list' },
    { key: 'low', label: 'گزارش نقطه سفارش', icon: AlertTriangle, kind: 'list' },
    { key: 'count-list', label: 'فهرست انبارگردانی‌ها', icon: ListChecks, kind: 'list' },
    { key: 'issue-return-list', label: 'برگشت‌های خروج انبار', icon: RotateCcw, kind: 'list' },
    { key: 'serials', label: 'جستجوی سریال', icon: ScanSearch, kind: 'list' },
    { key: 'batches', label: 'بچ و انقضا', icon: CalendarClock, kind: 'list' },
  ],
  distributor: [
    { key: 'catalog', label: 'کاتالوگ', icon: Package },
    { key: 'orders', label: 'سفارش‌ها', icon: ClipboardList },
    { key: 'connections', label: 'اتصال‌ها', icon: Link2 },
    { key: 'commission', label: 'کمیسیون', icon: Percent },
    { key: 'settings', label: 'تنظیمات', icon: Settings },
  ],
  marketplace: [
    { key: 'distributors', label: 'پخش‌کننده‌ها', icon: Store },
    { key: 'catalog', label: 'کاتالوگ', icon: Package },
    { key: 'orders', label: 'سفارش‌های من', icon: ClipboardList },
  ],
  contacts: [
    { key: 'contacts', label: 'طرف حساب‌ها', icon: UsersRound, kind: 'list' },
    { key: 'aging', label: 'سنین مطالبات', icon: CalendarClock, kind: 'list' },
    { key: 'import', label: 'ورود گروهی اشخاص', icon: FileUp },
  ],
  crm: [
    { key: 'leads', label: 'سرنخ‌ها', icon: Target },
    { key: 'activities', label: 'پیگیری‌ها', icon: CalendarClock },
    { key: 'loyalty', label: 'باشگاه مشتریان', icon: Gift },
    { key: 'segments', label: 'بخش‌بندی', icon: PieChart, kind: 'list' },
    { key: 'tiers', label: 'سطوح باشگاه', icon: Medal },
    { key: 'rewards', label: 'جوایز', icon: Ticket },
    { key: 'birthdays', label: 'تولدها', icon: Cake },
  ],
  //: ترتیب همان است که کاربر خواست. پنج بخشِ آخر دفترند و در ستونِ «فهرست» می‌آیند.
  manufacturing: [
    { key: 'boms', label: 'فرمول‌های ساخت', icon: FlaskConical },
    { key: 'orders', label: 'سفارش تولید', icon: ClipboardList },
    { key: 'materials', label: 'تحویل مواد', icon: PackageMinus },
    { key: 'receipts', label: 'رسید محصول', icon: PackageCheck },
    { key: 'costing', label: 'محاسبه قیمت تمام‌شده', icon: Calculator },
    { key: 'bom-list', label: 'فهرست فرمول‌های ساخته‌شده', icon: Layers, kind: 'list' },
    { key: 'order-list', label: 'سفارشات تولید', icon: ListChecks, kind: 'list' },
    { key: 'variance', label: 'انحراف مصرف مواد', icon: AlertTriangle, kind: 'list' },
    { key: 'kardex', label: 'کاردکس تولید', icon: History, kind: 'list' },
    { key: 'cost-report', label: 'گزارش قیمت تمام‌شده', icon: PieChart, kind: 'list' },
  ],
  //: ترتیب همان است که کاربر خواست. پنج بخشِ آخر دفترند و در ستونِ «فهرست» می‌آیند.
  fixedassets: [
    { key: 'assets', label: 'کارت دارایی', icon: Landmark },
    { key: 'placement', label: 'تحویل و استقرار', icon: UserCheck },
    { key: 'depreciation-calc', label: 'محاسبه استهلاک', icon: Calculator },
    { key: 'depreciation-post', label: 'صدور سند استهلاک', icon: TrendingDown },
    { key: 'estimate', label: 'تغییر روش یا عمر مفید', icon: SlidersHorizontal },
    { key: 'transfer', label: 'جابه‌جایی دارایی', icon: ArrowLeftRight },
    { key: 'disposal', label: 'خروج دارایی', icon: PackageX },
    { key: 'improvement', label: 'تعمیرات اساسی', icon: Wrench },
    { key: 'registry', label: 'فهرست دارایی‌ها', icon: ClipboardList, kind: 'list' },
    { key: 'depreciation-list', label: 'فهرست محاسبات استهلاک', icon: ListChecks, kind: 'list' },
    { key: 'depreciation-docs', label: 'گزارش اسناد استهلاک', icon: FileText, kind: 'list' },
    { key: 'assignments', label: 'جابه‌جایی‌ها و تحویل‌ها', icon: History, kind: 'list' },
    { key: 'disposals', label: 'خروج و فروش دارایی', icon: Receipt, kind: 'list' },
  ],
  payroll: [
    { key: 'staff', label: 'پرسنل و احکام', icon: Users },
    { key: 'run', label: 'کارکرد و صدور فیش', icon: CalendarPlus },
    { key: 'benefits', label: 'مزایا', icon: Gift },
    { key: 'settings', label: 'تنظیماتِ حقوق', icon: Settings },
  ],
  integration: [
    { key: 'build', label: 'فروشگاهِ کوبیتا', icon: Store },
    { key: 'connect', label: 'اتصال به سایتِ موجود', icon: Link2 },
  ],
  calendar: [
    { key: 'reminders', label: 'کارهای امروز', icon: BellRing },
    { key: 'calendar', label: 'تقویم ماهانه', icon: CalendarDays },
  ],
}
