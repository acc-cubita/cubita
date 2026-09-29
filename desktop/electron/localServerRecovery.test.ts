// The subprocess, filesystem and NIC inventory are mocked: never starts real services.
import path from 'node:path'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const qa = vi.hoisted(() => ({ app: { isPackaged: true }, exists: vi.fn(), exec: vi.fn(), interfaces: vi.fn() }))
vi.mock('electron', () => ({ app: qa.app }))
vi.mock('node:child_process', () => ({ execFile: qa.exec }))
vi.mock('node:fs', () => ({ default: { existsSync: qa.exists } }))
vi.mock('node:os', () => ({ default: { networkInterfaces: qa.interfaces } }))
import { isLocalServerUrl, recoverLocalServer } from './localServerRecovery'

const platform = Object.getOwnPropertyDescriptor(process, 'platform')!
const resources = Object.getOwnPropertyDescriptor(process, 'resourcesPath')
beforeEach(() => {
  qa.app.isPackaged = true
  qa.exists.mockReset().mockReturnValue(true); qa.exec.mockReset()
  qa.interfaces.mockReset().mockReturnValue({ LAN: [{ address: '192.168.50.1' }] })
  Object.defineProperty(process, 'platform', { configurable: true, value: 'win32' })
  Object.defineProperty(process, 'resourcesPath', { configurable: true, value: path.resolve('QA-only/resources') })
})
afterEach(() => {
  Object.defineProperty(process, 'platform', platform)
  if (resources) Object.defineProperty(process, 'resourcesPath', resources)
  else Reflect.deleteProperty(process, 'resourcesPath')
})

it.each(['http://localhost:8420', 'http://127.0.0.1:8420', 'http://[::1]:8420', 'http://192.168.50.1:8420'])('recognizes only this machine: %s', (url) => {
  expect(isLocalServerUrl(url)).toBe(true)
})
it.each(['http://192.168.50.2:8420', 'http://other-server:8420', 'not a URL'])('never treats a remote/invalid URL as local: %s', (url) => {
  expect(isLocalServerUrl(url)).toBe(false)
})
it.each(['development', 'non-Windows', 'client-only'])('cannot execute service actions in %s', async (mode) => {
  if (mode === 'development') qa.app.isPackaged = false
  if (mode === 'non-Windows') Object.defineProperty(process, 'platform', { configurable: true, value: 'linux' })
  if (mode === 'client-only') qa.exists.mockReturnValue(false)
  expect((await recoverLocalServer()).state).toBe('client')
  expect(qa.exec).not.toHaveBeenCalled()
})
it('executes only the bundled fixed helper without a shell/elevation and with a deadline', async () => {
  qa.exec.mockImplementation((_file, _args, _options, callback: (error: Error | null, stdout: string) => void) => {
    callback(null, JSON.stringify({ state: 'ready', message: 'آماده' }))
  })
  expect(await recoverLocalServer()).toEqual({ state: 'ready', message: 'آماده' })
  expect(qa.exec).toHaveBeenCalledWith(path.join(process.resourcesPath, 'server', 'cubita-server.exe'), ['service-recover'],
    { windowsHide: true, timeout: 70_000, maxBuffer: 32_768, encoding: 'utf8' }, expect.any(Function))
})
it.each(['invalid JSON', '{"state":"stop-other-service","message":"not allowed"}', '{"state":"ready","message":123}'])('rejects unsupported helper output: %s', async (output) => {
  qa.exec.mockImplementation((_file, _args, _options, callback: (error: Error | null, stdout: string) => void) => callback(null, output))
  expect((await recoverLocalServer()).state).toBe('repair')
})
it('process failure cannot report readiness even with a ready JSON body', async () => {
  qa.exec.mockImplementation((_file, _args, _options, callback: (error: Error | null, stdout: string) => void) => callback(new Error('timeout'), '{"state":"ready","message":"آماده"}'))
  expect((await recoverLocalServer()).state).toBe('repair')
})
