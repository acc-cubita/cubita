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
  Coins,
  Group,
  Hourglass,
  Megaphone,
  Handshake,
  PhoneCall,
} from 'lucide-react'
import { MODULE_SECTIONS } from './moduleSections'
import { DAILY_SECTION, DEFINITIONS_SECTION } from '../lib/menuSections'
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
  /** دسته‌ی ردیف در منوی بلند — همان تیترِ کوچکِ `NavItem.section` برای ورودی‌های `OPS_MENUS`/`LIST_MENUS`.
   *  نامش `section` نیست چون `section` این‌جا تبِ صفحه است. */
  category?: string
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
  //: چهار دسته، به ترتیبِ کار (۱۴۰۵/۰۷/۰۶): شش کارِ اصلیِ انبار که کاربر خواست در دو دسته‌ی اول
  //: ماندند (رسید و حواله، انبارگردانی و قیمت‌گذاری)، بعد خرید، و تعریف‌ها — کالا، انبار، واحد،
  //: لیست قیمت، … — ته و پیش‌فرض بسته.
  'تامین‌کنندگان و انبار': [
    { key: 'purchases', section: 'receipts', label: 'رسید انبار', icon: PackageCheck, category: 'رسید و حواله' },
    { key: 'inventory', section: 'issues', label: 'حواله انبار', icon: PackageMinus, category: 'رسید و حواله' },
    { key: 'inventory', section: 'transfer', label: 'انتقال بین انبارها', icon: ArrowLeftRight, category: 'رسید و حواله' },
    { key: 'inventory', section: 'issue-returns', label: 'برگشت خروج انبار', icon: RotateCcw, category: 'رسید و حواله' },
    { key: 'inventory', section: 'count-tags', label: 'تگ انبارگردانی', icon: Tag, category: 'انبارگردانی و قیمت‌گذاری' },
    { key: 'inventory', section: 'count', label: 'ثبت مغایرت انبارگردانی', icon: ClipboardCheck, category: 'انبارگردانی و قیمت‌گذاری' },
    { key: 'inventory', section: 'valuation', label: 'قیمت‌گذاری اسناد انبار', icon: Calculator, category: 'انبارگردانی و قیمت‌گذاری' },
    { key: 'inventory', section: 'unpriced', label: 'قیمت‌گذاری ورودی‌ها', icon: BadgeDollarSign, category: 'انبارگردانی و قیمت‌گذاری' },
    { key: 'inventory', section: 'adjust', label: 'تعدیل دستی', icon: ClipboardList, category: 'انبارگردانی و قیمت‌گذاری' },
    { key: 'purchases', section: 'invoices', label: 'فاکتور خرید', icon: PackagePlus, category: 'خرید' },
    { key: 'purchases', section: 'services', label: 'فاکتور خرید خدمات', icon: Briefcase, category: 'خرید' },
    { key: 'purchases', section: 'returns', label: 'برگشت از خرید', icon: Undo2, category: 'خرید' },
    { key: 'creditnote', label: 'اعلامیه بدهکار بستانکار', icon: FileSpreadsheet, category: 'خرید' },
    { key: 'inventory', section: 'products', label: 'کالاها', icon: Package, category: DEFINITIONS_SECTION },
    { key: 'inventory', section: 'warehouses', label: 'انبارها', icon: Warehouse, category: DEFINITIONS_SECTION },
    { key: 'inventory', section: 'locations', label: 'موقعیت‌های انبار', icon: MapPin, category: DEFINITIONS_SECTION },
    { key: 'inventory', section: 'units', label: 'واحدها', icon: Ruler, category: DEFINITIONS_SECTION },
    { key: 'inventory', section: 'taxonomy', label: 'گروه و مشخصات', icon: FolderTree, category: DEFINITIONS_SECTION },
    { key: 'inventory', section: 'pricelists', label: 'لیست قیمت', icon: Tags, category: DEFINITIONS_SECTION },
    { key: 'purchases', section: 'deductions', label: 'انواع کسورات', icon: Percent, category: DEFINITIONS_SECTION },
    { key: 'inventory', section: 'import', label: 'ورود گروهی کالا', icon: FileUp, category: DEFINITIONS_SECTION },
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
 *
 * منوی بلند (بیش از هشت ردیف) `category` می‌گیرد، با همان واژگانِ کارتِ «عملیات»: تیترِ کوچک بالای
 * هر دسته، و «تعریف‌ها» پیش‌فرض بسته. ردیف‌های هم‌دسته پشتِ هم می‌آیند.
 */
export const LIST_MENUS: Record<string, ListMenuItem[]> = {
  'اتوماسیون اداری': [
    { key: 'letterlist', label: 'دبیرخانه و بایگانی', icon: FileText },
  ],
  //: «تامین‌کنندگان و انبار» — همان سه دسته‌ی کاریِ کارتِ «عملیات». بیشترشان تبِ صفحه‌ی
  //: «انبار»/«خرید»اند (`section`)؛ «تأمین‌کنندگان» همان صفحه‌ی طرف‌حساب‌هاست با نقشِ تأمین‌کننده.
  'تامین‌کنندگان و انبار': [
    { key: 'inventory', section: 'documents', label: 'رسیدها و حواله‌های انبار', icon: FileStack, category: 'رسید و حواله' },
    { key: 'inventory', section: 'issue-return-list', label: 'برگشت‌های خروج انبار', icon: RotateCcw, category: 'رسید و حواله' },
    { key: 'inventory', section: 'stock', label: 'مرور انبار / موجودی کالا', icon: PackageSearch, category: 'موجودی و انبارگردانی' },
    { key: 'inventory', section: 'kardex', label: 'کاردکس کالا', icon: History, category: 'موجودی و انبارگردانی' },
    { key: 'inventory', section: 'low', label: 'گزارش نقطه سفارش', icon: AlertTriangle, category: 'موجودی و انبارگردانی' },
    { key: 'inventory', section: 'count-list', label: 'انبارگردانی‌ها', icon: ListChecks, category: 'موجودی و انبارگردانی' },
    { key: 'inventory', section: 'batches', label: 'بچ و انقضا', icon: CalendarClock, category: 'موجودی و انبارگردانی' },
    { key: 'inventory', section: 'serials', label: 'جست‌وجوی سریال', icon: ScanSearch, category: 'موجودی و انبارگردانی' },
    { key: 'supplierlist', label: 'تأمین‌کنندگان', icon: UsersRound, category: 'خرید' },
    { key: 'purchases', section: 'invoice-list', label: 'فاکتورهای خرید', icon: ClipboardList, category: 'خرید' },
    { key: 'purchases', section: 'service-list', label: 'فاکتورهای خرید خدمات', icon: FileText, category: 'خرید' },
    { key: 'notelist', label: 'اعلامیه‌های بدهکار و بستانکار', icon: FileSpreadsheet, category: 'خرید' },
  ],
  //: کلید باید **دقیقاً** `heading`ِ گروهِ ناوبری باشد، نه نامِ ماژول: هم `ModulePanels` و هم
  //: کشوی موبایل با `group.heading` این نگاشت را می‌خوانند. تا روزی این‌جا «فروش» بود در حالی که
  //: heading «مشتریان و فروش» است، و هر دوازده صفحه‌ی فهرستِ فروش از هیچ عرضی باز نمی‌شدند.
  //:
  //: تب‌های «اشخاص» و «باشگاه» تبِ صفحه‌اند نه صفحه‌ی جدا. بدونِ ردیفشان، تبی که `kind: 'list'`
  //: می‌گیرد از کارتِ «عملیات» بیرون می‌رود و در «فهرست» هم نمی‌آید — «طرف حساب‌ها»، «سنین
  //: مطالبات» و «بخش‌بندی» یک بار دقیقاً همین‌طور بالای ۱۰۲۴px بی‌راه شدند (قاعده‌ی R13).
  //:
  //: **دو فهرستِ اشخاص، دو نگاه:** «طرف حساب‌ها» شناسنامه است (نقش، گروه، محل، تلفن) و «مانده و
  //: اعتبار اشخاص» مالی (مانده، سقفِ اعتبار). تا امروز هر دو «طرف حساب‌ها» نام داشتند و در دو کارتِ
  //: جدا بودند؛ کنارِ هم با یک نام، کاربر نمی‌فهمید کدام را باز کند.
  'مشتریان و فروش': [
    { key: 'saleslist', label: 'فاکتورهای فروش', icon: ClipboardList, category: 'اسناد فروش' },
    { key: 'quotationlist', label: 'پیش‌فاکتورها', icon: FileText, category: 'اسناد فروش' },
    { key: 'returnlist', label: 'فاکتورهای برگشتی', icon: Undo2, category: 'اسناد فروش' },
    { key: 'notelist', label: 'اعلامیه‌های بدهکار و بستانکار', icon: FileSpreadsheet, category: 'اسناد فروش' },
    { key: 'installmentplans', label: 'قراردادهای اقساطی', icon: CalendarClock, category: 'اسناد فروش' },
    { key: 'allinstallments', label: 'همه اقساط', icon: ListChecks, category: 'اسناد فروش' },
    { key: 'contactlist', label: 'طرف حساب‌ها', icon: UsersRound, category: 'اشخاص' },
    { key: 'contacts', section: 'contacts', label: 'مانده و اعتبار اشخاص', icon: Scale, category: 'اشخاص' },
    { key: 'contacts', section: 'aging', label: 'سنین مطالبات', icon: Hourglass, category: 'اشخاص' },
    { key: 'relatedpeople', label: 'افراد مرتبط', icon: Contact2, category: 'اشخاص' },
    { key: 'crm', section: 'leads', label: 'سرنخ‌ها', icon: Target, category: 'باشگاه مشتریان' },
    { key: 'crm', section: 'activities', label: 'پیگیری‌ها', icon: PhoneCall, category: 'باشگاه مشتریان' },
    { key: 'crm', section: 'segments', label: 'بخش‌بندی', icon: PieChart, category: 'باشگاه مشتریان' },
    { key: 'crm', section: 'tiers', label: 'سطوح باشگاه', icon: Medal, category: 'باشگاه مشتریان' },
    { key: 'crm', section: 'rewards', label: 'جوایز', icon: Ticket, category: 'باشگاه مشتریان' },
    { key: 'crm', section: 'birthdays', label: 'تولدها', icon: Cake, category: 'باشگاه مشتریان' },
    { key: 'commissionrulelist', label: 'قواعد پورسانت', icon: Wallet, category: 'پورسانت و گمرک' },
    { key: 'commissionrunlist', label: 'محاسبه‌های پورسانت', icon: Calculator, category: 'پورسانت و گمرک' },
    { key: 'customslist', label: 'اظهارنامه‌های گمرکی', icon: Ship, category: 'پورسانت و گمرک' },
    { key: 'saletypelist', label: 'انواع فروش', icon: Tags, category: DEFINITIONS_SECTION },
    { key: 'priceannouncelist', label: 'اعلامیه‌های قیمت', icon: Megaphone, category: DEFINITIONS_SECTION },
    { key: 'bundlelist', label: 'بسته‌های محصول', icon: Boxes, category: DEFINITIONS_SECTION },
    { key: 'pricingfactorlist', label: 'تخفیف‌ها و عوامل افزاینده', icon: Percent, category: DEFINITIONS_SECTION },
    { key: 'discountgrouplist', label: 'گروه‌های کالای تخفیف', icon: Layers, category: DEFINITIONS_SECTION },
    { key: 'contactgrouplist', label: 'گروه‌های طرف حساب', icon: Group, category: DEFINITIONS_SECTION },
    { key: 'geolist', label: 'محل‌های جغرافیایی', icon: MapPin, category: DEFINITIONS_SECTION },
  ],
  //: فقط دفترهای سطحِ شرکت. سفارش‌ها و مرجوعی‌های پخش/بازار تا ۱۴۰۵/۰۷/۰۶ این‌جا بودند؛ حالا
  //: تب‌های فهرستِ صفحه‌ی خودشان‌اند و در کارتِ «فهرست»ِ همان ماژول می‌آیند (`listSections`).
  'تنظیمات': [
    { key: 'backuplist', label: 'نسخه‌های پشتیبانی و بازیابی', icon: DatabaseBackup },
    { key: 'userlist', label: 'کاربران', icon: UsersRound },
    { key: 'fiscalyearlist', label: 'سال‌های مالی', icon: CalendarRange },
    { key: 'numberinglist', label: 'روش‌های شماره‌گذاری', icon: Hash },
  ],
  //: «حسابداری» — دفترهایی که هیچ صفحه‌ی عملیاتی تمامشان را نشان نمی‌دهد: اسناد، دوره‌های
  //: بسته‌شده، و مراکزِ هزینه (از «شرکت» آمد). «فهرست حساب‌ها» و «تفصیلی‌های سایر» در بازچینیِ
  //: ۱۴۰۵/۰۷/۰۳ رفتند: درختواره و برگه‌ی تفصیلی خودشان دفترِ کاملِ همان داده‌اند.
  'حسابداری': [
    { key: 'entrylist', label: 'اسناد حسابداری', icon: FileStack },
    { key: 'periodcloselist', label: 'دوره‌های بسته‌شده', icon: Archive },
    { key: 'costcenterlist', label: 'مراکز هزینه', icon: Target },
  ],
  //: «دریافت و پرداخت» — همان دسته‌های کارتِ «عملیات». «تراکنش‌های شریک» از «شرکت» آمد.
  'دریافت و پرداخت': [
    { key: 'treasuryledger', label: 'دریافت‌ها و پرداخت‌ها', icon: HandCoins, category: DAILY_SECTION },
    { key: 'paymentnoticelist', label: 'اعلامیه‌های پرداخت', icon: Receipt, category: DAILY_SECTION },
    //: تسویه‌ی طرف مقابل رابطه است نه گردشِ پول، پس دفترِ خودش را دارد و در
    //: «دریافت‌ها و پرداخت‌ها» قاطیِ رسیدها نمی‌شود.
    { key: 'contactsettlelist', label: 'تسویه‌های طرف مقابل', icon: Scale, category: DAILY_SECTION },
    { key: 'ownertxnlist', label: 'تراکنش‌های شریک', icon: Coins, category: DAILY_SECTION },
    //: «چه عملیاتی کِی روی چه چکی» — نمای دومِ دامنه‌ی چک، در برابرِ
    //: «جست‌وجوی چک» که می‌گوید الان چه داریم و وضعیتشان چیست.
    { key: 'checkoplist', label: 'عملیات چک', icon: History, category: 'چک و بانک' },
    { key: 'statementlist', label: 'ردیف‌های صورت‌حساب بانکی', icon: FileSpreadsheet, category: 'چک و بانک' },
    { key: 'possettlelist', label: 'تسویه‌های کارتخوان', icon: CreditCard, category: 'چک و بانک' },
    { key: 'pettylist', label: 'گردش تنخواه', icon: Wallet, category: 'چک و بانک' },
    //: «دسته‌چک‌ها» و «دستگاه‌های کارتخوان» رفتند: برگه‌های «حساب‌های نقد و بانک» خودشان دفترِ کاملِ همان داده‌اند.
  ],
  //: «سامانه مؤدیان» — فهرستِ خودکارِ قبلی (چند ردیفِ آخرِ ارسال‌ها) جایش را به منو
  //: داد: تاریخچه‌ی ارسال یک دفترِ قانونی است و فیلتر و جست‌وجو و خروجی می‌خواهد،
  //: نه یک پیش‌نمایشِ چندردیفی.
  //: «حقوق و دستمزد» — دفترِ نظیرِ «قرارداد». بقیه‌ی منوهای این ماژول
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
    { key: 'contractinglist', label: 'پیمان‌ها', icon: Handshake },
    { key: 'contractingamendmentlist', label: 'متمم‌های پیمان', icon: FilePenLine },
    { key: 'contractingstatementlist', label: 'صورت وضعیت‌های دریافتی', icon: Receipt },
    { key: 'contractingsettlementlist', label: 'تسویه‌حساب‌های پیمان', icon: HandCoins },
  ],
  //: «حسابرسی» — دو دفتر: یافته‌های آخرین بررسی، و تاریخچه‌ی اجراها. هر دو پشتِ
  //: ماژولِ مشتق‌اند، پس پیش از تأییدِ قرارداد اصلاً در منو نمی‌آیند.
  'حسابرسی': [
    { key: 'assurancefindinglist', label: 'یافته‌های حسابرسی', icon: ListChecks },
    { key: 'assurancerunlist', label: 'تاریخچه بررسی‌ها', icon: History },
  ],
  //: «گزارش و ابزار» (جانشینِ «شرکت») — دفترِ گزارش‌های ساخته‌شده و رویدادهای تقویم. بقیه‌ی
  //: فهرست‌های «شرکت» به ماژولِ داده‌ی خودشان رفتند.
  'گزارش و ابزار': [
    { key: 'dynamicreports', label: 'گزارش‌های پویا', icon: LayoutList },
    { key: 'calendarlist', label: 'رویدادهای تقویم', icon: CalendarDays },
  ],
}

/**
 * صفحه‌های فهرست در هیچ گروهی از منو نیستند (وگرنه در کارتِ «عملیات» هم تکرار
 * می‌شدند)، ولی وقتی بازند باید همان دو کارتِ ماژولِ خودشان را کنارشان داشته باشند —
 * وگرنه کاربر بدونِ راهِ برگشت می‌ماند. این نگاشت همان پیوند را می‌سازد.
 */
export const LIST_PAGE_GROUP: Partial<Record<PageKey, string>> = {
  letterlist: 'اتوماسیون اداری',
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
  possettlelist: 'دریافت و پرداخت',
  checkoplist: 'دریافت و پرداخت',
  contactsettlelist: 'دریافت و پرداخت',
  statementlist: 'دریافت و پرداخت',
  pettylist: 'دریافت و پرداخت',
  geolist: 'مشتریان و فروش',
  ownertxnlist: 'دریافت و پرداخت',
  contactgrouplist: 'مشتریان و فروش',
  calendarlist: 'گزارش و ابزار',
  numberinglist: 'تنظیمات',
  contractlist: 'حقوق و دستمزد',
  payslipledger: 'حقوق و دستمزد',
  moadianhistory: 'سامانه مؤدیان',
  contractinglist: 'پیمانکاری',
  contractingamendmentlist: 'پیمانکاری',
  contractingstatementlist: 'پیمانکاری',
  contractingsettlementlist: 'پیمانکاری',
  assurancefindinglist: 'حسابرسی',
  assurancerunlist: 'حسابرسی',
  entrylist: 'حسابداری',
  recurringlist: 'حسابداری',
  budgetlist: 'حسابداری',
  currencylist: 'حسابداری',
  periodcloselist: 'حسابداری',
  costcenterlist: 'حسابداری',
  backuplist: 'تنظیمات',
  userlist: 'تنظیمات',
  fiscalyearlist: 'تنظیمات',
  dataexport: 'گزارش و ابزار',
  dataimport: 'گزارش و ابزار',
  reportbuilder: 'گزارش و ابزار',
  dynamicreports: 'گزارش و ابزار',
  dayactivity: 'گزارش و ابزار',
  mgmtreports: 'گزارش و ابزار',
  usagereport: 'گزارش و ابزار',
  contactlist: 'مشتریان و فروش',
  //: همان صفحه‌ی طرف‌حساب‌ها با نقشِ تأمین‌کننده — فهرستِ گروهِ انبار، نه نمای دوم.
  supplierlist: 'تامین‌کنندگان و انبار',
  relatedpeople: 'مشتریان و فروش',
  installmentplans: 'مشتریان و فروش',
  allinstallments: 'مشتریان و فروش',
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
  automation: 'view',
  letternew: 'letterlist',
  ownertxn: 'ownertxnlist', //: ثبت ↔ دفتر — الگوی «فروش اقساطی»
  // ── دریافت و پرداخت ──
  payflow: 'none', //: راهنمای مسیر
  receiptvoucher: 'treasuryledger', //: سه عملیات، یک دفترِ مشترک با فیلتر
  paymentvoucher: 'paymentnoticelist',
  contactsettle: 'contactsettlelist',
  //: دفترِ چک‌ها همان «جستجوی چک» است — کاربر صریحاً آن را در کارتِ عملیات خواست،
  //: و فهرستِ دومِ چک یعنی دو نمای یک داده.
  checkops: 'checksearch',
  checkreturn: 'checkoplist',
  checkpayclear: 'checkoplist',
  bankreconcile: 'state',
  checksearch: 'view',
  bankledger: 'view',
  cashbox: 'view',
  possettle: 'possettlelist',
  bankstatement: 'statementlist',
  //: پنج برگه‌ی اکسلیِ تعریف — هر برگه هم فرم است و هم دفترِ کاملِ همان رکوردها با مانده‌شان (الگوی «ب»ِ تمِ
  //: اکسلی). فهرستِ نظیرِ جدا دو نمای یک داده بود و رفت.
  cashbank: 'view',
  pettyholder: 'pettylist', //: شارژ و هزینه، یک دفترِ مشترک
  pettyexpense: 'pettylist',

  // ── حسابداری ──
  //: درختواره خودش دفترِ کاملِ حساب‌هاست (جست‌وجو، نمای تخت، مانده) — مثلِ «حساب بانکی».
  acctchart: 'view',
  openingbalance: 'entrylist', //: خروجی‌اش یک سندِ حسابداری است
  journalentry: 'entrylist',
  mergeentries: 'entrylist',
  fxrevaluation: 'entrylist',
  //: سندش در فهرستِ اسناد با منشأ «انتقال مانده به حساب دیگر» دیده می‌شود.
  balancereclass: 'entrylist',
  closingopening: 'entrylist',
  closepnl: 'periodcloselist',
  //: برگه‌ی «تفصیلی سایر» همه‌ی تفصیلی‌ها را با همان ستون‌های دفتر دارد و همان‌جا ویرایش می‌شود.
  analytics: 'view',
  entrycartable: 'state',
  renumber: 'state',
  reclassify: 'state',
  vat: 'view',
  ebooks: 'view',
  accountbrowse: 'view',
  balancereport: 'view',
  ledgerreport: 'view',
  integrity: 'view',
  reports: 'view',

  // ── اشخاص، اقساط، مرکز هزینه و ابتدا/پایانِ سال (پیش‌تر ماژولِ «شرکت») ──
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

  //: «گزارش و ابزار» — گزینه‌هایی که با دامنه‌دارشدنِ کارتِ فهرست به «عملیات» آمدند.
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
  shortcuts: 'none', //: ترجیحِ شخصی، رکوردی نمی‌سازد
  fiscalyear: 'fiscalyearlist',
  //: قالبِ صنفی حساب می‌سازد، و دفترِ حساب‌ها همان «درختواره حساب‌ها» است — فهرستِ
  //: دوم یعنی دو نمای یک داده.
  coding: 'acctchart',
  personalization: 'none', //: ترجیحِ رفتاریِ کسب‌وکار، رکوردی نمی‌سازد
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
  //: حسابرسی — «درخواست» خودش دفترِ قراردادش است (هر کسب‌وکار یک قراردادِ باز
  //: دارد؛ فهرستی از یک ردیف بی‌معناست)، و «کارنامه» دفترِ اجراهایش را دارد.
  assurancerequest: 'view',
  assurancehealth: ['assurancefindinglist', 'assurancerunlist'],
  distributor: 'view',
  marketplace: 'view',
  overview: 'view',
  modules: 'none',
  license: 'none',
  profile: 'none',
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

  // ── «حساب‌های نقد و بانک»: هر برگه دفترِ خودش است ──
  'cashbank/cashboxes': [],
  'cashbank/banks': [],
  'cashbank/pos': [],
  'cashbank/checkbooks': [],
  'cashbank/petty': [],

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
