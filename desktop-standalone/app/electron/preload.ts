import { contextBridge, ipcRenderer } from 'electron'

// نسخه‌ی محلی: پلِ صف/کشِ آفلاینِ ابری (`cubita`) حذف شد؛ کلِ داده مستقیم از سایدکارِ
// FastAPIِ محلی خوانده/نوشته می‌شود. فقط پل‌های پوسته‌ی دسکتاپ (کنترلِ پنجره، به‌روزرسانی)
// و آدرسِ پایه‌ی سایدکار باقی می‌مانند.

contextBridge.exposeInMainWorld('windowControls', {
  minimize: () => ipcRenderer.invoke('window:minimize'),
  toggleMaximize: () => ipcRenderer.invoke('window:toggleMaximize'),
  close: () => ipcRenderer.invoke('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
  onMaximizedChanged: (cb: (maximized: boolean) => void) => {
    const listener = (_evt: unknown, maximized: boolean) => cb(maximized)
    ipcRenderer.on('window:maximizedChanged', listener)
    return () => ipcRenderer.removeListener('window:maximizedChanged', listener)
  },
})

// آدرسِ پایه‌ی موتورِ محلی که main هنگامِ اسپاونِ سایدکار انتخاب کرد (پورت پویاست).
// از طریقِ additionalArguments به این پردازه رسیده؛ api.ts در renderer آن را می‌خواند.
const apiArg = process.argv.find((a) => a.startsWith('--hesabdari-api='))
contextBridge.exposeInMainWorld('hesabdariEnv', {
  apiBaseUrl: apiArg ? apiArg.slice('--hesabdari-api='.length) : null,
})

contextBridge.exposeInMainWorld('cubitaUpdate', {
  status: () => ipcRenderer.invoke('update:status'),
  installNow: () => ipcRenderer.invoke('update:installNow'),
  onStatus: (cb: (status: unknown) => void) => {
    const listener = (_evt: unknown, status: unknown) => cb(status)
    ipcRenderer.on('update:status', listener)
    return () => ipcRenderer.removeListener('update:status', listener)
  },
})
