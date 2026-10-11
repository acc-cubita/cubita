// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ModulesPage } from './ModulesPage'
import { fetchModules, updateModules, fetchMe, type MeResponse, type ModulesState } from '../api'

vi.mock('../api', () => ({ fetchModules: vi.fn(), updateModules: vi.fn(), fetchMe: vi.fn(), setTrade: vi.fn() }))
vi.mock('../lib/useTrades', () => ({ useTrades: () => ({ groups: [] }) }))

const core = ['overview', 'contacts', 'reports']
const optional = ['accounting', 'sales', 'banking', 'contracting', 'manufacturing']
const state: ModulesState = {
  industry: 'general', trade: null, core, optional, restricted: ['manufacturing'],
  allowed: [...core, ...optional.slice(0, 4)], enabled: core, industries: ['general'],
}
let container: HTMLDivElement
let root: Root
let updated: ReturnType<typeof vi.fn<(me: MeResponse) => void>>
beforeEach(async () => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  vi.clearAllMocks()
  vi.mocked(fetchModules).mockResolvedValue(state)
  vi.mocked(updateModules).mockImplementation(async (_token, enabled) => ({ ...state, enabled: core.concat(enabled) }))
  vi.mocked(fetchMe).mockResolvedValue({ role_key: 'owner' } as MeResponse)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  updated = vi.fn()
  await act(async () => root.render(createElement(ModulesPage, { token: 'test', me: { role_key: 'owner' } as MeResponse, onMeUpdated: updated })))
})
afterEach(() => { act(() => root.unmount()); container.remove() })
async function click(label: string) {
  const button = [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === label)
  expect(button, label).toBeDefined()
  await act(async () => button!.click())
}
describe('دکمه‌های انتخاب گروهی شخصی‌سازی', () => {
  it('همه، کلیدهای ماژول چندصفحه‌ای را ذخیره و ناوبری را تازه می‌کند', async () => {
    await click('همه')
    await click('ذخیره‌ی تغییرات')
    expect(updateModules).toHaveBeenCalledWith('test', ['accounting', 'sales', 'banking', 'contracting'])
    expect(updated).toHaveBeenCalledOnce()
    expect(container.textContent).toContain('تغییرات ذخیره شد.')
  })
  it('هیچ‌کدام پس از همه، هسته را دست نمی‌زند و گزینه‌های مجاز را خاموش می‌کند', async () => {
    await click('همه')
    await click('ذخیره‌ی تغییرات')
    await click('هیچ‌کدام')
    await click('ذخیره‌ی تغییرات')
    expect(updateModules).toHaveBeenLastCalledWith('test', [])
    expect(container.querySelectorAll('.is-core')).toHaveLength(core.length)
    expect(container.querySelectorAll('.is-lock')).toHaveLength(1)
  })
})
