import {
  Archive,
  BadgeCheck,
  ArrowDownToLine,
  ArrowLeftRight,
  ArrowUpFromLine,
  Activity,
  BarChart3,
  BellRing,
  BookMarked,
  BookOpen,
  BookOpenCheck,
  Boxes,
  Building,
  FilePenLine,
  FileUp,
  FileSignature,
  Briefcase,
  Building2,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ClipboardCheck,
  ClipboardList,
  Coins,
  Download,
  Gauge,
  Repeat,
  Upload,
  Wrench,
  Combine,
  CreditCard,
  DatabaseBackup,
  Factory,
  FileSpreadsheet,
  FolderTree,
  GitCompareArrows,
  Banknote,
  HandCoins,
  HardHat,
  Hash,
  HeartHandshake,
  HelpCircle,
  Keyboard,
  KeyRound,
  Layers,
  LayoutDashboard,
  ListTree,
  Lock,
  MapPin,
  PackagePlus,
  Palette,
  Percent,
  PiggyBank,
  PlayCircle,
  Receipt,
  RefreshCcw,
  Route,
  Scale,
  ScanLine,
  ScrollText,
  Settings,
  Settings2,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  SlidersHorizontal,
  Store,
  Tag,
  Tags,
  Target,
  Truck,
  Undo2,
  UserCircle,
  UserCog,
  UserPlus,
  Users,
  UsersRound,
  Wallet,
  Warehouse,
  FileText,
  Calculator,
  Ship,
  BadgePercent,
  TrendingUp,
  Contact,
  PackageX,
  Megaphone,
  Group,
  Vault,
  Sheet,
  DoorOpen,
  Crosshair,
  ListChecks,
  History,
  Handshake,
} from 'lucide-react'
import type { ReactNode } from 'react'

import type { ExperienceMode } from './experienceMode'
import { DAILY_SECTION, DEFINITIONS_SECTION } from './menuSections'
import { isEnterprise } from '../platform'

// شناسه‌ی هر صفحه‌ی برنامه. منبعِ واحد؛ Sidebar و TopNav هر دو از همین می‌خوانند.
export type PageKey =
  | 'overview'
  | 'automation'
  | 'repair'
  | 'letternew'
  | 'letterlist'
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
  | 'contractingnew'
  | 'contractingstatus'
  | 'contractingamendment'
  | 'contractingstatement'
  | 'contractingsettlement'
  //: حسابرسی — «درخواست» پیش از تأیید هم دیده می‌شود؛ بقیه پشتِ ماژولِ مشتق.
  | 'assurancerequest'
  | 'assurancehealth'
  | 'moadian'
  | 'distributor'
  | 'marketplace'
  | 'payroll'
  | 'contractnew'
  | 'ownertxn'
  | 'contractlist'
  | 'payslipledger'
  | 'servicelocation'
  | 'jobtitle'
  | 'payrollfactors'
  | 'payrolltaxgroups'
  | 'taxtables'
  | 'loantype'
  | 'employeeloans'
  | 'settlement'
  | 'deploymentinfo'
  | 'integration'
  | 'reports'
  | 'calendar'
  | 'team'
  | 'modules'
  | 'license'
  | 'profile'
  | 'help'
  | 'theme'
  | 'fiscalyear'
  | 'password'
  | 'backup'
  | 'numbering'
  | 'coding'
  | 'personalization'
  | 'shortcuts'
  | 'contactimport'
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
  | 'supplierlist'
  | 'relatedpeople'
  | 'installmentplans'
  | 'allinstallments'
  | 'costcenterlist'
  | 'contractinglist'
  | 'ownertxnlist'
  | 'contractingamendmentlist'
  | 'contractingstatementlist'
  | 'contractingsettlementlist'
  //: فهرستِ «سامانه مؤدیان» — از کارتِ «فهرست» باز می‌شود، نه از منوی عملیات.
  | 'moadianhistory'
  //: ماژولِ «دریافت و پرداخت» — هجده عملیات. کلیدِ گیت‌کننده‌شان `banking` است
  //: (نگاشتِ PAGE_MODULE_KEY پایین)، نه خودشان.
  | 'payflow'
  | 'receiptvoucher'
  | 'paymentvoucher'
  | 'contactsettle'
  //: «چک‌ها» — چهار برگه (دریافتنی، پرداختنی، استرداد، جست‌وجو) در یک صفحه؛ جانشینِ
  //: `checkops`/`checkpayclear`/`checkreturn`/`checksearch` (`LEGACY_PAGES`).
  | 'checks'
  | 'possettle'
  //: «مغایرت‌گیری بانکی» — ورود و تطبیقِ صورت‌حساب؛ جانشینِ `bankstatement` (`LEGACY_PAGES`).
  | 'bankreconcile'
  | 'cashbox'
  //: «حساب‌های نقد و بانک» — پنج برگه‌ی تعریف (صندوق، بانک، کارتخوان، دسته‌چک، تنخواه) در یک صفحه؛ جانشینِ
  //: `cashboxes`/`bankaccounts`/`posterminals`/`checkbooks` و دو فهرستِ `checkbooklist`/`posterminallist` (`LEGACY_PAGES`).
  | 'cashbank'
  | 'pettyholder'
  | 'pettyexpense'
  | 'bankledger'
  //: فهرست‌های همین ماژول — از کارتِ «فهرست» باز می‌شوند. قاعده‌ی نظیر: هر عملیاتِ
  //: رکوردساز یک دفتر دارد (نگاشتِ OPS_LIST_MAP در moduleLists).
  //: ماژولِ فروش — هجده عملیات و دوازده دفترِ نظیر (قاعده‌ی نظیر).
  | 'salesflow'
  | 'invoiceclose'
  | 'salesinvoice'
  | 'quotations'
  | 'salesreturn'
  | 'commission'
  | 'commissioncalc'
  | 'customs'
  | 'contactstatement'
  | 'creditnote'
  | 'saletype'
  | 'returnreason'
  | 'priceannounce'
  | 'bundle'
  | 'discount'
  | 'discountgroup'
  | 'markup'
  | 'salesbrowse'
  | 'contactoverview'
  | 'saleslist'
  | 'quotationlist'
  | 'returnlist'
  | 'saletypelist'
  | 'pricingfactorlist'
  | 'discountgrouplist'
  | 'priceannouncelist'
  | 'bundlelist'
  | 'commissionrulelist'
  | 'commissionrunlist'
  | 'customslist'
  | 'notelist'
  | 'treasuryledger'
  | 'paymentnoticelist'
  | 'possettlelist'
  | 'contactsettlelist'
  | 'checkoplist'
  | 'statementlist'
  | 'pettylist'
  //: دفترهای نظیرِ ماژول‌های حسابداری، شرکت و تنظیمات.
  | 'geolist'
  | 'contactgrouplist'
  | 'calendarlist'
  | 'numberinglist'
  //: ماژولِ «حسابداری» — هجده عملیاتِ دفترداری. کلیدِ ماژولِ گیت‌کننده‌شان
  //: `accounting` است (نگاشتِ PAGE_MODULE_KEY پایین)، نه خودشان.
  | 'acctchart'
  | 'journalentry'
  | 'renumber'
  | 'mergeentries'
  | 'fxrevaluation'
  | 'balancereclass'
  | 'entrycartable'
  | 'closingopening'
  | 'vat'
  | 'ebooks'
  | 'reclassify'
  | 'closepnl'
  | 'analytics'
  | 'openingbalance'
  | 'accountbrowse'
  | 'balancereport'
  | 'ledgerreport'
  | 'integrity'
  //: فهرست‌های حسابداری — از کارتِ «فهرست» باز می‌شوند.
  | 'entrylist'
  | 'recurringlist'
  | 'budgetlist'
  | 'currencylist'
  | 'periodcloselist'
  //: فهرست‌های حسابرسی
  | 'assurancefindinglist'
  | 'assurancerunlist'

export type NavItem = {
  key: PageKey
  label: string
  icon: ReactNode
  /**
   * دسته‌ی ردیف درونِ گروه — تیترِ کوچکی که کارتِ «عملیات» و کشوی موبایل بالای هر دسته
   * می‌گذارند. ردیف‌های هم‌دسته پشتِ هم می‌آیند (`navSections`). گروهی که دسته ندارد، همان
   * فهرستِ یک‌دستِ قبلی است.
   */
  section?: string
  /**
   * صفحه‌ی «مسیرِ کار» — راهنمای ترتیبِ کارهای ماژول، نه خودِ یک کار. بی‌دسته بالای کارتِ «عملیات»
   * می‌نشیند (به شکلِ پیوندِ کم‌رنگ، نه ردیفِ هم‌وزنِ بقیه) و مقصدِ کلیک روی نامِ ماژول نمی‌شود.
   */
  guide?: boolean
}
export type NavGroup = { heading: string; icon?: ReactNode; items: NavItem[] }

// چیدمانِ ماژول‌ها گروه‌بندی‌شده تا کاربر به‌جای اسکنِ فهرستِ تخت، روی «دسته» تمرکز کند.
// ترتیبِ گروه‌ها بر اساسِ گردشِ کار: پرکاربردِ روزمره بالا، مالی وسط، اطلاعات/گزارش، ابزارِ کم‌استفاده ته.
//
// **درونِ هر گروه، کارِ روزانه اول و تعریف‌ها آخر** (مرتب‌سازیِ زیرمنوها، ۱۴۰۵/۰۷/۰۶). پیش از این
// «فروش»، «دریافت و پرداخت» و «انبار» هر کدام ۱۹ تا ۲۲ ردیفِ تخت بودند و تعریف‌های یک‌باره لابه‌لای
// فاکتور و رسید نشسته بودند. نام‌ها هم یک قاعده گرفتند: ردیفِ عملیاتی که دفترِ جدا دارد **مفرد** است
// («فاکتور فروش»، «بسته محصول») و دفترش **جمع** («فاکتورهای فروش»، «بسته‌های محصول»)؛ صفحه‌ای که فرم و
// دفترش یکی است جمع است («صندوق‌ها»، «حساب‌های بانکی»). پسوندِ «جدید» رفت — کارِ هر ردیفِ عملیات ساختن است.
export const NAV_GROUPS: NavGroup[] = [
  { heading: 'تعمیرگاه', icon: <Wrench size={17} />, items: [{ key: 'repair', label: 'تعمیرگاه', icon: <Wrench size={18} /> }] },
  {
    heading: 'میزکار',
    items: [{ key: 'overview', label: 'داشبورد', icon: <LayoutDashboard size={18} /> }],
  },
  {
    //: «مشتریان و فروش» = طرفِ‌حساب + گردشِ کالا و پولِ فروش، یک گروه. شناسنامه‌ی طرف‌حساب‌ها
    //: (ثبت، گروه، محلِ جغرافیایی، ورودِ گروهی) از «شرکت» و «تنظیمات» به همین‌جا آمد — داده‌شان
    //: همین اشخاص است — و «فروش اقساطی» هم کنارِ بقیه‌ی فروش نشست.
    heading: 'مشتریان و فروش',
    icon: <ShoppingBag size={17} />,
    items: [
      { key: 'salesflow', label: 'فرآیند فروش', icon: <Route size={18} />, guide: true },
      { key: 'salesinvoice', label: 'فاکتور فروش', icon: <ShoppingCart size={18} />, section: DAILY_SECTION },
      { key: 'quotations', label: 'پیش‌فاکتور', icon: <FileText size={18} />, section: DAILY_SECTION },
      { key: 'salesreturn', label: 'فاکتور برگشتی', icon: <Undo2 size={18} />, section: DAILY_SECTION },
      { key: 'pos', label: 'صندوق فروشگاهی', icon: <ScanLine size={18} />, section: DAILY_SECTION },
      { key: 'installments', label: 'فروش اقساطی', icon: <CalendarClock size={18} />, section: DAILY_SECTION },
      { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} />, section: 'اشخاص' },
      { key: 'contactnew', label: 'ثبت طرف حساب', icon: <UserPlus size={18} />, section: 'اشخاص' },
      //: دسته‌ی جدا: شش دفترِ باشگاه (سرنخ، پیگیری، …) کنارِ همین صفحه می‌نشینند (`mergeMenu`).
      { key: 'crm', label: 'باشگاه مشتریان', icon: <HeartHandshake size={18} />, section: 'باشگاه مشتریان' },
      { key: 'invoiceclose', label: 'بستن فاکتور', icon: <Lock size={18} />, section: 'اصلاح و بستن' },
      { key: 'creditnote', label: 'اعلامیه بدهکار بستانکار', icon: <FileSpreadsheet size={18} />, section: 'اصلاح و بستن' },
      { key: 'commission', label: 'قاعده پورسانت', icon: <Wallet size={18} />, section: 'پورسانت و گمرک' },
      { key: 'commissioncalc', label: 'محاسبه پورسانت', icon: <Calculator size={18} />, section: 'پورسانت و گمرک' },
      { key: 'customs', label: 'اظهارنامه گمرکی', icon: <Ship size={18} />, section: 'پورسانت و گمرک' },
      { key: 'salesbrowse', label: 'مرور فروش', icon: <TrendingUp size={18} />, section: 'مرور و گزارش' },
      { key: 'contactoverview', label: 'مرور جامع طرف حساب', icon: <Contact size={18} />, section: 'مرور و گزارش' },
      { key: 'contactstatement', label: 'صورت حساب طرف مقابل', icon: <ClipboardList size={18} />, section: 'مرور و گزارش' },
      { key: 'saletype', label: 'نوع فروش', icon: <Tags size={18} />, section: DEFINITIONS_SECTION },
      { key: 'returnreason', label: 'علت برگشت کالا', icon: <PackageX size={18} />, section: DEFINITIONS_SECTION },
      { key: 'priceannounce', label: 'اعلامیه قیمت', icon: <Megaphone size={18} />, section: DEFINITIONS_SECTION },
      { key: 'bundle', label: 'بسته محصول', icon: <Boxes size={18} />, section: DEFINITIONS_SECTION },
      { key: 'discount', label: 'تخفیف', icon: <Percent size={18} />, section: DEFINITIONS_SECTION },
      { key: 'markup', label: 'عامل افزاینده', icon: <BadgePercent size={18} />, section: DEFINITIONS_SECTION },
      { key: 'discountgroup', label: 'گروه کالای تخفیف', icon: <Layers size={18} />, section: DEFINITIONS_SECTION },
      { key: 'contactgroup', label: 'گروه طرف حساب', icon: <Group size={18} />, section: DEFINITIONS_SECTION },
      { key: 'geo', label: 'محل جغرافیایی', icon: <MapPin size={18} />, section: DEFINITIONS_SECTION },
      { key: 'contactimport', label: 'ورود گروهی اشخاص', icon: <FileUp size={18} />, section: DEFINITIONS_SECTION },
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
      //: **همان صفحه‌ی گروهِ فروش، نه نسخه‌ی دوم.** اعلامیه سندِ مشترکِ طرف مقابل
      //: است و تهاترِ تأمین‌کننده با تأمین‌کننده نباید پشتِ ماژولِ فروش پنهان
      //: بماند (فصلِ اعلامیه، §۶). فهرست‌های تخت (جست‌وجو، فرمان) با
      //: `uniqueNavItems` تکرارش را حذف می‌کنند.
      { key: 'creditnote', label: 'اعلامیه بدهکار بستانکار', icon: <FileSpreadsheet size={18} /> },
    ],
  },
  {
    //: سرتیترِ گروه همان نامِ ماژول است («سفارش کار» حذف شد، به خواستِ کاربر). گروهِ
    //: تک‌ماژولیِ هم‌نام در کشوی موبایل ردیفِ تکراری نمی‌گیرد و بخش‌های «تولید» مستقیم
    //: زیرِ سرتیتر می‌آیند.
    heading: 'تولید',
    icon: <Factory size={17} />,
    items: [{ key: 'manufacturing', label: 'تولید', icon: <Factory size={18} /> }],
  },
  {
    //: «دریافت و پرداخت» = گردشِ پول. کارِ هرروزه (رسید، اعلامیه، تسویه) اول، بعد چک، بعد بانک و
    //: کارتخوان و تنخواه، بعد مرورها، و ته تعریف‌ها (صندوق، حساب، دسته‌چک، کارتخوان، تنخواه‌دار).
    //: «تراکنش شریک» از «شرکت» آمد: آورده و برداشتِ شریک گردشِ پول است.
    heading: 'دریافت و پرداخت',
    icon: <HandCoins size={17} />,
    items: [
      { key: 'payflow', label: 'فرآیند دریافت و پرداخت', icon: <Route size={18} />, guide: true },
      { key: 'receiptvoucher', label: 'رسید دریافت', icon: <ArrowDownToLine size={18} />, section: DAILY_SECTION },
      { key: 'paymentvoucher', label: 'اعلامیه پرداخت', icon: <ArrowUpFromLine size={18} />, section: DAILY_SECTION },
      { key: 'contactsettle', label: 'تسویه حساب طرف مقابل', icon: <Scale size={18} />, section: DAILY_SECTION },
      { key: 'ownertxn', label: 'تراکنش شریک', icon: <HandCoins size={18} />, section: DAILY_SECTION },
      //: چهار منوی چک، یک صفحه با چهار برگه (مرحله‌ی ۲، ۱۴۰۵/۰۷/۰۶) — برگه‌ها زیرِ همین ردیف باز می‌شوند.
      { key: 'checks', label: 'چک‌ها', icon: <ScrollText size={18} />, section: 'چک' },
      //: ورود و تطبیقِ صورت‌حساب یک صفحه شد (مرحله‌ی ۲، ۱۴۰۵/۰۷/۰۶) — «صورت حساب بانکی» نمای دومِ همین داده بود.
      { key: 'bankreconcile', label: 'مغایرت‌گیری بانکی', icon: <GitCompareArrows size={18} />, section: 'بانک، کارتخوان و تنخواه' },
      { key: 'possettle', label: 'تسویه کارتخوان', icon: <CreditCard size={18} />, section: 'بانک، کارتخوان و تنخواه' },
      //: «تنخواه‌دار»ِ قبلی تعریف نبود، شارژِ تنخواه بود — کنارِ صورت‌هزینه‌اش می‌نشیند (۱۴۰۵/۰۷/۰۶).
      { key: 'pettyholder', label: 'شارژ تنخواه', icon: <Wallet size={18} />, section: 'بانک، کارتخوان و تنخواه' },
      { key: 'pettyexpense', label: 'صورت هزینه تنخواه', icon: <Receipt size={18} />, section: 'بانک، کارتخوان و تنخواه' },
      { key: 'cashbox', label: 'گردش صندوق', icon: <PiggyBank size={18} />, section: 'مرور و گزارش' },
      { key: 'bankledger', label: 'مرور عملیات بانکی', icon: <ListTree size={18} />, section: 'مرور و گزارش' },
      //: پنج تعریف، یک صفحه با پنج برگه‌ی اکسلی (مرحله‌ی ۲، ۱۴۰۵/۰۷/۰۶) — تب‌هایش زیرِ همین ردیف باز می‌شوند.
      { key: 'cashbank', label: 'حساب‌های نقد و بانک', icon: <Vault size={18} />, section: DEFINITIONS_SECTION },
    ],
  },
  {
    heading: 'دارایی ثابت',
    icon: <Building2 size={17} />,
    items: [{ key: 'fixedassets', label: 'دارایی ثابت', icon: <Building2 size={18} /> }],
  },
  {
    //: «حسابداری» = دفترداری. صفحه‌هایش همه با تمِ اکسلی بازسازی شده‌اند و دست نخوردند؛ فقط ترتیبِ
    //: دسته‌ها عوض شد (۱۴۰۵/۰۷/۰۶): کارِ هرروزه (ثبت، بازبینی، گزارش) بالا، پایانِ دوره بعد، و ساختار
    //: — که سالی یک‌بار ساخته می‌شود — ته و پیش‌فرض بسته. «مرکز هزینه» و سه کارِ ابتدا/پایانِ سال از
    //: «شرکت» به این‌جا آمدند: پایانِ سال پیش از این در سه ماژول پخش بود.
    //: بازچینیِ ۱۴۰۵/۰۷/۰۳ منوهای تکراری را یکی کرد (PROJECT_OVERVIEW §۱۰): «سرفصل جدید» و «فهرست
    //: حساب‌ها» در درختواره، «تبدیل اسناد موقت به دائم» در کارتابل، «صدور سند کل» در گزارش ترازها.
    //: کلیدهای قدیمی از `LEGACY_PAGES` به جای تازه‌شان می‌روند.
    heading: 'حسابداری',
    icon: <BookOpen size={17} />,
    items: [
      { key: 'journalentry', label: 'سند حسابداری', icon: <BookOpen size={18} />, section: 'ثبت سند' },
      { key: 'openingbalance', label: 'مانده اول دوره', icon: <Wallet size={18} />, section: 'ثبت سند' },
      //: این سه فرم و دفترشان را در همان صفحه دارند (RecurringPage، BudgetPage،
      //: CurrenciesPanel) — فرم و دفترشان یکی است، پس عملیات‌اند نه فهرست.
      { key: 'recurringlist', label: 'اسناد تکرارشونده', icon: <Repeat size={18} />, section: 'ثبت سند' },
      { key: 'entrycartable', label: 'کارتابل اسناد موقت', icon: <ClipboardCheck size={18} />, section: 'بازبینی اسناد' },
      { key: 'mergeentries', label: 'ادغام اسناد', icon: <Combine size={18} />, section: 'بازبینی اسناد' },
      { key: 'renumber', label: 'شماره‌گذاری مجدد اسناد', icon: <Hash size={18} />, section: 'بازبینی اسناد' },
      { key: 'accountbrowse', label: 'مرور حساب‌ها', icon: <Layers size={18} />, section: 'گزارش و کنترل' },
      { key: 'balancereport', label: 'گزارش ترازها', icon: <Scale size={18} />, section: 'گزارش و کنترل' },
      { key: 'ledgerreport', label: 'گزارش دفتر', icon: <BookOpenCheck size={18} />, section: 'گزارش و کنترل' },
      { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} />, section: 'گزارش و کنترل' },
      { key: 'vat', label: 'مالیات بر ارزش افزوده', icon: <Percent size={18} />, section: 'گزارش و کنترل' },
      { key: 'ebooks', label: 'دفاتر تجارت الکترونیک', icon: <BookMarked size={18} />, section: 'گزارش و کنترل' },
      { key: 'integrity', label: 'بررسی یکپارچگی', icon: <ShieldCheck size={18} />, section: 'گزارش و کنترل' },
      { key: 'balancereclass', label: 'انتقال مانده به حساب دیگر', icon: <ArrowLeftRight size={18} />, section: 'اصلاح و تعدیل' },
      { key: 'fxrevaluation', label: 'صدور سند تسعیر ارز', icon: <RefreshCcw size={18} />, section: 'اصلاح و تعدیل' },
      { key: 'yearendops', label: 'عملیات پایان سال', icon: <ListChecks size={18} />, section: 'پایان دوره' },
      { key: 'closepnl', label: 'بستن حساب‌های سود و زیان', icon: <CalendarCheck size={18} />, section: 'پایان دوره' },
      { key: 'closingopening', label: 'صدور سند اختتامیه و افتتاحیه', icon: <Archive size={18} />, section: 'پایان دوره' },
      { key: 'openingops', label: 'عملیات اول دوره', icon: <PlayCircle size={18} />, section: 'پایان دوره' },
      { key: 'yearendreminder', label: 'یادآوری عملیات پایان سال', icon: <BellRing size={18} />, section: 'پایان دوره' },
      { key: 'acctchart', label: 'درختواره حساب‌ها', icon: <ListTree size={18} />, section: 'ساختار و تعریف‌ها' },
      { key: 'costcenter', label: 'مرکز هزینه', icon: <Crosshair size={18} />, section: 'ساختار و تعریف‌ها' },
      { key: 'analytics', label: 'تفصیلی سایر', icon: <Tag size={18} />, section: 'ساختار و تعریف‌ها' },
      { key: 'reclassify', label: 'انتقال حساب به سرفصل دیگر', icon: <FolderTree size={18} />, section: 'ساختار و تعریف‌ها' },
      { key: 'currencylist', label: 'ارزها و نرخ ارز', icon: <Coins size={18} />, section: 'ساختار و تعریف‌ها' },
      { key: 'budgetlist', label: 'بودجه‌بندی', icon: <Target size={18} />, section: 'ساختار و تعریف‌ها' },
    ],
  },
  {
    //: کارِ ماهانه اول — «حقوق و دستمزد» (کارکرد و فیش) و قرارداد — و هفت تعریفِ پایه (محل خدمت،
    //: شغل، عوامل، گروه مالیاتی، جداول، نوع وام، سوابقِ پیش از کوبیتا) ته و پیش‌فرض بسته. پیش از این
    //: ترتیب برعکس بود و کلیک روی نامِ ماژول «قرارداد جدید» را باز می‌کرد، نه فیش را.
    heading: 'حقوق و دستمزد',
    icon: <Users size={17} />,
    items: [
      { key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} />, section: DAILY_SECTION },
      { key: 'contractnew', label: 'قرارداد', icon: <FileSignature size={18} />, section: DAILY_SECTION },
      { key: 'employeeloans', label: 'وام‌های پرسنلی', icon: <HandCoins size={18} />, section: DAILY_SECTION },
      { key: 'settlement', label: 'تسویه پایان کار', icon: <DoorOpen size={18} />, section: DAILY_SECTION },
      { key: 'servicelocation', label: 'محل‌های خدمت', icon: <Building size={18} />, section: DEFINITIONS_SECTION },
      { key: 'jobtitle', label: 'مشاغل', icon: <Briefcase size={18} />, section: DEFINITIONS_SECTION },
      { key: 'payrollfactors', label: 'عوامل حقوق و مزایا', icon: <SlidersHorizontal size={18} />, section: DEFINITIONS_SECTION },
      { key: 'payrolltaxgroups', label: 'گروه مالیاتی و شعب', icon: <Percent size={18} />, section: DEFINITIONS_SECTION },
      { key: 'taxtables', label: 'جداول مالیات', icon: <Sheet size={18} />, section: DEFINITIONS_SECTION },
      { key: 'loantype', label: 'انواع وام', icon: <Banknote size={18} />, section: DEFINITIONS_SECTION },
      { key: 'deploymentinfo', label: 'سوابق پیش از کوبیتا', icon: <History size={18} />, section: DEFINITIONS_SECTION },
    ],
  },
  {
    //: فازِ ۱+۲+۳+۴ — چهار عملیاتِ محتوایی و تغییرِ وضعیت. هر پنج فازِ این ماژول
    //: تمام شد (PROJECT_OVERVIEW §۱۰) — تسویه‌حساب تنها سندی است که حسابداریِ
    //: واقعی دارد.
    heading: 'پیمانکاری',
    icon: <HardHat size={17} />,
    items: [
      //: `FileSignature` در lucide نامِ دیگرِ `FilePenLine` است؛ «پیمان» و «متمم پیمان» یک نقش داشتند.
      { key: 'contractingnew', label: 'پیمان', icon: <Handshake size={18} /> },
      { key: 'contractingamendment', label: 'متمم پیمان', icon: <FilePenLine size={18} /> },
      { key: 'contractingstatement', label: 'صورت وضعیت دریافتی', icon: <Receipt size={18} /> },
      { key: 'contractingsettlement', label: 'تسویه حساب پیمان', icon: <HandCoins size={18} /> },
      { key: 'contractingstatus', label: 'تغییر وضعیت پیمان', icon: <RefreshCcw size={18} /> },
    ],
  },
  {
    //: «حسابرسی» — دو عملیات و دو دفتر. صفحه‌ی «درخواست» همیشه دیده می‌شود
    //: (کاربر باید بتواند درخواست بدهد) و «کارنامه» فقط پس از تأییدِ ما.
    heading: 'حسابرسی',
    icon: <ClipboardCheck size={17} />,
    items: [
      { key: 'assurancerequest', label: 'درخواست حسابرسی', icon: <FileSignature size={18} /> },
      { key: 'assurancehealth', label: 'کارنامه سلامت دفتر', icon: <Gauge size={18} /> },
    ],
  },
  {
    heading: 'اتوماسیون اداری',
    icon: <ClipboardList size={17} />,
    items: [
      { key: 'automation', label: 'کارتابل من', icon: <ClipboardList size={18} /> },
      { key: 'letternew', label: 'نامه', icon: <FilePenLine size={18} /> },
    ],
  },
  {
    heading: 'سامانه مؤدیان',
    icon: <FileSpreadsheet size={17} />,
    items: [{ key: 'moadian', label: 'سامانه مؤدیان', icon: <FileSpreadsheet size={18} /> }],
  },
  {
    //: جانشینِ «شرکت» (۱۴۰۵/۰۷/۰۶). «شرکت» شانزده کارِ بی‌ربط را کنارِ هم داشت؛ طرف‌حساب‌ها و
    //: فروشِ اقساطی به «مشتریان و فروش» رفتند، تراکنشِ شریک به «دریافت و پرداخت»، مرکزِ هزینه و
    //: ابتدا/پایانِ سال به «حسابداری». آنچه ماند کارِ هیچ ماژولِ خاصی نیست: گزارش‌های فراماژولی و ابزار.
    heading: 'گزارش و ابزار',
    icon: <BarChart3 size={17} />,
    items: [
      { key: 'mgmtreports', label: 'گزارش‌ها و نمودارهای مدیریتی', icon: <BarChart3 size={18} />, section: 'گزارش' },
      { key: 'reportbuilder', label: 'گزارش‌ساز', icon: <Wrench size={18} />, section: 'گزارش' },
      { key: 'dayactivity', label: 'فعالیت‌های روز', icon: <Activity size={18} />, section: 'گزارش' },
      { key: 'usagereport', label: 'گزارش استفاده از نرم‌افزار', icon: <Gauge size={18} />, section: 'گزارش' },
      { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} />, section: 'ابزار' },
      { key: 'dataexport', label: 'ارسال اطلاعات', icon: <Upload size={18} />, section: 'ابزار' },
      { key: 'dataimport', label: 'دریافت اطلاعات', icon: <Download size={18} />, section: 'ابزار' },
    ],
  },
  {
    //: فقط تنظیماتِ سطحِ شرکت. ترجیح‌های شخصی (رمز، ظاهر، کلیدهای میان‌بر) و راهنما به منوی کاربر
    //: رفتند (`SECONDARY_NAV_ITEMS`)، و «ورود گروهی اشخاص» به «مشتریان و فروش».
    heading: 'تنظیمات',
    icon: <Settings size={17} />,
    items: [
      { key: 'fiscalyear', label: 'سال مالی', icon: <CalendarRange size={18} /> },
      { key: 'coding', label: 'کدینگ', icon: <ListTree size={18} /> },
      { key: 'numbering', label: 'شماره‌گذاری اسناد', icon: <Hash size={18} /> },
      { key: 'personalization', label: 'شخصی‌سازی', icon: <Settings2 size={18} /> },
      { key: 'team', label: 'دعوت کاربر', icon: <UserCog size={18} /> },
      { key: 'backup', label: 'پشتیبان‌گیری خودکار', icon: <DatabaseBackup size={18} /> },
    ],
  },
]

//: کلیدهایی که با سیستمِ شخصی‌سازیِ ماژول گیت می‌شوند. بقیه‌ی ورودی‌های منو (کاربران،
//: تنظیمات، راهنما، ماژول‌های تازه‌ای که هنوز در رجیستریِ بک‌اند نیستند) همیشه دیده
//: می‌شوند — وگرنه با روشنِ‌شدن فیلتر، ناوبریِ سیستمی هم ناپدید می‌شد.
//: صفحه‌هایی که خودشان کلیدِ ماژول نیستند ولی زیرِ چترِ یک ماژول گیت می‌شوند.
//: بدونِ این نگاشت، خاموش‌کردنِ «حسابداری» در شخصی‌سازیِ پنل هجده ورودی را روشن
//: می‌گذاشت — و بدتر، گرنت‌نداشتنِ ماژول هم جلویشان را نمی‌گرفت.
//:
//: مقدارِ آرایه یعنی «هر یک از این ماژول‌ها کافی است» — برای صفحه‌ای که واقعاً مالِ
//: دو ماژول است.
export const PAGE_MODULE_KEY: Partial<Record<PageKey, string | string[]>> = Object.fromEntries(
  (
    [
      'acctchart', 'openingbalance', 'journalentry', 'entrycartable',
      'renumber', 'mergeentries', 'reclassify', 'analytics', 'fxrevaluation', 'balancereclass',
      'closepnl', 'closingopening', 'vat', 'ebooks', 'accountbrowse',
      'balancereport', 'ledgerreport', 'integrity',
      'entrylist', 'recurringlist', 'budgetlist', 'currencylist', 'periodcloselist',
      //: از «شرکت» به «حسابداری» آمدند (۱۴۰۵/۰۷/۰۶). بی‌گیت، گروهِ «حسابداری» برای کسب‌وکارِ بی‌ماژولِ
      //: حسابداری با همین پنج ردیف زنده می‌ماند — بسته‌شدنِ سال و مرکزِ هزینه بی دفترِ حساب معنایی ندارند.
      'costcenter', 'costcenterlist', 'openingops', 'yearendops', 'yearendreminder',
    ] as PageKey[]
  ).map((key) => [key, 'accounting']),
) as Partial<Record<PageKey, string | string[]>>

//: هجده عملیاتِ «دریافت و پرداخت» + فهرستش، همگی زیرِ چترِ ماژولِ `banking`.
for (const key of [
  'payflow', 'receiptvoucher', 'paymentvoucher', 'contactsettle', 'checks',
  'possettle', 'bankreconcile', 'cashbox',
  'cashbank', 'pettyholder', 'pettyexpense', 'bankledger',
  'treasuryledger', 'paymentnoticelist', 'possettlelist',
  'checkoplist', 'contactsettlelist',
  'statementlist', 'pettylist',
  //: «تراکنش شریک» از «شرکت» آمد — همان قاعده‌ی حسابداری: بی‌گیت، گروه را تنها زنده نگه می‌داشت.
  'ownertxn', 'ownertxnlist',
] as PageKey[]) {
  PAGE_MODULE_KEY[key] = 'banking'
}

//: هجده عملیاتِ «فروش» + دوازده دفترش، همگی زیرِ چترِ ماژولِ `sales`. بدونِ این،
//: کسب‌وکاری که ماژولِ فروش را ندارد همه‌ی این منوها را می‌دید.
for (const key of [
  'salesflow', 'salesinvoice', 'quotations', 'salesreturn', 'invoiceclose', 'creditnote',
  'contactstatement', 'commission', 'commissioncalc', 'customs', 'saletype', 'returnreason', 'priceannounce',
  'bundle', 'discount', 'discountgroup', 'markup', 'salesbrowse', 'contactoverview',
  'saleslist', 'quotationlist', 'returnlist', 'notelist', 'commissionrulelist',
  'commissionrunlist', 'customslist', 'saletypelist', 'priceannouncelist', 'bundlelist',
  'pricingfactorlist', 'discountgrouplist',
] as PageKey[]) {
  PAGE_MODULE_KEY[key] = 'sales'
}

//: اعلامیه‌ی بدهکار/بستانکار و دفترش مالِ فروش **یا** خرید‌اند: کسب‌وکاری که فقط
//: خرید دارد هم تهاترِ تأمین‌کننده‌ها را لازم دارد.
PAGE_MODULE_KEY.creditnote = ['sales', 'purchases']
PAGE_MODULE_KEY.notelist = ['sales', 'purchases']

//: «ورود گروهی اشخاص» داده‌اش طرف‌حساب است؛ پس کسب‌وکاری که ماژولِ اشخاص را ندارد نباید ببیندش.
PAGE_MODULE_KEY.contactimport = 'contacts'
PAGE_MODULE_KEY.repair = 'repair'
for (const key of ['automation', 'letternew', 'letterlist'] as PageKey[]) {
  PAGE_MODULE_KEY[key] = 'automation'
}

//: «پیمانکاری» — کلیدِ ماژولِ مجازی، دقیقاً مثلِ `sales`: خودِ `contracting`
//: هیچ‌کدام از این PageKeyها نیست، فقط نگاشتشان می‌کند.
for (const key of [
  'contractingnew',
  'contractingstatus',
  'contractingamendment',
  'contractingstatement',
  'contractingsettlement',
  'contractinglist',
  'contractingamendmentlist',
  'contractingstatementlist',
  'contractingsettlementlist',
] as PageKey[]) {
  PAGE_MODULE_KEY[key] = 'contracting'
}

//: حسابرسی — دو گیتِ متفاوت روی یک ماژول.
//:
//: «درخواست حسابرسی» با ماژولِ عادیِ `assurance` باز است (هر کسب‌وکاری باید
//: بتواند درخواست بدهد)، ولی صفحه‌های کاری با ماژولِ **مشتقِ** `assurance_work`
//: که فقط با قراردادِ تأییدشده وجود دارد. هیچ‌کدام نباید از این نگاشت جا بماند:
//: کلیدی که در هیچ‌یک از دو نگاشت نباشد، `isVisible` را از شاخه‌ی fail-open رد
//: می‌کند و **برای همه** دیده می‌شود.
PAGE_MODULE_KEY.assurancerequest = 'assurance'
for (const key of [
  'assurancehealth',
  'assurancefindinglist',
  'assurancerunlist',
] as PageKey[]) {
  PAGE_MODULE_KEY[key] = 'assurance_work'
}

const GATED_MODULE_KEYS = new Set<PageKey>([
  'overview', 'pos', 'installments', 'crm', 'purchases', 'inventory',
  'manufacturing', 'accounting', 'banking', 'fixedassets', 'payroll',
  'integration', 'calendar', 'contacts', 'reports',
])

//: **مدیریتِ پلتفرم اینجا نیست و نباید برگردد.** چهار منوی «مدیریت سامانه»
//: (مدیریت اکانت‌ها، کمیسیونِ بازار، کارتابلِ حسابرسی، خریدهای سایت) به اپِ
//: مستقلِ `admin/` کوچ کردند — `admin.cubita.ir`. این اپ فقط دفترِ مشتری است.
//: تستِ `navModel.test.ts` نمی‌گذارد هیچ‌کدامشان بی‌صدا برگردند.

//: ورودی‌های منوی کاربر (آواتار در نوار، پایینِ سایدبار). **ترجیح‌های شخصی این‌جایند، نه در
//: «تنظیمات»** (۱۴۰۵/۰۷/۰۶): رمزِ من، ظاهرِ من و کلیدهای میان‌برِ من مالِ کاربرند، نه تنظیمِ شرکت —
//: و «تنظیمات» با آن‌ها دوازده ردیف شده بود. راهنما هم کنارشان است تا در هر دو پوسته یک‌جا باشد.
export const SECONDARY_NAV_ITEMS: NavItem[] = [
  { key: 'profile', label: 'پروفایل من', icon: <UserCircle size={18} /> },
  { key: 'password', label: 'تغییر کلمه عبور', icon: <KeyRound size={18} /> },
  { key: 'theme', label: 'ظاهر و پوسته', icon: <Palette size={18} /> },
  { key: 'shortcuts', label: 'کلیدهای میان‌بر', icon: <Keyboard size={18} /> },
  { key: 'help', label: 'راهنما', icon: <HelpCircle size={18} /> },
]

//: ورودیِ «مجوز نرم‌افزار» — فقط کوبیتا سازمانی. برای همه‌ی اعضا (دیدنِ اینکه چرا
//: ثبت بسته است)؛ خودِ فعال‌سازی داخلِ صفحه مالک‌محور است.
const LICENSE_SETTINGS_ITEM: NavItem = {
  key: 'license',
  label: 'سرور و مجوز',
  icon: <BadgeCheck size={18} />,
}

//: ورودیِ «شخصی‌سازیِ پنل» — فقط برای مالک (روشن/خاموش‌کردنِ ماژول‌ها).
const MODULES_SETTINGS_ITEM: NavItem = {
  key: 'modules',
  label: 'شخصی‌سازیِ پنل',
  icon: <SlidersHorizontal size={18} />,
}

/** آیتم‌های همه‌ی گروه‌ها، **یک بار** هر صفحه.
 *
 *  صفحه‌ای که در دو گروه آمده (اعلامیه بدهکار/بستانکار در فروش و در خرید) در
 *  فهرستِ تخت دو بار نمی‌آید — نه در نتیجه‌ی جست‌وجو، و نه به‌صورتِ کلیدِ تکراریِ React.
 */
export function uniqueNavItems(groups: NavGroup[], extra: NavItem[] = []): NavItem[] {
  const seen = new Set<PageKey>()
  return [...groups.flatMap((g) => g.items), ...extra].filter((i) => {
    if (seen.has(i.key)) return false
    seen.add(i.key)
    return true
  })
}

/** فهرستِ گروه‌ها و آیتم‌های ثانویه را با گیتِ نقش/نوعِ حساب و شخصی‌سازیِ ماژول می‌سازد.
 *  Sidebar و TopNav هر دو همین را صدا می‌زنند تا ناوبری یکسان بماند. */
export function buildNav({
  tenantKind,
  marketplaceRoles,
  enabledModules = [],
  allowedModules = [],
  isOwner = false,
}: {
  tenantKind: string
  marketplaceRoles?: string[]
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
    if (Array.isArray(moduleKey)) return moduleKey.some((k) => visible.has(k))
    if (moduleKey) return visible.has(moduleKey)
    return !GATED_MODULE_KEYS.has(key) || visible.has(key)
  }

  const businessGroups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => isVisible(i.key)),
  })).filter((g) => g.items.length > 0)

  // نقشِ بازار از مجوزِ همین عضو می‌آید؛ fallback فقط برای کلاینتِ قدیمیِ فاقدِ فیلد است.
  const marketRoles = marketplaceRoles ?? (tenantKind === 'retailer' || tenantKind === 'distributor' ? [tenantKind] : [])
  const marketplaceItems: NavItem[] = [
    ...(marketRoles.includes('distributor')
      ? [{ key: 'distributor' as PageKey, label: 'پخشِ من', icon: <Truck size={18} /> }]
      : []),
    ...(marketRoles.includes('retailer')
      ? [{ key: 'marketplace' as PageKey, label: 'بازارِ خرید', icon: <Store size={18} /> }]
      : []),
  ]
  const groups: NavGroup[] = [
    ...businessGroups,
    ...(marketplaceItems.length
      ? [{ heading: 'بازارِ عمده‌فروشی', icon: <Truck size={17} />, items: marketplaceItems }]
      : []),
  ]

  // «شخصی‌سازیِ پنل» (فقط مالک) به انتهای گروهِ «تنظیمات» اضافه می‌شود.
  if (isOwner) {
    const settings = groups.find((g) => g.heading === 'تنظیمات')
    if (settings) settings.items = [...settings.items, MODULES_SETTINGS_ITEM]
  }
  if (isEnterprise) {
    const settings = groups.find((g) => g.heading === 'تنظیمات')
    if (settings) settings.items = [...settings.items, LICENSE_SETTINGS_ITEM]
  }

  return { groups, secondary: [...SECONDARY_NAV_ITEMS] }
}

/**
 * گروه‌هایی که در هر حالت جلوتر از بقیه می‌آیند؛ بقیه ترتیبِ `NAV_GROUPS` را نگه می‌دارند.
 *
 * **فقط ترتیب، نه محتوا** (UI-01 §۵۲). `buildNav` تصمیم می‌گیرد *چه* دیده شود — با
 * ماژول و نقش — و این فقط *کجا*. پس حالت هیچ صفحه‌ای را اضافه یا پنهان نمی‌کند.
 *
 * `NAV_GROUPS` به ترتیبِ گردشِ کارِ کسب‌وکار چیده شده و «حسابداری» در آن هشتم است،
 * بعد از فروش و انبار و تولید. روزِ حسابدار با سند و بانک می‌گذرد، پس آن دو
 * بلافاصله بعد از داشبورد می‌آیند.
 *
 * فقط نوار و سایدبار این را صدا می‌زنند. کارتِ «عملیات» (`groupOf`)، پالتِ فرمان و
 * انتخاب‌گرِ کارت همان ترتیبِ ثابت را می‌خوانند، تا «اولین گروهی که این صفحه را
 * دارد» (اعلامیه بدهکار بستانکار در دو گروه است) با عوض‌شدنِ حالت عوض نشود.
 */
export const MODE_GROUP_ORDER: Record<ExperienceMode, readonly string[]> = {
  accountant: ['میزکار', 'حسابداری', 'دریافت و پرداخت'],
  simple: [],
}

export function orderNavGroups(groups: NavGroup[], mode: ExperienceMode): NavGroup[] {
  const first = MODE_GROUP_ORDER[mode]
  const rank = (g: NavGroup) => {
    const i = first.indexOf(g.heading)
    return i === -1 ? first.length : i
  }
  //: `sort` از ES2019 پایدار است، پس گروه‌های هم‌رتبه ترتیبِ نسبیِ خودشان را نگه می‌دارند.
  return [...groups].sort((a, b) => rank(a) - rank(b))
}

/**
 * صفحه‌ای که کلیک روی نامِ گروه در نوار باز می‌کند، وقتی با پیش‌فرض فرق دارد.
 *
 * پیش‌فرض اولین کارِ گروه است (`groupEntry`). از ۱۴۰۵/۰۷/۰۶ اولین کارِ «حسابداری» خودش «سند
 * حسابداری» است، پس این نگاشت امروز همان پیش‌فرض را می‌گوید — می‌ماند تا اگر ترتیب روزی عوض شد،
 * حسابدار باز هم مستقیم به سند برسد.
 */
export const MODE_GROUP_LANDING: Record<ExperienceMode, Partial<Record<string, PageKey>>> = {
  accountant: { 'حسابداری': 'journalentry' },
  simple: {},
}

export function groupLanding(group: NavGroup, mode: ExperienceMode): PageKey | undefined {
  const key = MODE_GROUP_LANDING[mode][group.heading]
  //: صفحه‌ای که این کسب‌وکار نمی‌بیند مقصد نمی‌شود — حالت ≠ مجوز.
  return key && group.items.some((i) => i.key === key) ? key : undefined
}

/** اولین **کارِ** گروه — صفحه‌ی «مسیرِ کار» (`guide`) راهنماست، نه جایی که با کلیک روی نامِ ماژول
 *  باید فرود آمد. گروهی که فقط راهنما دارد به همان می‌رود. */
export function groupEntry(group: NavGroup): NavItem {
  return group.items.find((i) => !i.guide) ?? group.items[0]
}

/**
 * نامِ گروه روی نوارِ بالا.
 *
 * گروهی که **ذاتاً** تک‌صفحه است («دارایی ثابت»، «داشبورد») نامِ همان صفحه را می‌گیرد. ولی گروهی که
 * فقط برای این کسب‌وکار به یک صفحه رسیده نامِ خودش را نگه می‌دارد: پیش از این «حسابرسی» پیش از تأییدِ
 * قرارداد روی نوار «درخواست حسابرسی» خوانده می‌شد — نامِ یک کار، جای نامِ ماژول.
 */
export function groupBarLabel(group: NavGroup): string {
  if (group.items.length !== 1) return group.heading
  const defined = NAV_GROUPS.find((g) => g.heading === group.heading)
  return !defined || defined.items.length === 1 ? group.items[0].label : group.heading
}

//: صفحه‌هایی که خودشان ردیفِ منوی اصلی دارند، برای هر نوعِ کسب‌وکار. صفحه‌های
//: فهرست (saleslist، …) این‌جا نیستند؛ فقط از منوی گروه باز می‌شوند.
const MENU_PAGE_KEYS = new Set<PageKey>([
  ...NAV_GROUPS.flatMap((g) => g.items.map((i) => i.key)),
  'distributor',
  'marketplace',
])

/**
 * آیا ورودیِ منوی گروه (`LIST_MENUS`/`OPS_MENUS`) برای این کسب‌وکار دیده شود؟
 *
 * این منوها ثابت‌اند، ولی صفحه‌ای که به آن اشاره می‌کنند شاید این‌جا نباشد: ماژولش
 * خاموش است، یا مالِ نوعِ دیگری از کسب‌وکار است («سفارش‌های پخش» فقط برای پخش‌کننده).
 * چنین ورودی‌ای صفحه‌ی خالی باز می‌کرد، پس پنهان می‌شود. صفحه‌ای که اصلاً ردیفِ منو
 * ندارد (صفحه‌ی فهرست) دست نمی‌خورد.
 */
const modulesOf = (key: PageKey): string[] => {
  const mapped = PAGE_MODULE_KEY[key]
  if (mapped === undefined) return [key]
  return Array.isArray(mapped) ? mapped : [mapped]
}

export function menuEntryVisible(key: PageKey, groups: NavGroup[]): boolean {
  if (MENU_PAGE_KEYS.has(key)) return groups.some((g) => g.items.some((i) => i.key === key))
  //: صفحه‌ی **فهرست** ردیفِ منوی اصلی ندارد، پس فیلترِ ناوبری هرگز نمی‌بیندش. تا
  //: امروز این بی‌خطر بود، چون خاموش‌شدنِ یک ماژول همه‌ی صفحه‌های منویش را می‌بُرد و
  //: کارتِ «فهرست» اصلاً ساخته نمی‌شد. ماژولِ حسابرسی این فرض را شکست: صفحه‌ی
  //: «درخواست» همیشه دیده می‌شود، پس گروه زنده می‌ماند و دفترهایش هم — حتی پیش
  //: از تأییدِ قرارداد.
  //:
  //: قاعده: دفتر با همان ماژولی گیت می‌شود که صفحه‌های منویِ هم‌ماژولش. اگر هیچ
  //: صفحه‌ی منویی از آن ماژول زنده نمانده باشد، دفترش هم راهی ندارد.
  const wanted = modulesOf(key)
  if (PAGE_MODULE_KEY[key] === undefined) return true
  return groups.some((g) => g.items.some((i) => modulesOf(i.key).some((m) => wanted.includes(m))))
}

/**
 * ردیف‌های یک گروه، دسته‌به‌دسته — برای تیترهای کوچکِ کارتِ «عملیات» و کشوی موبایل.
 *
 * دسته‌ها به ترتیبِ اولین ظهورشان می‌آیند و ردیف‌های هر دسته ترتیبِ خودشان را نگه می‌دارند؛ پس
 * فهرستی که با ترتیبِ دلخواهِ کاربر مرتب شده هم دسته‌ها را به‌هم نمی‌ریزد. گروهی که ردیف‌هایش دسته
 * ندارند یک دسته‌ی بی‌نام می‌شود — همان فهرستِ یک‌دستِ قبلی، بی‌تیتر.
 */
export function navSections<T extends { section?: string }>(items: readonly T[]): { title: string | null; items: T[] }[] {
  return groupByTitle(items, (it) => it.section)
}

/** همان دسته‌بندی برای ورودی‌های `OPS_MENUS`/`LIST_MENUS` — دسته‌شان در `category` است، چون
 *  `section` آن‌جا تبِ صفحه است. */
export function menuCategories<T extends { category?: string }>(items: readonly T[]): { title: string | null; items: T[] }[] {
  return groupByTitle(items, (it) => it.category)
}

function groupByTitle<T>(items: readonly T[], titleOf: (it: T) => string | undefined): { title: string | null; items: T[] }[] {
  const out: { title: string | null; items: T[] }[] = []
  const at = new Map<string | null, number>()
  for (const it of items) {
    const title = titleOf(it) ?? null
    let i = at.get(title)
    if (i === undefined) {
      i = out.length
      at.set(title, i)
      out.push({ title, items: [] })
    }
    out[i].items.push(it)
  }
  return out
}

/**
 * منوهایی که در بازچینیِ حسابداری (۱۴۰۵/۰۷/۰۳) در صفحه‌ی دیگری ادغام شدند. کلیدِ قدیمی هنوز
 * ممکن است در میان‌برهای ذخیره‌شده‌ی کاربر باشد؛ به‌جای صفحه‌ی خالی، به جای تازه‌اش می‌رود.
 */
export const LEGACY_PAGES: Readonly<Record<string, { page: PageKey; section?: string }>> = {
  newaccount: { page: 'acctchart', section: 'new' },
  accountlist: { page: 'acctchart', section: 'flat' },
  analyticlist: { page: 'analytics' },
  finalizeentries: { page: 'entrycartable' },
  generaldoc: { page: 'balancereport', section: 'general' },
  //: پنج تعریفِ «دریافت و پرداخت» و دو فهرستِ تکراری‌شان در «حساب‌های نقد و بانک» (۱۴۰۵/۰۷/۰۶).
  cashboxes: { page: 'cashbank', section: 'cashboxes' },
  bankaccounts: { page: 'cashbank', section: 'banks' },
  posterminals: { page: 'cashbank', section: 'pos' },
  posterminallist: { page: 'cashbank', section: 'pos' },
  checkbooks: { page: 'cashbank', section: 'checkbooks' },
  checkbooklist: { page: 'cashbank', section: 'checkbooks' },
  //: چهار منوی چک در «چک‌ها» (۱۴۰۵/۰۷/۰۶).
  checkops: { page: 'checks', section: 'receivable' },
  checkpayclear: { page: 'checks', section: 'payable' },
  checkreturn: { page: 'checks', section: 'return' },
  checksearch: { page: 'checks', section: 'search' },
  //: ورودِ صورت‌حساب دکمه‌ای در «مغایرت‌گیری بانکی» شد.
  bankstatement: { page: 'bankreconcile' },
}

/** مقصدِ واقعیِ یک ناوبری — کلیدِ قدیمی به جای تازه‌اش، بقیه همان که بود. */
export function resolveLegacyPage(page: string, section: string | null = null): { page: PageKey; section: string | null } {
  const to = LEGACY_PAGES[page]
  return to ? { page: to.page, section: to.section ?? null } : { page: page as PageKey, section }
}
