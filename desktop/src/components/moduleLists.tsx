import {
  fetchChecks,
  fetchContacts,
  fetchCrmActivities,
  fetchEmployees,
  fetchFiscalYears,
  fetchMembers,
  fetchNumbering,
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
import type { PageKey } from './Sidebar'
import { isElectron } from '../platform'
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

const MEMBER_STATUS: Record<string, string> = {
  active: 'فعال', invited: 'در انتظار دعوت', disabled: 'غیرفعال',
}

/** فهرستِ کاربران از یک شیء می‌آید نه آرایه؛ این‌جا به شکلِ مشترک درمی‌آید. */
const listMembers = (token: string) => fetchMembers(token).then((d) => d.members)

/**
 * نسخه‌های پشتیبان روی دیسکِ خودِ کاربرند، نه روی سرور — پس برخلافِ بقیه‌ی فهرست‌ها
 * توکن نمی‌گیرد. در نسخه‌ی وب پوشه‌ای وجود ندارد و فهرست خالی می‌ماند، که همان
 * حقیقت است: پشتیبانِ محلی فقط در دسکتاپ هست.
 */
const listLocalBackups = () =>
  isElectron ? window.cubita.backupListLocal() : Promise.resolve([])

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
  // ── ماژولِ تنظیمات ──────────────────────────────────────────────────────
  // چهار فهرست: نسخه‌های پشتیبان، کاربران، روش‌های شماره‌گذاری، و سال‌های مالی.
  backup: {
    __default: def('نسخه‌های پشتیبان', listLocalBackups, (r) => ({
      id: r.file,
      title: new Date(r.mtime).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' }),
      subtitle: r.file,
      meta:
        r.size < 1048576
          ? `${faNum(Math.round(r.size / 1024))} کیلوبایت`
          : `${(r.size / 1048576).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} مگابایت`,
    })),
  },
  team: {
    __default: def('کاربران', listMembers, (r) => ({
      id: r.id,
      title: r.name,
      subtitle: r.email,
      meta: MEMBER_STATUS[r.status] ?? r.status,
    })),
  },
  numbering: {
    __default: def('روش‌های شماره‌گذاری', fetchNumbering, (r) => ({
      id: r.doc_type,
      title: r.label,
      subtitle: r.last_number === 0 ? 'هنوز سندی ثبت نشده' : `آخرین شماره ${faNum(r.last_number)}`,
      meta: `بعدی ${faNum(r.next_number)}`,
    })),
  },
  fiscalyear: {
    __default: def('سال‌های مالی', fetchFiscalYears, (r) => ({
      id: r.id,
      title: r.title,
      subtitle: `${day(r.start_date)} تا ${day(r.end_date)}`,
      meta: r.status === 'closed' ? 'بسته' : r.is_active ? 'جاری' : 'باز',
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
