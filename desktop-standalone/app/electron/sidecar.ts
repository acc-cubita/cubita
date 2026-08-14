import { spawn, type ChildProcess } from 'node:child_process'
import { app } from 'electron'
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'

// موتورِ حسابداری در این محصولِ محلی، همان بک‌اندِ FastAPIِ کوبیتاست که به‌صورتِ یک
// «سایدکار» روی 127.0.0.1 و SQLite اجرا می‌شود. Electron آن را پیش از ساختِ پنجره بالا
// می‌آورد و کلِ داده از همین‌جا خوانده/نوشته می‌شود (بدونِ ابر، تک‌کاربر).

export interface SidecarHandle {
  baseUrl: string
  port: number
}

let child: ChildProcess | null = null

/** یک پورتِ آزاد روی loopback می‌گیرد تا با اجرای موازی/نمونه‌ی دیگر تصادم نکند. */
function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.on('error', reject)
    srv.listen(0, '127.0.0.1', () => {
      const addr = srv.address()
      if (addr && typeof addr === 'object') {
        const { port } = addr
        srv.close(() => resolve(port))
      } else {
        srv.close(() => reject(new Error('پورتِ آزاد پیدا نشد')))
      }
    })
  })
}

/** مفسر/اسکریپت یا exeِ سایدکار و پوشه‌ی اجرا.
 *
 * - packaged: exeِ بسته‌بندی‌شده‌ی PyInstaller در `resources/engine` (در M5 ساخته می‌شود).
 * - dev: مفسرِ پایتون (`HESABDARI_PYTHON`، یا venvِ بک‌اندِ کنارِ مخزن، یا `python` سیستم)
 *   + `run_local.py` با cwd = پوشه‌ی engine (کنارِ app در همین مخزن).
 */
function resolveCommand(): { cmd: string; args: string[]; cwd: string } {
  if (app.isPackaged) {
    const exe = path.join(process.resourcesPath, 'engine', 'hesabdari-engine.exe')
    return { cmd: exe, args: [], cwd: path.dirname(exe) }
  }
  const engineDir = path.join(app.getAppPath(), '..', 'engine')
  const venvPython = path.join(app.getAppPath(), '..', '..', 'backend', 'venv', 'Scripts', 'python.exe')
  const python = process.env.HESABDARI_PYTHON ?? (fs.existsSync(venvPython) ? venvPython : 'python')
  return { cmd: python, args: ['run_local.py'], cwd: engineDir }
}

/** URLِ SQLite در پوشه‌ی دیتای کاربر. SQLAlchemy روی ویندوز اسلش می‌خواهد. */
function databaseUrl(): string {
  const dir = path.join(app.getPath('userData'), 'data')
  fs.mkdirSync(dir, { recursive: true })
  const file = path.join(dir, 'hesabdari.db')
  return `sqlite:///${file.replace(/\\/g, '/')}`
}

/** تا سبزشدنِ `/api/health` صبر می‌کند؛ اگر سایدکار زودتر بمیرد فوراً fail می‌کند. */
function waitForHealth(port: number, isDead: () => string | null, timeoutMs: number): Promise<void> {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const retry = () => {
      const dead = isDead()
      if (dead) return reject(new Error(`سایدکار پیش از آماده‌شدن متوقف شد (${dead})`))
      if (Date.now() - start > timeoutMs) return reject(new Error('سرورِ محلی در زمانِ مقرر بالا نیامد'))
      setTimeout(tick, 300)
    }
    const tick = () => {
      const req = http.get({ host: '127.0.0.1', port, path: '/api/health', timeout: 1500 }, (res) => {
        res.resume()
        if (res.statusCode === 200) resolve()
        else retry()
      })
      req.on('error', retry)
      req.on('timeout', () => {
        req.destroy()
        retry()
      })
    }
    tick()
  })
}

export async function startSidecar(log: (msg: string) => void): Promise<SidecarHandle> {
  const port = await findFreePort()
  const { cmd, args, cwd } = resolveCommand()
  const database_url = databaseUrl()
  log(`sidecar: spawning ${cmd} ${args.join(' ')} (cwd=${cwd}, port=${port})`)

  let exitInfo: string | null = null
  child = spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      PORT: String(port),
      DATABASE_URL: database_url,
      // renderer در بسته‌ی نصبی origin برابرِ `null` (file://) و در dev برابرِ localhost دارد.
      // چون سرور فقط روی 127.0.0.1 گوش می‌دهد و احراز با Bearer است (نه کوکی)، `*` امن است.
      ALLOWED_ORIGINS: '*',
      // بدونِ این، printهای فارسیِ seed روی کنسولِ cp1252ِ ویندوز کرش می‌کنند.
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      ENV: 'development',
    },
    windowsHide: true,
  })

  child.stdout?.on('data', (d) => log(`[engine] ${String(d).trimEnd()}`))
  child.stderr?.on('data', (d) => log(`[engine!] ${String(d).trimEnd()}`))
  child.on('exit', (code, signal) => {
    exitInfo = `code=${code} signal=${signal}`
    log(`sidecar exited ${exitInfo}`)
  })
  child.on('error', (err) => {
    exitInfo = err instanceof Error ? err.message : String(err)
    log(`sidecar spawn error: ${exitInfo}`)
  })

  await waitForHealth(port, () => exitInfo, 30_000)
  log(`sidecar: healthy on port ${port}`)
  return { baseUrl: `http://127.0.0.1:${port}`, port }
}

export function stopSidecar(): void {
  if (child && !child.killed) {
    child.kill()
    child = null
  }
}
