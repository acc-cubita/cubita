import type { ExperienceMode } from './experienceMode'
import { textMatches } from './faText'
import { launchIndex, type LaunchGroup, type LaunchIconSource } from './launchers'
import type { PageKey } from './navModel'

/**
 * «همه‌ی گزارش‌ها» — فهرستِ یک‌جای هر گزارشی که در برنامه هست (UI-01 §۶۱، Reports Workspace).
 *
 * **چرا لازم شد:** گزارش‌ها در دست‌کم پنج گروهِ منو پخش‌اند (حسابداری، مشتریان و فروش،
 * دریافت و پرداخت، شرکت، سامانه مؤدیان) و صفحه‌ی «گزارش‌ها» خودش می‌نوشت که تراز و دفتر
 * «به جای دیگری منتقل شده‌اند». کسی که دنبالِ یک گزارش است باید می‌دانست زیرِ کدام
 * ماژول است.
 *
 * **هیچ گزارشی این‌جا ساخته نمی‌شود** (§۵۶). هر ردیف به صفحه‌ای می‌رود که همین حالا
 * هست. برچسب، آیکن و گیتِ دسترسی از کاتالوگِ کارت‌ها (`buildLaunchers`) می‌آیند، پس
 * گزارشی که کاربر نمی‌بیند این‌جا هم نمی‌آید — حالت ≠ مجوز.
 */

/** دوازده گزارشِ صفحه‌ی «گزارش‌ها». کلید همان `section`ِ ناوبری است. */
export const REPORT_TABS = [
  { key: 'income-statement', label: 'سود و زیان' },
  { key: 'balance-sheet', label: 'ترازنامه' },
  { key: 'budget', label: 'بودجه در برابر عملکرد' },
  { key: 'cash-flow', label: 'جریان وجوه نقد' },
  { key: 'equity-statement', label: 'تغییرات حقوق صاحبان سهام' },
  { key: 'cost-center', label: 'سود پروژه/مرکز هزینه' },
  { key: 'receivable-aging', label: 'سنی مطالبات' },
  { key: 'payable-aging', label: 'سنی بدهی‌ها' },
  { key: 'contact-statement', label: 'صورت‌حساب اشخاص' },
  { key: 'inventory', label: 'ارزش موجودی انبار' },
  { key: 'kardex', label: 'کاردکس کالا' },
  { key: 'seasonal', label: 'معاملات فصلی (م۱۶۹)' },
] as const

export type ReportKind = (typeof REPORT_TABS)[number]['key']

export function isReportKind(v: unknown): v is ReportKind {
  return REPORT_TABS.some((t) => t.key === v)
}

export type ReportGroupKey = 'ledgers' | 'statements' | 'contacts' | 'treasury' | 'inventory' | 'tax' | 'management'

/**
 * `reports/<کلید>` یکی از دوازده تبِ بالاست؛ بقیه شناسه‌ی کاتالوگِ کارت‌اند
 * (`page` یا `page/section`). `label` فقط وقتی می‌آید که نامِ منو این‌جا، بیرون از
 * گروهِ خودش، مبهم می‌ماند.
 */
interface EntrySpec {
  id: string
  label?: string
}

/**
 * **عمداً بیرون:** «کاردکس کالا»ی انبار و «صورت حساب طرف مقابل»ِ فروش — همان داده‌ی
 * دو تبِ «کاردکس کالا» و «صورت‌حساب اشخاص»، و دو ردیفِ هم‌نام کاربر را وادار می‌کرد
 * حدس بزند کدام را باز کند. «سنین مطالبات»ِ اشخاص هم به همین دلیل.
 */
export const REPORT_GROUPS: { key: ReportGroupKey; heading: string; entries: EntrySpec[] }[] = [
  {
    key: 'ledgers',
    heading: 'دفاتر و ترازها',
    entries: [
      { id: 'balancereport' },
      //: قالبِ «سند کل»ِ همان صفحه — پیش‌تر منوی جدای «صدور سند کل» (بازچینیِ ۱۴۰۵/۰۷/۰۳).
      { id: 'balancereport/general', label: 'سند کل' },
      { id: 'ledgerreport' },
      { id: 'accountbrowse' },
      { id: 'ebooks' },
      { id: 'integrity' },
    ],
  },
  {
    key: 'statements',
    heading: 'صورت‌های مالی',
    entries: [
      { id: 'reports/income-statement' },
      { id: 'reports/balance-sheet' },
      { id: 'reports/cash-flow' },
      { id: 'reports/equity-statement' },
      { id: 'reports/budget' },
      { id: 'reports/cost-center' },
    ],
  },
  {
    key: 'contacts',
    heading: 'اشخاص و فروش',
    entries: [
      { id: 'reports/receivable-aging' },
      { id: 'reports/payable-aging' },
      { id: 'reports/contact-statement' },
      { id: 'contactoverview' },
      { id: 'salesbrowse' },
    ],
  },
  {
    key: 'treasury',
    heading: 'بانک و صندوق',
    entries: [{ id: 'bankledger' }, { id: 'checksearch' }, { id: 'cashbox' }],
  },
  {
    key: 'inventory',
    heading: 'انبار',
    entries: [{ id: 'reports/inventory' }, { id: 'reports/kardex' }, { id: 'inventory/stock' }, { id: 'inventory/low' }],
  },
  {
    key: 'tax',
    heading: 'مالیات',
    entries: [
      { id: 'reports/seasonal' },
      { id: 'vat' },
      { id: 'moadianhistory', label: 'تاریخچه ارسال به سامانه مؤدیان' },
    ],
  },
  {
    key: 'management',
    heading: 'مدیریتی',
    entries: [
      { id: 'mgmtreports' },
      { id: 'dynamicreports' },
      { id: 'reportbuilder' },
      { id: 'dayactivity' },
      { id: 'payslipledger' },
      { id: 'usagereport' },
    ],
  },
]

/**
 * دوازده تب، دسته‌بندی‌شده به **همان** دسته‌های کاتالوگ — سربرگِ صفحه‌ی «گزارش‌ها». از `REPORT_GROUPS`
 * ساخته می‌شود نه فهرستِ دوم، تا تبی که به دسته‌ی دیگری برود در هر دو جا با هم جابه‌جا شود.
 */
export const REPORT_TAB_GROUPS: { key: ReportGroupKey; heading: string; tabs: (typeof REPORT_TABS)[number][] }[] =
  REPORT_GROUPS.map((g) => ({
    key: g.key,
    heading: g.heading,
    tabs: g.entries.flatMap((e) => REPORT_TABS.filter((t) => e.id === `reports/${t.key}`)),
  })).filter((g) => g.tabs.length > 0)

/**
 * ترتیبِ دسته‌ها در هر حالت. حسابدار با دفتر و تراز شروع می‌کند؛ صاحبِ کسب‌وکار با
 * سود و بدهکار — همان دو کارتی که داشبوردِ ساده‌اش هم دارد (§۵۳).
 */
export const MODE_REPORT_ORDER: Record<ExperienceMode, readonly ReportGroupKey[]> = {
  accountant: ['ledgers', 'statements', 'contacts', 'treasury', 'inventory', 'tax', 'management'],
  simple: ['statements', 'contacts', 'inventory', 'treasury', 'tax', 'management', 'ledgers'],
}

export interface ReportEntry {
  id: string
  label: string
  page: PageKey
  section?: string
  icon: LaunchIconSource
}

export interface ReportGroup {
  key: ReportGroupKey
  heading: string
  entries: ReportEntry[]
}

const REPORTS_PREFIX = 'reports/'

/**
 * کاتالوگِ همین کاربر: فقط گزارش‌هایی که می‌بیند، به ترتیبِ حالتش. دسته‌ی خالی نمی‌آید.
 *
 * `launchers` خروجیِ `buildLaunchers(me)` است — همان گیتِ ماژول و نقشی که منو و کارت‌ها
 * دارند. دوازده تبِ «گزارش‌ها» با دیده‌شدنِ خودِ صفحه‌ی `reports` گیت می‌شوند.
 */
export function buildReportCatalog(launchers: LaunchGroup[], mode: ExperienceMode): ReportGroup[] {
  const index = launchIndex(launchers)
  const reportsPage = index.get('reports')
  const byKey = new Map(REPORT_GROUPS.map((g) => [g.key, g]))

  return MODE_REPORT_ORDER[mode]
    .map((key) => byKey.get(key)!)
    .map((g) => ({
      key: g.key,
      heading: g.heading,
      entries: g.entries.flatMap((e): ReportEntry[] => {
        if (e.id.startsWith(REPORTS_PREFIX)) {
          const tab = REPORT_TABS.find((t) => REPORTS_PREFIX + t.key === e.id)
          if (!tab || !reportsPage) return []
          return [{ id: e.id, label: e.label ?? tab.label, page: 'reports', section: tab.key, icon: reportsPage.icon }]
        }
        const t = index.get(e.id)
        if (t) return [{ id: e.id, label: e.label ?? t.label, page: t.page, section: t.section, icon: t.icon }]
        //: قالبی از صفحه‌ای که تب ندارد («سند کل»ِ گزارش ترازها): با دیده‌شدنِ خودِ صفحه گیت می‌شود.
        const [base, section] = e.id.split('/')
        const b = section ? index.get(base) : undefined
        return b && e.label ? [{ id: e.id, label: e.label, page: b.page, section, icon: b.icon }] : []
      }),
    }))
    .filter((g) => g.entries.length > 0)
}

/** صافیِ متنی روی برچسبِ ردیف و نامِ دسته؛ دسته‌ی بی‌ردیف حذف می‌شود. */
export function filterReportCatalog(catalog: ReportGroup[], query: string): ReportGroup[] {
  if (!query.trim()) return catalog
  return catalog
    .map((g) => ({ ...g, entries: g.entries.filter((e) => textMatches(`${e.label} ${g.heading}`, query)) }))
    .filter((g) => g.entries.length > 0)
}
