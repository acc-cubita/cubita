import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
const mock = vi.hoisted(() => ({
  listeners: new Map<string, ((info: any) => void)[]>(),
  updater: { on: vi.fn(), checkForUpdates: vi.fn(), setFeedURL: vi.fn(), quitAndInstall: vi.fn(), autoDownload: false, autoInstallOnAppQuit: false, disableDifferentialDownload: false },
}))
vi.mock('electron', () => ({ app: { isPackaged: true } }))
vi.mock('electron-updater', () => ({ autoUpdater: mock.updater }))
function emit(name: string, data?: unknown) { for (const callback of mock.listeners.get(name) ?? []) callback(data) }
let api: typeof import('./updater')
beforeEach(async () => {
  vi.useFakeTimers(); vi.resetModules(); vi.clearAllMocks(); mock.listeners.clear()
  mock.updater.on.mockImplementation((name, callback) => {
    const list = mock.listeners.get(name) ?? []; list.push(callback); mock.listeners.set(name, list)
  })
  mock.updater.checkForUpdates.mockImplementation(async () => { emit('checking-for-update'); emit('update-not-available') })
  api = await import('./updater')
})
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers() })
const setup = (options: import('./updater').UpdateOptions = {}) => api.setupAutoUpdate(() => null, () => {}, options)
describe('آپدیت دستی LAN با همان updater', () => {
  it('فید سازمانی بدون verifier هرگز به مسیر نصب بدون امضا برنمی‌گردد', async () => {
    setup({ feedUrl: 'http://a/updates/' })
    expect(api.currentUpdateStatus()).toMatchObject({ state: 'error', message: expect.stringMatching(/سنجش امضا/) })
    await api.checkForUpdatesNow(); expect(mock.updater.checkForUpdates).not.toHaveBeenCalled()
    emit('update-downloaded', { version: '1.9.4', downloadedFile: 'not-a-real-file' })
    api.quitAndInstall(); expect(mock.updater.quitAndInstall).not.toHaveBeenCalled(); expect(mock.updater.autoInstallOnAppQuit).toBe(false)
  })
  it('فقط فید شرکت، بدون دانلود تفاضلی و بدون نصب پیش از سنجش', async () => {
    const verifyFeed = vi.fn().mockResolvedValue(null)
    setup({ feedUrl: 'http://192.168.50.1:8420/updates/', verifyFeed, verify: async () => null })
    expect(mock.updater.setFeedURL).toHaveBeenCalledExactlyOnceWith({ provider: 'generic', url: 'http://192.168.50.1:8420/updates/' })
    expect(mock.updater.disableDifferentialDownload).toBe(true)
    api.quitAndInstall(); expect(mock.updater.quitAndInstall).not.toHaveBeenCalled()
    expect(await api.checkForUpdatesNow()).toEqual({ state: 'none' }); expect(verifyFeed).toHaveBeenCalledOnce()
  })
  it('دو بررسی همزمان یک درخواست می‌سازند و تغییر سرور listener/timer اضافه نمی‌کند', async () => {
    let resolve!: (problem: null) => void
    setup({ feedUrl: 'http://a/updates/', verify: async () => null, verifyFeed: () => new Promise((done) => { resolve = done }) })
    const first = api.checkForUpdatesNow(); const second = api.checkForUpdatesNow(); resolve(null)
    await Promise.all([first, second]); expect(mock.updater.checkForUpdates).toHaveBeenCalledOnce()
    setup({ feedUrl: 'http://b/updates/', verify: async () => null })
    expect(mock.listeners.get('update-downloaded')).toHaveLength(1); expect(vi.getTimerCount()).toBe(2)
    await api.checkForUpdatesNow(); expect(mock.updater.setFeedURL).toHaveBeenLastCalledWith({ provider: 'generic', url: 'http://b/updates/' })
  })
  it('امضای ناقص مانع بررسی provider است و فایل معتبر به نصب می‌رسد', async () => {
    setup({ feedUrl: 'http://a/updates/', verify: async () => null, verifyFeed: async () => 'امضای آپدیت معتبر نیست' })
    expect((await api.checkForUpdatesNow()).state).toBe('error'); expect(mock.updater.checkForUpdates).not.toHaveBeenCalled()
    setup({ feedUrl: 'http://a/updates/', verify: async () => null })
    emit('update-downloaded', { version: '1.9.4', downloadedFile: 'not-a-real-file' }); await Promise.resolve(); await Promise.resolve()
    expect(api.currentUpdateStatus()).toEqual({ state: 'ready', version: '1.9.4' })
    api.quitAndInstall(); expect(mock.updater.quitAndInstall).toHaveBeenCalledOnce()
  })
  it('خطای I/O سنجش و پاسخ دیررس سرور قبلی هرگز اجازه نصب نمی‌دهند', async () => {
    setup({ feedUrl: 'http://a/updates/', verify: async () => { throw new Error('ENOENT') } })
    emit('update-downloaded', { version: '1.9.4', downloadedFile: 'not-a-real-file' }); await Promise.resolve(); await Promise.resolve()
    expect(api.currentUpdateStatus().state).toBe('error'); expect(mock.updater.autoInstallOnAppQuit).toBe(false)
    let resolve!: (value: null) => void
    setup({ feedUrl: 'http://a/updates/', verify: () => new Promise((done) => { resolve = done }) })
    emit('update-downloaded', { version: '1.9.4', downloadedFile: 'not-a-real-file' })
    setup({ feedUrl: 'http://b/updates/', verify: async () => null }); resolve(null); await Promise.resolve(); await Promise.resolve()
    expect(api.currentUpdateStatus()).toEqual({ state: 'idle' }); api.quitAndInstall(); expect(mock.updater.quitAndInstall).not.toHaveBeenCalled()
  })
})
