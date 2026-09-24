import { app, BrowserWindow, ipcMain, Menu, MenuItem, shell } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import { clearReferenceCaches, getLocalDb, initLocalDb, pendingOutboxCount } from './db.js'
import {
  bestEffortLogout,
  clearSession as clearStoredSession,
  currentRefreshToken,
  persistSession as persistStoredSession,
  restoreSession,
  type RestoreResult,
} from './authSession.js'

// پوشه‌ی داده‌ی کوبیتا سازمانی جداست. نامِ برنامه از `name`ِ package.json («desktop»)
// می‌آید، نه از appIdِ electron-builder — پس بدونِ این خط هر دو نسخه در یک userData
// می‌نشستند و اتصالِ سازمانی، نشست و کشِ نصبِ ابریِ کنارش را پاک می‌کرد (دقیقاً
// همین اتفاق در اولین آزمونِ بسته افتاد). باید پیش از هر خواندنِ userData باشد.
if (EDITION === 'enterprise') {
  app.setPath('userData', path.join(app.getPath('appData'), 'Cubita Enterprise'))
}

const DEBUG_LOG = path.join(app.getPath('userData'), 'startup-debug.log')
function debugLog(msg: string) {
  try {
    fs.mkdirSync(path.dirname(DEBUG_LOG), { recursive: true })
    fs.appendFileSync(DEBUG_LOG, `${new Date().toISOString()} ${msg}\n`)
  } catch {
    // اگر حتی لاگ‌نویسی هم شکست بخورد، کاری نمی‌توان کرد؛ فقط جلوی کرش اضافه را می‌گیریم
  }
}
import {
  pullAccounts,
  pullBankAccounts,
  pullItems,
  pullWarehouses,
  pushOutbox,
  queueCheck,
  queueJournalEntry,
  queuePurchaseInvoice,
  queueSalesInvoice,
} from './sync.js'
import {
  autoSnapshot,
  backupStatus,
  chooseDir,
  deleteLocal,
  getSettings,
  listLocalBackups,
  openBackupsFolder,
  resetDir,
  restoreFromFile,
  restoreFromLocal,
  saveToFile,
  setSettings,
  snapshotNow,
  type BackupSettings,
} from './backup.js'
import { currentUpdateStatus, quitAndInstall, setupAutoUpdate } from './updater.js'
import { EDITION, currentServerUrl, discoverServers, probeServer, saveServerUrl } from './serverSettings.js'
import { verifyDownloadedUpdate } from './updateVerify.js'
import { TRUSTED_UPDATE_KEYS } from './updateKeys.js'
import { normalizeServerUrl } from './serverAddress.js'
import { driverFor, listSerialPorts } from './pos/drivers.js'
import type { PayResult, PosStatus, PosTerminalProfile } from './pos/types.js'

// نشانیِ بک‌اند. ابری: acc.cubita.ir ثابت (acc.ipnetcity.ir هم به همان بک‌اند می‌رود،
// ولی رندرر روی acc.cubita.ir ساخته می‌شود و دو دامنه در دو نیمه‌ی یک اپ یعنی هر
// تغییرِ آینده در دو جا یادآوری شود). سازمانی: نشانیِ سرورِ شرکت که کاربر در جادوگرِ
// «اتصال به سرور» داده — پس `let`، و خالی تا وقتی هنوز وصل نشده.
let apiBaseUrl = currentServerUrl() ?? ''

let mainWindow: BrowserWindow | null = null
let authToken: string | null = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 860,
    minHeight: 560,
    frame: false, // نوار عنوان و منوی پیش‌فرض ویندوز حذف می‌شود؛ نوار عنوان سفارشی در رابط کاربری ساخته می‌شود
    backgroundColor: '#0a0e1a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.on('maximize', () => mainWindow?.webContents.send('window:maximizedChanged', true))
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window:maximizedChanged', false))

  // اجازه‌ی دوربین برای بارکدخوانِ صندوقِ فروشگاهی. الکترون به‌صورتِ پیش‌فرض هر
  // درخواستِ media را رد می‌کند؛ بدونِ این هندلر، دکمه‌ی «اسکن با دوربین» در دسکتاپ
  // بی‌صدا کار نمی‌کرد. فقط media (دوربین/میکروفون) مجاز می‌شود، نه هر مجوزِ دیگری.
  const ses = mainWindow.webContents.session
  ses.setPermissionRequestHandler((_wc, permission, callback) => callback(permission === 'media'))
  ses.setPermissionCheckHandler((_wc, permission) => permission === 'media')

  // منوی کلیک‌راست سفارشی (فارسی) روی فیلدهای متنی و متن انتخاب‌شده
  mainWindow.webContents.on('context-menu', (_event, params) => {
    const menu = new Menu()

    if (params.isEditable) {
      menu.append(new MenuItem({ label: 'واگرد', role: 'undo', enabled: params.editFlags.canUndo }))
      menu.append(new MenuItem({ label: 'ازنو', role: 'redo', enabled: params.editFlags.canRedo }))
      menu.append(new MenuItem({ type: 'separator' }))
      menu.append(new MenuItem({ label: 'برش', role: 'cut', enabled: params.editFlags.canCut }))
      menu.append(new MenuItem({ label: 'کپی', role: 'copy', enabled: params.editFlags.canCopy }))
      menu.append(new MenuItem({ label: 'چسباندن', role: 'paste', enabled: params.editFlags.canPaste }))
      menu.append(new MenuItem({ type: 'separator' }))
      menu.append(new MenuItem({ label: 'انتخاب همه', role: 'selectAll', enabled: params.editFlags.canSelectAll }))
    } else if (params.selectionText) {
      menu.append(new MenuItem({ label: 'کپی', role: 'copy' }))
    }

    if (menu.items.length > 0) menu.popup()
  })

  mainWindow.webContents.on('did-fail-load', (_evt, errorCode, errorDescription) => {
    debugLog(`did-fail-load: ${errorCode} ${errorDescription}`)
  })
  mainWindow.webContents.on('did-finish-load', () => {
    debugLog('did-finish-load')
  })
  mainWindow.webContents.on('render-process-gone', (_evt, details) => {
    debugLog(`render-process-gone: ${JSON.stringify(details)}`)
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    const indexPath = path.join(__dirname, '../dist/index.html')
    debugLog(`loadFile: ${indexPath} (exists=${fs.existsSync(indexPath)})`)
    mainWindow.loadFile(indexPath)
  }
}

debugLog('main.ts loaded, waiting for app.whenReady()')

app.whenReady().then(() => {
  debugLog('app.whenReady resolved')
  try {
    Menu.setApplicationMenu(null) // منوی پیش‌فرض File/Edit/View/Window حذف می‌شود
    debugLog('menu cleared')
    initLocalDb()
    debugLog('initLocalDb done')
    createWindow()
    debugLog('createWindow called')

    // ابری: فیدِ acc.cubita.ir. سازمانی: فیدِ سرورِ خودِ شرکت با سنجشِ امضا پیش از نصب
    // (ENTERPRISE_PLAN.md، M5). سازمانیِ هنوز وصل‌نشده فیدی ندارد.
    if (EDITION === 'cloud') {
      setupAutoUpdate(() => mainWindow, debugLog)
      debugLog('auto-update wired')
    } else if (apiBaseUrl) {
      const feedUrl = `${apiBaseUrl}/updates/`
      setupAutoUpdate(() => mainWindow, debugLog, {
        feedUrl,
        verify: (file) => verifyDownloadedUpdate(feedUrl, file, TRUSTED_UPDATE_KEYS),
      })
      debugLog(`auto-update wired (enterprise feed ${feedUrl})`)
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  } catch (err) {
    debugLog(`STARTUP ERROR: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`)
  }
}).catch((err) => {
  debugLog(`whenReady REJECTED: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`)
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// --- IPC: پل بین رابط کاربری (renderer، بدون دسترسی مستقیم به Node) و منطق محلی/Sync ---

ipcMain.handle('window:minimize', () => {
  mainWindow?.minimize()
})

ipcMain.handle('window:toggleMaximize', () => {
  if (!mainWindow) return
  if (mainWindow.isMaximized()) mainWindow.unmaximize()
  else mainWindow.maximize()
})

ipcMain.handle('window:close', () => {
  mainWindow?.close()
})

ipcMain.handle('window:isMaximized', () => {
  return mainWindow?.isMaximized() ?? false
})

// --- نسخه و نشانیِ سرور ---
//
// همزمان (`sendSync`) چون رندرر باید نشانی را **پیش از اولین fetch** بداند؛ preload
// آن را روی `window.cubitaConfig` می‌گذارد. بعد از تغییرِ نشانی، رندرر صفحه را
// دوباره بار می‌کند تا همه‌چیز از نشانیِ تازه شروع شود.
ipcMain.on('server:config', (evt) => {
  evt.returnValue = { edition: EDITION, serverUrl: apiBaseUrl || null }
})

ipcMain.handle('server:probe', (_evt, input: string) => probeServer(String(input ?? '')))

ipcMain.handle('server:discover', () => discoverServers())

// اجرای نصابِ نسخه‌ی تازه روی **خودِ سرور** (کوبیتا سازمانی). مسیر از API می‌آید، پس فقط
// نصابی اجرا می‌شود که واقعاً در پوشه‌ی آپدیتِ سرور است — نه هر exeِ دلخواه.
ipcMain.handle('updates:runInstaller', async (_evt, installerPath: string) => {
  if (EDITION !== 'enterprise') return 'فقط در کوبیتا سازمانی.'
  const root = path.resolve(process.env.ProgramData ?? 'C:\\ProgramData', 'Cubita', 'updates')
  const target = path.resolve(String(installerPath ?? ''))
  if (!target.toLowerCase().startsWith(root.toLowerCase() + path.sep) || !target.toLowerCase().endsWith('.exe')) {
    return 'مسیرِ نصاب مجاز نیست.'
  }
  if (!fs.existsSync(target)) return 'فایلِ نصاب روی این رایانه نیست؛ این دکمه فقط روی خودِ سرور کار می‌کند.'
  const err = await shell.openPath(target)
  return err || null
})

ipcMain.handle('server:save', (_evt, input: string) => {
  const target = normalizeServerUrl(String(input ?? ''))
  if (!target.ok) return target
  // سندِ صف‌شده‌ی آفلاین مالِ سرورِ قبلی است؛ اگر نشانی عوض شود، دفعه‌ی بعد به
  // سرورِ دیگری فرستاده می‌شد — یعنی سندی در دفترِ شرکتِ اشتباه.
  const pending = (() => {
    try {
      return pendingOutboxCount()
    } catch {
      return -1
    }
  })()
  if (apiBaseUrl && target.url !== apiBaseUrl && pending !== 0) {
    return {
      ok: false as const,
      error:
        pending > 0
          ? `${pending.toLocaleString('fa-IR')} سندِ ارسال‌نشده روی این رایانه هست. پیش از تغییرِ سرور، به سرورِ فعلی وصل شوید تا ارسال شوند.`
          : 'وضعیتِ سندهای ارسال‌نشده معلوم نشد؛ برای امنیتِ داده، سرور عوض نشد.',
    }
  }
  const result = saveServerUrl(target.url)
  if (!result.ok) return result
  if (result.url !== apiBaseUrl) {
    // نشست و کشِ مرجع مالِ سرورِ قبلی‌اند.
    clearStoredSession()
    try {
      clearReferenceCaches()
    } catch {
      // کش در اولین اتصال هنوز خالی است.
    }
    authToken = null
  }
  apiBaseUrl = result.url
  return result
})

ipcMain.handle('auth:setToken', (_evt, token: string | null) => {
  authToken = token
})

// --- نشستِ آفلاین: بارِ اول یوزر/پسورد، از آن به بعد اپ خودش وارد می‌ماند ---
//
// سه IPC، هرکدام یک لحظه از عمرِ نشست: `persistSession` بعد از هر ورود/سوییچِ
// موفق (نشستِ کامل روی دیسک + authToken حافظه‌ای برای sync)، `restoreSession`
// یک‌بار در بدو اجرا (App.tsx به‌جای loadStoredToken صدایش می‌زند)، `clearSession`
// روی خروجِ دستی. منطقِ «خطای شبکه ≠ بطلانِ نشست» داخلِ authSession.ts است؛
// اینجا فقط authToken حافظه‌ای را با نتیجه هماهنگ نگه می‌داریم.

ipcMain.handle(
  'auth:persistSession',
  (_evt, access: string, refresh: string, me: unknown) => {
    persistStoredSession(access, refresh, me)
    authToken = access
  },
)

ipcMain.handle('auth:restoreSession', async (): Promise<RestoreResult> => {
  // سازمانیِ هنوز وصل‌نشده: نشستی برای بازیابی نیست.
  if (!apiBaseUrl) return null
  const result = await restoreSession({ apiBaseUrl: apiBaseUrl })
  authToken = result?.session.access_token ?? null
  return result
})

ipcMain.handle('auth:clearSession', async () => {
  // بهترین‌تلاش: خروجِ سمتِ سرور نباید مانعِ خروجِ محلی شود (مثلاً آفلاین).
  await bestEffortLogout({ apiBaseUrl: apiBaseUrl })
  clearStoredSession()
  authToken = null
})

// رفرشِ فعلی — فقط برای سوییچِ کسب‌وکار (TenantSwitcher باید رفرشِ قبلی را به
// switch-tenant بدهد تا سرور آن را باطل و یکی برای مستأجرِ مقصد صادر کند).
ipcMain.handle('auth:currentRefreshToken', () => currentRefreshToken())

ipcMain.handle('sync:pullAll', async () => {
  const config = { apiBaseUrl: apiBaseUrl, getToken: () => authToken }
  await Promise.all([pullAccounts(config), pullWarehouses(config), pullItems(config), pullBankAccounts(config)])
})

ipcMain.handle('sync:pushOutbox', async () => {
  return pushOutbox({ apiBaseUrl: apiBaseUrl, getToken: () => authToken })
})

ipcMain.handle('journal:queueEntry', (_evt, payload: unknown) => {
  return queueJournalEntry(payload)
})

ipcMain.handle('journal:listOutbox', () => {
  return getLocalDb().prepare('SELECT * FROM outbox_journal_entries ORDER BY created_at DESC').all()
})

ipcMain.handle('invoice:queueSalesInvoice', (_evt, payload: unknown) => {
  return queueSalesInvoice(payload)
})

ipcMain.handle('invoice:listOutbox', () => {
  return getLocalDb().prepare('SELECT * FROM outbox_sales_invoices ORDER BY created_at DESC').all()
})

ipcMain.handle('check:queueCheck', (_evt, payload: unknown) => {
  return queueCheck(payload)
})

ipcMain.handle('check:listOutbox', () => {
  return getLocalDb().prepare('SELECT * FROM outbox_checks ORDER BY created_at DESC').all()
})

ipcMain.handle('purchaseInvoice:queue', (_evt, payload: unknown) => {
  return queuePurchaseInvoice(payload)
})

ipcMain.handle('purchaseInvoice:listOutbox', () => {
  return getLocalDb().prepare('SELECT * FROM outbox_purchase_invoices ORDER BY created_at DESC').all()
})

ipcMain.handle('accounts:listCached', () => {
  return getLocalDb().prepare('SELECT * FROM accounts_cache ORDER BY code').all()
})

ipcMain.handle('warehouses:listCached', () => {
  return getLocalDb().prepare('SELECT * FROM warehouses_cache ORDER BY code').all()
})

ipcMain.handle('items:listCached', () => {
  return getLocalDb().prepare('SELECT * FROM items_cache ORDER BY sku').all()
})

ipcMain.handle('bankAccounts:listCached', () => {
  return getLocalDb().prepare('SELECT * FROM bank_accounts_cache ORDER BY name').all()
})

// --- پشتیبان‌گیری/بازیابیِ محلی ---
const backupConfig = () => ({ apiBaseUrl: apiBaseUrl, getToken: () => authToken })
ipcMain.handle('backup:auto', () => autoSnapshot(backupConfig()))
ipcMain.handle('backup:saveToFile', () => saveToFile(backupConfig(), mainWindow))
ipcMain.handle('backup:listLocal', () => listLocalBackups())
ipcMain.handle('backup:openFolder', () => openBackupsFolder())
ipcMain.handle('backup:restoreFromFile', () => restoreFromFile(backupConfig(), mainWindow))
ipcMain.handle('backup:now', () => snapshotNow(backupConfig()))
ipcMain.handle('backup:status', () => backupStatus())
ipcMain.handle('backup:getSettings', () => getSettings())
ipcMain.handle('backup:setSettings', (_e, patch: Partial<BackupSettings>) => setSettings(patch))
ipcMain.handle('backup:chooseDir', () => chooseDir(mainWindow))
ipcMain.handle('backup:resetDir', () => resetDir())
ipcMain.handle('backup:deleteLocal', (_e, file: string) => deleteLocal(file))
ipcMain.handle('backup:restoreFromLocal', (_e, file: string) => restoreFromLocal(backupConfig(), file))

// زمان‌بندِ پشتیبانِ خودکار.
//
// پیش از این، نسخه‌ی خودکار فقط *پس از همگام‌سازی* گرفته می‌شد؛ یعنی کاربری که یک
// هفته همگام‌سازی نمی‌کرد یک هفته بی‌پشتیبان می‌ماند. حالا یک تیکِ ساعتی هم هست و
// خودِ `autoSnapshot` تصمیم می‌گیرد که نوبتش رسیده یا نه (طبقِ فاصله‌ی تنظیم‌شده)،
// پس این تیک هیچ‌وقت بیش از حد نسخه نمی‌سازد. خطا عمداً بلعیده می‌شود: کارِ
// پس‌زمینه نباید به کاربر خطا نشان بدهد.
const BACKUP_TICK_MS = 60 * 60 * 1000
setInterval(() => {
  void autoSnapshot(backupConfig()).catch(() => {})
}, BACKUP_TICK_MS)

// --- کارتخوان (POS): پلِ سخت‌افزار فقط در دسکتاپ ---
// خطاها هرگز از IPC پرتاب نمی‌شوند؛ به نتیجه‌ی ساختاریافته تبدیل می‌شوند تا رابط
// کاربری همیشه پیامِ روشن نشان دهد نه یک reject خام.

ipcMain.handle(
  'pos:pay',
  async (_evt, profile: PosTerminalProfile, amountRial: number, refId: string): Promise<PayResult> => {
    try {
      return await driverFor(profile).pay(amountRial, refId)
    } catch (err) {
      return { approved: false, message: err instanceof Error ? err.message : 'خطای ناشناخته در ارتباط با کارتخوان' }
    }
  },
)

//: فهرستِ درگاه‌های سریال برای انتخابگرِ رابط. تایپ‌کردنِ دستیِ «COM3» یعنی
//: حدس‌زدن؛ و درگاهی که وجود ندارد خطایی می‌دهد که کاربر نمی‌داند از کجاست.
//: تعویضِ کسب‌وکار به این دو نیاز دارد: شمردنِ صف برای گارد، و پاک‌کردنِ کش
//: پس از تعویض. کش ستونِ مستأجر ندارد، پس داده‌ی کسب‌وکارِ قبلی باید برود.
ipcMain.handle('tenant:pendingOutbox', (): number => {
  try {
    return pendingOutboxCount()
  } catch {
    //: اگر شمارش ممکن نشد، **محافظه‌کارانه** عددی برمی‌گردد که گارد را ببندد؛
    //: بازگرداندنِ صفر یعنی اجازه‌ی تعویض با صفی که نمی‌دانیم خالی است یا نه.
    return -1
  }
})

ipcMain.handle('tenant:clearCaches', (): boolean => {
  try {
    clearReferenceCaches()
    return true
  } catch {
    return false
  }
})

ipcMain.handle('pos:serial-ports', async (): Promise<{ path: string; label: string }[]> => {
  try {
    return await listSerialPorts()
  } catch {
    return []
  }
})

ipcMain.handle('pos:status', async (_evt, profile: PosTerminalProfile): Promise<PosStatus> => {
  try {
    return await driverFor(profile).status()
  } catch (err) {
    return { online: false, message: err instanceof Error ? err.message : 'خطای ناشناخته در ارتباط با کارتخوان' }
  }
})

// --- به‌روزرسانی ---

ipcMain.handle('update:status', () => currentUpdateStatus())

ipcMain.handle('update:installNow', () => {
  quitAndInstall()
})
