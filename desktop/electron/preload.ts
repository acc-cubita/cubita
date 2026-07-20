import { contextBridge, ipcRenderer } from 'electron'

// تنها سطح دسترسی مجاز renderer به دنیای بیرون: چند فراخوانی IPC مشخص، نه دسترسی خام به Node/فایل‌سیستم.
contextBridge.exposeInMainWorld('cubita', {
  setAuthToken: (token: string | null) => ipcRenderer.invoke('auth:setToken', token),
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
