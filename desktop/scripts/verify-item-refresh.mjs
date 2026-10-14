// فرم‌های واقعی، HTTP/IPC آزمایشی؛ هیچ پایگاه یا نصب فعال لمس نمی‌شود.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'
const origin = process.env.ITEM_TEST_ORIGIN || 'http://127.0.0.1:5530'
const output = path.resolve('../_deploy/item-refresh-qa')
fs.mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
try {
  for (const desktop of [true, false]) for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 950 } })
    const page = await context.newPage()
    const errors = []
    let rows = []
    const warehouse = { id: 'warehouse', code: '1', name: 'انبار آزمایشی' }
    page.on('pageerror', error => errors.push(error.message))
    await context.addInitScript(({ desktop, origin, warehouse }) => {
      if (!desktop) return
      window.__cache = []
      window.__pushes = 0
      window.__itemPulls = 0
      window.cubitaConfig = { edition: 'enterprise', serverUrl: origin }
      window.cubita = {
        pullAll: async () => ({ pulled: ['items', 'warehouses'], skipped: ['accounts', 'bankAccounts'], failed: [] }),
        pullItems: async () => {
          window.__itemPulls++
          const response = await fetch(origin + '/api/items')
          window.__cache = (await response.json()).items
        },
        pushOutbox: async () => { window.__pushes++; return { pushed: 0, failed: 0 } },
        listCachedAccounts: async () => [], listCachedWarehouses: async () => [warehouse],
        listCachedItems: async () => window.__cache, listCachedBankAccounts: async () => [],
        listOutbox: async () => [], listSalesInvoiceOutbox: async () => [], listPurchaseInvoiceOutbox: async () => [], listCheckOutbox: async () => [],
      }
    }, { desktop, origin, warehouse })
    await context.route('**/api/**', async route => {
      const request = route.request()
      const endpoint = new URL(request.url()).pathname
      const send = json => route.fulfill({ json, headers: { 'access-control-allow-origin': '*' } })
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' } })
      if (endpoint === '/api/items') {
        if (request.method() === 'POST') {
          const item = { ...request.postDataJSON(), id: `item-${rows.length}`, sales_price: '0' }
          rows.push(item)
          return send(item)
        }
        return send({ items: rows, next_cursor: null })
      }
      if (endpoint === '/api/warehouses') return send([warehouse])
      if (endpoint === '/api/alerts') return send({ items: [], total: 0 })
      if (endpoint === '/api/reports/dashboard') return send({ monthly: [], top_items: [], top_customers: [] })
      return send([])
    })
    await page.goto(`${origin}/tests/fixtures/item-refresh.html`)
    // ناوبری خود محصول به رسید انبار.
    if (width > 760) {
      await page.locator('.topnav-menu .topnav-item').filter({ hasText: /^تامین‌کنندگان و انبار$/ }).click()
    } else {
      await page.locator('.topnav-hamburger').click()
      await page.locator('.mob-row-label').filter({ hasText: /^تامین‌کنندگان و انبار$/ }).click()
      await page.getByText('رسید انبار', { exact: true }).first().click()
    }
    await page.getByText('رسید انبار مستقیم', { exact: true }).waitFor()
    const description = page.getByLabel('توضیحات', { exact: true })
    await description.fill('پیش‌نویس رسید محفوظ')
    for (const name of ['کالای تازه اول', 'کالای تازه دوم']) {
      await page.getByRole('button', { name: 'ساخت سریع آزمون' }).click()
      await page.getByRole('dialog').getByLabel('نام کالا', { exact: true }).fill(name)
      await page.getByRole('dialog').getByRole('button', { name: /ثبت/ }).click()
      await page.getByRole('dialog').waitFor({ state: 'hidden' })
      await page.locator('option').filter({ hasText: name }).waitFor({ state: 'attached' })
      assert.equal(await description.inputValue(), 'پیش‌نویس رسید محفوظ')
    }
    if (desktop) {
      assert.deepEqual(await page.evaluate(() => [window.__cache.length, window.__itemPulls, window.__pushes]), [2, 2, 1])
    }
    await page.locator('table tbody select').first().selectOption('item-1')
    assert.match(await page.locator('table tbody select').first().locator('option:checked').innerText(), /کالای تازه دوم/)
    assert.deepEqual(errors, [])
    await page.screenshot({ path: path.join(output, `${desktop ? 'desktop' : 'web'}-${width}.png`) })
    console.log(`${desktop ? 'desktop' : 'web'} ${width}: two new items visible without restart; draft preserved`)
    await context.close()
  }
} finally { await browser.close() }
