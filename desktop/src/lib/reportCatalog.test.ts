import { describe, expect, it } from 'vitest'

import { buildLaunchers, launchIndex } from './launchers'
import {
  MODE_REPORT_ORDER,
  REPORT_GROUPS,
  REPORT_TABS,
  buildReportCatalog,
  filterReportCatalog,
  isReportKind,
} from './reportCatalog'
import type { ExperienceMode } from './experienceMode'
import type { MeResponse } from '../api'

const meWith = (modules: string[]) =>
  ({ tenant_kind: 'standard', enabled_modules: modules, allowed_modules: modules, role_key: 'owner' }) as unknown as MeResponse

//: خالی یعنی «فیلتر نکن» — همه‌ی صفحه‌ها.
const EVERYTHING = buildLaunchers(meWith([]))
const MODES: ExperienceMode[] = ['accountant', 'simple']
const allIds = REPORT_GROUPS.flatMap((g) => g.entries.map((e) => e.id))
const ids = (mode: ExperienceMode, launchers = EVERYTHING) =>
  buildReportCatalog(launchers, mode).flatMap((g) => g.entries.map((e) => e.id))

describe('کاتالوگِ گزارش‌ها', () => {
  //: شناسه‌ی غلط خطا نمی‌دهد — `buildReportCatalog` بی‌صدا کنارش می‌گذارد و گزارش از
  //: فهرست غیب می‌شود. پس باید صریح سنجیده شود.
  it('هر شناسه واقعاً به صفحه‌ای می‌رسد', () => {
    const index = launchIndex(EVERYTHING)
    for (const id of allIds) {
      if (id.startsWith('reports/')) expect(isReportKind(id.slice('reports/'.length)), id).toBe(true)
      else expect(index.has(id), id).toBe(true)
    }
    expect(ids('accountant')).toHaveLength(allIds.length)
  })

  it('هیچ ردیفی دو بار نیست', () => {
    expect(new Set(allIds).size).toBe(allIds.length)
  })

  it('هر دوازده تبِ صفحه‌ی «گزارش‌ها» در فهرست هست — هیچ گزارشی جا نمی‌ماند', () => {
    for (const t of REPORT_TABS) expect(allIds, t.key).toContain(`reports/${t.key}`)
  })

  it.each(MODES)('ترتیبِ «%s» همه‌ی دسته‌ها را دقیقاً یک بار دارد', (mode) => {
    expect([...MODE_REPORT_ORDER[mode]].sort()).toEqual(REPORT_GROUPS.map((g) => g.key).sort())
  })

  it('حسابدار با دفتر و تراز شروع می‌کند، ساده با سود و زیان', () => {
    const acc = buildReportCatalog(EVERYTHING, 'accountant')
    const simple = buildReportCatalog(EVERYTHING, 'simple')
    expect(acc[0].heading).toBe('دفاتر و ترازها')
    expect(acc[0].entries[0].id).toBe('balancereport')
    expect(simple[0].heading).toBe('صورت‌های مالی')
    expect(simple[0].entries[0]).toMatchObject({ page: 'reports', section: 'income-statement', label: 'سود و زیان' })
  })

  it('**حالت ≠ مجوز** — هر دو حالت دقیقاً همان گزارش‌ها را دارند', () => {
    for (const modules of [[], ['overview', 'accounting', 'contacts', 'banking'], ['overview', 'reports', 'inventory']]) {
      const launchers = buildLaunchers(meWith(modules))
      expect(ids('accountant', launchers).sort(), modules.join(',')).toEqual(ids('simple', launchers).sort())
    }
  })

  it('گزارشی که کاربر نمی‌بیند نمی‌آید، و دسته‌ی خالی هم نه', () => {
    const cat = buildReportCatalog(buildLaunchers(meWith(['overview', 'accounting', 'contacts', 'banking'])), 'accountant')
    const got = cat.flatMap((g) => g.entries.map((e) => e.id))
    //: بی ماژولِ `reports` هیچ‌کدام از دوازده تب نیست؛ بی انبار، مرورِ انبار نیست.
    expect(got.filter((id) => id.startsWith('reports/'))).toEqual([])
    expect(got).not.toContain('inventory/stock')
    expect(got).toContain('balancereport')
    expect(cat.every((g) => g.entries.length > 0)).toBe(true)
  })
})

describe('صافیِ متنی', () => {
  const cat = buildReportCatalog(EVERYTHING, 'accountant')
  const found = (q: string) => filterReportCatalog(cat, q).flatMap((g) => g.entries.map((e) => e.id))

  it('با نامِ گزارش', () => {
    expect(found('ترازنامه')).toEqual(['reports/balance-sheet'])
  })

  it('با نامِ دسته — همه‌ی گزارش‌های آن دسته', () => {
    expect(found('بانک و صندوق')).toEqual(['bankledger', 'checksearch', 'cashbox'])
  })

  it('ی و ک عربی و نیم‌فاصله فرقی نمی‌کنند', () => {
    expect(found('سود و زيان')).toContain('reports/income-statement')
    expect(found('کاردکس')).toEqual(found('كاردكس'))
  })

  it('بی‌نتیجه → خالی؛ کوئریِ خالی → همه', () => {
    expect(found('چیزی که نیست')).toEqual([])
    expect(filterReportCatalog(cat, '  ')).toBe(cat)
  })
})
