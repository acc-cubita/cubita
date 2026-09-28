import { expect, it } from 'vitest'
import { trustedNetworkHelper, NETWORK_INSTALL_ACL_CHECK } from './enterpriseNetworkPaths'

it('helper elevated باید داخل Program Files باشد، نه مسیر توسعه/کاربر یا پیشوند مشابه', () => {
  const roots = ['C:\\Program Files', 'D:\\Program Files']
  expect(trustedNetworkHelper('C:\\Program Files\\Cubita Enterprise\\resources\\server\\cubita-server.exe', roots)).toBe(true)
  for (const executable of ['D:\\repo\\cubita-server.exe', 'C:\\Program Files Evil\\cubita-server.exe', 'C:\\Program Files\\..\\Users\\a\\cubita-server.exe', 'C:\\Program Files\\Cubita\\evil.exe']) {
    expect(trustedNetworkHelper(executable, roots)).toBe(false)
  }
  expect(NETWORK_INSTALL_ACL_CHECK).toContain('ReparsePoint')
  expect(NETWORK_INSTALL_ACL_CHECK).toContain('GetOwner')
  expect(NETWORK_INSTALL_ACL_CHECK).toContain('-Recurse')
})
