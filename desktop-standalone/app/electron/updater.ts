/**
 * به‌روزرسانی خودکار اپ دسکتاپ.
 *
 * **چرا این لازم شد:** تا امروز هیچ کانالی وجود نداشت. بسته‌ی نصبی روی دستگاه
 * مشتری برای همیشه همان می‌ماند، در حالی که سرور جلو می‌رود — و دقیقاً همین اتفاق
 * روی محیط دمو افتاد که هشت مهاجرت عقب ماند بدون اینکه کسی متوجه شود. اپی که
 * نتواند خودش را به‌روز کند، همان مسئله را روی هر دستگاه مشتری تکرار می‌کند.
 *
 * **چرا سرور خودمان و نه GitHub Releases:** تحریم‌ها دسترسی به GitHub را از ایران
 * غیرقابل‌اتکا می‌کنند، و به‌روزرسانی‌ای که نصفِ وقت‌ها در دسترس نباشد بدتر از
 * نداشتنش است چون کسی به آن اعتماد نمی‌کند. provider از نوع generic فقط یک پوشه‌ی
 * ایستا روی همان سروری می‌خواهد که API آنجاست.
 *
 * **هرگز بی‌صدا نصب نمی‌شود.** این نرم‌افزار حسابداری است؛ بستن ناگهانی برنامه وسط
 * ثبت فاکتور یعنی از دست رفتن کار کاربر. دانلود در پس‌زمینه انجام می‌شود، کاربر
 * خبردار می‌شود، و نصب فقط موقع بستن برنامه اتفاق می‌افتد.
 *
 * **ریسکی که باید بدانید:** بسته امضای کد ندارد (`signAndEditExecutable: false`)،
 * پس `verifyUpdateCodeSignature` خاموش است. یعنی تنها چیزی که به‌روزرسانی را
 * محافظت می‌کند HTTPS است. هرکسی که بتواند اتصال به acc.cubita.ir را جعل کند
 * می‌تواند کد دلخواه بفرستد. با گواهی امضای کد (~۳۰۰ دلار در سال) این بسته
 * می‌شود؛ تا آن وقت این یک بدهی آگاهانه است، نه یک غفلت.
 */
import { autoUpdater } from 'electron-updater'
import type { BrowserWindow } from 'electron'
import { app } from 'electron'

/** وضعیتی که به رابط کاربری فرستاده می‌شود. */
export type UpdateStatus =
  | { state: 'checking' }
  | { state: 'available'; version: string }
  | { state: 'downloading'; percent: number }
  | { state: 'ready'; version: string }
  | { state: 'none' }
  | { state: 'error'; message: string }

/** هر شش ساعت. کاربر معمولاً برنامه را روزها باز نگه می‌دارد. */
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000

let lastStatus: UpdateStatus = { state: 'none' }

export function currentUpdateStatus(): UpdateStatus {
  return lastStatus
}

export function setupAutoUpdate(getWindow: () => BrowserWindow | null, log: (msg: string) => void): void {
  // در حالت توسعه اصلاً فعال نمی‌شود: نسخه‌ی dev برابر 0.0.0 است و هر انتشاری
  // «به‌روزرسانی موجود» به‌نظر می‌رسد.
  if (!app.isPackaged) {
    log('auto-update: غیرفعال (بسته‌بندی‌نشده)')
    return
  }

  // نصب خودکار موقع خروج بله، دانلود خودکار هم بله — ولی *راه‌اندازی مجدد* خودکار نه.
  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true

  const send = (status: UpdateStatus) => {
    lastStatus = status
    getWindow()?.webContents.send('update:status', status)
  }

  autoUpdater.on('checking-for-update', () => send({ state: 'checking' }))
  autoUpdater.on('update-available', (info) => {
    log(`auto-update: نسخه‌ی ${info.version} موجود است`)
    send({ state: 'available', version: info.version })
  })
  autoUpdater.on('update-not-available', () => send({ state: 'none' }))
  autoUpdater.on('download-progress', (p) => send({ state: 'downloading', percent: Math.round(p.percent) }))
  autoUpdater.on('update-downloaded', (info) => {
    log(`auto-update: نسخه‌ی ${info.version} دانلود شد، در خروج نصب می‌شود`)
    send({ state: 'ready', version: info.version })
  })
  autoUpdater.on('error', (err) => {
    // شکست بررسی به‌روزرسانی نباید به کاربر به‌شکل خطا نشان داده شود و کارش را
    // قطع کند: نبودِ اینترنت حالت عادی این برنامه است، نه استثنا.
    log(`auto-update error: ${err.message}`)
    send({ state: 'error', message: err.message })
  })

  const check = () => {
    autoUpdater.checkForUpdates().catch((err) => log(`auto-update check failed: ${String(err)}`))
  }

  // کمی تأخیر تا بررسی به‌روزرسانی با راه‌اندازی پنجره رقابت نکند
  setTimeout(check, 10_000)
  setInterval(check, CHECK_INTERVAL_MS)
}

/** نصب فوری به درخواست صریح کاربر. */
export function quitAndInstall(): void {
  autoUpdater.quitAndInstall()
}
