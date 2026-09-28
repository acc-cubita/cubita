import { describe, expect, it } from 'vitest'
import { editableNetworkAdapters, initialNetworkConfig, NETWORK_TOPOLOGIES, type NetworkInventory } from './enterpriseNetwork'

const inventory: NetworkInventory = {
  role: 'server', state: { enabled: false, message: '' },
  adapters: [
    { id: 'lan', name: 'LAN 2', physical: true, kind: 'wired' },
    { id: 'wifi', name: 'Wireless 4', physical: true, kind: 'wifi' },
    { id: 'vpn', physical: false, kind: 'wired' },
  ] as NetworkInventory['adapters'],
  suggestions: { lan: { address: '192.168.91.1', prefix: 24, mode: 'static' }, wifi: { address: '10.2.3.4', prefix: 24, mode: 'keep' } },
}
describe('پیشنهاد و انتخاب شبکهٔ محلی', () => {
  it('نوع ارتباط، کارت فیزیکی را محدود می‌کند؛ نام/شماره ثابت فرض نمی‌شود', () => {
    expect(editableNetworkAdapters(inventory, 'direct').map((a) => a.id)).toEqual(['lan'])
    expect(editableNetworkAdapters(inventory, 'wifi-router').map((a) => a.id)).toEqual(['wifi'])
    expect(editableNetworkAdapters(inventory, 'mixed').map((a) => a.id)).toEqual(['lan', 'wifi'])
    expect(NETWORK_TOPOLOGIES).toHaveLength(5)
  })
  it('پیشنهاد ثابت فقط برای کابل مستقیم است و تأیید را از قبل تیک نمی‌زند', () => {
    expect(initialNetworkConfig(inventory, 'direct', 'lan')).toMatchObject({ address: '192.168.91.1', mode: 'static', staticConsent: false })
    expect(initialNetworkConfig(inventory, 'wired-router', 'lan').mode).toBe('keep')
  })
  it('با DHCP تازه، IP کهنه را روی کارت بازنویسی نمی‌کند', () => {
    const saved = initialNetworkConfig(inventory, 'wifi-router', 'wifi')
    const renewed = { ...inventory, state: { ...inventory.state, config: { ...saved, address: '10.2.3.3' } } }
    expect(initialNetworkConfig(renewed, 'wifi-router', 'wifi').address).toBe('10.2.3.4')
  })
})
