import { createHash, generateKeyPairSync, sign } from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { UPDATE_CONTEXT, verifyDownloadedUpdate, verifyManifestSignature } from './updateVerify'

const { publicKey, privateKey } = generateKeyPairSync('ed25519')
const rawPublic = publicKey.export({ format: 'jwk' }).x as string
const KEYS = { test: rawPublic }

const b64u = (b: Buffer) => b.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const signManifest = (data: Buffer) => b64u(sign(null, Buffer.concat([UPDATE_CONTEXT, data]), privateKey))

function fixture(installer: Buffer) {
  const sha = createHash('sha512').update(installer).digest('base64')
  const manifest = Buffer.from(`version: 1.8.0\npath: Setup.exe\nsha512: ${sha}\n`)
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cubita-upd-'))
  const file = path.join(dir, 'Setup.exe')
  fs.writeFileSync(file, installer)
  return { manifest, file }
}

function feed(files: Record<string, Buffer | string>): typeof fetch {
  return (async (url: string | URL | Request) => {
    const name = String(url).split('/').pop() ?? ''
    const body = files[name]
    return body === undefined ? new Response('', { status: 404 }) : new Response(body)
  }) as typeof fetch
}

describe('verifyDownloadedUpdate', () => {
  const installer = Buffer.from('MZ-cubita-installer')

  it('accepts a signed manifest whose hash matches the downloaded file', async () => {
    const { manifest, file } = fixture(installer)
    const sig = signManifest(manifest)
    expect(await verifyDownloadedUpdate('http://srv:8420/updates/', file, KEYS, feed({ 'latest.yml': manifest, 'latest.yml.sig': sig }))).toBeNull()
  })

  it('rejects a manifest swapped on the LAN', async () => {
    const { manifest, file } = fixture(installer)
    const sig = signManifest(manifest)
    const evil = Buffer.from(manifest.toString().replace('1.8.0', '9.9.9'))
    const err = await verifyDownloadedUpdate('http://srv', file, KEYS, feed({ 'latest.yml': evil, 'latest.yml.sig': sig }))
    expect(err).toMatch(/امضا/)
  })

  it('rejects a downloaded file that differs from the signed hash', async () => {
    const { manifest } = fixture(installer)
    const { file } = fixture(Buffer.from('MZ-evil'))
    const err = await verifyDownloadedUpdate('http://srv', file, KEYS, feed({ 'latest.yml': manifest, 'latest.yml.sig': signManifest(manifest) }))
    expect(err).toMatch(/یکی نیست/)
  })

  it('fails closed without keys or without a signature', async () => {
    const { manifest, file } = fixture(installer)
    expect(await verifyDownloadedUpdate('http://srv', file, {}, feed({}))).toMatch(/کلید/)
    expect(await verifyDownloadedUpdate('http://srv', file, KEYS, feed({ 'latest.yml': manifest }))).toMatch(/گرفته نشد/)
  })

  it('does not accept a signature made without the update context', () => {
    const data = Buffer.from('version: 1.8.0\n')
    const bare = b64u(sign(null, data, privateKey))
    expect(verifyManifestSignature(data, bare, KEYS)).toBe(false)
  })
})
