import { app, BrowserWindow, ipcMain, Menu, MenuItem } from 'electron'
import path from 'node:path'
import fs from 'node:fs'

const DEBUG_LOG = path.join(app.getPath('userData'), 'startup-debug.log')
function debugLog(msg: string) {
  try {
    fs.mkdirSync(path.dirname(DEBUG_LOG), { recursive: true })
    fs.appendFileSync(DEBUG_LOG, `${new Date().toISOString()} ${msg}\n`)
  } catch {
    // اگر حتی لاگ‌نویسی هم شکست بخورد، کاری نمی‌توان کرد؛ فقط جلوی کرش اضافه را می‌گیریم
  }
}
import { startSidecar, stopSidecar } from './sidecar.js'
import { currentUpdateStatus, quitAndInstall, setupAutoUpdate } from './updater.js'

// محصولِ محلی: کلِ داده مستقیم از سایدکارِ FastAPIِ روی 127.0.0.1 خوانده/نوشته می‌شود
// (نه ابر، نه صف/کشِ آفلاین). این آدرس هنگامِ بالا آمدنِ سایدکار با پورتِ واقعیِ آزادش
// پر می‌شود و از راهِ additionalArguments به renderer می‌رود؛ مقدارِ اولیه فقط یک fallback
// برای حالتی است که سایدکار بالا نیاید (تا پنجره‌ی خطا آدرسی داشته باشد).
let API_BASE_URL = process.env.CUBITA_API_URL ?? 'http://127.0.0.1:8799'

let mainWindow: BrowserWindow | null = null

function createWindow(apiBaseUrl: string) {
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
      // پورتِ سایدکار پویاست؛ آدرسِ پایه را از همین‌جا به preload می‌دهیم تا api.ts در
      // renderer به همان پورتِ واقعی وصل شود (منبعِ یگانه‌ی حقیقت = پورتی که main گرفت).
      additionalArguments: [`--hesabdari-api=${apiBaseUrl}`],
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

app.whenReady().then(async () => {
  debugLog('app.whenReady resolved')
  try {
    Menu.setApplicationMenu(null) // منوی پیش‌فرض File/Edit/View/Window حذف می‌شود
    debugLog('menu cleared')

    // موتورِ محلی پیش از هر چیز بالا می‌آید؛ کلِ داده از آن می‌آید. اگر بالا نیاید،
    // پنجره را باز می‌کنیم تا کاربر خطا را ببیند (به‌جای اپِ خالیِ بی‌توضیح).
    try {
      const handle = await startSidecar(debugLog)
      API_BASE_URL = handle.baseUrl
      debugLog(`sidecar ready at ${API_BASE_URL}`)
    } catch (err) {
      debugLog(`SIDECAR ERROR: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`)
    }

    createWindow(API_BASE_URL)
    debugLog('createWindow called')

    setupAutoUpdate(() => mainWindow, debugLog)
    debugLog('auto-update wired')

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow(API_BASE_URL)
    })
  } catch (err) {
    debugLog(`STARTUP ERROR: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`)
  }
}).catch((err) => {
  debugLog(`whenReady REJECTED: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`)
})

// سایدکار باید با بسته‌شدنِ اپ خاموش شود، وگرنه پردازه‌ی پایتون یتیم می‌ماند.
app.on('will-quit', () => stopSidecar())

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// --- IPC: فقط کنترلِ پنجره و به‌روزرسانی. داده مستقیم از سایدکار می‌آید، پس دیگر
// هیچ پلِ صف/کش/همگام‌سازی وجود ندارد. ---

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

// --- به‌روزرسانی ---

ipcMain.handle('update:status', () => currentUpdateStatus())

ipcMain.handle('update:installNow', () => {
  quitAndInstall()
})
