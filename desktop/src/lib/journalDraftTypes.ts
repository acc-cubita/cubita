/** نوع خالص مشترک main و renderer؛ بدون وابستگی به React یا API مرورگر. */
export interface JournalDraftLine {
  originIndex?: number
  accountId: string
  debit: string
  credit: string
  fxAmount?: string
  trackingNo?: string
  trackingDate?: string
  analyticId?: string
  costCenterId?: string
  description?: string
}
