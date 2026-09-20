import { cloneElement, isValidElement, type ReactElement } from 'react'
import type { LucideIcon } from 'lucide-react'

import type { LaunchIconSource } from '../lib/launchers'

/**
 * آیکنِ یک مقصدِ داشبورد، در اندازه‌ی دلخواه.
 *
 * منبعِ آیکون دو شکل دارد: `NAV_GROUPS` عنصرِ آماده می‌دهد (`<Package size={18} />`)
 * و `OPS_MENUS`/`MODULE_SECTIONS` خودِ کامپوننت را. عنصرِ آماده با `size`ِ تازه کلون
 * می‌شود، پس کارتِ درشتِ داشبورد و ردیفِ ریزِ انتخاب‌گر هر دو از یک منبع می‌آیند و
 * لازم نیست جایی آیکونِ دوم تعریف شود.
 */
export function LaunchIcon({ icon, size }: { icon: LaunchIconSource; size: number }) {
  if (isValidElement(icon)) return cloneElement(icon as ReactElement<{ size?: number }>, { size })
  const Icon = icon as LucideIcon
  return <Icon size={size} />
}
