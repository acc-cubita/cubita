import type { SalesInvoiceRecord } from '../api'

/**
 * پیامِ بعد از ثبتِ فاکتور فروش — **از پاسخِ سرور، نه از حدس**.
 *
 * کسب‌وکار یکی از دو سیاست را دارد (`services/sales_posting.py`): «خودکار» (پیش‌فرض)
 * که سندِ حسابداری و خروجِ انبار را همان لحظه می‌زند، و «دومرحله‌ای» که هر دو را به
 * فهرستِ فاکتورها می‌سپارد. پیامِ پیشین همیشه دومی را می‌گفت — «سند و خروج را از
 * فهرست صادر کنید» — پس کاربرِ حالتِ پیش‌فرض دنبالِ کاری می‌گشت که از قبل انجام شده
 * بود، و اگر انجامش می‌داد با خطای «از قبل صادر شده» روبه‌رو می‌شد.
 *
 * `accounting_status` و `fulfillment_status`ِ پاسخ دقیقاً می‌گویند چه شد؛ پیام همان
 * را بازگو می‌کند. فاکتورِ خدماتی خروجِ انبار ندارد (`not_applicable`).
 */
export function salesInvoiceSavedMessage(
  inv: Pick<SalesInvoiceRecord, 'accounting_status' | 'fulfillment_status'>,
): string {
  const posted = inv.accounting_status === 'posted'
  const issued = inv.fulfillment_status === 'fully_issued' || inv.fulfillment_status === 'not_applicable'
  if (posted && issued) {
    return inv.fulfillment_status === 'not_applicable'
      ? 'فاکتور ثبت شد و سندِ حسابداری‌اش هم صادر شد.'
      : 'فاکتور ثبت شد؛ سندِ حسابداری و خروجِ انبار هم خودکار صادر شدند.'
  }
  const pending = [!posted && 'سندِ حسابداری', !issued && 'خروجِ انبار'].filter(Boolean).join(' و ')
  return `فاکتور ثبت شد؛ ${pending} را از فهرستِ فاکتورها صادر کنید.`
}
