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
  FolderPlus,
  GitCompareArrows,
  Banknote,
  HandCoins,
  HardHat,
  Hash,
  HeartHandshake,
  HelpCircle,
  Keyboard,
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
  PiggyBank,
  PlayCircle,
  Receipt,
  RefreshCcw,
  Route,
  Scale,
  ScanLine,
  ScrollText,
  Search,
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
  UploadCloud,
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
} from 'lucide-react'
import type { ReactNode } from 'react'

import type { ExperienceMode } from './experienceMode'
import { isEnterprise } from '../platform'

// شناسه‌ی هر صفحه‌ی برنامه. منبعِ واحد؛ Sidebar و TopNav هر دو از همین می‌خوانند.
export type PageKey =
  | 'overview'
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
  | 'checkops'
  | 'contactsettle'
  | 'checkreturn'
  | 'checkpayclear'
  | 'checksearch'
  | 'possettle'
  | 'bankstatement'
  | 'bankreconcile'
  | 'cashbox'
  | 'cashboxes'
  | 'bankaccounts'
  | 'posterminals'
  | 'checkbooks'
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
  | 'checkbooklist'
  | 'posterminallist'
  | 'possettlelist'
  | 'contactsettlelist'
  | 'checkoplist'
  | 'statementlist'
  | 'pettylist'
  //: دفترهای نظیرِ ماژول‌های حسابداری، شرکت و تنظیمات.
  | 'analyticlist'
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
  | 'finalizeentries'
  | 'fxrevaluation'
  | 'balancereclass'
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
  | 'integrity'
  //: فهرست‌های حسابداری — از کارتِ «فهرست» باز می‌شوند.
  | 'entrylist'
  | 'accountlist'
  | 'recurringlist'
  | 'budgetlist'
  | 'currencylist'
  | 'periodcloselist'
  //: فهرست‌های حسابرسی
  | 'assurancefindinglist'
  | 'assurancerunlist'

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
    //: «مشتریان و فروش» = طرفِ‌حساب + گردشِ کالا و پولِ فروش، یک گروه — قبلاً دو
    //: گروهِ جدا بودند و کاربر مجبور بود حدس بزند «اشخاص» زیرِ کدام است. ترتیب مسیرِ
    //: کارِ واقعی را دنبال می‌کند: اول طرفِ‌حساب و کانال‌های مشتری (اشخاص، باشگاه،
    //: صندوق)، بعد صدورِ سند (فاکتور، پیش‌فاکتور، برگشتی)، بعد اصلاح و بستن، بعد
    //: پورسانت و گمرک، بعد داده‌های پایه‌ی قیمت‌گذاری، و آخر مرورها.
    heading: 'مشتریان و فروش',
    icon: <ShoppingBag size={17} />,
    items: [
      { key: 'contacts', label: 'اشخاص', icon: <UsersRound size={18} /> },
      { key: 'crm', label: 'باشگاه مشتریان', icon: <HeartHandshake size={18} /> },
      { key: 'pos', label: 'صندوق فروشگاهی', icon: <ScanLine size={18} /> },
      { key: 'salesflow', label: 'فرآیند فروش', icon: <Route size={18} /> },
      { key: 'salesinvoice', label: 'فاکتور فروش', icon: <ShoppingCart size={18} /> },
      { key: 'quotations', label: 'پیش‌فاکتور', icon: <FileText size={18} /> },
      { key: 'salesreturn', label: 'فاکتور برگشتی', icon: <Undo2 size={18} /> },
      { key: 'invoiceclose', label: 'بستن فاکتور', icon: <Lock size={18} /> },
      { key: 'creditnote', label: 'اعلامیه بدهکار بستانکار', icon: <FileSpreadsheet size={18} /> },
      { key: 'contactstatement', label: 'صورت حساب طرف مقابل', icon: <ClipboardList size={18} /> },
      { key: 'commission', label: 'پورسانت', icon: <Wallet size={18} /> },
      { key: 'commissioncalc', label: 'محاسبه پورسانت', icon: <Calculator size={18} /> },
      { key: 'customs', label: 'اظهارنامه گمرکی', icon: <Ship size={18} /> },
      { key: 'saletype', label: 'نوع فروش', icon: <Tags size={18} /> },
      { key: 'returnreason', label: 'علت برگشت کالا', icon: <Undo2 size={18} /> },
      { key: 'priceannounce', label: 'اعلامیه قیمت', icon: <FileSpreadsheet size={18} /> },
      { key: 'bundle', label: 'بسته محصول جدید', icon: <Boxes size={18} /> },
      { key: 'discount', label: 'تخفیف جدید', icon: <Percent size={18} /> },
      { key: 'discountgroup', label: 'گروه کالای تخفیف جدید', icon: <Layers size={18} /> },
      { key: 'markup', label: 'عامل افزاینده جدید', icon: <BadgePercent size={18} /> },
      { key: 'salesbrowse', label: 'مرور فروش', icon: <TrendingUp size={18} /> },
      { key: 'contactoverview', label: 'مرور جامع طرف حساب', icon: <UsersRound size={18} /> },
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
    //: «دریافت و پرداخت» = گردشِ پول. ترتیب عمدی است و مسیرِ کارِ واقعی را دنبال
    //: می‌کند: اول فرآیند و ثبتِ رسید/اعلامیه، بعد چک، بعد بانک و کارتخوان، و آخر
    //: داده‌های پایه (صندوق، حساب، دسته‌چک، تنخواه).
    heading: 'دریافت و پرداخت',
    icon: <HandCoins size={17} />,
    items: [
      { key: 'payflow', label: 'فرآیند دریافت و پرداخت', icon: <Route size={18} /> },
      { key: 'receiptvoucher', label: 'رسید دریافت', icon: <ArrowDownToLine size={18} /> },
      { key: 'paymentvoucher', label: 'اعلامیه پرداخت', icon: <ArrowUpFromLine size={18} /> },
      { key: 'checkops', label: 'عملیات بانکی چک دریافتنی', icon: <ScrollText size={18} /> },
      { key: 'contactsettle', label: 'تسویه حساب طرف مقابل', icon: <Scale size={18} /> },
      { key: 'checkreturn', label: 'استرداد چک', icon: <Undo2 size={18} /> },
      { key: 'checkpayclear', label: 'وصول چک پرداختنی', icon: <Landmark size={18} /> },
      { key: 'checksearch', label: 'جستجوی چک', icon: <Search size={18} /> },
      { key: 'possettle', label: 'تسویه کارت خوان', icon: <CreditCard size={18} /> },
      { key: 'bankstatement', label: 'صورت حساب بانکی', icon: <FileSpreadsheet size={18} /> },
      { key: 'bankreconcile', label: 'مغایرت بانکی', icon: <GitCompareArrows size={18} /> },
      { key: 'cashbox', label: 'صندوق', icon: <PiggyBank size={18} /> },
      { key: 'cashboxes', label: 'تعریف صندوق', icon: <PiggyBank size={18} /> },
      { key: 'bankaccounts', label: 'حساب بانکی', icon: <Landmark size={18} /> },
      { key: 'posterminals', label: 'دستگاه کارت خوان', icon: <CreditCard size={18} /> },
      { key: 'checkbooks', label: 'دسته چک', icon: <BookMarked size={18} /> },
      { key: 'pettyholder', label: 'تنخواه دار', icon: <Wallet size={18} /> },
      { key: 'pettyexpense', label: 'صورت هزینه تنخواه', icon: <Receipt size={18} /> },
      { key: 'bankledger', label: 'مرور عملیات بانکی', icon: <ListTree size={18} /> },
    ],
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
      { key: 'reclassify', label: 'جابه‌جایی حساب در درختواره', icon: <ArrowLeftRight size={18} /> },
      { key: 'analytics', label: 'تفصیلی سایر', icon: <Tag size={18} /> },
      { key: 'fxrevaluation', label: 'صدور سند تسعیر ارز', icon: <Coins size={18} /> },
      { key: 'balancereclass', label: 'اصلاح طبقه‌بندی مانده', icon: <ArrowLeftRight size={18} /> },
      { key: 'generaldoc', label: 'صدور سند کل', icon: <FileSpreadsheet size={18} /> },
      { key: 'closepnl', label: 'بستن حساب‌های سود و زیان', icon: <CalendarCheck size={18} /> },
      { key: 'closingopening', label: 'صدور سند اختتامیه و افتتاحیه', icon: <Archive size={18} /> },
      { key: 'vat', label: 'مالیات بر ارزش افزوده', icon: <Percent size={18} /> },
      { key: 'ebooks', label: 'دفاتر تجارت الکترونیک', icon: <BookMarked size={18} /> },
      { key: 'accountbrowse', label: 'مرور حساب‌ها', icon: <Layers size={18} /> },
      { key: 'balancereport', label: 'گزارش ترازها', icon: <Scale size={18} /> },
      { key: 'ledgerreport', label: 'گزارش دفتر', icon: <BookOpenCheck size={18} /> },
      //: این سه پنلِ سازنده‌ی خودشان را در همان صفحه دارند (RecurringEntriesPanel،
      //: BudgetPanel، CurrenciesPanel) — فرم و دفترشان یکی است، پس عملیات‌اند نه فهرست.
      { key: 'recurringlist', label: 'اسناد تکرارشونده', icon: <Repeat size={18} /> },
      { key: 'budgetlist', label: 'بودجه‌بندی', icon: <Target size={18} /> },
      { key: 'currencylist', label: 'ارزها و نرخ ارز', icon: <Coins size={18} /> },
      { key: 'integrity', label: 'بررسی یکپارچگی', icon: <ShieldCheck size={18} /> },
      { key: 'reports', label: 'گزارش‌ها', icon: <BarChart3 size={18} /> },
    ],
  },
  {
    //: ترتیب عمدی است و همان ترتیبِ کار: اول داده‌های پایه (محل خدمت، شغل، عوامل،
    //: گروه مالیاتی) ساخته می‌شوند، بعد قرارداد که از همه‌ی آن‌ها انتخاب می‌کند.
    //: خودِ «حقوق و دستمزد» سرِ جایش می‌ماند — کارکرد، فیش و مزایا آن‌جاست.
    heading: 'حقوق و دستمزد',
    icon: <Users size={17} />,
    items: [
      { key: 'contractnew', label: 'قرارداد جدید', icon: <FileSignature size={18} /> },
      { key: 'servicelocation', label: 'محل خدمت جدید', icon: <Building size={18} /> },
      { key: 'jobtitle', label: 'شغل جدید', icon: <Briefcase size={18} /> },
      { key: 'payrollfactors', label: 'عوامل حقوق و مزایا', icon: <SlidersHorizontal size={18} /> },
      { key: 'payrolltaxgroups', label: 'گروه مالیاتی و شعب', icon: <Percent size={18} /> },
      { key: 'taxtables', label: 'جداول مالیات', icon: <Percent size={18} /> },
      { key: 'loantype', label: 'نوع وام جدید', icon: <Banknote size={18} /> },
      { key: 'employeeloans', label: 'تقسیط — وام‌های پرسنلی', icon: <HandCoins size={18} /> },
      { key: 'settlement', label: 'تسویه حساب', icon: <Undo2 size={18} /> },
      { key: 'deploymentinfo', label: 'اطلاعات استقرار', icon: <UploadCloud size={18} /> },
      { key: 'payroll', label: 'حقوق و دستمزد', icon: <Users size={18} /> },
    ],
  },
  {
    //: فازِ ۱+۲+۳+۴ — چهار عملیاتِ محتوایی و تغییرِ وضعیت. هر پنج فازِ این ماژول
    //: تمام شد (PROJECT_OVERVIEW §۱۰) — تسویه‌حساب تنها سندی است که حسابداریِ
    //: واقعی دارد.
    heading: 'پیمانکاری',
    icon: <HardHat size={17} />,
    items: [
      { key: 'contractingnew', label: 'پیمان', icon: <FileSignature size={18} /> },
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
      { key: 'ownertxn', label: 'تراکنش شریک', icon: <HandCoins size={18} /> },
      { key: 'installments', label: 'فروش اقساطی', icon: <CalendarClock size={18} /> },
      { key: 'costcenter', label: 'مرکز هزینه', icon: <Target size={18} /> },
      { key: 'geo', label: 'محل‌های جغرافیایی', icon: <MapPin size={18} /> },
      { key: 'contactgroup', label: 'گروه جدید', icon: <Tags size={18} /> },
      { key: 'openingops', label: 'عملیات اول دوره', icon: <PlayCircle size={18} /> },
      { key: 'yearendops', label: 'عملیات پایان سال', icon: <Archive size={18} /> },
      { key: 'yearendreminder', label: 'یادآوری عملیات پایان سال', icon: <BellRing size={18} /> },
      { key: 'calendar', label: 'تقویم و یادآوری', icon: <CalendarDays size={18} /> },
      //: شش ابزارِ زیر تا امروز فقط در کارتِ «فهرست» بودند، ولی دفترِ هیچ عملیاتی
      //: نیستند — خودشان کاری‌اند که اجرا می‌شود. با دامنه‌دارشدنِ کارتِ فهرست،
      //: جایشان این‌جاست وگرنه از هیچ‌جا باز نمی‌شدند.
      { key: 'dataexport', label: 'ارسال اطلاعات', icon: <Upload size={18} /> },
      { key: 'dataimport', label: 'دریافت اطلاعات', icon: <Download size={18} /> },
      { key: 'reportbuilder', label: 'گزارش‌ساز', icon: <Wrench size={18} /> },
      { key: 'dayactivity', label: 'فعالیت‌های روز', icon: <Activity size={18} /> },
      { key: 'mgmtreports', label: 'گزارش‌ها و نمودارهای مدیریتی', icon: <BarChart3 size={18} /> },
      { key: 'usagereport', label: 'گزارش استفاده از نرم‌افزار', icon: <Gauge size={18} /> },
    ],
  },
  {
    heading: 'تنظیمات',
    icon: <Settings size={17} />,
    items: [
      { key: 'fiscalyear', label: 'سال مالی', icon: <CalendarRange size={18} /> },
      { key: 'coding', label: 'کدینگ', icon: <ListTree size={18} /> },
      { key: 'personalization', label: 'شخصی‌سازی', icon: <Settings2 size={18} /> },
      { key: 'shortcuts', label: 'کلیدهای میان‌بر', icon: <Keyboard size={18} /> },
      { key: 'numbering', label: 'روش‌های شماره‌گذاری', icon: <Hash size={18} /> },
      { key: 'contactimport', label: 'ورود گروهی اشخاص', icon: <FileUp size={18} /> },
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
//:
//: مقدارِ آرایه یعنی «هر یک از این ماژول‌ها کافی است» — برای صفحه‌ای که واقعاً مالِ
//: دو ماژول است.
export const PAGE_MODULE_KEY: Partial<Record<PageKey, string | string[]>> = Object.fromEntries(
  (
    [
      'acctchart', 'newaccount', 'openingbalance', 'journalentry', 'entrycartable', 'finalizeentries',
      'renumber', 'mergeentries', 'reclassify', 'analytics', 'fxrevaluation', 'balancereclass',
      'generaldoc', 'closepnl', 'closingopening', 'vat', 'ebooks', 'accountbrowse',
      'balancereport', 'ledgerreport', 'integrity',
      'entrylist', 'accountlist', 'recurringlist', 'budgetlist', 'currencylist', 'periodcloselist',
    ] as PageKey[]
  ).map((key) => [key, 'accounting']),
) as Partial<Record<PageKey, string | string[]>>

//: هجده عملیاتِ «دریافت و پرداخت» + فهرستش، همگی زیرِ چترِ ماژولِ `banking`.
for (const key of [
  'payflow', 'receiptvoucher', 'paymentvoucher', 'checkops', 'contactsettle', 'checkreturn',
  'checkpayclear', 'checksearch', 'possettle', 'bankstatement', 'bankreconcile', 'cashbox', 'cashboxes',
  'bankaccounts', 'posterminals', 'checkbooks', 'pettyholder', 'pettyexpense', 'bankledger',
  'treasuryledger', 'paymentnoticelist', 'checkbooklist', 'posterminallist', 'possettlelist',
  'checkoplist', 'contactsettlelist',
  'statementlist', 'pettylist',
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

//: دفترِ «تفصیلی سایر» زیرِ چترِ حسابداری است، مثلِ بقیه‌ی فهرست‌های آن ماژول.
PAGE_MODULE_KEY.analyticlist = 'accounting'

//: «ورود گروهی اشخاص» در گروهِ «تنظیمات» می‌نشیند ولی داده‌اش طرف‌حساب است؛ پس
//: کسب‌وکاری که ماژولِ اشخاص را ندارد نباید ببیندش.
PAGE_MODULE_KEY.contactimport = 'contacts'

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

//: ورودی‌های پایینِ سایدبار/منوی کاربر. «ظاهر» و «راهنما» به گروهِ «تنظیمات» منتقل
//: شدند تا در ساختارِ تازه‌ی ماژول‌ها یک‌جا جمع باشند.
export const SECONDARY_NAV_ITEMS: NavItem[] = [
  { key: 'profile', label: 'پروفایل من', icon: <UserCircle size={18} /> },
]

//: ورودیِ «مجوز نرم‌افزار» — فقط کوبیتا سازمانی. برای همه‌ی اعضا (دیدنِ اینکه چرا
//: ثبت بسته است)؛ خودِ فعال‌سازی داخلِ صفحه مالک‌محور است.
const LICENSE_SETTINGS_ITEM: NavItem = {
  key: 'license',
  label: 'مجوز و به‌روزرسانی',
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
  enabledModules = [],
  allowedModules = [],
  isOwner = false,
}: {
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
    if (Array.isArray(moduleKey)) return moduleKey.some((k) => visible.has(k))
    if (moduleKey) return visible.has(moduleKey)
    return !GATED_MODULE_KEYS.has(key) || visible.has(key)
  }

  const businessGroups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => isVisible(i.key)),
  })).filter((g) => g.items.length > 0)

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
 * پیش‌فرض اولین صفحه‌ی گروه است؛ برای «حسابداری» یعنی «درختواره حساب‌ها» — ساختنِ
 * چارت، که کاری یک‌باره است. کارِ هرروزه‌ی حسابدار ثبتِ سند است.
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
