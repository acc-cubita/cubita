// قراردادِ مشترکِ درایورهای کارتخوان. رابط عمداً کوچک است: pay (ارسالِ مبلغ و گرفتنِ
// نتیجه‌ی کشیدنِ کارت) و status (بررسیِ در دسترس بودنِ دستگاه، برای «تستِ اتصال»).

export type PosTransport = 'simulator' | 'network' | 'serial' | 'sdk'

/** پروفایلِ اتصالِ یک ترمینال که از رابط کاربری پاس می‌شود (نه راز؛ فقط آدرس/پورت). */
export interface PosTerminalProfile {
  transport: PosTransport
  host?: string
  port?: number
  comPort?: string
  /**
   * نرخِ باودِ درگاهِ سریال. **پیش‌فرض ۹۶۰۰ است و تأییدنشده** — مستنداتِ PSP
   * در دست نبود و دستگاهِ آزمایشی هنوز درگاهِ سریال نمی‌سازد. اگر دستگاه
   * چیزِ دیگری بخواهد، همین‌جا عوض می‌شود.
   */
  baudRate?: number
  psp?: string
  // گزینه‌های شبیه‌ساز (فقط وقتی transport === 'simulator')
  simulateOutcome?: 'approve' | 'decline'
  simulateDelayMs?: number
}

/** نتیجه‌ی یک تراکنشِ کارت — چه تأیید شود چه رد. */
export interface PayResult {
  approved: boolean
  /** پیامِ نمایشی (دلیلِ رد یا توضیح). */
  message?: string
  /** شماره‌ی مرجع/پیگیری (RRN) — کلیدِ ثبت و idempotency در حسابداری. */
  rrn?: string
  traceNo?: string
  cardMask?: string
  terminalNo?: string
  /** زمانِ تراکنش به‌صورتِ ISO. */
  datetime?: string
  psp?: string
  /** پاسخِ خامِ دستگاه — برای اشکال‌زدایی. */
  raw?: unknown
}

export interface PosStatus {
  online: boolean
  message?: string
}

export interface PosTerminalDriver {
  pay(amountRial: number, refId: string): Promise<PayResult>
  status(): Promise<PosStatus>
}
