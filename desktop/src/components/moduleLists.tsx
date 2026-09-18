import {
  fetchContacts,
  fetchCrmActivities,
  fetchEmployees,
  fetchAssetDisposals,
  fetchDepreciationDocuments,
  fetchDepreciationEntries,
  fetchFixedAssets,
  DISPOSAL_TYPE_LABELS,
  type AssetDisposalRecord,
  type DepreciationDocumentRecord,
  type DepreciationEntryRecord,
  fetchInstallmentPlans,
  fetchIssueReturnLedger,
  fetchItemsLive,
  fetchLeads,
  fetchProductionPlans,
  fetchPurchaseInvoicesOfKind,
  fetchPurchaseDeductionTypes,
  fetchAllWarehouseReceipts,
  fetchPurchaseReturns,
  fetchStockAdjustments,
  fetchStockCounts,
  fetchValuationRunList,
  fetchWarehouseIssueLedger,
} from '../api'
import {
  Archive,
  BookMarked,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  Contact2,
  CreditCard,
  DatabaseBackup,
  FileCheck2,
  FilePenLine,
  FileSignature,
  FileSpreadsheet,
  FileStack,
  HandCoins,
  History,
  Hash,

  LayoutList,
  ListChecks,
  ListTree,
  MapPin,
  Receipt,
  Scale,
  Tag,
  Tags,
  Target,
  UsersRound,
  Wallet,
  type LucideIcon,
  ClipboardList,
  FileText,
  Undo2,
  Calculator,
  Ship,
  Boxes,
  Percent,
  Layers,
  AlertTriangle,
  ArrowLeftRight,
  BadgeDollarSign,
  Briefcase,
  ClipboardCheck,
  FileUp,
  FolderTree,
  Package,
  PackageCheck,
  PackageMinus,
  PackagePlus,
  PackageSearch,
  RotateCcw,
  Ruler,
  ScanSearch,
  Warehouse,
  Cake,
  Gift,
  Medal,
  PieChart,
  Ticket,
} from 'lucide-react'
import { MODULE_SECTIONS } from './moduleSections'
import type { PageKey } from './Sidebar'
import { formatJalali } from '../lib/jalali'

/**
 * «کارتِ فهرست» چه چیزی برای هر عملیات نشان بدهد.
 *
 * کارتِ فهرست کارِ *ذخیره‌شده‌ی* عملیاتِ انتخاب‌شده را نشان می‌دهد؛ پس نگاشت از جفتِ
 * (ماژول، عملیات) به یک fetcher و نحوه‌ی خلاصه‌کردنِ هر رکورد است. عمداً از همان
 * توابعِ موجودِ `api.ts` استفاده می‌کند تا هیچ منطقِ داده‌ای تکرار نشود.
 *
 * عملیاتی که این‌جا نگاشت ندارد (مثلِ تنظیمات یا فرم‌های بدونِ دفتر) کارتِ فهرست را
 * خالی نشان می‌دهد با پیامِ روشن — نه یک کارتِ گنگِ بی‌توضیح.
 */

const fa = (n: unknown) => Math.round(Number(n) || 0).toLocaleString('fa-IR')
const faNum = (n: unknown) => (n == null ? '—' : Number(n).toLocaleString('fa-IR'))
const day = (d: unknown) => (typeof d === 'string' && d ? formatJalali(d) : '—')

/** یک ردیفِ خلاصه در کارتِ فهرست. */
export interface ListRow {
  id: string
  /** خطِ اول — شناسه‌ی رکورد (شماره‌ی فاکتور، نامِ شخص، …). */
  title: string
  /** خطِ دوم — زمینه (طرف‌حساب، وضعیت، …). */
  subtitle?: string
  /** ستونِ چپ — مبلغ یا تاریخ. */
  meta?: string
}

/** یک ورودیِ منو در کارتِ «فهرست» — به‌جای ردیفِ داده، رهسپارِ صفحه‌ی همان فهرست. */
export interface ListMenuItem {
  key: PageKey
  label: string
  icon: LucideIcon
  /** تبِ مشخصی از همان صفحه. منوی گروهی که بخش‌هایش تبِ صفحه‌اند نه صفحه‌ی جدا
   *  («تامین‌کنندگان و انبار») با این به تبِ درست می‌رود. */
  section?: string
}

/**
 * منوی «عملیات»ِ گروهی که با فهرستِ صفحه‌هایش (`NAV_GROUPS`) ساخته نمی‌شود.
 *
 * **چرا:** «تامین‌کنندگان و انبار» دو صفحه‌ی تب‌دار است («خرید» و «انبار»). کاربر
 * منوی کار را بر اساسِ کار می‌خواهد نه صفحه: «رسید انبار» تبِ صفحه‌ی خرید است و
 * «حواله انبار» تبِ صفحه‌ی انبار، ولی هر دو کنارِ هم در «عملیات». `NAV_GROUPS`
 * دست نمی‌خورد، چون ماژول‌ها، مجوزها، جست‌وجو و «شخصی‌سازیِ پنل» با صفحه کار
 * می‌کنند؛ این نگاشت فقط ستونِ «عملیات» و کشوی موبایل را می‌سازد.
 */
export const OPS_MENUS: Record<string, ListMenuItem[]> = {
  //: ترتیب: شش کارِ اصلیِ انبار که کاربر خواست، بعد کارهای منوهای قدیمیِ «خرید»،
  //: «انبار» و «اعلامیه بدهکار بستانکار». تعریف‌ها (کالا، انبار، واحد، …) فرم و
  //: جدولشان یک کار است و در همین ستون می‌مانند.
  'تامین‌کنندگان و انبار': [
    { key: 'purchases', section: 'receipts', label: 'رسید انبار', icon: PackageCheck },
    { key: 'inventory', section: 'issues', label: 'حواله انبار', icon: PackageMinus },
    { key: 'inventory', section: 'transfer', label: 'رسید/حواله انتقال بین انبارها', icon: ArrowLeftRight },
    { key: 'inventory', section: 'count-tags', label: 'تگ انبارگردانی', icon: Tag },
    { key: 'inventory', section: 'count', label: 'ثبت مغایرت انبارگردانی', icon: ClipboardCheck },
    { key: 'inventory', section: 'valuation', label: 'قیمت‌گذاری اسناد انبار', icon: Calculator },
    { key: 'purchases', section: 'invoices', label: 'فاکتور خرید', icon: PackagePlus },
    { key: 'purchases', section: 'services', label: 'فاکتور خرید خدمات', icon: Briefcase },
    { key: 'purchases', section: 'returns', label: 'برگشت از خرید', icon: Undo2 },
    { key: 'inventory', section: 'issue-returns', label: 'برگشت خروج انبار', icon: RotateCcw },
    { key: 'inventory', section: 'adjust', label: 'تعدیل دستی', icon: ClipboardList },
    { key: 'inventory', section: 'unpriced', label: 'قیمت‌گذاری ورودی‌ها', icon: BadgeDollarSign },
    { key: 'creditnote', label: 'اعلامیه بدهکار بستانکار', icon: FileSpreadsheet },
    { key: 'inventory', section: 'products', label: 'کالاها', icon: Package },
    { key: 'inventory', section: 'warehouses', label: 'انبارها', icon: Warehouse },
    { key: 'inventory', section: 'units', label: 'واحدها', icon: Ruler },
    { key: 'inventory', section: 'taxonomy', label: 'گروه و مشخصات', icon: FolderTree },
    { key: 'inventory', section: 'pricelists', label: 'لیست قیمت', icon: Tags },
    { key: 'purchases', section: 'deductions', label: 'انواع کسورات', icon: Percent },
    { key: 'inventory', section: 'import', label: 'ورود گروهی کالا', icon: FileUp },
  ],
}

/** آیا این ورودیِ منو همان جایی است که کاربر ایستاده؟ ورودیِ بی‌تب با خودِ صفحه
 *  فعال است؛ ورودیِ تب‌دار فقط وقتی همان تب باز است. */
export function menuEntryActive(e: ListMenuItem, page: PageKey, section: string | null): boolean {
  return e.key === page && (e.section === undefined || e.section === section)
}

/**
 * ماژول‌هایی که کارتِ «فهرست»شان به‌جای ردیف‌های داده، **منو** نشان می‌دهد.
 *
 * تنظیمات چند فهرستِ کاملاً بی‌ربط دارد (نسخه‌های پشتیبان، کاربران، سال‌های مالی) که
 * هیچ‌کدام به «عملیاتِ انتخاب‌شده» گره نمی‌خورند. نشان‌دادنِ ردیف‌های یکی از آن‌ها
 * بسته به اینکه کاربر روی کدام زیرمنو ایستاده، بیشتر گیج‌کننده بود تا مفید. پس این‌جا
 * کارت خودش یک منوی سه‌تایی می‌شود و هر کدام صفحه‌ی همان فهرست را باز می‌کند.
 *
 * کلید، **نامِ گروهِ ناوبری** است نه صفحه — چون این تصمیم به کلِ ماژول تعلق دارد.
 */
export const LIST_MENUS: Record<string, ListMenuItem[]> = {
  //: «فروش» — دفترِ نظیرِ هر عملیاتِ رکوردساز. «تخفیف‌ها و عوامل» عمداً یک دفترِ
  //: مشترک است، چون دو منوی عملیات در یک جدول می‌نویسند (استثنای دومِ قاعده‌ی نظیر).
  //: کلید باید **دقیقاً** `heading`ِ گروهِ ناوبری باشد، نه نامِ ماژول: هم
  //: `ModulePanels` و هم کشوی موبایل با `group.heading` این نگاشت را می‌خوانند.
  //: تا امروز این‌جا «فروش» بود در حالی که heading «مشتریان و فروش» است، پس هر
  //: دوازده صفحه‌ی فهرستِ فروش — از فاکتورهای فروش تا اعلامیه‌های قیمت — از
  //: هیچ عرضی قابلِ باز کردن نبودند. نه تایپ‌اسکریپت می‌دیدش (کلید `string` است)
  //: و نه ممیزِ ایستا، چون ثبتشان در `OPS_LIST_MAP` درست بود.
  //: «تامین‌کنندگان و انبار» — شش دفتری که کاربر خواست، بعد دفترهای منوهای قدیمی.
  //: بیشترشان تبِ صفحه‌ی «انبار»/«خرید»اند (`section`)؛ «فهرست تامین‌کنندگان» همان
  //: صفحه‌ی طرف‌حساب‌هاست با نقشِ تأمین‌کننده.
  'تامین‌کنندگان و انبار': [
    { key: 'inventory', section: 'documents', label: 'فهرست رسیدها و حواله‌های انبار', icon: FileStack },
    { key: 'inventory', section: 'kardex', label: 'کاردکس کالا', icon: History },
    { key: 'inventory', section: 'stock', label: 'مرور انبار / موجودی کالا', icon: PackageSearch },
    { key: 'supplierlist', label: 'فهرست تامین‌کنندگان', icon: UsersRound },
    { key: 'inventory', section: 'low', label: 'گزارش نقطه سفارش', icon: AlertTriangle },
    { key: 'inventory', section: 'count-list', label: 'فهرست انبارگردانی‌ها', icon: ListChecks },
    { key: 'purchases', section: 'invoice-list', label: 'فاکتورهای خرید', icon: ClipboardList },
    { key: 'purchases', section: 'service-list', label: 'فاکتورهای خرید خدمات', icon: FileText },
    { key: 'inventory', section: 'issue-return-list', label: 'برگشت‌های خروج انبار', icon: RotateCcw },
    { key: 'notelist', label: 'اعلامیه‌های بدهکار و بستانکار', icon: FileSpreadsheet },
    { key: 'inventory', section: 'serials', label: 'جستجوی سریال', icon: ScanSearch },
    { key: 'inventory', section: 'batches', label: 'بچ و انقضا', icon: CalendarClock },
  ],
  //: هشت ردیفِ اول تبِ صفحه‌اند نه صفحه‌ی جدا. بدونِ این‌ها، تبی که `kind: 'list'`
  //: می‌گیرد از کارتِ «عملیات» بیرون می‌رود و در «فهرست» هم نمی‌آید — چون این گروه
  //: `LIST_MENUS` دارد و منوی گروه بر `sectionLists` مقدم است. سه تبِ «طرف حساب‌ها»،
  //: «سنین مطالبات» و «بخش‌بندی» دقیقاً به همین شکل بالای ۱۰۲۴px بی‌راه شدند.
  'مشتریان و فروش': [
    { key: 'contacts', section: 'contacts', label: 'طرف حساب‌ها', icon: UsersRound },
    { key: 'contacts', section: 'aging', label: 'سنین مطالبات', icon: CalendarClock },
    { key: 'crm', section: 'leads', label: 'سرنخ‌ها', icon: Target },
    { key: 'crm', section: 'activities', label: 'پیگیری‌ها', icon: CalendarClock },
    { key: 'crm', section: 'segments', label: 'بخش‌بندی', icon: PieChart },
    { key: 'crm', section: 'tiers', label: 'سطوح باشگاه', icon: Medal },
    { key: 'crm', section: 'rewards', label: 'جوایز', icon: Ticket },
    { key: 'crm', section: 'birthdays', label: 'تولدها', icon: Cake },
    { key: 'saleslist', label: 'فاکتورهای فروش', icon: ClipboardList },
    { key: 'quotationlist', label: 'پیش‌فاکتورها', icon: FileText },
    { key: 'returnlist', label: 'فاکتورهای برگشتی', icon: Undo2 },
    { key: 'notelist', label: 'اعلامیه‌های بدهکار و بستانکار', icon: FileSpreadsheet },
    { key: 'commissionrulelist', label: 'قواعد پورسانت', icon: Wallet },
    { key: 'commissionrunlist', label: 'محاسبه‌های پورسانت', icon: Calculator },
    { key: 'customslist', label: 'اظهارنامه‌های گمرکی', icon: Ship },
    { key: 'saletypelist', label: 'انواع فروش', icon: Tags },
    { key: 'priceannouncelist', label: 'اعلامیه‌های قیمت', icon: FileSpreadsheet },
    { key: 'bundlelist', label: 'بسته‌های محصول', icon: Boxes },
    { key: 'pricingfactorlist', label: 'تخفیف‌ها و عوامل افزاینده', icon: Percent },
    { key: 'discountgrouplist', label: 'گروه‌های کالای تخفیف', icon: Layers },
  ],
  'تنظیمات': [
    { key: 'distributor', section: 'orders', label: 'سفارش‌های پخش', icon: ClipboardList },
    { key: 'distributor', section: 'returns', label: 'مرجوعی‌های پخش', icon: Undo2 },
    { key: 'distributor', section: 'commission', label: 'کمیسیون پخش', icon: Percent },
    { key: 'marketplace', section: 'orders', label: 'سفارش‌های من', icon: ClipboardList },
    { key: 'marketplace', section: 'returns', label: 'مرجوعی‌های من', icon: Undo2 },
    { key: 'backuplist', label: 'نسخه‌های پشتیبانی و بازیابی', icon: DatabaseBackup },
    { key: 'userlist', label: 'کاربران', icon: UsersRound },
    { key: 'fiscalyearlist', label: 'سال‌های مالی', icon: CalendarRange },
    { key: 'numberinglist', label: 'روش‌های شماره‌گذاری', icon: Hash },
  ],
  //: «حسابداری» — داده‌ی ذخیره‌شده‌ی ماژول: اسناد، حساب‌ها، و سه پنلی که پیش‌تر
  //: تبِ درونِ صفحه بودند (تکرارشونده، بودجه، ارز) و حالا صفحه‌ی مستقل دارند.
  'حسابداری': [
    { key: 'entrylist', label: 'اسناد حسابداری', icon: FileStack },
    { key: 'accountlist', label: 'فهرست حساب‌ها', icon: ListTree },
    { key: 'periodcloselist', label: 'دوره‌های بسته‌شده', icon: Archive },
    { key: 'analyticlist', label: 'تفصیلی‌های سایر', icon: Tag },
  ],
  //: «دریافت و پرداخت» — دفترِ رسیدها و اعلامیه‌ها. پیش‌تر تبِ ماژولِ «اشخاص» بود؛
  //: داده‌ی این ماژول در ماژولِ دیگری زندگی می‌کرد.
  'دریافت و پرداخت': [
    { key: 'treasuryledger', label: 'دریافت‌ها و پرداخت‌ها', icon: HandCoins },
    { key: 'paymentnoticelist', label: 'اعلامیه‌های پرداخت', icon: HandCoins },
    { key: 'checkbooklist', label: 'دسته‌چک‌ها', icon: BookMarked },
    { key: 'posterminallist', label: 'دستگاه‌های کارتخوان', icon: CreditCard },
    { key: 'possettlelist', label: 'تسویه‌های کارتخوان', icon: CreditCard },
    //: «چه عملیاتی کِی روی چه چکی» — نمای دومِ دامنه‌ی چک، در برابرِ
    //: «جستجوی چک» که می‌گوید الان چه داریم و وضعیتشان چیست.
    { key: 'checkoplist', label: 'عملیات چک', icon: History },
    //: تسویه‌ی طرف مقابل رابطه است نه گردشِ پول، پس دفترِ خودش را دارد و در
    //: «دریافت‌ها و پرداخت‌ها» قاطیِ رسیدها نمی‌شود.
    { key: 'contactsettlelist', label: 'تسویه‌های طرف مقابل', icon: Scale },
    { key: 'statementlist', label: 'ردیف‌های صورت‌حساب بانکی', icon: FileSpreadsheet },
    { key: 'pettylist', label: 'گردش تنخواه', icon: Wallet },
  ],
  //: «سامانه مؤدیان» — فهرستِ خودکارِ قبلی (چند ردیفِ آخرِ ارسال‌ها) جایش را به منو
  //: داد: تاریخچه‌ی ارسال یک دفترِ قانونی است و فیلتر و جست‌وجو و خروجی می‌خواهد،
  //: نه یک پیش‌نمایشِ چندردیفی.
  //: «حقوق و دستمزد» — دفترِ نظیرِ «قرارداد جدید». بقیه‌ی منوهای این ماژول
  //: خودشان فهرستِ خودشان را دارند (نگاهی به OPS_LIST_MAP).
  'حقوق و دستمزد': [
    { key: 'payroll', section: 'staff', label: 'پرسنل و احکام', icon: UsersRound },
    { key: 'payroll', section: 'benefits', label: 'مزایا', icon: Gift },
    { key: 'contractlist', label: 'قراردادها', icon: FileSignature },
    { key: 'payslipledger', label: 'مرور حقوق', icon: Receipt },
  ],
  'سامانه مؤدیان': [
    { key: 'moadianhistory', label: 'تاریخچه ارسال‌ها', icon: FileCheck2 },
  ],
  //: «پیمانکاری» — هر چهار فهرست، هر پنج فازِ ماژول تمام شد (PROJECT_OVERVIEW §۱۰).
  'پیمانکاری': [
    { key: 'contractinglist', label: 'پیمان‌ها', icon: FileSignature },
    { key: 'contractingamendmentlist', label: 'متمم‌های پیمان', icon: FilePenLine },
    { key: 'contractingstatementlist', label: 'صورت وضعیت‌های دریافتی', icon: Receipt },
    { key: 'contractingsettlementlist', label: 'تسویه‌حساب‌های پیمان', icon: HandCoins },
  ],
  //: «شرکت» — سه دسته پشتِ‌هم: تبادل و ساختِ گزارش، گزارش‌های آماده، و فهرستِ
  //: داده‌های پایه. ترتیب همان است که کاربر تعیین کرد.
  'شرکت': [
    { key: 'dynamicreports', label: 'گزارش‌های پویا', icon: LayoutList },
    { key: 'contactlist', label: 'طرف حساب‌ها', icon: UsersRound },
    { key: 'ownertxnlist', label: 'تراکنش‌های شریک', icon: HandCoins },
    { key: 'relatedpeople', label: 'افراد مرتبط', icon: Contact2 },
    { key: 'installmentplans', label: 'قراردادهای اقساطی', icon: CalendarClock },
    { key: 'allinstallments', label: 'همه اقساط', icon: ListChecks },
    { key: 'costcenterlist', label: 'مراکز هزینه', icon: Target },
    { key: 'geolist', label: 'محل‌های جغرافیایی', icon: MapPin },
    { key: 'contactgrouplist', label: 'گروه‌های طرف حساب', icon: Tags },
    { key: 'calendarlist', label: 'رویدادهای تقویم', icon: CalendarDays },
  ],
}

/**
 * صفحه‌های فهرست در هیچ گروهی از منو نیستند (وگرنه در کارتِ «عملیات» هم تکرار
 * می‌شدند)، ولی وقتی بازند باید همان دو کارتِ ماژولِ خودشان را کنارشان داشته باشند —
 * وگرنه کاربر بدونِ راهِ برگشت می‌ماند. این نگاشت همان پیوند را می‌سازد.
 */
export const LIST_PAGE_GROUP: Partial<Record<PageKey, string>> = {
  saleslist: 'مشتریان و فروش',
  quotationlist: 'مشتریان و فروش',
  returnlist: 'مشتریان و فروش',
  notelist: 'مشتریان و فروش',
  commissionrulelist: 'مشتریان و فروش',
  commissionrunlist: 'مشتریان و فروش',
  customslist: 'مشتریان و فروش',
  saletypelist: 'مشتریان و فروش',
  priceannouncelist: 'مشتریان و فروش',
  bundlelist: 'مشتریان و فروش',
  pricingfactorlist: 'مشتریان و فروش',
  discountgrouplist: 'مشتریان و فروش',
  treasuryledger: 'دریافت و پرداخت',
  paymentnoticelist: 'دریافت و پرداخت',
  checkbooklist: 'دریافت و پرداخت',
  posterminallist: 'دریافت و پرداخت',
  possettlelist: 'دریافت و پرداخت',
  checkoplist: 'دریافت و پرداخت',
  contactsettlelist: 'دریافت و پرداخت',
  statementlist: 'دریافت و پرداخت',
  pettylist: 'دریافت و پرداخت',
  analyticlist: 'حسابداری',
  geolist: 'شرکت',
  ownertxnlist: 'شرکت',
  contactgrouplist: 'شرکت',
  calendarlist: 'شرکت',
  numberinglist: 'تنظیمات',
  contractlist: 'حقوق و دستمزد',
  payslipledger: 'حقوق و دستمزد',
  moadianhistory: 'سامانه مؤدیان',
  contractinglist: 'پیمانکاری',
  contractingamendmentlist: 'پیمانکاری',
  contractingstatementlist: 'پیمانکاری',
  contractingsettlementlist: 'پیمانکاری',
  entrylist: 'حسابداری',
  accountlist: 'حسابداری',
  recurringlist: 'حسابداری',
  budgetlist: 'حسابداری',
  currencylist: 'حسابداری',
  periodcloselist: 'حسابداری',
  backuplist: 'تنظیمات',
  userlist: 'تنظیمات',
  fiscalyearlist: 'تنظیمات',
  dataexport: 'شرکت',
  dataimport: 'شرکت',
  reportbuilder: 'شرکت',
  dynamicreports: 'شرکت',
  dayactivity: 'شرکت',
  mgmtreports: 'شرکت',
  usagereport: 'شرکت',
  contactlist: 'شرکت',
  //: همان صفحه‌ی طرف‌حساب‌ها با نقشِ تأمین‌کننده — فهرستِ گروهِ انبار، نه نمای دوم.
  supplierlist: 'تامین‌کنندگان و انبار',
  relatedpeople: 'شرکت',
  installmentplans: 'شرکت',
  allinstallments: 'شرکت',
  costcenterlist: 'شرکت',
}

/**
 * قاعده‌ی نظیر: **هر منوی عملیاتی که رکوردِ تازه ثبت می‌کند، فهرستِ نظیرِ خودش را دارد.**
 *
 * الگوی مرجع: «فروش اقساطی» (عملیات: فرم + جدولِ کاری) ↔ «قراردادهای اقساطی»
 * (فهرست: دفترِ خواندنی با جمع‌ها و فیلتر). صفحه‌ی عملیات برای *ثبت* است و صفحه‌ی
 * فهرست برای *مرور*؛ این دو تکراری نیستند و کاربر می‌داند کدام را کِی باز کند.
 *
 * **چرا این نگاشت وجود دارد:** بدونِ آن، منوی عملیاتِ تازه بی‌سروصدا بدونِ فهرست
 * می‌ماند و کسی متوجه نمی‌شود تا وقتی کاربر بپرسد «ثبت‌شده‌ها کجا رفتند؟». ممیزِ
 * صفحه‌ها (قاعده‌ی R11) هر منویی را که این‌جا ردیف ندارد خطا می‌دهد، پس تصمیم
 * درباره‌ی فهرست *اجباری* است، نه فراموش‌شدنی.
 *
 * مقدارِ هر ردیف یا کلیدِ صفحه‌ی فهرست است، یا یکی از سه دلیلِ استثنا:
 *
 *  * `'state'` — رکورد نمی‌سازد، وضعیتِ رکوردِ موجود را عوض می‌کند (وصول چک،
 *    تبدیل سندِ موقت به دائم). دفترش از قبل هست.
 *  * `'view'`  — خودش فهرست یا گزارش است (جستجوی چک، گزارش ترازها).
 *  * `'none'`  — چیزی ثبت نمی‌کند (راهنمای مسیر، تنظیمات، تغییر رمز).
 */
export type OpsListTarget = PageKey | readonly PageKey[] | 'state' | 'view' | 'none'

export const OPS_LIST_MAP: Record<string, OpsListTarget> = {
  ownertxn: 'ownertxnlist', //: ثبت ↔ دفتر — الگوی «فروش اقساطی»
  // ── دریافت و پرداخت ──
  payflow: 'none', //: راهنمای مسیر
  receiptvoucher: 'treasuryledger', //: سه عملیات، یک دفترِ مشترک با فیلتر
  paymentvoucher: 'paymentnoticelist',
  contactsettle: 'contactsettlelist',
  //: دفترِ چک‌ها همان «جستجوی چک» است — کاربر صریحاً آن را در کارتِ عملیات خواست،
  //: و فهرستِ دومِ چک یعنی دو نمای یک داده.
  checkops: 'checksearch',
  checkbooks: 'checkbooklist',
  checkreturn: 'checkoplist',
  checkpayclear: 'checkoplist',
  bankreconcile: 'state',
  checksearch: 'view',
  bankledger: 'view',
  cashbox: 'view',
  possettle: 'possettlelist',
  bankstatement: 'statementlist',
  //: «تعریف صندوق» خودش هم فرم است و هم دفترِ صندوق‌ها با مانده‌شان — همان
  //: الگوی «حساب بانکی». فهرستِ نظیرِ جدا یعنی دو نمای یک داده.
  cashboxes: 'view',
  //: «حساب بانکی» خودش هم فرم است و هم دفترِ حساب‌ها با مانده‌شان — همان
  //: الگوی «تعریف صندوق». فهرستِ نظیرِ جدا یعنی دو نمای یک داده.
  bankaccounts: 'view',
  posterminals: 'posterminallist',
  pettyholder: 'pettylist', //: شارژ و هزینه، یک دفترِ مشترک
  pettyexpense: 'pettylist',

  // ── حسابداری ──
  acctchart: 'accountlist',
  newaccount: 'accountlist',
  openingbalance: 'entrylist', //: خروجی‌اش یک سندِ حسابداری است
  journalentry: 'entrylist',
  mergeentries: 'entrylist',
  fxrevaluation: 'entrylist',
  //: سندش در فهرستِ اسناد با منشأ «اصلاح طبقه‌بندی مانده» دیده می‌شود.
  balancereclass: 'entrylist',
  closingopening: 'entrylist',
  closepnl: 'periodcloselist',
  analytics: 'analyticlist',
  entrycartable: 'state',
  finalizeentries: 'state',
  renumber: 'state',
  reclassify: 'state',
  generaldoc: 'view',
  vat: 'view',
  ebooks: 'view',
  accountbrowse: 'view',
  balancereport: 'view',
  ledgerreport: 'view',
  integrity: 'view',
  reports: 'view',

  // ── شرکت ──
  //: «افراد مرتبط» دفترِ دومِ همین عملیات است؛ صاحبِ دیگری ندارد.
  contactnew: ['contactlist', 'relatedpeople'],
  //: الگوی مرجعِ این قاعده. «همه اقساط» نمای ردیف‌به‌ردیفِ همان قراردادهاست.
  installments: ['installmentplans', 'allinstallments'],
  costcenter: 'costcenterlist',
  geo: 'geolist',
  contactgroup: 'contactgrouplist',
  calendar: 'calendarlist',
  yearendreminder: 'calendarlist', //: یادآوری‌اش روی همان تقویم می‌نشیند
  openingops: 'none', //: راهنمای مسیر
  yearendops: 'none',

  //: نُه گزینه‌ای که با دامنه‌دارشدنِ کارتِ فهرست به «عملیات» آمدند.
  dataexport: 'none',
  dataimport: 'none',
  reportbuilder: 'dynamicreports', //: دفترِ همان چیزی که می‌سازد
  dayactivity: 'view',
  mgmtreports: 'view',
  usagereport: 'view',
  //: فرم و دفترشان یک صفحه است — استثنای «عملیاتی که خودش فهرست است».
  recurringlist: 'view',
  budgetlist: 'view',
  currencylist: 'view',

  // ── تنظیمات ──
  fiscalyear: 'fiscalyearlist',
  //: قالبِ صنفی حساب می‌سازد، و دفترِ حساب‌ها همان «فهرست حساب‌ها» است — فهرستِ
  //: دوم یعنی دو نمای یک داده.
  coding: 'accountlist',
  personalization: 'accountlist',
  numbering: 'numberinglist',
  team: 'userlist',
  backup: 'backuplist',
  contactimport: 'contactlist', //: اشخاصِ واردشده همان طرف‌حساب‌ها هستند
  password: 'none',
  theme: 'none',
  help: 'none',

  // ── سامانه مؤدیان ──
  //: بخش‌های تب‌دارِ این ماژول با کلیدِ خودشان در MODULE_SECTIONS می‌آیند، نه این‌جا؛
  //: تنها صفحه‌ی مستقلش همان فهرستِ تاریخچه است.
  moadian: 'moadianhistory',

  // ── فروش ──
  //: ماژولِ فروش دیگر تب‌دار نیست؛ هجده منوی عملیات دارد و هرکدام دفترِ نظیرش را.
  salesflow: 'none', //: راهنمای مسیر
  salesinvoice: 'saleslist',
  quotations: 'quotationlist',
  salesreturn: 'returnlist',
  invoiceclose: 'state', //: فاکتور را قفل می‌کند، رکوردِ تازه نمی‌سازد
  creditnote: 'notelist',
  contactstatement: 'view', //: خودش گزارش است
  commission: 'commissionrulelist',
  commissioncalc: 'commissionrunlist',
  customs: 'customslist',
  saletype: 'saletypelist',
  //: مِسترِ کوچکی که دفترش خودِ همان صفحه است — فرمِ ساخت و جدولِ علت‌ها کنارِ
  //: هم. صفحه‌ی فهرستِ جدا فقط همان جدول را دوباره نشان می‌داد.
  returnreason: 'view',
  priceannounce: 'priceannouncelist',
  bundle: 'bundlelist',
  discount: 'pricingfactorlist', //: تخفیف و افزاینده یک جدول‌اند → دفترِ مشترک
  markup: 'pricingfactorlist',
  discountgroup: 'discountgrouplist',
  salesbrowse: 'view',
  contactoverview: 'view',

  // ── ماژول‌های تب‌دار ──
  //: هر تب دفترِ خودش را داخلِ خودش دارد، پس قاعده همان‌جا برآورده است.
  pos: 'view',
  contacts: 'contactlist',
  crm: 'view',
  purchases: 'view',
  inventory: 'view',
  manufacturing: 'view',
  banking: 'view',
  fixedassets: 'view',
  payroll: 'view',
  //: ── حقوق و دستمزد ──
  contractnew: 'contractlist',
  //: این چهار صفحه خودشان دفترِ خودشان‌اند: فرمِ ساختِ کوتاه بالا، فهرستِ کاملِ
  //: همان رکوردها زیرش. فهرستِ جدا یعنی دو نمای یک داده — استثنای سومِ قاعده‌ی نظیر.
  servicelocation: 'view',
  jobtitle: 'view',
  payrollfactors: 'view',
  payrolltaxgroups: 'view',
  taxtables: 'view',
  loantype: 'view',
  employeeloans: 'view',
  settlement: 'view',
  deploymentinfo: 'view',
  integration: 'none',
  //: پیمانکاری — الگوی «فروش»: هر عملیات فهرستِ نظیرِ خودش. هر پنج فاز تمام شد.
  contractingnew: 'contractinglist',
  contractingamendment: 'contractingamendmentlist',
  contractingstatement: 'contractingstatementlist',
  contractingsettlement: 'contractingsettlementlist',
  contractingstatus: 'state',
  distributor: 'view',
  marketplace: 'view',
  overview: 'view',
  modules: 'none',
  profile: 'none',
  billing: 'view',
  accounts: 'view',
  mpcommission: 'view',
}

export interface ListDef {
  /** برچسبِ کارت وقتی این عملیات فعال است. */
  label: string
  fetch: (token: string) => Promise<unknown[]>
  row: (r: never) => ListRow
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const def = (label: string, fetch: (t: string) => Promise<any[]>, row: (r: any) => ListRow): ListDef =>
  ({ label, fetch, row }) as ListDef

export const MODULE_LISTS: Partial<Record<PageKey, Record<string, ListDef>>> = {
  //: «فروش» اینجا نیست: دیگر ماژولِ تب‌دار نیست و دفترهایش صفحه‌ی مستقل دارند
  //: (LIST_MENUS['فروش']). گذاشتنش اینجا یعنی نمای دومِ همان داده.
  purchases: {
    invoices: def('فاکتورهای خرید', (t) => fetchPurchaseInvoicesOfKind(t, 'goods'), (r) => ({
      id: r.id,
      title: `فاکتور ${faNum(r.number)}`,
      subtitle: day(r.invoice_date),
      meta: fa(r.total_amount),
    })),
    services: def('فاکتورهای خرید خدمات', (t) => fetchPurchaseInvoicesOfKind(t, 'service'), (r) => ({
      id: r.id,
      title: `خدمات ${faNum(r.number)}`,
      subtitle: day(r.invoice_date),
      meta: fa(r.payable_amount),
    })),
    deductions: def('انواع کسورات', (t) => fetchPurchaseDeductionTypes(t), (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.nature_label,
      meta: `${faNum(r.rate)}٪`,
    })),
    receipts: def('رسیدهای انبار', (t) => fetchAllWarehouseReceipts(t), (r) => ({
      id: r.id,
      title: `رسید ${faNum(r.number)}`,
      subtitle: day(r.receipt_date),
      meta: fa(r.net_amount),
    })),
    returns: def('برگشت از خرید', fetchPurchaseReturns, (r) => ({
      id: r.id,
      title: `برگشتی ${faNum(r.number)}`,
      subtitle: day(r.return_date),
      meta: fa(r.total_amount),
    })),
  },
  inventory: {
    products: def('کالاها', fetchItemsLive, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.sku,
      meta: fa(r.sales_price),
    })),
    adjust: def('تعدیل‌های ثبت‌شده', fetchStockAdjustments, (r) => ({
      id: r.id,
      title: r.reason || 'تعدیل موجودی',
      subtitle: day(r.adjustment_date),
      meta: faNum(r.qty_diff),
    })),
    issues: def('خروج‌های انبار', (t) => fetchWarehouseIssueLedger(t), (r) => ({
      id: r.id,
      title: `${r.type_label} ${faNum(r.number)}`,
      subtitle: day(r.doc_date),
      meta: r.kind === 'transfer' ? `به ${r.destination_warehouse_name}` : r.receiver_name || `${faNum(r.line_count)} قلم`,
    })),
    'issue-returns': def('برگشت‌های خروج انبار', (t) => fetchIssueReturnLedger(t), (r) => ({
      id: r.id,
      title: `برگشت ${r.type_label} ${faNum(r.number)}`,
      subtitle: day(r.return_date),
      meta: r.deliverer_name || `${faNum(r.line_count)} قلم`,
    })),
    //: همان دفترِ خروج‌ها با نوعِ انتقال — نه فراخوانیِ جداگانه‌ی حواله‌ها.
    transfer: def('انتقال‌های بین انبار', (t) => fetchWarehouseIssueLedger(t, { issue_type: 'transfer' }), (r) => ({
      id: r.id,
      title: `انتقال ${faNum(r.number)}`,
      subtitle: r.description || day(r.doc_date),
      meta: `${faNum(r.line_count)} قلم`,
    })),
    count: def('انبارگردانی‌ها', fetchStockCounts, (r) => ({
      id: r.id,
      title: `انبارگردانی ${faNum(r.number ?? '')}`.trim(),
      subtitle: r.status ?? '—',
      meta: day(r.count_date ?? r.created_at),
    })),
    valuation: def('اجراهای قیمت‌گذاری', fetchValuationRunList, (r) => ({
      id: r.id,
      title: `قیمت‌گذاری ${faNum(r.number)}`,
      subtitle: r.voided_at ? 'باطل' : day(r.date_to),
      meta: fa(r.total_delta),
    })),
  },
  contacts: {
    contacts: def('طرف‌حساب‌ها', fetchContacts, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.phone || '—',
      //: از پرچم‌ها ساخته می‌شود نه از رشته‌ی مشتق: با `type === 'none'` شاخه‌ی
      //: آخر «هر دو» می‌گفت — دقیقاً وارونه‌ی حقیقت.
      meta: [
        r.is_customer && 'مشتری', r.is_supplier && 'تأمین‌کننده',
        r.is_broker && 'واسطه', r.is_shareholder && 'سهامدار',
      ].filter(Boolean).join('، ') || 'بی‌نقش',
    })),
  },
  crm: {
    leads: def('سرنخ‌ها', fetchLeads, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.company || r.phone || '—',
      meta: fa(r.estimated_value),
    })),
    activities: def('پیگیری‌ها', fetchCrmActivities, (r) => ({
      id: r.id,
      title: r.subject || 'پیگیری',
      subtitle: r.done ? 'انجام‌شده' : 'در انتظار',
      meta: day(r.activity_date),
    })),
  },
  manufacturing: {
    orders: def('سفارش‌های تولید', fetchProductionPlans, (r) => ({
      id: r.id,
      title: `سفارش ${faNum(r.number)}`,
      subtitle: day(r.planned_date),
      meta: faNum(r.qty_planned),
    })),
    materials: def('حواله‌های موادِ تولید', (t) => fetchWarehouseIssueLedger(t, { issue_type: 'production' }), (r) => ({
      id: r.id,
      title: `حواله ${faNum(r.number ?? 0)}`,
      subtitle: day(r.doc_date),
      meta: faNum(r.total_qty),
    })),
    receipts: def('رسیدهای محصولِ تولید', (t) => fetchAllWarehouseReceipts(t, { receipt_type: 'production' }), (r) => ({
      id: r.id,
      title: `رسید ${faNum(r.number)}`,
      subtitle: day(r.receipt_date),
      meta: faNum(r.lines?.[0]?.qty ?? 0),
    })),
  },
  installments: {
    // این ماژول تب ندارد؛ کلیدِ پیش‌فرض همان نامِ ماژول است.
    __default: def('قراردادهای اقساطی', fetchInstallmentPlans, (r) => ({
      id: r.id,
      title: r.title || `قرارداد ${faNum(r.number)}`,
      subtitle: r.contact_name || '—',
      meta: fa(r.total_amount),
    })),
  },
  fixedassets: {
    //: `purchase_date`/`purchase_cost` هیچ‌وقت روی `FixedAssetRecord` نبودند — نامِ
    //: واقعیِ فیلدها `acquired_date`/`cost` است، پس این کارت تا امروز تاریخ و مبلغِ
    //: خالی نشان می‌داد.
    __default: def('دارایی‌های ثابت', fetchFixedAssets, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: day(r.acquired_date),
      meta: fa(r.cost),
    })),
    disposals: def('خروج و فروش دارایی', (t: string) => fetchAssetDisposals(t), (r: AssetDisposalRecord) => ({
      id: r.id,
      title: r.asset_name,
      subtitle: `${DISPOSAL_TYPE_LABELS[r.disposal_type]} · ${day(r.disposal_date)}`,
      meta: Number(r.gain_loss) === 0 ? '—' : `${Number(r.gain_loss) > 0 ? 'سود' : 'زیان'} ${fa(Math.abs(Number(r.gain_loss)))}`,
    })),
    'depreciation-list': def('محاسبات استهلاک', (t: string) => fetchDepreciationEntries(t), (r: DepreciationEntryRecord) => ({
      id: r.id,
      title: r.asset_name,
      subtitle: day(r.period_date),
      meta: fa(r.amount),
    })),
    'depreciation-docs': def('اسناد استهلاک', (t: string) => fetchDepreciationDocuments(t), (r: DepreciationDocumentRecord) => ({
      id: `${r.journal_entry_id ?? 'x'}-${r.period_date}`,
      title: r.journal_entry_number != null ? `سند ${faNum(r.journal_entry_number)}` : 'بدونِ سند',
      subtitle: `${day(r.period_date)} · ${faNum(r.asset_count)} دارایی`,
      meta: fa(r.total_amount),
    })),
  },
  payroll: {
    staff: def('پرسنل', fetchEmployees, (r) => ({
      id: r.id,
      title: `${r.first_name} ${r.last_name}`.trim(),
      subtitle: r.phone || r.national_id || '—',
      meta: r.is_active === false ? 'غیرفعال' : 'فعال',
    })),
  },
}

/** تعریفِ فهرستِ عملیاتِ فعال — با fallback به `__default` برای ماژول‌های بدونِ تب. */
export function listDefFor(page: PageKey, section: string | null): ListDef | null {
  const mod = MODULE_LISTS[page]
  if (!mod) return null
  return mod[section ?? '__default'] ?? mod.__default ?? null
}

// ── دامنه‌ی کارتِ «فهرست» ──────────────────────────────────────────────────

/**
 * کارتِ «فهرست» زیرمجموعه‌ی همان گزینه‌ای است که در «عملیات» فعال است — نه
 * منوی کلِ گروه.
 *
 * **چرا این عوض شد:** تا امروز کارت به *گروه* گره خورده بود
 * (`LIST_MENUS[group.heading]`)، پس در «مشتریان و فروش» هر بیست ردیف دیده
 * می‌شد چه روی «اشخاص» ایستاده باشی چه روی «فاکتور فروش». کاربر همین را
 * رد کرد: «فهرستِ مربوط به اون فقط باید بیاد، نه یک فهرستِ فله‌ای».
 *
 * ترتیبِ حل، از ریز به درشت:
 *
 *  1. `SECTION_LIST_MAP` — ریزکردنِ دستی برای تبی که دفترِ مشخصی دارد
 *     («حواله انبار» ← «فهرست رسیدها و حواله‌ها»، نه هر هشت دفترِ انبار).
 *  2. تب‌های `kind: 'list'`ِ **همان صفحه** — پیش‌فرضِ ماژول‌های تب‌دار.
 *  3. `OPS_LIST_MAP[page]` — برای صفحه‌ای که تبِ فهرستی ندارد.
 *
 * هیچ‌کدام جواب ندهد، کارت به `ListPanel` می‌افتد که چند رکوردِ آخرِ همان
 * عملیات را زنده نشان می‌دهد. یعنی «خالی» حالتِ آخر است، نه اولین.
 */

/** مقصدِ فهرست: یا `'<page>/<section>'` (تبِ یک صفحه)، یا کلیدِ صفحه‌ی فهرست. */
export type ListTarget = string

/**
 * ریزکردن در سطحِ تب. فقط جایی نوشته می‌شود که پیش‌فرضِ «همه‌ی تب‌های فهرستِ
 * صفحه» زیادی درشت باشد — یعنی ماژولی با چند دفترِ بی‌ربط به هم.
 *
 * نبودنِ یک تب این‌جا خطا نیست؛ یعنی «همان پیش‌فرض درست است».
 */
export const SECTION_LIST_MAP: Record<string, readonly ListTarget[]> = {
  // ── انبار: هشت دفتر دارد و هیچ‌کدام به همه‌ی چهارده عملیات مربوط نیست ──
  'inventory/products': ['inventory/stock', 'inventory/kardex', 'inventory/low', 'inventory/batches', 'inventory/serials'],
  'inventory/warehouses': ['inventory/stock'],
  'inventory/count-tags': ['inventory/count-list'],
  'inventory/count': ['inventory/count-list'],
  'inventory/issues': ['inventory/documents'],
  'inventory/issue-returns': ['inventory/issue-return-list'],
  'inventory/transfer': ['inventory/documents'],
  'inventory/unpriced': ['inventory/documents'],
  'inventory/valuation': ['inventory/documents'],
  //: تعریف‌های کوچک دفترِ جدا ندارند؛ جدولشان داخلِ خودِ تب است.
  'inventory/units': [],
  'inventory/taxonomy': [],
  'inventory/pricelists': [],
  'inventory/adjust': [],
  'inventory/import': [],

  // ── خرید ──
  //: «فهرست تامین‌کنندگان» صاحبِ دیگری ندارد و این نزدیک‌ترین عملیات به آن است.
  'purchases/invoices': ['purchases/invoice-list', 'supplierlist'],
  'purchases/services': ['purchases/service-list'],
  'purchases/receipts': ['inventory/documents'],
  'purchases/returns': [],
  'purchases/deductions': [],

  // ── دارایی ثابت ──
  'fixedassets/assets': ['fixedassets/registry'],
  'fixedassets/placement': ['fixedassets/assignments'],
  'fixedassets/transfer': ['fixedassets/assignments'],
  'fixedassets/depreciation-calc': ['fixedassets/depreciation-list'],
  'fixedassets/depreciation-post': ['fixedassets/depreciation-docs'],
  'fixedassets/disposal': ['fixedassets/disposals'],
  'fixedassets/estimate': ['fixedassets/registry'],
  'fixedassets/improvement': ['fixedassets/registry'],

  // ── تولید ──
  'manufacturing/boms': ['manufacturing/bom-list'],
  'manufacturing/orders': ['manufacturing/order-list'],
  'manufacturing/materials': ['manufacturing/variance'],
  'manufacturing/receipts': ['manufacturing/kardex'],
  'manufacturing/costing': ['manufacturing/cost-report'],

  // ── پخش و بازارگاه: دفترها مالِ چیزی‌اند که می‌فروشی ──
  'distributor/catalog': ['distributor/orders', 'distributor/returns', 'distributor/commission'],
  'distributor/connections': [],
  'distributor/zones': [],
  'distributor/settings': [],
  'marketplace/catalog': ['marketplace/orders', 'marketplace/returns'],
  'marketplace/distributors': [],

  // ── حقوق ──
  //: فیش که صادر می‌شود، سه دفتر کنارِ هم لازم است: خودِ فیش‌ها، پرسنل، و مزایا.
  'payroll/run': ['payslipledger', 'payroll/staff', 'payroll/benefits'],
  'payroll/settings': [],

  // ── مؤدیان: دفترش صفحه‌ی مستقل است، نه تب ──
  'moadian/send': ['moadianhistory'],
  'moadian/status': [],
  'moadian/settings': [],

  // ── ماژول‌هایی که دفتری ندارند ──
  'integration/build': [],
  'integration/connect': [],
  'calendar/reminders': ['calendarlist'],
  'calendar/calendar': ['calendarlist'],
}

/** نمایه‌ی «مقصد ← برچسب و آیکن»، از همان دو جایی که از قبل دارندشان. */
let destIndex: Map<string, ListMenuItem> | null = null

function destinations(): Map<string, ListMenuItem> {
  if (destIndex) return destIndex
  const m = new Map<string, ListMenuItem>()
  //: صفحه‌های فهرست (و تب‌هایی که در منوی گروه ردیف دارند).
  for (const items of Object.values(LIST_MENUS)) {
    for (const it of items) m.set(it.section ? `${it.key}/${it.section}` : it.key, it)
  }
  //: تب‌های `kind: 'list'` — برچسب و آیکن را از خودِ تعریفِ بخش می‌گیرند.
  for (const [page, secs] of Object.entries(MODULE_SECTIONS)) {
    for (const s of secs) {
      if (s.kind !== 'list') continue
      const id = `${page}/${s.key}`
      if (!m.has(id)) m.set(id, { key: page as PageKey, section: s.key, label: s.label, icon: s.icon })
    }
  }
  destIndex = m
  return m
}

/** تب‌های فهرستِ یک صفحه، به ترتیبی که در `MODULE_SECTIONS` آمده‌اند. */
function ownListTabs(page: PageKey): ListTarget[] {
  return (MODULE_SECTIONS[page] ?? []).filter((s) => s.kind === 'list').map((s) => `${page}/${s.key}`)
}

/** فهرست‌هایی که به گزینه‌ی عملیاتِ فعال مربوط‌اند. خالی یعنی «دفترِ جدا ندارد». */
export function listsForOps(page: PageKey, section: string | null): ListMenuItem[] {
  const refined = section ? SECTION_LIST_MAP[`${page}/${section}`] : undefined
  const targets =
    refined ??
    (ownListTabs(page).length > 0
      ? ownListTabs(page)
      : ((t) => (t === undefined || t === 'state' || t === 'view' || t === 'none'
          ? []
          : Array.isArray(t)
            ? t
            : [t]))(OPS_LIST_MAP[page]))

  const index = destinations()
  //: مقصدِ ناشناخته بی‌صدا حذف می‌شود تا یک غلطِ تایپی کلِ کارت را نشکند؛
  //: قاعده‌ی R14 همان را در ممیز قرمز می‌کند.
  return targets.map((t) => index.get(t)).filter((x): x is ListMenuItem => x !== undefined)
}
