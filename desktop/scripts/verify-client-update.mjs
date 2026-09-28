import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'
const origin = process.env.JOURNAL_TEST_ORIGIN || 'http://127.0.0.1:5520'
const output = path.resolve('../_deploy/enterprise-journal-qa'); fs.mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
try {
  for (const [width, theme] of [[1440, 'light'], [1440, 'dark'], [1200, 'light'], [390, 'light']]) {
    const context = await browser.newContext({ viewport: { width, height: 950 } })
    const page = await context.newPage(); const errors = []
    page.on('pageerror', error => errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    await context.addInitScript(() => {
      window.cubitaConfig = { edition: 'enterprise', serverUrl: 'http://192.168.50.1:8420', version: '1.9.3' }
      const listeners = new Set(); let initialResolve
      window.__updateQA = { checks: 0, installs: 0, complete: false,
        emit: status => { for (const listener of listeners) listener(status) },
        initial: () => initialResolve({ state: 'idle' }),
      }
      window.cubitaUpdate = {
        status: () => new Promise(resolve => { initialResolve = resolve }),
        onStatus: callback => { listeners.add(callback); return () => listeners.delete(callback) },
        check: async () => {
          window.__updateQA.checks++
          const result = window.__updateQA.complete ? { state: 'none' } : { state: 'downloading', percent: 25 }
          window.__updateQA.emit(result)
          // پاسخ IPC قدیمی نباید رویداد تازه پیشرفت را بازنویسی کند.
          return window.__updateQA.complete ? result : { state: 'checking' }
        }, installNow: async () => { window.__updateQA.installs++ },
      }
    })
    await context.route('**/api/**', route => route.fulfill({ json: { mode: 'active', writable: true, seats: 5, seats_used: 2, org: 'شرکت آزمایشی', expires_at: null }, headers: { 'access-control-allow-origin': '*' } }))
    await page.goto(`${origin}/tests/fixtures/client-update.html?theme=${theme}`)
    const card = page.locator('section').filter({ has: page.getByRole('heading', { name: 'به‌روزرسانی این رایانه از سرور', exact: true }) })
    await card.waitFor(); assert.equal(await card.getByText('۱.۹.۳', { exact: true }).count(), 1)
    await card.getByRole('button', { name: 'بررسی آپدیت از سرور', exact: true }).click()
    await card.getByRole('progressbar').waitFor()
    assert.equal(await card.getByRole('progressbar').getAttribute('value'), '25')
    await page.evaluate(() => window.__updateQA.initial())
    assert.equal(await card.getByRole('progressbar').count(), 1)
    async function metrics(state) {
      const result = await page.evaluate(() => ({ overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth), tables: document.querySelectorAll('table:not(.cards-on-mobile):not(.table-plain)').length, cells: document.querySelectorAll('table.cards-on-mobile td:not([data-label]):not(.card-title):not(.card-actions):not(.card-wide):not(.card-full):not(.card-hide)').length }))
      assert.deepEqual(result, { overflow: 0, tables: 0, cells: 0 }); assert.deepEqual(errors, [])
      console.log(`LAN client ${width} ${theme} ${state}: overflow=0 console=0 tables=0 cells=0`)
      if (theme === 'light' && [390, 1440].includes(width)) await page.screenshot({ path: path.join(output, `client-${width}-${state}.png`), fullPage: true })
    }
    await metrics('downloading')
    await page.evaluate(() => window.__updateQA.emit({ state: 'verifying' })); await card.getByText(/در حال بررسی امضا/).waitFor()
    await page.evaluate(() => window.__updateQA.emit({ state: 'ready', version: '1.9.4' })); await card.getByText(/نسخه ۱.۹.۴ آماده نصب/).waitFor()
    page.once('dialog', dialog => dialog.dismiss()); await card.getByRole('button', { name: 'نصب و راه‌اندازی مجدد', exact: true }).click()
    assert.equal(await page.evaluate(() => window.__updateQA.installs), 0)
    page.once('dialog', dialog => dialog.accept()); await card.getByRole('button', { name: 'نصب و راه‌اندازی مجدد', exact: true }).click()
    assert.equal(await page.evaluate(() => window.__updateQA.installs), 1)
    await metrics('ready')
    await page.evaluate(() => { window.__updateQA.emit({ state: 'error', message: 'سرور در دسترس نیست؛ اتصال شبکه را بررسی کنید.' }); window.__updateQA.complete = true })
    await card.getByText(/سرور در دسترس نیست/).waitFor()
    await card.getByRole('button', { name: 'بررسی آپدیت از سرور', exact: true }).click(); await card.getByText(/آخرین نسخه ارائه‌شده توسط سرور/).waitFor()
    assert.equal(await page.evaluate(() => window.__updateQA.checks), 2); await metrics('none')
    await context.close()
  }
} finally { await browser.close() }
