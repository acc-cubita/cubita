// @vitest-environment jsdom
// Real App recovery/session orchestration; unrelated pages and IPC are mocked.
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useServerReconnect } from './lib/useServerConnection'
import type { CubitaBridge } from './electron'
import type { ServerConnection } from './lib/serverConnection'

const mocks = vi.hoisted(() => ({ setup: vi.fn(async () => ({ needs_setup: false })), sync: vi.fn() }))
vi.mock('./platform', () => ({ isElectron: true, isEnterprise: true, needsServerAddress: false }))
vi.mock('./api', () => ({ fetchSetupStatus: mocks.setup, fetchMe: vi.fn() }))
vi.mock('./lib/session', () => ({ loadStoredToken: () => null, storeToken: vi.fn() }))
vi.mock('./lib/tenantScope', () => ({ setTenantScope: vi.fn() }))
vi.mock('./lib/experienceMode', () => ({ adoptServerExperience: vi.fn() }))
vi.mock('./components/TitleBar', () => ({ TitleBar: () => null }))
vi.mock('./components/UpdateBanner', () => ({ UpdateBanner: () => null }))
vi.mock('./components/LoginScreen', () => ({ LoginScreen: () => <div>ورود آزمایشی</div> }))
vi.mock('./components/SignupScreen', () => ({ SignupScreen: () => null }))
vi.mock('./components/SetPasswordScreen', () => ({ SetPasswordScreen: () => null }))
vi.mock('./components/ServerConnectScreen', () => ({ ServerConnectScreen: () => null }))
vi.mock('./components/EnterpriseSetupScreen', () => ({ EnterpriseSetupScreen: () => null }))
vi.mock('./components/SubscriptionBanner', () => ({ SubscriptionBanner: () => null }))
vi.mock('./components/TrialBanner', () => ({ TrialBanner: () => null }))
vi.mock('./components/TrialExpiredScreen', () => ({ TrialExpiredScreen: () => null }))
vi.mock('./components/Dashboard', () => ({ Dashboard: (props: { token: string; onLogout: () => void }) => {
  useServerReconnect(mocks.sync)
  return <div data-token={props.token}><input aria-label="شرح" defaultValue="پیش‌نویس" /><button onClick={props.onLogout}>خروج آزمایشی</button></div>
} }))
import App from './App'

let root: Root, host: HTMLDivElement, listener: (status: ServerConnection) => void
const restore = vi.fn()
const me = { tenant_id: 'QA-only', tenant_name: 'دفتر QA', trial_expired: false }
const offline = { session: { access_token: 'cached', refresh_token: 'old-ref', me }, offline: true }
const online = { session: { access_token: 'fresh', refresh_token: 'next-ref', me }, offline: false }
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  restore.mockReset(); mocks.sync.mockClear(); mocks.setup.mockClear()
  restore.mockResolvedValueOnce(offline)
  Object.defineProperty(window, 'cubitaConfig', { configurable: true, value: { edition: 'enterprise', serverUrl: 'http://localhost:8420' } })
  window.cubita = { restoreSession: restore, clearSession: vi.fn(async () => {}),
    serverConnection: async () => ({ state: 'starting', message: 'راه‌اندازی خودکار', url: 'http://localhost:8420' }),
    onServerConnection: (cb: (status: ServerConnection) => void) => { listener = cb; return () => {} } } as unknown as CubitaBridge
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove() })
async function connect() { await act(async () => listener({ state: 'ready', message: 'آماده', url: 'http://localhost:8420' })) }

it('cached session/form stay mounted, then renew and sync automatically after server startup', async () => {
  restore.mockResolvedValueOnce(online)
  await act(async () => root.render(<App />))
  const input = host.querySelector('input')!; input.value = 'اصلاح ذخیره‌نشده'
  expect(restore).toHaveBeenCalledTimes(1); expect(mocks.sync).not.toHaveBeenCalled()
  await connect()
  expect(restore).toHaveBeenCalledTimes(2); expect(mocks.sync).toHaveBeenCalledTimes(1)
  expect(host.querySelector('[data-token]')?.getAttribute('data-token')).toBe('fresh')
  expect(host.querySelector('input')).toBe(input); expect(input.value).toBe('اصلاح ذخیره‌نشده')
  expect(host.querySelector('.offline-banner')).toBeNull()
  await connect(); expect(restore).toHaveBeenCalledTimes(2); expect(mocks.sync).toHaveBeenCalledTimes(1)
})

it('logout during reconnect cannot put the cached user back on screen', async () => {
  let finish!: (value: typeof online) => void
  restore.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  await act(async () => root.render(<App />)); await connect()
  await act(async () => host.querySelector('button')!.click())
  await act(async () => finish(online))
  expect(host.textContent).toContain('ورود آزمایشی')
  expect(host.querySelector('[data-token]')).toBeNull()
})

it('connection recovery before login retries setup status without requiring restart', async () => {
  restore.mockReset(); restore.mockResolvedValue(null)
  await act(async () => root.render(<App />))
  const before = mocks.setup.mock.calls.length
  await connect()
  expect(mocks.setup.mock.calls.length).toBeGreaterThan(before)
  expect(host.textContent).toContain('ورود آزمایشی')
})
