import { app } from 'electron'
import { execFile } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { ServerConnection } from '../src/lib/serverConnection.js'

export function isLocalServerUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase()
    return ['localhost', '127.0.0.1', '::1', '[::1]'].includes(host)
      || Object.values(os.networkInterfaces()).some((list) => list?.some((item) => item.address === host))
  } catch { return false }
}

export async function recoverLocalServer(): Promise<Pick<ServerConnection, 'state' | 'message'>> {
  const client = { state: 'client', message: 'اتصال به سرور ذخیره‌شده دوباره بررسی می‌شود.' } as const
  // Never invoke OS service actions in development, web/cloud, or on the remote server.
  if (!app.isPackaged || process.platform !== 'win32') return client
  const helper = path.join(process.resourcesPath, 'server', 'cubita-server.exe')
  if (!fs.existsSync(helper)) return client
  return new Promise((resolve) => {
    execFile(helper, ['service-recover'], { windowsHide: true, timeout: 70_000, maxBuffer: 32_768, encoding: 'utf8' }, (err, stdout) => {
      try {
        const result: unknown = JSON.parse(stdout.trim())
        if (!err && result && typeof result === 'object' && 'state' in result && 'message' in result
            && ['ready', 'client', 'maintenance', 'permission', 'missing', 'repair'].includes(String(result.state))
            && typeof result.message === 'string') {
          resolve({ state: result.state as ServerConnection['state'], message: result.message })
          return
        }
      } catch { /* Old/mixed helper must not become a successful start. */ }
      resolve({ state: 'repair', message: 'ابزار راه‌اندازی سرور آماده نیست؛ نصاب کامل سازمانی را یک‌بار با نقش سرور و مسیر قبلی برای تعمیر اجرا کنید. داده‌ها را حذف نکنید.' })
    })
  })
}
