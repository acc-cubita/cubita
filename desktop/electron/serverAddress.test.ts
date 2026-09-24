import { describe, expect, it } from 'vitest'
import { normalizeServerUrl } from './serverAddress'

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
