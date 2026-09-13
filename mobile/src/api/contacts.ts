import { apiGet, apiGetAll } from './client'
import type { Contact, ContactStatement, CreditStatus } from './types'

// اشخاص/طرف‌حساب‌ها. فهرست صفحه‌بندیِ keyset است (بی‌جست‌وجوی سرور)، پس همه را
// می‌گیریم و سمتِ کلاینت فیلتر می‌کنیم — برای تعدادِ معمولِ کسب‌وکار سبک است.

export const fetchContacts = () => apiGetAll<Contact>('/api/contacts')
export const fetchContactStatement = (id: string) =>
  apiGet<ContactStatement>(`/api/reports/contact-statement/${id}`)
export const fetchCreditStatus = (id: string) => apiGet<CreditStatus>(`/api/contacts/${id}/credit`)

export const KIND_LABEL: Record<string, string> = {
  sales_invoice: 'فاکتور فروش',
  sales_return: 'برگشت از فروش',
  purchase_invoice: 'فاکتور خرید',
  purchase_return: 'برگشت از خرید',
  receipt: 'دریافت',
  payment: 'پرداخت',
  //: کلیدهای قانونیِ دیگرِ کارتِ حساب — بدونِ این‌ها ردیف با کلیدِ خام دیده می‌شد.
  credit_debit_note: 'اعلامیه بدهکار/بستانکار',
  check: 'چک',
  opening: 'مانده اول دوره',
}
