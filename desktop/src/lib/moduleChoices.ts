import type { ReactNode } from 'react'
import { NAV_GROUPS, PAGE_MODULE_KEY } from './navModel'

type Registry = { core: string[]; optional: string[]; allowed: string[] }
export type ModuleChoice = { key: string; label: string; icon: ReactNode }

/** Module keys belong to the server registry, not to individual pages.
 * A multi-page module (accounting, sales, treasury) has no matching nav item.
 */
export function moduleChoiceGroups(registry: Registry) {
  const groups = new Map<string, ModuleChoice[]>()
  for (const key of new Set([...registry.core, ...registry.optional])) {
    const directGroup = NAV_GROUPS.find((g) => g.items.some((i) => i.key === key))
    const group = directGroup ?? NAV_GROUPS.find((g) =>
      g.items.some((i) => PAGE_MODULE_KEY[i.key] === key),
    )
    const direct = directGroup?.items.find((i) => i.key === key)
    const heading = group?.heading ?? 'سایر ماژول‌ها'
    const item = {
      key,
      label: direct?.label ?? group?.heading ?? 'ماژول جدید',
      icon: direct?.icon ?? group?.icon,
    }
    const items = groups.get(heading) ?? []
    items.push(item)
    groups.set(heading, items)
  }
  return [...groups].map(([heading, items]) => ({ heading, items }))
}

export function toggleableModuleKeys(registry: Registry): string[] {
  return registry.optional.filter((key) => registry.allowed.includes(key) && !registry.core.includes(key))
}
