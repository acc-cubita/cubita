import { apiGet, apiPost } from './client'
import type { MpConnection, MpMessage, MpMessagesPage, MpOrder } from './types'

// بازارِ عمده‌فروشی + چت. مسیرها بسته به نقشِ حساب (پخش‌کننده/فروشگاه) فرق دارند.

// ── اتصال‌ها ────────────────────────────────────────────────────────────────
export const listDistributorConnections = () =>
  apiGet<MpConnection[]>('/api/marketplace/distributor/connections')
export const listRetailerConnections = () =>
  apiGet<MpConnection[]>('/api/marketplace/retailer/connections')
export const setConnectionStatus = (id: string, status: 'approved' | 'rejected' | 'blocked') =>
  apiPost<MpConnection>(`/api/marketplace/distributor/connections/${id}/status`, { status })

// ── سفارش‌ها ───────────────────────────────────────────────────────────────
export const listDistributorOrders = () => apiGet<MpOrder[]>('/api/marketplace/distributor/orders')
export const listRetailerOrders = () => apiGet<MpOrder[]>('/api/marketplace/retailer/orders')
export const confirmOrder = (id: string) =>
  apiPost<MpOrder>(`/api/marketplace/distributor/orders/${id}/confirm`, {})
export const rejectOrder = (id: string) =>
  apiPost<MpOrder>(`/api/marketplace/distributor/orders/${id}/reject`, {})
/**
 * ثبتِ تحویل — نقطه‌ی ورودِ کالا به انبارِ فروشگاه.
 *
 * `cash_percent` سهمِ نقدِ دریافتی هنگامِ تحویل است (بقیه اعتباری). اپ آن را از
 * روی *مبلغِ* واردشده می‌سازد؛ چرایی و محاسبه در `market/cod.ts`.
 */
export const deliverOrder = (id: string, cashPercent: string) =>
  apiPost<MpOrder>(`/api/marketplace/distributor/orders/${id}/deliver`, {
    cash_percent: cashPercent,
  })

// ── چت (اتصال و سفارش) ─────────────────────────────────────────────────────
export const getConnectionMessages = (id: string) =>
  apiGet<MpMessagesPage>(`/api/marketplace/connections/${id}/messages`)
export const postConnectionMessage = (id: string, body: string) =>
  apiPost<MpMessage>(`/api/marketplace/connections/${id}/messages`, { body })
export const getOrderMessages = (id: string) =>
  apiGet<MpMessagesPage>(`/api/marketplace/orders/${id}/messages`)
export const postOrderMessage = (id: string, body: string) =>
  apiPost<MpMessage>(`/api/marketplace/orders/${id}/messages`, { body })

// ── نشانِ خوانده‌نشده (جمعِ همه‌ی رشته‌ها) ───────────────────────────────────
export const fetchUnread = () => apiGet<number>('/api/marketplace/unread')

// برچسب‌های فارسیِ وضعیت
export const CONN_STATUS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'muted' }> = {
  pending: { label: 'در انتظارِ تأیید', tone: 'warning' },
  approved: { label: 'تأییدشده', tone: 'success' },
  rejected: { label: 'ردشده', tone: 'danger' },
  blocked: { label: 'مسدود', tone: 'danger' },
}
/**
 * وضعیتِ سفارش — برداشته از `ORDER_STATUSES` در `models/marketplace.py`.
 *
 * ⚠️ نسخه‌ی قبلی از روی *وضعیتِ اتصال* کپی شده بود و «pending» داشت، که اصلاً
 * وضعیتِ سفارش نیست. نتیجه: سفارشِ تازه برچسبِ خامِ «placed» می‌گرفت و شرطِ
 * `status === 'pending'` هرگز درست نمی‌شد — یعنی دکمه‌های تأیید/رد **هیچ‌وقت**
 * روی موبایل ظاهر نمی‌شدند و پخش‌کننده از گوشی نمی‌توانست سفارش را تأیید کند.
 */
export const ORDER_STATUS: Record<
  MpOrder['status'],
  { label: string; tone: 'success' | 'warning' | 'danger' | 'muted' }
> = {
  placed: { label: 'در انتظارِ تأیید', tone: 'warning' },
  confirmed: { label: 'تأییدشده — آماده‌ی تحویل', tone: 'success' },
  delivered: { label: 'تحویل‌شده', tone: 'success' },
  shipped: { label: 'ارسال‌شده', tone: 'success' },
  received: { label: 'تحویل‌شده', tone: 'success' },
  rejected: { label: 'ردشده', tone: 'danger' },
  cancelled: { label: 'لغوشده', tone: 'muted' },
}
