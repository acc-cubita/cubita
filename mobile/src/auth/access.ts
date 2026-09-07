/**
 * چه نقشی چه بخشی از اپ را می‌بیند.
 *
 * **مسئله‌ای که حل می‌کند:** تا امروز اپ برای *همه‌ی* نقش‌ها یک منو نشان می‌داد.
 * انباردار و مأمورِ حمل هم تبِ «گزارش» و «اشخاص» را می‌دیدند، رویشان می‌زدند، و
 * ۴۰۳ می‌گرفتند. نشتِ داده نبود — بک‌اند سرِ جایش جلو را می‌گیرد — ولی برای اپی که
 * قرار است دستِ کارمند باشد، تجربه‌ی شکسته‌ای است.
 *
 * **چرا این جدول اینجاست و نه پخش در صفحه‌ها:** هر ورودی باید *دقیقاً* همان مجوزی
 * را بگوید که بک‌اند برای آن اندپوینت اعمال می‌کند. اگر حدس بزنیم، دو حالتِ بد
 * داریم: چیزی را پنهان می‌کنیم که کاربر واقعاً به آن دسترسی دارد، یا چیزی را نشان
 * می‌دهیم که باز هم ۴۰۳ می‌دهد. یک جا بودنشان یعنی قابلِ بازبینی‌اند.
 *
 * منبعِ هر ردیف در کامنتش آمده — از `require_permission(...)`ِ همان روتر.
 */
import type { Me } from '../api/types'
import { hasPermission } from '../api/types'

/** بخش‌های اپ که مجوز می‌خواهند. */
export type Area =
  | 'dashboard'
  | 'reports'
  | 'contacts'
  | 'newInvoice'
  | 'treasury'
  | 'market'
  | 'stock'

/**
 * مجوزِ لازمِ هر بخش — برداشته از خودِ بک‌اند، نه حدس.
 *
 * دقت: «اشخاص» مجوزِ `contacts` **ندارد**؛ بک‌اند رویش
 * `require_permission("invoices", "view")` گذاشته (routers/inventory.py). این
 * دقیقاً همان جایی است که حدس‌زدن نتیجه‌ی غلط می‌داد.
 */
const REQUIRES: Record<Area, { resource: string; action: string }> = {
  // routers/reports.py → require_permission("accounting", "view")
  dashboard: { resource: 'accounting', action: 'view' },
  reports: { resource: 'accounting', action: 'view' },
  // routers/inventory.py، مسیرِ /api/contacts
  contacts: { resource: 'invoices', action: 'view' },
  // routers/invoices.py
  newInvoice: { resource: 'invoices', action: 'create' },
  // routers/treasury.py — عمداً `create` و نه `view`: تنها استفاده‌ی خزانه در
  // موبایل فرمِ *ثبتِ* دریافت/پرداخت است. با `view` دکمه به کسی نشان داده می‌شد
  // که می‌تواند ببیند ولی نمی‌تواند ثبت کند — یعنی همان ۴۰۳ که داریم حذفش می‌کنیم.
  treasury: { resource: 'checks_bank', action: 'create' },
  // routers/marketplace.py
  market: { resource: 'marketplace', action: 'view' },
  // routers/stock_taking.py — عمداً `update` و نه `view`.
  //
  // خواندنِ جلسه `view` می‌خواهد، ولی *شمردن* و *بستنِ جلسه* `update`. با `view`
  // تبِ انبارگردانی به فروشنده و حسابِ دمو هم نشان داده می‌شد؛ صفحه‌ای که همه‌ی
  // دکمه‌هایش خاموش است. این همان تبِ ۴۰۳‌دهنده‌ای است که فازِ ۲ حذفش کرد.
  //
  // در `DEFAULT_ROLES` هیچ نقشی `create` بدونِ `update` ندارد، پس همین یک ردیف
  // هم تب را گیت می‌کند و هم ساختِ جلسه را.
  stock: { resource: 'inventory', action: 'update' },
}

/** آیا این کاربر به این بخش دسترسی دارد؟ */
export function canAccess(me: Me | null, area: Area): boolean {
  if (!me) return false
  const need = REQUIRES[area]
  return hasPermission(me, need.resource, need.action)
}

/**
 * تبِ «بازار» علاوه بر مجوز، نوعِ کسب‌وکار هم می‌خواهد.
 *
 * این دو شرطِ متفاوت‌اند و باید جدا بمانند: یک مالکِ فروشگاهِ معمولی مجوزِ `*`
 * دارد ولی بازار برایش بی‌معنی است، و یک مأمورِ حملِ پخش‌کننده مجوزِ بازار دارد
 * ولی هیچ‌چیزِ دیگری.
 */
export function canSeeMarket(me: Me | null): boolean {
  if (!me) return false
  const isMarketTenant = me.tenant_kind === 'distributor' || me.tenant_kind === 'retailer'
  return isMarketTenant && canAccess(me, 'market')
}

/**
 * آیا این کاربر *هیچ* بخشِ محتوایی را نمی‌بیند؟
 *
 * برای نقش‌هایی مثلِ «مسئولِ حقوق و دستمزد» که هنوز هیچ صفحه‌ای در اپِ موبایل
 * ندارند، جوابْ بله است. (انباردار از فازِ ۴ به بعد دیگر در این دسته نیست.) آن‌وقت اپ باید صادقانه بگوید چرا خالی است — نه اینکه
 * تبِ خالی نشان بدهد یا کاربر را به صفحه‌ای بفرستد که ۴۰۳ می‌دهد.
 */
export function hasNoContent(me: Me | null): boolean {
  if (!me) return false
  return (
    !canAccess(me, 'dashboard') &&
    !canAccess(me, 'contacts') &&
    !canAccess(me, 'stock') &&
    !canSeeMarket(me)
  )
}
