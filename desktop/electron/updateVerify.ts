// سنجشِ آپدیتِ «کوبیتا سازمانی» پیش از نصب — منطقِ خالص (بدونِ Electron)، تست‌پذیر.
//
// electron-updater هشِ فایل را با `latest.yml` می‌سنجد، ولی خودِ `latest.yml` روی HTTPِ شبکه‌ی
// داخلی از سرورِ شرکت می‌آید و هر کسی روی آن شبکه می‌تواند عوضش کند. پس کلاینت خودش
// `latest.yml` و امضای Ed25519اش را می‌گیرد، امضا را با کلیدِ عمومیِ داخلِ برنامه می‌سنجد، و
// sha512ِ **فایلِ دانلودشده** را با همان `latest.yml`ِ سنجیده مقایسه می‌کند. فقط آن‌وقت نصب
// مجاز است. قالب و پیشوندِ امضا عیناً `backend/app/onprem/updates.py` است.

import { createHash, createPublicKey, verify } from 'node:crypto'
import fs from 'node:fs'

export const UPDATE_CONTEXT = Buffer.from('cubita-update-v1\n', 'utf8')

//: سرآیندِ DERِ SubjectPublicKeyInfo برای Ed25519 — کلیدِ خامِ ۳۲ بایتی پشتِ آن می‌نشیند.
const ED25519_SPKI_PREFIX = Buffer.from('302a300506032b6570032100', 'hex')

export function b64uDecode(text: string): Buffer {
  return Buffer.from(text.trim().replace(/-/g, '+').replace(/_/g, '/'), 'base64')
}

export function verifyManifestSignature(data: Buffer, signature: string, keys: Record<string, string>): boolean {
  const sig = b64uDecode(signature)
  for (const raw of Object.values(keys)) {
    try {
      const key = createPublicKey({ key: Buffer.concat([ED25519_SPKI_PREFIX, b64uDecode(raw)]), format: 'der', type: 'spki' })
      if (verify(null, Buffer.concat([UPDATE_CONTEXT, data]), key, sig)) return true
    } catch {
      // کلیدِ خراب در فهرست نباید بقیه را از کار بیندازد.
    }
  }
  return false
}

/** `sha512`ِ سطحِ اولِ latest.yml (همان که مسیرِ `path` را توصیف می‌کند). */
export function manifestSha512(text: string): string | null {
  const m = /^sha512:\s*(\S+)\s*$/m.exec(text)
  return m ? m[1].replace(/^['"]|['"]$/g, '') : null
}

export function fileSha512(file: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const h = createHash('sha512')
    fs.createReadStream(file)
      .on('data', (chunk) => h.update(chunk))
      .on('error', reject)
      .on('end', () => resolve(h.digest('base64')))
  })
}

/**
 * `null` یعنی نصب مجاز است؛ در غیرِ این صورت پیامِ فارسیِ دلیلِ رد.
 * `fetchImpl` برای تست جایگزین می‌شود.
 */
export async function verifyDownloadedUpdate(
  feedUrl: string,
  downloadedFile: string,
  keys: Record<string, string>,
  fetchImpl: typeof fetch = fetch,
  expectedVersion?: string,
): Promise<string | null> {
  const result = await readVerifiedManifest(feedUrl, keys, fetchImpl)
  if (typeof result === 'string') return result
  const text = result.toString('utf8')
  if (expectedVersion && manifestValue(text, 'version') !== expectedVersion) {
    return 'نسخه فایل دانلودشده با نسخه امضاشده سرور یکی نیست؛ دوباره بررسی کنید.'
  }
  const expected = manifestSha512(text)
  if (!expected) return 'فایلِ latest.yml ناقص است؛ آپدیت نصب نشد.'
  const actual = await fileSha512(downloadedFile)
  if (actual !== expected) return 'فایلِ دانلودشده با نسخه‌ی امضاشده یکی نیست؛ آپدیت نصب نشد.'
  return null
}

function manifestValue(text: string, name: string): string | null {
  return new RegExp(`^${name}:\\s*(.+)$`, 'm').exec(text)?.[1]?.trim().replace(/^['"]|['"]$/g, '') ?? null
}

export async function verifyUpdateFeed(feedUrl: string, keys: Record<string, string>, fetchImpl: typeof fetch = fetch): Promise<string | null> {
  const result = await readVerifiedManifest(feedUrl, keys, fetchImpl)
  if (typeof result === 'string') return result
  const text = result.toString('utf8')
  const names = [manifestValue(text, 'path'), ...Array.from(text.matchAll(/^\s*(?:-\s*)?url:\s*(.+)$/gm), (m) => m[1].trim().replace(/^['"]|['"]$/g, ''))]
  if (!manifestValue(text, 'version') || !manifestSha512(text) || names.some((name) => !name || !/^[A-Za-z0-9._ -]+\.exe$/.test(name))) {
    return 'فهرست آپدیت سرور ناقص است یا فایل خارج از سرور شرکت را معرفی می‌کند؛ نصب انجام نمی‌شود.'
  }
  return null
}

async function readVerifiedManifest(feedUrl: string, keys: Record<string, string>, fetchImpl: typeof fetch): Promise<Buffer | string> {
  if (Object.keys(keys).length === 0) {
    return 'کلیدِ امضای آپدیت در این نسخه تعریف نشده است؛ آپدیت نصب نمی‌شود.'
  }
  const base = feedUrl.endsWith('/') ? feedUrl : `${feedUrl}/`
  let manifest: Buffer
  let signature: string
  try {
    const [m, s] = await Promise.all([
      fetchImpl(`${base}latest.yml`, { cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10_000) }),
      fetchImpl(`${base}latest.yml.sig`, { cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10_000) }),
    ])
    if (!m.ok || !s.ok) return 'امضای آپدیت از سرور گرفته نشد؛ آپدیت نصب نمی‌شود.'
    manifest = Buffer.from(await m.arrayBuffer())
    signature = await s.text()
  } catch {
    return 'امضای آپدیت از سرور گرفته نشد؛ آپدیت نصب نمی‌شود.'
  }
  if (!verifyManifestSignature(manifest, signature, keys)) {
    return 'امضای آپدیت معتبر نیست؛ ممکن است فایل روی شبکه دست‌کاری شده باشد. آپدیت نصب نشد.'
  }
  return manifest
}
