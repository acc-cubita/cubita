import { describe, expect, it } from 'vitest'
import { candidateHosts, isPrivateIPv4, normalizeServerUrl } from './serverAddress'

const ok = (input: string) => {
  const r = normalizeServerUrl(input)
  if (!r.ok) throw new Error(r.error)
  return r.url
}

describe('normalizeServerUrl', () => {
  it('adds scheme and the Cubita port to a bare machine name', () => {
    expect(ok('acc-server')).toBe('http://acc-server:8420')
  })
  it('keeps an explicit port and drops path and trailing slash', () => {
    expect(ok(' http://192.168.1.10:9000/api/ ')).toBe('http://192.168.1.10:9000')
  })
  it('adds the Cubita port to a bare IP', () => {
    expect(ok('192.168.1.10')).toBe('http://192.168.1.10:8420')
  })
  it('leaves https behind a proxy on its default port', () => {
    expect(ok('https://acc.company.local')).toBe('https://acc.company.local')
  })
  it('rejects empty, credentials and other schemes', () => {
    expect(normalizeServerUrl('   ').ok).toBe(false)
    expect(normalizeServerUrl('http://u:p@host').ok).toBe(false)
    expect(normalizeServerUrl('ftp://host').ok).toBe(false)
  })
})

describe('candidateHosts', () => {
  const lan = { address: '192.168.1.23', family: 'IPv4', internal: false }
  it('scans the /24 of private interfaces, skipping itself', () => {
    const hosts = candidateHosts([lan])
    expect(hosts).toHaveLength(253)
    expect(hosts).toContain('192.168.1.1')
    expect(hosts).not.toContain('192.168.1.23')
  })
  it('never scans public, loopback or IPv6 interfaces', () => {
    expect(
      candidateHosts([
        { address: '5.160.10.4', family: 'IPv4', internal: false },
        { address: '127.0.0.1', family: 'IPv4', internal: true },
        { address: 'fe80::1', family: 'IPv6', internal: false },
      ]),
    ).toEqual([])
  })
  it('recognises the three private ranges', () => {
    expect(isPrivateIPv4('10.2.3.4')).toBe(true)
    expect(isPrivateIPv4('172.20.0.1')).toBe(true)
    expect(isPrivateIPv4('172.40.0.1')).toBe(false)
    expect(isPrivateIPv4('192.168.0.9')).toBe(true)
  })
})
