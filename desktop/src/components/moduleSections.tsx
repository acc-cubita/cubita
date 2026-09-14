import {
  ScanSearch,
  AlertTriangle,
  ArrowLeftRight,
  Briefcase,
  BellRing,
  Cake,
  CalendarClock,
  CalendarDays,
  CalendarPlus,
  ClipboardCheck,
  ClipboardList,
  FileUp,
  FlaskConical,
  Gift,
  Hammer,
  History,
  Landmark,
  Link2,
  ListChecks,
  Medal,
  Package,
  PackageCheck,
  PackageMinus,
  PackagePlus,
  PackageSearch,
  Percent,
  PieChart,
  Send,
  Settings,
  Store,
  Tags,
  Target,
  Ticket,
  Undo2,
  Users,
  UsersRound,
  Warehouse,
  type LucideIcon,
} from 'lucide-react'
import type { PageKey } from './Sidebar'

/** یک تبِ درون‌ماژولی — کلید و برچسب و آیکنش باید دقیقاً با تعریفِ `<Tabs>` همان
 *  صفحه یکی باشد، چون سایدبار با همین کلید تبِ صفحه را کنترل می‌کند. */
export type SectionDef = { key: string; label: string; icon: LucideIcon }

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
  purchases: [
    { key: 'invoices', label: 'فاکتور خرید', icon: PackagePlus },
    { key: 'services', label: 'فاکتور خرید خدمات', icon: Briefcase },
    { key: 'receipts', label: 'رسید انبار', icon: PackageCheck },
    { key: 'returns', label: 'برگشت از خرید', icon: Undo2 },
    { key: 'deductions', label: 'انواع کسورات', icon: Percent },
  ],
  inventory: [
    { key: 'products', label: 'کالاها', icon: Package },
    { key: 'stock', label: 'موجودی', icon: PackageSearch },
    { key: 'kardex', label: 'کاردکس', icon: History },
    { key: 'low', label: 'نیازمندِ سفارش', icon: AlertTriangle },
    { key: 'warehouses', label: 'انبارها', icon: Warehouse },
    { key: 'count', label: 'انبارگردانی', icon: ClipboardCheck },
    { key: 'adjust', label: 'تعدیل دستی', icon: ClipboardList },
    { key: 'issues', label: 'خروج انبار', icon: PackageMinus },
    { key: 'issue-returns', label: 'برگشت خروج انبار', icon: PackagePlus },
    { key: 'transfer', label: 'انتقال بین انبار', icon: ArrowLeftRight },
    { key: 'pricelists', label: 'لیست قیمت', icon: Tags },
    { key: 'batches', label: 'بچ و انقضا', icon: CalendarClock },
    { key: 'serials', label: 'جستجوی سریال', icon: ScanSearch },
    { key: 'import', label: 'ورود گروهی کالا', icon: FileUp },
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
    { key: 'contacts', label: 'طرف حساب‌ها', icon: UsersRound },
    { key: 'aging', label: 'سنین مطالبات', icon: CalendarClock },
    { key: 'import', label: 'ورود گروهی اشخاص', icon: FileUp },
  ],
  crm: [
    { key: 'leads', label: 'سرنخ‌ها', icon: Target },
    { key: 'activities', label: 'پیگیری‌ها', icon: CalendarClock },
    { key: 'loyalty', label: 'باشگاه مشتریان', icon: Gift },
    { key: 'segments', label: 'بخش‌بندی', icon: PieChart },
    { key: 'tiers', label: 'سطوح باشگاه', icon: Medal },
    { key: 'rewards', label: 'جوایز', icon: Ticket },
    { key: 'birthdays', label: 'تولدها', icon: Cake },
  ],
  manufacturing: [
    { key: 'boms', label: 'فرمول‌های ساخت', icon: FlaskConical },
    { key: 'produce', label: 'تولید', icon: Hammer },
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
