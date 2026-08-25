export interface AccountCache {
  id: string
  code: string
  name: string
  type: string
  is_group: number
  parent_id: string | null
}

export interface WarehouseCache {
  id: string
  code: string
  name: string
}

export interface ItemCache {
  id: string
  sku: string
  name: string
  unit: string
  sales_price: string
  is_service: number
}

export interface BankAccountCache {
  id: string
  name: string
  bank_name: string
}

export interface OutboxEntry {
  local_id: string
  payload: string
  created_at: string
  synced: number
  server_id: string | null
  server_number: number | null
  sync_error: string | null
}

export interface PosTerminalProfileClient {
  transport: 'simulator' | 'network' | 'serial' | 'sdk'
  host?: string
  port?: number
  comPort?: string
  psp?: string
  simulateOutcome?: 'approve' | 'decline'
  simulateDelayMs?: number
}

export interface CardPayResult {
  approved: boolean
  message?: string
  rrn?: string
  traceNo?: string
  cardMask?: string
  terminalNo?: string
  datetime?: string
  psp?: string
  raw?: unknown
}

export interface PosStatusResult {
  online: boolean
  message?: string
}

export interface PosTerminalBridge {
  pay: (profile: PosTerminalProfileClient, amountRial: number, refId: string) => Promise<CardPayResult>
  status: (profile: PosTerminalProfileClient) => Promise<PosStatusResult>
}

export interface CubitaBridge {
  setAuthToken: (token: string | null) => Promise<void>
  pullAll: () => Promise<void>
  pushOutbox: () => Promise<{ pushed: number; failed: number }>
  queueJournalEntry: (payload: unknown) => Promise<string>
  listOutbox: () => Promise<OutboxEntry[]>
  queueSalesInvoice: (payload: unknown) => Promise<string>
  listSalesInvoiceOutbox: () => Promise<OutboxEntry[]>
  queueCheck: (payload: unknown) => Promise<string>
  listCheckOutbox: () => Promise<OutboxEntry[]>
  queuePurchaseInvoice: (payload: unknown) => Promise<string>
  listPurchaseInvoiceOutbox: () => Promise<OutboxEntry[]>
  listCachedAccounts: () => Promise<AccountCache[]>
  listCachedWarehouses: () => Promise<WarehouseCache[]>
  listCachedItems: () => Promise<ItemCache[]>
  listCachedBankAccounts: () => Promise<BankAccountCache[]>
  backupAuto: () => Promise<BackupAutoResult>
  backupSaveToFile: () => Promise<{ saved: boolean; path?: string }>
  backupListLocal: () => Promise<LocalBackup[]>
  backupOpenFolder: () => Promise<void>
  backupRestoreFromFile: () => Promise<{ restored: boolean; canceled?: boolean; message: string }>
  backupNow: () => Promise<LocalBackup>
  backupStatus: () => Promise<BackupStatus>
  backupGetSettings: () => Promise<BackupSettings>
  backupSetSettings: (patch: Partial<BackupSettings>) => Promise<BackupSettings>
  backupChooseDir: () => Promise<{ dir?: string; canceled?: boolean }>
  backupResetDir: () => Promise<BackupSettings>
  backupDeleteLocal: (file: string) => Promise<{ deleted: boolean }>
  backupRestoreFromLocal: (file: string) => Promise<{ restored: boolean; message: string }>
  posTerminal?: PosTerminalBridge
}

/** تنظیماتِ پشتیبانِ خودکار — آینه‌ی `BackupSettings` در electron/backup.ts. */
export interface BackupSettings {
  enabled: boolean
  /** کمینه‌ی فاصله‌ی دو نسخه‌ی خودکار (ساعت). ۰ = هر بار همگام‌سازی. */
  everyHours: number
  keep: number
  /** خالی = پوشه‌ی پیش‌فرضِ برنامه. */
  dir: string
}

export type BackupAutoResult =
  | { taken: true; backup: LocalBackup }
  | { taken: false; reason: 'disabled' | 'too-soon' | 'no-token'; nextAt?: number }

export interface BackupStatus {
  dir: string
  count: number
  totalSize: number
  last: LocalBackup | null
  /** زمانِ نسخه‌ی خودکارِ بعدی؛ null یعنی زمان‌بندی فعال نیست. */
  nextAt: number | null
  settings: BackupSettings
}

export interface LocalBackup {
  file: string
  path: string
  size: number
  mtime: number
}

export interface WindowControlsBridge {
  minimize: () => Promise<void>
  toggleMaximize: () => Promise<void>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
  onMaximizedChanged: (cb: (maximized: boolean) => void) => () => void
}

declare global {
  interface Window {
    cubita: CubitaBridge
    windowControls: WindowControlsBridge
  }
}
