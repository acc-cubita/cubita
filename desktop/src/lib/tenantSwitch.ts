/**
 * تصمیمِ «آیا الان می‌شود کسب‌وکار را عوض کرد؟»
 *
 * **چرا این یک گارد است و نه یک گزارش** — برخلافِ قاعده‌ی معمولِ این پروژه.
 *
 * کشِ محلیِ الکترون (`electron/db.ts`) هیچ ستونِ مستأجر ندارد؛ نه جدول‌های کش و
 * نه **صفِ خروجی**. یعنی سندی که آفلاین برای کسب‌وکارِ الف در صف نشسته، اگر
 * کاربر به ب برود، **به ب ثبت می‌شود** — فاکتور یا سندِ حسابداری در کسب‌وکارِ
 * اشتباه.
 *
 * «گزارش، نه گارد» برای جایی است که کاربر بتواند تصمیم بگیرد و اشتباهش
 * برگشت‌پذیر باشد. این‌جا اشتباه یک سندِ مالی در دفترِ دیگری است و کاربر هم
 * نمی‌بیند دارد چه می‌کند. پس بسته می‌شود تا وقتی صف خالی شود.
 *
 * راهِ اصولی‌اش مستأجر‌محورکردنِ کشِ محلی است؛ تا آن روز، این.
 */

export interface SwitchContext {
  /** شناسه‌ی کسب‌وکارِ فعلی. */
  currentTenantId: string
  /** مقصد. */
  targetTenantId: string
  /** رکوردهای همگام‌نشده‌ی صفِ آفلاین. در وب همیشه صفر. */
  pendingOutbox: number
  /** آیا نسخه‌ی دسکتاپ است — فقط آن کشِ محلی دارد. */
  isDesktop: boolean
}

export type SwitchDecision =
  | { allowed: true }
  | { allowed: false; reason: 'same' | 'pending-outbox'; message: string }

export function canSwitchTenant(ctx: SwitchContext): SwitchDecision {
  if (ctx.targetTenantId === ctx.currentTenantId) {
    return { allowed: false, reason: 'same', message: 'همین کسب‌وکار الان باز است.' }
  }
  //: گارد فقط در دسکتاپ معنا دارد؛ در وب صفِ محلی وجود ندارد.
  if (ctx.isDesktop && ctx.pendingOutbox > 0) {
    return {
      allowed: false,
      reason: 'pending-outbox',
      message:
        `${ctx.pendingOutbox.toLocaleString('fa-IR')} سندِ همگام‌نشده در صف دارید. ` +
        'پیش از تعویضِ کسب‌وکار همگامشان کنید — وگرنه در کسب‌وکارِ تازه ثبت می‌شوند.',
    }
  }
  return { allowed: true }
}
