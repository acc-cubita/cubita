import { contextBridge, ipcRenderer } from 'electron'

// نسخه و نشانیِ سرور — همزمان، چون api.ts پیش از اولین fetch به آن نیاز دارد.
contextBridge.exposeInMainWorld('cubitaConfig', ipcRenderer.sendSync('server:config'))

// تنها سطح دسترسی مجاز renderer به دنیای بیرون: چند فراخوانی IPC مشخص، نه دسترسی خام به Node/فایل‌سیستم.
contextBridge.exposeInMainWorld('cubita', {
  setAuthToken: (token: string | null) => ipcRenderer.invoke('auth:setToken', token),
  // نشستِ آفلاین — بارِ اول یوزر/پسورد، از آن به بعد اپ خودش وارد می‌ماند.
  persistSession: (access: string, refresh: string, me: unknown) =>
    ipcRenderer.invoke('auth:persistSession', access, refresh, me),
  restoreSession: () => ipcRenderer.invoke('auth:restoreSession'),
  clearSession: () => ipcRenderer.invoke('auth:clearSession'),
  currentRefreshToken: () => ipcRenderer.invoke('auth:currentRefreshToken'),
  pullAll: () => ipcRenderer.invoke('sync:pullAll'),
  pushOutbox: () => ipcRenderer.invoke('sync:pushOutbox'),
  queueJournalEntry: (payload: unknown) => ipcRenderer.invoke('journal:queueEntry', payload),
  listOutbox: () => ipcRenderer.invoke('journal:listOutbox'),
  queueSalesInvoice: (payload: unknown) => ipcRenderer.invoke('invoice:queueSalesInvoice', payload),
  listSalesInvoiceOutbox: () => ipcRenderer.invoke('invoice:listOutbox'),
  queueCheck: (payload: unknown) => ipcRenderer.invoke('check:queueCheck', payload),
  listCheckOutbox: () => ipcRenderer.invoke('check:listOutbox'),
  queuePurchaseInvoice: (payload: unknown) => ipcRenderer.invoke('purchaseInvoice:queue', payload),
  listPurchaseInvoiceOutbox: () => ipcRenderer.invoke('purchaseInvoice:listOutbox'),
  listCachedAccounts: () => ipcRenderer.invoke('accounts:listCached'),
  listCachedWarehouses: () => ipcRenderer.invoke('warehouses:listCached'),
  listCachedItems: () => ipcRenderer.invoke('items:listCached'),
  listCachedBankAccounts: () => ipcRenderer.invoke('bankAccounts:listCached'),
  // پشتیبان‌گیری/بازیابیِ محلی
  backupAuto: () => ipcRenderer.invoke('backup:auto'),
  backupSaveToFile: () => ipcRenderer.invoke('backup:saveToFile'),
  backupListLocal: () => ipcRenderer.invoke('backup:listLocal'),
  backupOpenFolder: () => ipcRenderer.invoke('backup:openFolder'),
  backupRestoreFromFile: () => ipcRenderer.invoke('backup:restoreFromFile'),
  backupNow: () => ipcRenderer.invoke('backup:now'),
  backupStatus: () => ipcRenderer.invoke('backup:status'),
  backupGetSettings: () => ipcRenderer.invoke('backup:getSettings'),
  backupSetSettings: (patch: unknown) => ipcRenderer.invoke('backup:setSettings', patch),
  backupChooseDir: () => ipcRenderer.invoke('backup:chooseDir'),
  backupResetDir: () => ipcRenderer.invoke('backup:resetDir'),
  backupDeleteLocal: (file: string) => ipcRenderer.invoke('backup:deleteLocal', file),
  backupRestoreFromLocal: (file: string) => ipcRenderer.invoke('backup:restoreFromLocal', file),
  // پلِ کارتخوان — فقط در دسکتاپ تعریف می‌شود؛ در نسخه‌ی وب window.cubita وجود ندارد،
  // پس رابط کاربری با feature-detect دکمه را «فقط دسکتاپ» نشان می‌دهد.
  //: تعویضِ کسب‌وکار — شمارشِ صف برای گارد، و پاک‌کردنِ کشِ مرجع پس از تعویض.
  tenantPendingOutbox: () => ipcRenderer.invoke('tenant:pendingOutbox'),
  tenantClearCaches: () => ipcRenderer.invoke('tenant:clearCaches'),
  //: کوبیتا سازمانی — آزمایش و ذخیره‌ی نشانیِ سرورِ شرکت.
  serverProbe: (url: string) => ipcRenderer.invoke('server:probe', url),
  serverSave: (url: string) => ipcRenderer.invoke('server:save', url),
  posTerminal: {
    pay: (profile: unknown, amountRial: number, refId: string) =>
      ipcRenderer.invoke('pos:pay', profile, amountRial, refId),
    status: (profile: unknown) => ipcRenderer.invoke('pos:status', profile),
    serialPorts: () => ipcRenderer.invoke('pos:serial-ports'),
  },
})

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

contextBridge.exposeInMainWorld('cubitaUpdate', {
  status: () => ipcRenderer.invoke('update:status'),
  installNow: () => ipcRenderer.invoke('update:installNow'),
  onStatus: (cb: (status: unknown) => void) => {
    const listener = (_evt: unknown, status: unknown) => cb(status)
    ipcRenderer.on('update:status', listener)
    return () => ipcRenderer.removeListener('update:status', listener)
  },
})
