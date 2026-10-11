import { describe, expect, it } from 'vitest'
import { moduleChoiceGroups, toggleableModuleKeys } from './moduleChoices'
import { buildNav } from './navModel'

const core = ['overview', 'contacts', 'reports']
const optional = ['automation', 'sales', 'pos', 'installments', 'crm', 'purchases', 'inventory', 'manufacturing', 'contracting', 'accounting', 'banking', 'fixedassets', 'payroll', 'integration', 'calendar', 'assurance']
const registry = { core, optional, allowed: [...core, ...optional] }

describe('شخصی‌سازی با کلید ماژول، نه صفحه', () => {
  it('هر ماژول رجیستری دقیقاً یک گزینه دارد، حتی ماژول چندصفحه‌ای', () => {
    const items = moduleChoiceGroups(registry).flatMap((g) => g.items)
    expect(items.map((i) => i.key).sort()).toEqual([...core, ...optional].sort())
    expect(items.find((i) => i.key === 'accounting')?.label).toBe('حسابداری')
    expect(items.find((i) => i.key === 'banking')?.label).toBe('دریافت و پرداخت')
    expect(items.find((i) => i.key === 'sales')?.label).toBe('مشتریان و فروش')
  })
  it('همه، صفحات سند و فروش و دریافت را در ناوبری حفظ می‌کند', () => {
    const enabled = [...core, ...toggleableModuleKeys(registry)]
    const pages = buildNav({ tenantKind: 'standard', enabledModules: enabled, allowedModules: registry.allowed }).groups.flatMap((g) => g.items.map((i) => i.key))
    expect(pages).toContain('journalentry')
    expect(pages).toContain('salesinvoice')
    expect(pages).toContain('receiptvoucher')
  })
  it('ماژول بدون مجوز و هسته با همه قابل تغییر نیستند', () => {
    expect(toggleableModuleKeys({ ...registry, allowed: core.concat('accounting') })).toEqual(['accounting'])
  })
})
