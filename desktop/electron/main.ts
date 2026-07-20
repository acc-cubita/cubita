import { app, BrowserWindow, ipcMain, Menu, MenuItem } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import { initLocalDb, getLocalDb } from './db.js'

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
import { currentUpdateStatus, quitAndInstall, setupAutoUpdate } from './updater.js'

// acc.cubita.ir و acc.ipnetcity.ir به یک بک‌اند می‌روند، ولی رندرر روی
// acc.cubita.ir ساخته می‌شود و این خط دامنه‌ی قدیمی را داشت. دو دامنه‌ی متفاوت در
// دو نیمه‌ی یک اپ یعنی هر تغییر آینده‌ای (CORS، کوکی، دامنه‌ی جدید) باید در دو جا
// یادآوری شود — و یکی‌شان فراموش می‌شود.
const API_BASE_URL =
  process.env.CUBITA_API_URL ?? (app.isPackaged ? 'https://acc.cubita.ir' : 'http://localhost:8000')

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

    setupAutoUpdate(() => mainWindow, debugLog)
    debugLog('auto-update wired')

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

ipcMain.handle('auth:setToken', (_evt, token: string | null) => {
  authToken = token
})

ipcMain.handle('sync:pullAll', async () => {
  const config = { apiBaseUrl: API_BASE_URL, getToken: () => authToken }
  await Promise.all([pullAccounts(config), pullWarehouses(config), pullItems(config), pullBankAccounts(config)])
})

ipcMain.handle('sync:pushOutbox', async () => {
  return pushOutbox({ apiBaseUrl: API_BASE_URL, getToken: () => authToken })
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

// --- به‌روزرسانی ---

ipcMain.handle('update:status', () => currentUpdateStatus())

ipcMain.handle('update:installNow', () => {
  quitAndInstall()
})
