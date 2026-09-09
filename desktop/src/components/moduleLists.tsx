import {
  fetchContacts,
  fetchCrmActivities,
  fetchEmployees,
  fetchFixedAssets,
  fetchInstallmentPlans,
  fetchItemsLive,
  fetchLeads,
  fetchProductionOrders,
  fetchPurchaseInvoices,
  fetchPurchaseReturns,
  fetchStockAdjustments,
  fetchStockCounts,
  fetchStockTransfers,
} from '../api'
import {
  Activity,
  Archive,
  BarChart3,
  BookMarked,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  Coins,
  Contact2,
  CreditCard,
  DatabaseBackup,
  Download,
  FileCheck2,
  FileSignature,
  FileSpreadsheet,
  FileStack,
  Gauge,
  HandCoins,
  Hash,
  Landmark,
  LayoutList,
  ListChecks,
  ListTree,
  MapPin,
  Receipt,
  Repeat,
  Tag,
  Tags,
  Target,
  Upload,
  UsersRound,
  Wallet,
  Wrench,
  type LucideIcon,
  ClipboardList,
  FileText,
  Undo2,
  Calculator,
  Ship,
  Boxes,
  Percent,
  Layers,
} from 'lucide-react'
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
  'فروش': [
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
    { key: 'recurringlist', label: 'اسناد تکرارشونده', icon: Repeat },
    { key: 'budgetlist', label: 'بودجه‌بندی', icon: Target },
    { key: 'currencylist', label: 'ارزها و نرخ ارز', icon: Coins },
    { key: 'periodcloselist', label: 'دوره‌های بسته‌شده', icon: Archive },
    { key: 'analyticlist', label: 'تفصیلی‌های سایر', icon: Tag },
  ],
  //: «دریافت و پرداخت» — دفترِ رسیدها و اعلامیه‌ها. پیش‌تر تبِ ماژولِ «اشخاص» بود؛
  //: داده‌ی این ماژول در ماژولِ دیگری زندگی می‌کرد.
  'دریافت و پرداخت': [
    { key: 'treasuryledger', label: 'دریافت‌ها و پرداخت‌ها', icon: HandCoins },
    { key: 'checkbooklist', label: 'دسته‌چک‌ها', icon: BookMarked },
    { key: 'bankaccountlist', label: 'حساب‌های بانکی', icon: Landmark },
    { key: 'posterminallist', label: 'دستگاه‌های کارتخوان', icon: CreditCard },
    { key: 'possettlelist', label: 'تسویه‌های کارتخوان', icon: CreditCard },
    { key: 'statementlist', label: 'ردیف‌های صورت‌حساب بانکی', icon: FileSpreadsheet },
    { key: 'pettylist', label: 'گردش تنخواه', icon: Wallet },
  ],
  //: «سامانه مؤدیان» — فهرستِ خودکارِ قبلی (چند ردیفِ آخرِ ارسال‌ها) جایش را به منو
  //: داد: تاریخچه‌ی ارسال یک دفترِ قانونی است و فیلتر و جست‌وجو و خروجی می‌خواهد،
  //: نه یک پیش‌نمایشِ چندردیفی.
  //: «حقوق و دستمزد» — دفترِ نظیرِ «قرارداد جدید». بقیه‌ی منوهای این ماژول
  //: خودشان فهرستِ خودشان را دارند (نگاهی به OPS_LIST_MAP).
  'حقوق و دستمزد': [
    { key: 'contractlist', label: 'قراردادها', icon: FileSignature },
    { key: 'payslipledger', label: 'مرور حقوق', icon: Receipt },
  ],
  'سامانه مؤدیان': [
    { key: 'moadianhistory', label: 'تاریخچه ارسال‌ها', icon: FileCheck2 },
  ],
  //: «شرکت» — سه دسته پشتِ‌هم: تبادل و ساختِ گزارش، گزارش‌های آماده، و فهرستِ
  //: داده‌های پایه. ترتیب همان است که کاربر تعیین کرد.
  'شرکت': [
    { key: 'dataexport', label: 'ارسال اطلاعات', icon: Upload },
    { key: 'dataimport', label: 'دریافت اطلاعات', icon: Download },
    { key: 'reportbuilder', label: 'گزارش‌ساز', icon: Wrench },
    { key: 'dynamicreports', label: 'گزارش‌های پویا', icon: LayoutList },
    { key: 'dayactivity', label: 'فعالیت‌های روز', icon: Activity },
    { key: 'mgmtreports', label: 'گزارش‌ها و نمودارهای مدیریتی', icon: BarChart3 },
    { key: 'usagereport', label: 'گزارش استفاده از نرم‌افزار', icon: Gauge },
    { key: 'contactlist', label: 'طرف حساب‌ها', icon: UsersRound },
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
  saleslist: 'فروش',
  quotationlist: 'فروش',
  returnlist: 'فروش',
  notelist: 'فروش',
  commissionrulelist: 'فروش',
  commissionrunlist: 'فروش',
  customslist: 'فروش',
  saletypelist: 'فروش',
  priceannouncelist: 'فروش',
  bundlelist: 'فروش',
  pricingfactorlist: 'فروش',
  discountgrouplist: 'فروش',
  treasuryledger: 'دریافت و پرداخت',
  checkbooklist: 'دریافت و پرداخت',
  bankaccountlist: 'دریافت و پرداخت',
  posterminallist: 'دریافت و پرداخت',
  possettlelist: 'دریافت و پرداخت',
  statementlist: 'دریافت و پرداخت',
  pettylist: 'دریافت و پرداخت',
  analyticlist: 'حسابداری',
  geolist: 'شرکت',
  contactgrouplist: 'شرکت',
  calendarlist: 'شرکت',
  numberinglist: 'تنظیمات',
  contractlist: 'حقوق و دستمزد',
  payslipledger: 'حقوق و دستمزد',
  moadianhistory: 'سامانه مؤدیان',
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
export type OpsListTarget = PageKey | 'state' | 'view' | 'none'

export const OPS_LIST_MAP: Record<string, OpsListTarget> = {
  // ── دریافت و پرداخت ──
  payflow: 'none', //: راهنمای مسیر
  receiptvoucher: 'treasuryledger', //: سه عملیات، یک دفترِ مشترک با فیلتر
  paymentvoucher: 'treasuryledger',
  contactsettle: 'treasuryledger',
  //: دفترِ چک‌ها همان «جستجوی چک» است — کاربر صریحاً آن را در کارتِ عملیات خواست،
  //: و فهرستِ دومِ چک یعنی دو نمای یک داده.
  checkops: 'checksearch',
  checkbooks: 'checkbooklist',
  checkreturn: 'state',
  checkpayclear: 'state',
  bankreconcile: 'state',
  checksearch: 'view',
  bankledger: 'view',
  cashbox: 'view',
  possettle: 'possettlelist',
  bankstatement: 'statementlist',
  //: «تعریف صندوق» خودش هم فرم است و هم دفترِ صندوق‌ها با مانده‌شان — همان
  //: الگوی «حساب بانکی». فهرستِ نظیرِ جدا یعنی دو نمای یک داده.
  cashboxes: 'view',
  bankaccounts: 'bankaccountlist',
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
  contactnew: 'contactlist',
  installments: 'installmentplans', //: الگوی مرجعِ این قاعده
  costcenter: 'costcenterlist',
  geo: 'geolist',
  contactgroup: 'contactgrouplist',
  calendar: 'calendarlist',
  yearendreminder: 'calendarlist', //: یادآوری‌اش روی همان تقویم می‌نشیند
  openingops: 'none', //: راهنمای مسیر
  yearendops: 'none',

  // ── تنظیمات ──
  fiscalyear: 'fiscalyearlist',
  //: قالبِ صنفی حساب می‌سازد، و دفترِ حساب‌ها همان «فهرست حساب‌ها» است — فهرستِ
  //: دوم یعنی دو نمای یک داده.
  coding: 'accountlist',
  personalization: 'accountlist',
  numbering: 'numberinglist',
  team: 'userlist',
  backup: 'backuplist',
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
  loantype: 'view',
  employeeloans: 'view',
  settlement: 'view',
  deploymentinfo: 'view',
  integration: 'none',
  contracting: 'view',
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
    invoices: def('فاکتورهای خرید', fetchPurchaseInvoices, (r) => ({
      id: r.id,
      title: `فاکتور ${faNum(r.number)}`,
      subtitle: day(r.invoice_date),
      meta: fa(r.total_amount),
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
    transfer: def('انتقال‌های بین انبار', fetchStockTransfers, (r) => ({
      id: r.id,
      title: `انتقال ${faNum(r.number)}`,
      subtitle: r.description || day(r.transfer_date),
      meta: `${faNum(r.lines?.length ?? 0)} قلم`,
    })),
    count: def('انبارگردانی‌ها', fetchStockCounts, (r) => ({
      id: r.id,
      title: `انبارگردانی ${faNum(r.number ?? '')}`.trim(),
      subtitle: r.status ?? '—',
      meta: day(r.count_date ?? r.created_at),
    })),
  },
  contacts: {
    contacts: def('طرف‌حساب‌ها', fetchContacts, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.phone || '—',
      meta: r.type === 'customer' ? 'مشتری' : r.type === 'supplier' ? 'تأمین‌کننده' : 'هر دو',
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
    produce: def('سفارش‌های تولید', fetchProductionOrders, (r) => ({
      id: r.id,
      title: `تولید ${faNum(r.number)}`,
      subtitle: day(r.production_date),
      meta: faNum(r.qty_produced),
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
    __default: def('دارایی‌های ثابت', fetchFixedAssets, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: day(r.purchase_date),
      meta: fa(r.purchase_cost),
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
