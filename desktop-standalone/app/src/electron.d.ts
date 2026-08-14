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

export interface WindowControlsBridge {
  minimize: () => Promise<void>
  toggleMaximize: () => Promise<void>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
  onMaximizedChanged: (cb: (maximized: boolean) => void) => () => void
}

/** آدرسِ پایه‌ی موتورِ محلی که main (هنگامِ اسپاونِ سایدکار) از طریقِ preload می‌دهد. */
export interface HesabdariEnvBridge {
  apiBaseUrl: string | null
}

declare global {
  interface Window {
    // در اجرای وبِ صرف (بدونِ preload) هیچ‌کدام موجود نیستند؛ به همین خاطر اختیاری.
    windowControls?: WindowControlsBridge
    hesabdariEnv?: HesabdariEnvBridge
  }
}
