import { app } from 'electron'
import { execFile } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import type { NetworkConfig, NetworkInventory, NetworkPlan, NetworkResult, NetworkState } from '../src/lib/enterpriseNetwork.js'
import { NETWORK_INSTALL_ACL_CHECK, trustedNetworkHelper } from './enterpriseNetworkPaths.js'

interface Helper { exe: string; prefix: string[] }
let preview: { key: string; expires: number } | null = null
let busy = false

function helper(): Helper {
  if (process.platform !== 'win32') throw new Error('تنظیم شبکه فقط در نسخهٔ ویندوز در دسترس است.')
  if (app.isPackaged) {
    const exe = path.join(process.resourcesPath, 'server', 'cubita-server.exe')
    if (!fs.existsSync(exe)) throw new Error('بستهٔ سرور همراه این نصب نیست؛ نصاب کامل سازمانی را نصب کنید.')
    return { exe, prefix: [] }
  }
  const backend = path.resolve(app.getAppPath(), '..', 'backend')
  return { exe: path.join(backend, 'venv', 'Scripts', 'python.exe'), prefix: [path.join(backend, 'packaging', 'server_entry.py')] }
}

function execute(exe: string, args: string[], timeout = 60000): Promise<string> {
  return new Promise((resolve, reject) => {
    const env = { ...process.env }
    delete env.PSModulePath
    execFile(exe, args, { windowsHide: true, timeout, maxBuffer: 512 * 1024, encoding: 'utf8', env }, (error, stdout, stderr) => {
      // The helper's structured validation failure exits 1, but still has a useful JSON result.
      if (error && !stdout.trim().startsWith('{')) reject(new Error(stderr.trim().slice(-1500) || error.message))
      else resolve(stdout.trim())
    })
  })
}

function payload(config: unknown): string {
  const json = JSON.stringify(config)
  if (!json || json.length > 2500) throw new Error('ورودی تنظیم شبکه نامعتبر است.')
  return Buffer.from(json, 'utf8').toString('base64')
}

async function call<T>(command: string, config?: NetworkConfig): Promise<NetworkResult<T>> {
  try {
    const h = helper()
    const output = await execute(h.exe, [...h.prefix, command, ...(config ? ['--payload', payload(config)] : [])])
    return JSON.parse(output.replace(/^\uFEFF/, '')) as NetworkResult<T>
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'تنظیم شبکه خوانده نشد؛ دوباره بررسی کنید.' }
  }
}

export function inspectNetwork(): Promise<NetworkResult<NetworkInventory>> {
  return call('network-inspect')
}

export async function previewNetwork(config: NetworkConfig): Promise<NetworkResult<NetworkPlan>> {
  preview = null
  const result = await call<NetworkPlan>('network-plan', config)
  if (result.ok) preview = { key: payload(config), expires: Date.now() + 120000 }
  return result
}

// Values are JSON/base64, never renderer-provided commands or executable paths.
function psLiteral(value: string): string { return `'${value.replaceAll("'", "''")}'` }

async function elevated(command: 'network-apply' | 'network-disable', config?: NetworkConfig): Promise<NetworkResult<NetworkState>> {
  if (busy) return { ok: false, error: 'یک تنظیم شبکه در حال اجراست؛ صبر کنید.' }
  busy = true
  try {
    if (!app.isPackaged) throw new Error('در حالت توسعه، اعمال شبکه غیرفعال است؛ فقط بررسی و پیش‌نمایش مجاز است.')
    const h = helper()
    const real = fs.realpathSync(h.exe)
    if (!trustedNetworkHelper(real, [process.env.ProgramFiles, process.env.ProgramW6432].filter((v): v is string => !!v))) {
      throw new Error('برای اعمال شبکه، نصاب کامل سازمانی را در Program Files نصب کنید؛ فایل توسعه یا مسیر قابل نوشتن elevated اجرا نمی‌شود.')
    }
    const psExe = path.join(process.env.SystemRoot ?? 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    const check = `$exe=${psLiteral(real)};` + NETWORK_INSTALL_ACL_CHECK
    await execute(psExe, ['-NoProfile', '-NonInteractive', '-EncodedCommand', Buffer.from(check, 'utf16le').toString('base64')], 90000)
    const code = `$ErrorActionPreference='Stop'; $p=Start-Process -FilePath ${psLiteral(h.exe)} -ArgumentList ${psLiteral(command + (config ? ` --payload ${payload(config)}` : ''))} -Verb RunAs -WindowStyle Hidden -Wait -PassThru; Write-Output $p.ExitCode`
    const started = Date.now()
    const output = await execute(psExe,
      ['-NoProfile', '-NonInteractive', '-EncodedCommand', Buffer.from(code, 'utf16le').toString('base64')], 180000)
    const statePath = path.join(process.env.ProgramData ?? 'C:\\ProgramData', 'CubitaNetwork', 'state.json')
    if (output !== '0') {
      let detail = ''
      try {
        const state = JSON.parse(fs.readFileSync(statePath, 'utf8')) as NetworkState
        if (!state.enabled && fs.statSync(statePath).mtimeMs >= started) detail = state.message
      } catch { /* UAC may have been cancelled before the helper started. */ }
      throw new Error(detail || 'اعمال شبکه کامل نشد؛ دسترسی مدیر و مسیر نصب Program Files را بررسی کنید. تنظیمات اینترنت بازنویسی نمی‌شود.')
    }
    return { ok: true, data: JSON.parse(fs.readFileSync(statePath, 'utf8')) as NetworkState }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'اعمال شبکه انجام نشد؛ دوباره بررسی کنید.' }
  } finally { busy = false }
}

export async function applyNetwork(config: NetworkConfig): Promise<NetworkResult<NetworkState>> {
  if (!preview || preview.expires < Date.now() || preview.key !== payload(config)) {
    return { ok: false, error: 'پیش‌نمایش معتبر نیست یا منقضی شده؛ دوباره «بررسی تغییرات» را بزنید.' }
  }
  preview = null
  return elevated('network-apply', config)
}

export function disableNetwork(): Promise<NetworkResult<NetworkState>> {
  preview = null
  return elevated('network-disable')
}
