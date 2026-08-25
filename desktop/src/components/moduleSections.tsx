import {
  AlertTriangle,
  ArrowLeftRight,
  BellRing,
  BookOpen,
  BookOpenCheck,
  Cake,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarPlus,
  ClipboardCheck,
  ClipboardList,
  Coins,
  FileText,
  FileUp,
  FlaskConical,
  FolderKanban,
  Gift,
  GitCompareArrows,
  Hammer,
  HandCoins,
  Hash,
  History,
  Landmark,
  Link2,
  ListChecks,
  ListTree,
  Medal,
  Package,
  PackagePlus,
  PackageSearch,
  Percent,
  PieChart,
  Repeat,
  ScrollText,
  Settings,
  ShoppingCart,
  Store,
  Tags,
  Target,
  Ticket,
  Undo2,
  Users,
  UsersRound,
  Wallet,
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
  sales: [
    { key: 'invoices', label: 'فاکتور فروش', icon: ShoppingCart },
    { key: 'quotations', label: 'پیش‌فاکتور', icon: FileText },
    { key: 'returns', label: 'برگشت از فروش', icon: Undo2 },
    { key: 'moadian', label: 'سامانه مؤدیان', icon: Landmark },
  ],
  purchases: [
    { key: 'invoices', label: 'فاکتور خرید', icon: PackagePlus },
    { key: 'returns', label: 'برگشت از خرید', icon: Undo2 },
  ],
  inventory: [
    { key: 'products', label: 'کالاها', icon: Package },
    { key: 'stock', label: 'موجودی', icon: PackageSearch },
    { key: 'kardex', label: 'کاردکس', icon: History },
    { key: 'low', label: 'نیازمندِ سفارش', icon: AlertTriangle },
    { key: 'warehouses', label: 'انبارها', icon: Warehouse },
    { key: 'count', label: 'انبارگردانی', icon: ClipboardCheck },
    { key: 'adjust', label: 'تعدیل دستی', icon: ClipboardList },
    { key: 'transfer', label: 'انتقال بین انبار', icon: ArrowLeftRight },
    { key: 'pricelists', label: 'لیست قیمت', icon: Tags },
    { key: 'batches', label: 'بچ و انقضا', icon: CalendarClock },
  ],
  coding: [
    { key: 'chart', label: 'کدینگ حساب‌ها', icon: ListTree },
    { key: 'numbering', label: 'روش‌های شماره‌گذاری', icon: Hash },
  ],
  accounting: [
    { key: 'journal', label: 'ثبت سند', icon: BookOpen },
    { key: 'daybook', label: 'دفتر روزنامه', icon: BookOpenCheck },
    { key: 'chart', label: 'چارت حساب‌ها', icon: ListTree },
    { key: 'budget', label: 'بودجه‌بندی', icon: Target },
    { key: 'cost-centers', label: 'مراکز هزینه', icon: FolderKanban },
    { key: 'recurring', label: 'اسناد تکرارشونده', icon: Repeat },
    { key: 'currencies', label: 'ارزها و نرخ ارز', icon: Coins },
    { key: 'close', label: 'بستن دوره‌ی مالی', icon: CalendarCheck },
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
  banking: [
    { key: 'checks', label: 'چک‌ها', icon: ScrollText },
    { key: 'accounts', label: 'حساب‌های بانکی', icon: Landmark },
    { key: 'petty', label: 'تنخواه‌گردان', icon: Wallet },
    { key: 'reconciliation', label: 'تطبیق بانکی', icon: GitCompareArrows },
  ],
  contacts: [
    { key: 'contacts', label: 'طرف حساب‌ها', icon: UsersRound },
    { key: 'treasury', label: 'دریافت و پرداخت', icon: HandCoins },
    { key: 'aging', label: 'سنین مطالبات', icon: CalendarClock },
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
    { key: 'list', label: 'فهرست رویدادها', icon: ListChecks },
  ],
  onboarding: [
    { key: 'items', label: 'ورود گروهی کالا', icon: FileUp },
    { key: 'contacts', label: 'ورود گروهی اشخاص', icon: FileUp },
    { key: 'opening', label: 'مانده اول دوره', icon: Wallet },
  ],
}
