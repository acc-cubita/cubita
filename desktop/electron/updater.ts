// همان updater بسته‌بندی‌شده؛ سازمانی فقط از سرور تنظیم‌شده و با امضای ناشر.
import { autoUpdater } from 'electron-updater'
import { app, type BrowserWindow } from 'electron'
import fs from 'node:fs'
import { updateProblem, type UpdateStatus } from '../src/lib/updateStatus.js'
export type { UpdateStatus } from '../src/lib/updateStatus.js'

export interface UpdateOptions {
  feedUrl?: string
  verifyFeed?: () => Promise<string | null>
  verify?: (downloadedFile: string, version: string) => Promise<string | null>
}

let options: UpdateOptions = {}
let getWindow: () => BrowserWindow | null = () => null
let log: (message: string) => void = () => {}
let lastStatus: UpdateStatus = { state: 'idle' }
let configured = false
let listening = false
let generation = 0
let installAllowed = false
let checking: Promise<UpdateStatus> | null = null
let startup: ReturnType<typeof setTimeout> | undefined
let interval: ReturnType<typeof setInterval> | undefined

function send(status: UpdateStatus) {
  lastStatus = status
  getWindow()?.webContents.send('update:status', status)
}

function failed(error: unknown) {
  log(`auto-update: ${String(error)}`)
  installAllowed = false
  autoUpdater.autoInstallOnAppQuit = false
  send({ state: 'error', message: updateProblem(error, Boolean(options.feedUrl)) })
}

export function currentUpdateStatus(): UpdateStatus { return lastStatus }

export async function checkForUpdatesNow(): Promise<UpdateStatus> {
  if (!app.isPackaged || !configured) {
    return { state: 'error', message: 'بررسی آپدیت در نسخه نصب‌شده و پس از اتصال به سرور در دسترس است.' }
  }
  if (checking) return checking
  if (['available', 'downloading', 'verifying', 'ready'].includes(lastStatus.state)) return lastStatus
  const epoch = generation
  const verifyFeed = options.verifyFeed
  send({ state: 'checking' })
  const task = (async () => {
    try {
      const problem = await verifyFeed?.()
      if (epoch !== generation) return lastStatus
      if (problem) throw new Error(problem)
      await autoUpdater.checkForUpdates()
    } catch (error) {
      if (epoch === generation) failed(error)
    }
    return lastStatus
  })()
  checking = task
  try { return await task } finally { if (checking === task) checking = null }
}

export function setupAutoUpdate(window: () => BrowserWindow | null, logger: (message: string) => void, next: UpdateOptions = {}): void {
  getWindow = window
  log = logger
  if (!app.isPackaged) { log('auto-update: غیرفعال (بسته‌بندی‌نشده)'); return }
  generation += 1
  options = next
  configured = true
  checking = null
  installAllowed = false
  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = false
  clearTimeout(startup)
  clearInterval(interval)
  if (options.feedUrl && !options.verify) {
    configured = false
    failed(new Error('سنجش امضای آپدیت سازمانی تنظیم نشده است؛ برای امنیت، نصب انجام نمی‌شود.'))
    return
  }
  if (options.feedUrl) {
    autoUpdater.setFeedURL({ provider: 'generic', url: options.feedUrl })
    autoUpdater.disableDifferentialDownload = true
  }
  send({ state: 'idle' })
  if (!listening) {
    listening = true
    autoUpdater.on('checking-for-update', () => send({ state: 'checking' }))
    autoUpdater.on('update-available', (info) => {
      installAllowed = false
      autoUpdater.autoInstallOnAppQuit = false
      send({ state: 'available', version: info.version })
    })
    autoUpdater.on('update-not-available', () => send({ state: 'none' }))
    autoUpdater.on('download-progress', (progress) => send({ state: 'downloading', percent: Math.max(0, Math.min(100, Math.round(progress.percent))) }))
    autoUpdater.on('update-downloaded', (info) => {
      if (!configured) return
      const epoch = generation
      const verify = options.verify
      send({ state: 'verifying' })
      void (async () => {
        try {
          const problem = await verify?.(info.downloadedFile, info.version)
          if (epoch !== generation) return
          if (problem) {
            // فقط فایل موقت همین دانلود؛ داده‌ها و نصاب سرور دست‌نخورده می‌مانند.
            try { fs.unlinkSync(info.downloadedFile) } catch { /* نصب همچنان ممنوع است. */ }
            throw new Error(problem)
          }
          installAllowed = true
          autoUpdater.autoInstallOnAppQuit = true
          send({ state: 'ready', version: info.version })
        } catch (error) { if (epoch === generation) failed(error) }
      })()
    })
    autoUpdater.on('error', failed)
  }
  startup = setTimeout(() => { void checkForUpdatesNow() }, 10_000)
  interval = setInterval(() => { void checkForUpdatesNow() }, 6 * 60 * 60 * 1000)
}

export function quitAndInstall(): void {
  if (installAllowed && lastStatus.state === 'ready') autoUpdater.quitAndInstall()
}
