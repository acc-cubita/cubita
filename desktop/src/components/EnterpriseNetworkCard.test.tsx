// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { CubitaBridge } from '../electron'
import { EnterpriseNetworkCard } from './EnterpriseNetworkCard'
import type { NetworkConfig, NetworkInventory } from '../lib/enterpriseNetwork'

let root: Root
let host: HTMLDivElement
const sample: NetworkInventory = { role: 'server', state: { enabled: false, message: 'هنوز فعال نیست' },
  adapters: [{ id: 'lan', name: 'LAN 2', description: 'Realtek', index: 44, physical: true, kind: 'wired', status: 'Up', dhcp: false, addresses: [{ address: '192.168.91.1', prefix: 24 }], gateways: [], defaultRoute: false, profile: 'Public' }],
  suggestions: { lan: { address: '192.168.91.1', prefix: 24, mode: 'keep' } } }
const inspect = vi.fn(async () => ({ ok: true, data: sample }))
const preview = vi.fn(async (config: NetworkConfig) => ({ ok: true, data: { config, adapterName: 'LAN 2', subnet: '192.168.91.0/24', serverUrl: 'http://192.168.91.1:8420', addAddress: false, warnings: ['اینترنت حفظ می‌شود'] } }))
const apply = vi.fn(async () => ({ ok: true, data: { enabled: true, message: 'اعمال شد' } }))

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  Object.defineProperty(window, 'cubitaConfig', { configurable: true, value: { edition: 'enterprise', serverUrl: null, version: '1.9.5' } })
  window.cubita = { networkInspect: inspect, networkPreview: preview, networkApply: apply } as unknown as CubitaBridge
  inspect.mockClear(); preview.mockClear(); apply.mockClear()
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove() })
async function render() { await act(async () => root.render(<EnterpriseNetworkCard />)) }
async function select(label: string, value: string) {
  await act(async () => {
    const s = host.querySelector<HTMLSelectElement>(`[aria-label="${label}"]`)!
    s.value = value; s.dispatchEvent(new Event('change', { bubbles: true }))
  })
}
async function button(text: string) { await act(async () => Array.from(host.querySelectorAll('button')).find((b) => b.textContent?.includes(text))!.click()) }

it('قبل از انتخاب نوع اتصال و کارت، تنظیمی اعمال نمی‌شود؛ پیش‌نمایش و تأیید جدا هستند', async () => {
  await render()
  expect(inspect).toHaveBeenCalledTimes(1)
  expect(host.querySelector('[aria-label="نوع ارتباط شبکه"]')?.getAttribute('value')).toBeNull()
  expect(preview).not.toHaveBeenCalled(); expect(apply).not.toHaveBeenCalled()
  await select('نوع ارتباط شبکه', 'direct'); await select('کارت شبکه', 'lan')
  await button('بررسی تغییرات')
  const applyButton = Array.from(host.querySelectorAll('button')).find((b) => b.textContent?.includes('اعمال با تأیید'))!
  expect(applyButton.disabled).toBe(true)
  const consent = Array.from(host.querySelectorAll<HTMLInputElement>('input[type=checkbox]')).at(-1)!
  await act(async () => consent.click())
  expect(applyButton.disabled).toBe(false)
  await button('اعمال با تأیید')
  expect(apply).toHaveBeenCalledTimes(1)
})

it('تنظیم دستی در دسترس است و تغییر کارت/نوع اتصال، تأیید قبلی را باطل می‌کند', async () => {
  await render(); await select('نوع ارتباط شبکه', 'direct'); await select('کارت شبکه', 'lan')
  const manual = host.querySelector<HTMLInputElement>('input[type=checkbox]')!
  await act(async () => manual.click())
  expect(host.querySelector<HTMLInputElement>('[aria-label="پورت سرور"]')!.readOnly).toBe(false)
  await button('بررسی تغییرات'); expect(host.textContent).toContain('پیش‌نمایش تغییرات')
  await select('نوع ارتباط شبکه', 'wifi-router')
  expect(host.textContent).not.toContain('پیش‌نمایش تغییرات')
  expect(apply).not.toHaveBeenCalled()
})

it('در نسخهٔ ابری، پل شبکه استفاده نمی‌شود', async () => {
  Object.defineProperty(window, 'cubitaConfig', { configurable: true, value: { edition: 'cloud' } })
  await render(); expect(host.textContent).toBe(''); expect(inspect).not.toHaveBeenCalled()
})
