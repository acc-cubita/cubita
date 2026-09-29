export type NetworkTopology = 'direct' | 'wired-router' | 'wifi-router' | 'mixed' | 'other'
export interface NetworkConfig {
  adapterId: string
  topology: NetworkTopology
  mode: 'keep' | 'static'
  address: string
  prefix: number
  port: number
  startup: boolean
  staticConsent: boolean
}
export interface NetworkAdapter {
  id: string
  name: string
  description: string
  index: number
  physical: boolean
  kind: 'wired' | 'wifi' | 'other'
  status: string
  dhcp: boolean
  addresses: { address: string; prefix: number; origin?: string }[]
  gateways: string[]
  defaultRoute: boolean
  profile: string
  networkId?: string | null
}
export interface NetworkState {
  enabled: boolean
  message: string
  config?: NetworkConfig
  serverUrl?: string
}
export interface NetworkInventory {
  adapters: NetworkAdapter[]
  suggestions: Record<string, { address: string; prefix: number; mode: 'keep' | 'static' }>
  role: 'server' | 'client'
  state: NetworkState
}
export interface NetworkPlan {
  config: NetworkConfig
  adapterName: string
  subnet: string
  serverUrl: string
  addAddress: boolean
  warnings: string[]
}
export type NetworkResult<T> = { ok: true; data: T } | { ok: false; error: string }

export const NETWORK_TOPOLOGIES: { value: NetworkTopology; label: string; hint: string }[] = [
  { value: 'direct', label: 'کابل LAN مستقیم بین رایانه‌ها', hint: 'کارت سیمیِ جدا از اینترنت؛ سرور و کلاینت باید IP متفاوت در یک محدوده داشته باشند.' },
  { value: 'wired-router', label: 'LAN از طریق مودم، روتر یا سوئیچ', hint: 'IP و DHCP مودم حفظ می‌شود؛ برای IP ثابت سرور، رزرو DHCP را در مودم تنظیم کنید.' },
  { value: 'wifi-router', label: 'Wi‑Fi از طریق مودم یا روتر', hint: 'هر دو رایانه در شبکهٔ مورد اعتماد باشند؛ شبکهٔ مهمان ممکن است ارتباط بین دستگاه‌ها را ببندد.' },
  { value: 'mixed', label: 'ترکیبی از LAN و Wi‑Fi', hint: 'کارتی را انتخاب کنید که کلاینت‌ها از آن به سرور می‌رسند؛ تنظیم کارت دیگر تغییر نمی‌کند.' },
  { value: 'other', label: 'ارتباط دیگر / تنظیم دستی', hint: 'تنظیمات فعلی حفظ می‌شود؛ VPN و کارت مجازی برای تنظیم خودکار انتخاب نمی‌شوند.' },
]

export function editableNetworkAdapters(inventory: NetworkInventory, topology: NetworkTopology): NetworkAdapter[] {
  return inventory.adapters.filter((a) => a.physical &&
    (topology === 'direct' || topology === 'wired-router' ? a.kind === 'wired' :
      topology === 'wifi-router' ? a.kind === 'wifi' : a.kind === 'wired' || a.kind === 'wifi'))
}

export function initialNetworkConfig(inventory: NetworkInventory, topology: NetworkTopology, adapterId: string): NetworkConfig {
  const suggestion = inventory.suggestions[adapterId]
  const saved = inventory.state.config
  if (saved?.adapterId === adapterId && saved.topology === topology) return { ...saved, ...(saved.mode === 'keep' && suggestion ? { address: suggestion.address, prefix: suggestion.prefix } : {}), staticConsent: false }
  return {
    adapterId, topology, mode: topology === 'direct' ? suggestion?.mode ?? 'keep' : 'keep',
    address: suggestion?.address ?? '', prefix: suggestion?.prefix ?? 24,
    port: 8420, startup: true, staticConsent: false,
  }
}
