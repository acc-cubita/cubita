/**
 * منویِ اپِ ستاد.
 *
 * عمداً `buildNav`ِ اپِ مشتری نیست و نباید هم باشد: محورِ گیت اینجا **نقشِ
 * ستاد** است، نه ماژولِ فعالِ یک کسب‌وکار. یکی‌کردنشان یعنی دو معنا روی یک
 * سازوکار سوار می‌شد و اولین تغییرِ یکی، دیگری را بی‌صدا می‌شکست.
 *
 * فهرست تخت است چون هست — نُه صفحه سلسله‌مراتب نمی‌خواهد.
 */
import {
  AlertTriangle,
  Briefcase,
  ClipboardCheck,
  CreditCard,
  KeyRound,
  Percent,
  ShieldCheck,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { StaffMe } from './api'

export type PageKey =
  | 'accounts'
  | 'assurance'
  | 'commissions'
  | 'purchases'
  | 'licenses'
  | 'errors'
  | 'staff'

export interface NavItem {
  key: PageKey
  label: string
  icon: LucideIcon
  /** حوزه‌ی مجوز در `app/staff_roles.py`. */
  area: string
  /** فقط مالکِ سامانه. */
  ownerOnly?: boolean
}

export const NAV: NavItem[] = [
  { key: 'accounts', label: 'مدیریت اکانت‌ها', icon: ShieldCheck, area: 'accounts' },
  { key: 'assurance', label: 'کارتابل حسابرسی', icon: ClipboardCheck, area: 'assurance' },
  { key: 'commissions', label: 'کمیسیون بازار', icon: Percent, area: 'commissions' },
  { key: 'purchases', label: 'خریدهای سایت', icon: CreditCard, area: 'billing' },
  { key: 'licenses', label: 'مجوزهای سازمانی', icon: KeyRound, area: 'licenses' },
  { key: 'errors', label: 'گزارش خطاها', icon: AlertTriangle, area: 'errors' },
  { key: 'staff', label: 'کاربران ستاد', icon: Users, area: 'staff', ownerOnly: true },
]

export const PAGE_TITLES: Record<PageKey, string> = {
  accounts: 'مدیریت اکانت‌ها',
  assurance: 'کارتابل حسابرسی',
  commissions: 'کمیسیون بازار',
  purchases: 'خریدهای سایت',
  licenses: 'مجوزهای سازمانی',
  errors: 'گزارش خطاها',
  staff: 'کاربران ستاد',
}

export const FALLBACK_ICON = Briefcase

function can(me: StaffMe, area: string): boolean {
  //: همان معناشناسیِ `staff_roles.has_permission` — وایلدکارد روی حوزه و کنش.
  for (const key of [area, '*']) {
    const actions = me.permissions[key]
    if (actions && (actions.includes('view') || actions.includes('*'))) return true
  }
  return false
}

/**
 * منویی که این کارمند می‌بیند.
 *
 * **این فقط ظاهر است.** گاردِ واقعی سرور است؛ پنهان‌بودنِ یک منو هیچ چیزی را
 * اثبات نمی‌کند و تست‌های بک‌اند همین را جداگانه می‌سنجند.
 */
export function visibleNav(me: StaffMe): NavItem[] {
  return NAV.filter((item) => {
    if (item.ownerOnly) return me.role === 'owner'
    return can(me, item.area)
  })
}
