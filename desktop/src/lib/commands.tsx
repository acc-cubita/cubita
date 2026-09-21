import { buildNav, uniqueNavItems, type PageKey } from './navModel'
import { TASK_LAUNCHERS } from './taskRegistry'
import type { MeResponse } from '../api'
import type { ReactNode } from 'react'

import { normalizeFa, textMatches } from './faText'

/**
 * فهرستِ «هرجا که می‌شود رفت» — یک منبع برای هر جست‌وجویی که در برنامه هست.
 *
 * پیش از این همین منطق داخلِ `CommandPalette` در یک `useMemo` زندانی بود و
 * جست‌وجوی نوارِ بالا نسخه‌ی خودش را داشت (`label.includes(query)`). دو فهرستِ
 * موازی از یک داده دیر یا زود واگرا می‌شوند — کارها فقط در یکی بودند، و تطبیق
 * در هرکدام جور دیگری کار می‌کرد.
 */
export interface Command {
  id: string
  title: string
  subtitle?: string
  /** متنی که جست‌وجو رویش می‌گردد — عنوان به‌علاوه‌ی هر چیزی که کاربر ممکن است تایپ کند. */
  keywords: string
  icon: ReactNode
  page: PageKey
  section?: string
  kind: 'task' | 'page'
}

//: دوباره export می‌شوند چون چهار مصرف‌کننده و دو تست از همین‌جا واردشان می‌کنند.
export { normalizeFa, textMatches }

/** همان، روی متنِ جست‌وجوپذیرِ یک فرمان. */
export function commandMatches(command: Command, query: string): boolean {
  return textMatches(command.keywords, query)
}

/** فرمان‌های منطبق، حداکثر `limit` تا. بی‌کوئری یعنی همه. */
export function searchCommands(commands: Command[], query: string, limit?: number): Command[] {
  const hits = commands.filter((c) => commandMatches(c, query))
  return limit === undefined ? hits : hits.slice(0, limit)
}

/**
 * هر جایی که این کاربر می‌تواند برود: کارهای `TASK_LAUNCHERS` و بعد صفحه‌های منو.
 *
 * ترتیب عمدی است — کار بالاتر از صفحه می‌آید، چون کسی که «فاکتور فروش» تایپ
 * می‌کند معمولاً می‌خواهد یکی ثبت کند، نه فهرستش را ببیند.
 */
export function buildCommands(me: MeResponse): Command[] {
  const { groups, secondary } = buildNav({
    isPlatformAdmin: me.is_platform_admin,
    isSuperAdmin: me.is_super_admin,
    tenantKind: me.tenant_kind,
    enabledModules: me.enabled_modules,
    allowedModules: me.allowed_modules,
    isOwner: me.role_key === 'owner',
  })

  const tasks: Command[] = TASK_LAUNCHERS.map((t) => ({
    id: `task-${t.key}`,
    title: t.title,
    subtitle: t.desc,
    keywords: `${t.title} ${t.desc}`,
    icon: <t.icon size={16} />,
    page: t.page,
    section: t.section,
    kind: 'task',
  }))

  const pages: Command[] = uniqueNavItems(groups, secondary).map((it) => ({
    id: `page-${it.key}`,
    title: it.label,
    subtitle: 'رفتن به صفحه',
    keywords: it.label,
    icon: it.icon,
    page: it.key,
    kind: 'page',
  }))

  return [...tasks, ...pages]
}
