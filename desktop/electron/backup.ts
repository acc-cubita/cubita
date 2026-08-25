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

/** تنظیماتِ پشتیبان‌گیریِ خودکار — در userData کنارِ خودِ نسخه‌ها نگه داشته می‌شود. */
export interface BackupSettings {
  /** پشتیبان‌گیریِ خودکار روشن است یا نه. */
  enabled: boolean
  /** کمینه‌ی فاصله‌ی دو نسخه‌ی خودکار (ساعت). ۰ یعنی هر بار همگام‌سازی. */
  everyHours: number
  /** چند نسخه نگه داشته شود؛ کهنه‌ترها چرخانده می‌شوند. */
  keep: number
  /** پوشه‌ی مقصد. خالی یعنی پوشه‌ی پیش‌فرضِ برنامه. */
  dir: string
}

const DEFAULTS: BackupSettings = { enabled: true, everyHours: 24, keep: 20, dir: '' }

function settingsPath(): string {
  return path.join(app.getPath('userData'), 'backup-settings.json')
}

export function getSettings(): BackupSettings {
  try {
    const raw = JSON.parse(fs.readFileSync(settingsPath(), 'utf8')) as Partial<BackupSettings>
    return {
      enabled: raw.enabled ?? DEFAULTS.enabled,
      // مقادیرِ بی‌معنا (منفی، غیرعدد) نباید زمان‌بند را خراب کنند.
      everyHours: Math.min(Math.max(Number(raw.everyHours ?? DEFAULTS.everyHours) || 0, 0), 24 * 30),
      keep: Math.min(Math.max(Number(raw.keep ?? DEFAULTS.keep) || 1, 1), 200),
      dir: typeof raw.dir === 'string' ? raw.dir : '',
    }
  } catch {
    // نبودن/خرابیِ فایل یعنی هنوز چیزی تنظیم نشده — پیش‌فرضِ امن.
    return { ...DEFAULTS }
  }
}

export function setSettings(patch: Partial<BackupSettings>): BackupSettings {
  const next = { ...getSettings(), ...patch }
  const clean: BackupSettings = {
    enabled: Boolean(next.enabled),
    everyHours: Math.min(Math.max(Number(next.everyHours) || 0, 0), 24 * 30),
    keep: Math.min(Math.max(Number(next.keep) || 1, 1), 200),
    dir: typeof next.dir === 'string' ? next.dir : '',
  }
  fs.writeFileSync(settingsPath(), JSON.stringify(clean, null, 2), 'utf8')
  // تغییرِ نگه‌داری باید همان لحظه اعمال شود، نه نسخه‌ی بعد.
  try {
    rotate()
  } catch {
    // چرخاندن اختیاری است؛ نباید ذخیره‌ی تنظیمات را شکست بدهد.
  }
  return clean
}

const MAX_LOCAL = 20

function backupDir(): string {
  const custom = getSettings().dir
  return custom || path.join(app.getPath('userData'), 'backups')
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
  const keep = getSettings().keep || MAX_LOCAL
  for (const b of listLocalBackups().slice(keep)) {
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

/** نتیجه‌ی یک تلاشِ خودکار — رد شدن هم یک نتیجه‌ی درست است، نه خطا. */
export type AutoResult =
  | { taken: true; backup: LocalBackup }
  | { taken: false; reason: 'disabled' | 'too-soon' | 'no-token'; nextAt?: number }

/**
 * اسنپ‌شاتِ خودکار با احترام به تنظیمات.
 *
 * دو چیز جلویش را می‌گیرد: خاموش‌بودنِ قابلیت، و نرسیدنِ فاصله‌ی تعیین‌شده از آخرین
 * نسخه. هیچ‌کدام خطا نیستند، پس به‌جای throw دلیل برگردانده می‌شود تا هم صداکننده‌ی
 * پس‌زمینه ساکت بماند و هم صفحه‌ی تنظیمات بتواند وضعیت را نشان بدهد.
 */
export async function autoSnapshot(config: BackupConfig): Promise<AutoResult> {
  const s = getSettings()
  if (!s.enabled) return { taken: false, reason: 'disabled' }
  if (!config.getToken()) return { taken: false, reason: 'no-token' }

  if (s.everyHours > 0) {
    const last = listLocalBackups()[0]
    if (last) {
      const nextAt = last.mtime + s.everyHours * 3_600_000
      if (Date.now() < nextAt) return { taken: false, reason: 'too-soon', nextAt }
    }
  }
  return { taken: true, backup: writeLocal(await fetchExport(config)) }
}

/** پشتیبانِ فوری، بدونِ توجه به زمان‌بندی — دکمه‌ی «همین حالا یک نسخه بگیر». */
export async function snapshotNow(config: BackupConfig): Promise<LocalBackup> {
  return writeLocal(await fetchExport(config))
}

/** وضعیتِ پوشه: تعداد، حجمِ کل، آخرین نسخه، و زمانِ نسخه‌ی خودکارِ بعدی. */
export function backupStatus(): {
  dir: string
  count: number
  totalSize: number
  last: LocalBackup | null
  nextAt: number | null
  settings: BackupSettings
} {
  const s = getSettings()
  const list = listLocalBackups()
  const last = list[0] ?? null
  const nextAt = s.enabled && s.everyHours > 0 && last ? last.mtime + s.everyHours * 3_600_000 : null
  return {
    dir: backupDir(),
    count: list.length,
    totalSize: list.reduce((sum, b) => sum + b.size, 0),
    last,
    nextAt,
    settings: s,
  }
}

/** انتخابِ پوشه‌ی مقصد (درایوِ بیرونی، پوشه‌ی ابری، …). */
export async function chooseDir(
  win: BrowserWindow | null,
): Promise<{ dir?: string; canceled?: boolean }> {
  const opts = {
    title: 'پوشه‌ی نسخه‌های پشتیبان',
    properties: ['openDirectory' as const, 'createDirectory' as const],
  }
  const r = win ? await dialog.showOpenDialog(win, opts) : await dialog.showOpenDialog(opts)
  if (r.canceled || !r.filePaths[0]) return { canceled: true }
  setSettings({ dir: r.filePaths[0] })
  ensureDir()
  return { dir: r.filePaths[0] }
}

/** بازگشت به پوشه‌ی پیش‌فرضِ برنامه. */
export function resetDir(): BackupSettings {
  return setSettings({ dir: '' })
}

/** حذفِ یک نسخه‌ی محلی. فقط نسخه‌های داخلِ پوشه‌ی پشتیبان قابلِ حذف‌اند. */
export function deleteLocal(file: string): { deleted: boolean } {
  const target = listLocalBackups().find((b) => b.file === file)
  if (!target) return { deleted: false }
  fs.unlinkSync(target.path)
  return { deleted: true }
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

/** بازیابی از یکی از نسخه‌های فهرست‌شده — بدونِ عبور از دیالوگِ فایل. */
export async function restoreFromLocal(
  config: BackupConfig,
  file: string,
): Promise<{ restored: boolean; message: string }> {
  const target = listLocalBackups().find((b) => b.file === file)
  if (!target) return { restored: false, message: 'این نسخه دیگر روی دیسک نیست.' }
  return sendRestore(config, fs.readFileSync(target.path, 'utf8'))
}

/** ارسالِ بدنه‌ی پشتیبان به سرور برای جایگزینی — مشترکِ هر دو مسیرِ بازیابی. */
async function sendRestore(
  config: BackupConfig,
  body: string,
): Promise<{ restored: boolean; message: string }> {
  const token = config.getToken()
  if (!token) return { restored: false, message: 'برای بازیابی باید وارد شده باشید.' }
  try {
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
  } catch {
    return { restored: false, message: 'فایلِ انتخابی خوانده نشد.' }
  }
  return sendRestore(config, body)
}
