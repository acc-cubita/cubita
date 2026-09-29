// Real React/browser rendering, but MOCK IPC/API only. Never a service/DB/network mutation.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const origin = process.env.RECOVERY_TEST_ORIGIN ?? 'http://127.0.0.1:5531'
const output = path.resolve('../_deploy/server-recovery-qa')
fs.mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
let count = 0
try {
  for (const [width, theme] of [[1440, 'light'], [1440, 'dark'], [1200, 'light'], [390, 'light']]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } })
    await context.addInitScript(() => {
      window.cubitaConfig = { edition: 'enterprise', serverUrl: 'http://localhost:8420', version: '1.9.7-QA' }
      const callbacks = new Set()
      window.__recoveryQA = { online: false, retries: 0, status: { state: 'starting', url: 'http://localhost:8420', message: 'در حال راه‌اندازی خودکار سرور؛ لطفاً کمی صبر کنید…' },
        set(state) { this.status = { ...this.status, state, message: state === 'maintenance'
          ? 'سرور در حال نصب یا تعمیر است؛ بازیابی خودکار تا پایان نصب متوقف می‌ماند.'
          : state === 'permission' ? 'مجوز شروع خودکار هنوز نصب نشده؛ نصاب کامل سازمانی را یک‌بار با نقش سرور و مسیر قبلی اجرا کنید.'
          : 'ارتباط با سرور برقرار است.' }; this.online = state === 'ready'; callbacks.forEach(cb => cb(this.status)) } }
      window.cubita = { serverConnection: async () => window.__recoveryQA.status,
        onServerConnection: cb => { callbacks.add(cb); return () => callbacks.delete(cb) },
        serverRetryConnection: async () => { window.__recoveryQA.retries++; return window.__recoveryQA.status } }
      const originalFetch = window.fetch.bind(window)
      window.fetch = async (input, options) => {
        const url = new URL(String(input), location.href)
        if (!url.pathname.startsWith('/api/')) return originalFetch(input, options)
        if (!window.__recoveryQA.online) throw new TypeError('Failed to fetch')
        const body = url.pathname === '/api/updates' ? { running: '1.9.7', latest_available: null, serving_clients: true, installer_path: null }
          : url.pathname === '/api/maintenance/backups' ? { last_at: '2026-09-28T12:00:00Z', age_hours: 1, stale: false, last_error: null, count: 2, total_bytes: 102400, folder: 'C:\\ProgramData\\Cubita\\backups', automatic: true }
          : null
        if (!body) throw new Error(`Unexpected QA API: ${url.pathname}`)
        return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
    })
    // Defense in depth: accidental requests can never reach the real API.
    await context.route('**/api/**', route => route.abort())
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', event => { if (event.type() === 'error') errors.push(event.text()) })
    await page.goto(`${origin}/tests/fixtures/server-recovery.html?theme=${theme}`)
    const draft = page.getByLabel('شرحِ در حال ویرایش')
    await draft.fill('اصلاحات ذخیره‌نشده محفوظ بماند')
    async function metrics(state) {
      const metrics = await page.evaluate(() => ({ overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth), tables: document.querySelectorAll('table:not(.cards-on-mobile):not(.table-plain)').length, cells: document.querySelectorAll('table.cards-on-mobile td:not([data-label]):not(.card-title):not(.card-actions):not(.card-wide):not(.card-full):not(.card-hide)').length }))
      assert.deepEqual(metrics, { overflow: 0, tables: 0, cells: 0 }); assert.deepEqual(errors, [])
      assert.equal(await draft.inputValue(), 'اصلاحات ذخیره‌نشده محفوظ بماند')
      assert.equal(await page.getByText('Failed to fetch', { exact: true }).count(), 0)
      await page.screenshot({ path: path.join(output, `${width}-${theme}-${state}.png`), fullPage: true })
      count++; console.log(`recovery ${width} ${theme} ${state}: overflow=0 console=0 tables=0 cells=0 draft preserved`)
    }
    await page.getByText('اطلاعات پس از برقراری اتصال خودکار تازه می‌شود.').first().waitFor()
    assert.equal(await page.getByRole('button', { name: 'بررسی دوباره', exact: true }).isEnabled(), false)
    await metrics('starting')
    await page.evaluate(() => window.__recoveryQA.set('maintenance')); await metrics('maintenance')
    await page.evaluate(() => window.__recoveryQA.set('permission'))
    await page.getByRole('button', { name: 'بررسی دوباره', exact: true }).click()
    assert.equal(await page.evaluate(() => window.__recoveryQA.retries), 1)
    await metrics('one-time-repair')
    await page.evaluate(() => window.__recoveryQA.set('ready'))
    await page.getByText('کلاینت‌ها از همین سرور به‌روز می‌شوند', { exact: true }).waitFor()
    assert.equal(await page.getByText('اطلاعات پس از برقراری اتصال خودکار تازه می‌شود.').count(), 0)
    assert.equal(await page.locator('.server-connection-banner').count(), 0)
    await metrics('reconnected')
    await context.close()
  }
  console.log(`PASS: ${count} browser scenarios, mocked IPC/API; no live service/reboot/UAC QA.`)
} finally { await browser.close() }
