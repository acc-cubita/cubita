// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ServerConnectionBanner } from './ServerConnectionBanner'
import { useServerConnection, useServerReconnect } from '../lib/useServerConnection'
import { connectionError, type ServerConnection } from '../lib/serverConnection'
import type { CubitaBridge } from '../electron'

let root: Root, host: HTMLDivElement
let listener: (status: ServerConnection) => void
const ready = { state: 'ready', message: 'آماده', url: 'http://localhost:8420' } as const
const starting = { ...ready, state: 'starting', message: 'در حال راه‌اندازی خودکار' } as const
const retry = vi.fn(async () => ready)
const stop = vi.fn()
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  retry.mockClear(); stop.mockClear()
  Object.defineProperty(window, 'cubitaConfig', { configurable: true, value: { edition: 'enterprise', serverUrl: ready.url } })
  window.cubita = { serverRetryConnection: retry, serverConnection: async () => starting,
    onServerConnection: (cb: (status: ServerConnection) => void) => { listener = cb; return stop } } as unknown as CubitaBridge
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove() })

it('automatic starting is visible before login and cannot queue another start', async () => {
  await act(async () => root.render(<ServerConnectionBanner status={starting} />))
  expect(host.textContent).toContain('راه‌اندازی خودکار')
  expect(host.querySelector('button')?.disabled).toBe(true)
  expect(retry).not.toHaveBeenCalled()
})
it('repair guidance is readable with a safe retry, ready state hides the banner', async () => {
  await act(async () => root.render(<ServerConnectionBanner status={{ ...ready, state: 'permission', message: 'نصاب سرور را یک‌بار اجرا کنید' }} />))
  await act(async () => host.querySelector('button')!.click())
  expect(retry).toHaveBeenCalledTimes(1)
  await act(async () => root.render(<ServerConnectionBanner status={ready} />))
  expect(host.textContent).toBe('')
})
it('IPC subscription updates without reloading/unmounting the edited input', async () => {
  function Fixture() {
    const status = useServerConnection()
    return <><input defaultValue="سند در حال ویرایش" /><ServerConnectionBanner status={status} /></>
  }
  await act(async () => root.render(<Fixture />))
  const input = host.querySelector('input')!; input.value = 'اصلاح ذخیره‌نشده'
  await act(async () => listener(ready))
  expect(host.querySelector('input')).toBe(input)
  expect(input.value).toBe('اصلاح ذخیره‌نشده')
  expect(host.querySelector('[role=status]')).toBeNull()
})
it('read-only cards can reload once on reconnect and unsubscribe', async () => {
  const load = vi.fn()
  function Fixture() { useServerReconnect(load); return null }
  await act(async () => root.render(<Fixture />))
  window.dispatchEvent(new Event('cubita:server-reconnected')); expect(load).toHaveBeenCalledTimes(1)
  act(() => root.render(null)); window.dispatchEvent(new Event('cubita:server-reconnected'))
  expect(load).toHaveBeenCalledTimes(1)
})
it('cloud never subscribes to enterprise service recovery', async () => {
  Object.defineProperty(window, 'cubitaConfig', { configurable: true, value: { edition: 'cloud' } })
  const query = vi.spyOn(window.cubita, 'serverConnection')
  function Fixture() { const status = useServerConnection(); return <ServerConnectionBanner status={status} /> }
  await act(async () => root.render(<Fixture />)); expect(query).not.toHaveBeenCalled()
})
it('network failures are Persian and business errors remain intact', () => {
  expect(connectionError(new TypeError('Failed to fetch'))).toContain('خودکار')
  expect(connectionError(new Error('سال مالی بسته است'))).toBe('سال مالی بسته است')
})
