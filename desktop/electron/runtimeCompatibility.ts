import {webcrypto} from 'node:crypto'

declare const __CUBITA_LEGACY_WINDOWS__: boolean
export const LEGACY_WINDOWS = typeof __CUBITA_LEGACY_WINDOWS__ !== 'undefined' && __CUBITA_LEGACY_WINDOWS__

// Electron 22 embeds Node 16; keep this runtime confined to the separate 8.1 edition.
if (LEGACY_WINDOWS) {
  const compatible = require('undici') as typeof globalThis
  if (!globalThis.fetch) {
    globalThis.fetch = compatible.fetch
    globalThis.Headers = compatible.Headers
    globalThis.Request = compatible.Request
    globalThis.Response = compatible.Response
  }
  if (!globalThis.crypto) globalThis.crypto = webcrypto as unknown as typeof globalThis.crypto
}
