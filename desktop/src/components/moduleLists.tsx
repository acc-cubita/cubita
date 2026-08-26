import {
  fetchChecks,
  fetchContacts,
  fetchCrmActivities,
  fetchEmployees,
  fetchFixedAssets,
  fetchInstallmentPlans,
  fetchItemsLive,
  fetchJournalEntries,
  fetchLeads,
  fetchMoadianSubmissions,
  fetchProductionOrders,
  fetchPurchaseInvoices,
  fetchPurchaseReturns,
  fetchRecurringEntries,
  fetchSalesInvoices,
  fetchSalesQuotations,
  fetchSalesReturns,
  fetchStockAdjustments,
  fetchStockCounts,
  fetchStockTransfers,
  fetchTreasuryTransactions,
} from '../api'
import { CalendarRange, DatabaseBackup, UsersRound, type LucideIcon } from 'lucide-react'
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
const MOADIAN_STATUS: Record<string, string> = {
  pending: 'در صف', sent: 'ارسال‌شده', confirmed: 'تأییدشده',
  rejected: 'ردشده', failed: 'ناموفق',
}

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
  'تنظیمات': [
    { key: 'backuplist', label: 'نسخه‌های پشتیبانی و بازیابی', icon: DatabaseBackup },
    { key: 'userlist', label: 'کاربران', icon: UsersRound },
    { key: 'fiscalyearlist', label: 'سال‌های مالی', icon: CalendarRange },
  ],
}

/**
 * صفحه‌های فهرست در هیچ گروهی از منو نیستند (وگرنه در کارتِ «عملیات» هم تکرار
 * می‌شدند)، ولی وقتی بازند باید همان دو کارتِ ماژولِ خودشان را کنارشان داشته باشند —
 * وگرنه کاربر بدونِ راهِ برگشت می‌ماند. این نگاشت همان پیوند را می‌سازد.
 */
export const LIST_PAGE_GROUP: Partial<Record<PageKey, string>> = {
  backuplist: 'تنظیمات',
  userlist: 'تنظیمات',
  fiscalyearlist: 'تنظیمات',
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
  sales: {
    invoices: def('فاکتورهای فروش', fetchSalesInvoices, (r) => ({
      id: r.id,
      title: `فاکتور ${faNum(r.number)}`,
      subtitle: day(r.invoice_date),
      meta: fa(r.total_amount),
    })),
    quotations: def('پیش‌فاکتورها', fetchSalesQuotations, (r) => ({
      id: r.id,
      title: `پیش‌فاکتور ${faNum(r.number)}`,
      subtitle: r.customer_name || day(r.quotation_date),
      meta: fa(r.total_amount),
    })),
    returns: def('برگشت از فروش', fetchSalesReturns, (r) => ({
      id: r.id,
      title: `برگشتی ${faNum(r.number)}`,
      subtitle: day(r.return_date),
      meta: fa(r.total_amount),
    })),
    moadian: def('صورتحساب‌های ارسالی', fetchMoadianSubmissions, (r) => ({
      id: r.id,
      title: `صورتحساب ${faNum(r.serial)}`,
      subtitle: MOADIAN_STATUS[r.status] ?? r.status,
      meta: day(r.invoice_date),
    })),
  },
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
  accounting: {
    journal: def('اسنادِ ثبت‌شده', fetchJournalEntries, (r) => ({
      id: r.id,
      title: `سند ${faNum(r.number)}`,
      subtitle: r.description || day(r.entry_date),
      meta: day(r.entry_date),
    })),
    daybook: def('اسنادِ ثبت‌شده', fetchJournalEntries, (r) => ({
      id: r.id,
      title: `سند ${faNum(r.number)}`,
      subtitle: r.description || '—',
      meta: day(r.entry_date),
    })),
    recurring: def('اسنادِ تکرارشونده', fetchRecurringEntries, (r) => ({
      id: r.id,
      title: r.title,
      subtitle: r.is_active ? 'فعال' : 'غیرفعال',
      meta: day(r.next_run_date),
    })),
  },
  banking: {
    checks: def('چک‌ها', fetchChecks, (r) => ({
      id: r.id,
      title: `چک ${r.number}`,
      subtitle: `${r.bank_name ?? ''} — ${r.status ?? ''}`.trim(),
      meta: fa(r.amount),
    })),
  },
  contacts: {
    contacts: def('طرف‌حساب‌ها', fetchContacts, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.phone || '—',
      meta: r.type === 'customer' ? 'مشتری' : r.type === 'supplier' ? 'تأمین‌کننده' : 'هر دو',
    })),
    treasury: def('دریافت و پرداخت‌ها', fetchTreasuryTransactions, (r) => ({
      id: r.id,
      title: r.type === 'receipt' ? 'دریافت' : 'پرداخت',
      subtitle: r.contact_name || '—',
      meta: fa(r.amount),
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
  moadian: {
    __default: def('صورتحساب‌های ارسالی', fetchMoadianSubmissions, (r) => ({
      id: r.id,
      title: `صورتحساب ${faNum(r.serial)}`,
      subtitle: MOADIAN_STATUS[r.status] ?? r.status,
      meta: day(r.invoice_date),
    })),
  },
}

/** تعریفِ فهرستِ عملیاتِ فعال — با fallback به `__default` برای ماژول‌های بدونِ تب. */
export function listDefFor(page: PageKey, section: string | null): ListDef | null {
  const mod = MODULE_LISTS[page]
  if (!mod) return null
  return mod[section ?? '__default'] ?? mod.__default ?? null
}
