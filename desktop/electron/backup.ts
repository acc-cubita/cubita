import { app, dialog, shell, type BrowserWindow } from 'electron'
import path from 'node:path'
import fs from 'node:fs'

// پشتیبان‌گیری/بازیابیِ محلی برای نسخه‌ی دسکتاپ.
//
// داده‌ی اصلی روی سرور ابری می‌ماند؛ اینجا یک نسخه‌ی کاملِ JSON از داده‌ی همین
// کسب‌وکار روی خودِ سیستمِ کاربر ذخیره می‌شود — هم خودکار (پس از هر همگام‌سازی) و هم
// دستی (دکمه‌ی «ذخیره روی کامپیوتر»). بازیابی همان فایل را به سرور می‌فرستد و داده را
// *جایگزین* می‌کند. گرفتنِ خروجی و اعتبارسنجی سمتِ سرور است ([routers/backup.py]).

interface BackupConfig {
  apiBaseUrl: string
  getToken: () => string | null
}

export interface LocalBackup {
  file: string
  path: string
  size: number
  mtime: number
}

const MAX_LOCAL = 20

function backupDir(): string {
  return path.join(app.getPath('userData'), 'backups')
}

function ensureDir(): void {
  fs.mkdirSync(backupDir(), { recursive: true })
}

function snapshotName(): string {
  const ts = new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)
  return `cubita-backup-${ts}.json`
}

async function fetchExport(config: BackupConfig): Promise<string> {
  const token = config.getToken()
  if (!token) throw new Error('برای پشتیبان‌گیری باید وارد شده باشید.')
  const res = await fetch(`${config.apiBaseUrl}/api/backup/export`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    if (res.status === 403) throw new Error('فقط مالکِ کسب‌وکار می‌تواند پشتیبان‌گیری کند.')
    throw new Error(`خطا در دریافتِ پشتیبان (${res.status})`)
  }
  return JSON.stringify(await res.json())
}

export function listLocalBackups(): LocalBackup[] {
  ensureDir()
  return fs
    .readdirSync(backupDir())
    .filter((f) => f.endsWith('.json'))
    .map((f) => {
      const p = path.join(backupDir(), f)
      const st = fs.statSync(p)
      return { file: f, path: p, size: st.size, mtime: st.mtimeMs }
    })
    .sort((a, b) => b.mtime - a.mtime)
}

function rotate(): void {
  for (const b of listLocalBackups().slice(MAX_LOCAL)) {
    try {
      fs.unlinkSync(b.path)
    } catch {
      // اگر پاک‌کردنِ نسخه‌ی قدیمی شکست خورد مهم نیست؛ فقط فضا کمی بیشتر می‌ماند
    }
  }
}

function writeLocal(json: string): LocalBackup {
  ensureDir()
  const p = path.join(backupDir(), snapshotName())
  fs.writeFileSync(p, json, 'utf8')
  rotate()
  const st = fs.statSync(p)
  return { file: path.basename(p), path: p, size: st.size, mtime: st.mtimeMs }
}

/** اسنپ‌شاتِ خودکار: خروجی را می‌گیرد و در پوشه‌ی محلی می‌نویسد و نسخه‌های کهنه را می‌چرخاند. */
export async function autoSnapshot(config: BackupConfig): Promise<LocalBackup> {
  return writeLocal(await fetchExport(config))
}

/** ذخیره در محلِ دلخواهِ کاربر (USB/درایو) با دیالوگ؛ یک کپی هم در پوشه‌ی محلی می‌ماند. */
export async function saveToFile(
  config: BackupConfig,
  win: BrowserWindow | null,
): Promise<{ saved: boolean; path?: string }> {
  const json = await fetchExport(config)
  const opts = {
    title: 'ذخیره‌ی نسخه‌ی پشتیبان',
    defaultPath: snapshotName(),
    filters: [{ name: 'Cubita Backup', extensions: ['json'] }],
  }
  const r = win ? await dialog.showSaveDialog(win, opts) : await dialog.showSaveDialog(opts)
  if (r.canceled || !r.filePath) return { saved: false }
  fs.writeFileSync(r.filePath, json, 'utf8')
  try {
    writeLocal(json)
  } catch {
    // کپیِ محلیِ کمکی؛ اگر نشد، فایلِ انتخابیِ کاربر که ذخیره شده کافی است
  }
  return { saved: true, path: r.filePath }
}

export async function openBackupsFolder(): Promise<void> {
  ensureDir()
  await shell.openPath(backupDir())
}

/** بازیابی از فایل: دیالوگِ باز، خواندن، و ارسال به سرور برای *جایگزینیِ* داده. */
export async function restoreFromFile(
  config: BackupConfig,
  win: BrowserWindow | null,
): Promise<{ restored: boolean; canceled?: boolean; message: string }> {
  const token = config.getToken()
  if (!token) return { restored: false, message: 'برای بازیابی باید وارد شده باشید.' }
  const opts = {
    title: 'انتخابِ فایلِ پشتیبان برای بازیابی',
    properties: ['openFile' as const],
    filters: [{ name: 'Cubita Backup', extensions: ['json'] }],
  }
  const r = win ? await dialog.showOpenDialog(win, opts) : await dialog.showOpenDialog(opts)
  if (r.canceled || !r.filePaths[0]) return { restored: false, canceled: true, message: '' }

  let body: string
  try {
    body = fs.readFileSync(r.filePaths[0], 'utf8')
    JSON.parse(body)
  } catch {
    return { restored: false, message: 'فایلِ انتخابی یک پشتیبانِ معتبر نیست.' }
  }

  const res = await fetch(`${config.apiBaseUrl}/api/backup/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body,
  })
  if (!res.ok) {
    if (res.status === 403) return { restored: false, message: 'فقط مالکِ کسب‌وکار می‌تواند بازیابی کند.' }
    if (res.status === 400) return { restored: false, message: 'فایلِ پشتیبان معتبر نیست.' }
    return { restored: false, message: `خطا در بازیابی (${res.status})` }
  }
  const out = (await res.json()) as { total_rows?: number }
  const n = (out.total_rows ?? 0).toLocaleString('fa-IR')
  return { restored: true, message: `بازیابی کامل شد — ${n} ردیف بازگردانده شد.` }
}
