import { afterEach, expect, it, vi } from 'vitest'
import { ServerConnectionMonitor } from './serverConnection'
import type { ServerConnection } from '../src/lib/serverConnection'

function fixture(local = true) {
  let clock = 0
  let url: string | null = local ? 'http://localhost:8420' : 'http://192.168.50.1:8420'
  const probe = vi.fn(async (_url: string) => ({ ok: false }))
  const recover = vi.fn(async (): Promise<Pick<ServerConnection, 'state' | 'message'>> => ({ state: 'ready', message: 'آماده' }))
  const emit = vi.fn()
  const monitor = new ServerConnectionMonitor({ url: () => url, now: () => clock, local: () => local, probe, recover, emit })
  return { monitor, probe, recover, emit, advance: (ms: number) => { clock += ms }, setUrl: (next: string | null) => { url = next } }
}

afterEach(() => { vi.useRealTimers() })

it('healthy servers are not restarted', async () => {
  const f = fixture(); f.probe.mockResolvedValue({ ok: true })
  expect((await f.monitor.check()).state).toBe('ready')
  expect(f.recover).not.toHaveBeenCalled()
})

it('starts once, then verifies the configured endpoint', async () => {
  const f = fixture(); f.probe.mockResolvedValueOnce({ ok: false }).mockResolvedValueOnce({ ok: true })
  expect((await f.monitor.check()).state).toBe('ready')
  expect(f.recover).toHaveBeenCalledTimes(1)
  expect(f.emit.mock.calls.map(([s]) => s.state)).toEqual(['starting', 'ready'])
})

it('running wrapper is not mistaken for a ready API', async () => {
  const f = fixture()
  expect((await f.monitor.check()).state).toBe('offline')
})

it('remote client retries exactly its saved server without local service actions', async () => {
  const f = fixture(false)
  expect((await f.monitor.check()).state).toBe('offline')
  f.advance(10_000); f.probe.mockResolvedValue({ ok: true })
  expect((await f.monitor.check()).state).toBe('ready')
  expect(f.probe.mock.calls.map(([url]) => url)).toEqual(['http://192.168.50.1:8420', 'http://192.168.50.1:8420'])
  expect(f.recover).not.toHaveBeenCalled()
})

it('single flight and rate limit prevent repeated starts, even forced retries', async () => {
  const f = fixture()
  let finish!: (result: { ok: boolean }) => void
  f.probe.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
  const a = f.monitor.check(); const b = f.monitor.check(true)
  expect(a).toBe(b); finish({ ok: false }); await a
  f.advance(10_000); await f.monitor.check(true); expect(f.recover).toHaveBeenCalledTimes(1)
  f.advance(60_000); await f.monitor.check(); expect(f.recover).toHaveBeenCalledTimes(2)
})

it.each(['maintenance', 'permission', 'missing', 'repair'] as const)('%s stays visible until health recovers', async (state) => {
  const f = fixture(); f.recover.mockResolvedValue({ state, message: 'نصاب را کامل کنید' })
  expect((await f.monitor.check()).state).toBe(state)
  f.advance(10_000); expect((await f.monitor.check()).state).toBe(state)
  f.advance(10_000); f.probe.mockResolvedValue({ ok: true }); expect((await f.monitor.check()).state).toBe('ready')
})

it('unconfigured installs do not scan/switch/start anything', async () => {
  const f = fixture(); f.setUrl(null)
  expect((await f.monitor.check()).state).toBe('unconfigured')
  expect(f.probe).not.toHaveBeenCalled(); expect(f.recover).not.toHaveBeenCalled()
})

it('ignores results from an explicitly changed server', async () => {
  const f = fixture(false)
  f.probe.mockImplementationOnce(async () => { f.setUrl('http://another:8420'); return { ok: true } })
  await f.monitor.check(); expect(f.emit).not.toHaveBeenCalled()
})

it('background timer retries and stops without accumulating timers', async () => {
  vi.useFakeTimers(); const f = fixture(false)
  f.monitor.start(); f.monitor.start(); await vi.advanceTimersByTimeAsync(1)
  f.advance(10_000); await vi.advanceTimersByTimeAsync(10_000)
  expect(f.probe).toHaveBeenCalledTimes(2)
  f.monitor.stop(); f.advance(10_000); await vi.advanceTimersByTimeAsync(10_000)
  expect(f.probe).toHaveBeenCalledTimes(2)
})
