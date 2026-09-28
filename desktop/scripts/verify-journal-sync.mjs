/** مرورگرِ واقعی و رابطِ مشترک؛ تمام HTTP/IPC شبیه‌سازی است و دادهٔ واقعی نوشته نمی‌شود. */
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const origin = process.env.JOURNAL_TEST_ORIGIN || 'http://127.0.0.1:5520'
const accounts = [
  { id: 'bank', code: '1101', name: 'بانک آزمایشی', type: 'asset', is_group: 0, parent_id: null },
  { id: 'capital', code: '2101', name: 'سرمایه آزمایشی', type: 'equity', is_group: 0, parent_id: null },
]
const browser = await chromium.launch({ headless: true })
try {
  for (const desktop of [true, false]) {
    for (const [width, theme] of [[1440, 'light'], [1440, 'dark'], [1200, 'light'], [390, 'light']]) {
      const context = await browser.newContext({ viewport: { width, height: 950 } })
      const page = await context.newPage()
      const errors = []
      const calls = []
      let years = [{ title: '۱۴۰۵', start_date: '2026-03-21', end_date: '2027-03-20', status: 'open' }]
      let posts = 0
      page.on('pageerror', error => errors.push(error.message))
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
      await context.addInitScript(({ desktop, accounts, origin, pushThrows }) => {
        const NativeDate = Date
        window.Date = class extends NativeDate {
          constructor(...args) { super(...(args.length ? args : ['2026-09-28T12:00:00Z'])) }
          static now() { return new NativeDate('2026-09-28T12:00:00Z').getTime() }
        }
        window.__journalFixture = { pulls: [], pushes: 0, queued: [] }
        if (!desktop) return
        let cache = []
        const outbox = [{ local_id: 'existing', payload: '{"entry_date":"2026-09-28"}', synced: 0, server_id: null, server_number: null, created_at: '2026-09-28', sync_error: '{"detail":"تاریخ 2026-09-28 در هیچ سال مالی تعریف‌شده‌ای نیست"}' }]
        window.cubitaConfig = { edition: 'enterprise', serverUrl: origin }
        window.cubita = {
          pullAll: async permissions => {
            window.__journalFixture.pulls.push(permissions)
            cache = accounts
            return { pulled: ['accounts', 'bankAccounts'], skipped: ['warehouses', 'items'], failed: [] }
          },
          pushOutbox: async () => {
            window.__journalFixture.pushes++
            if (pushThrows) throw new Error('ارسال صف انجام نشد؛ دوباره هم‌گام‌سازی کنید.')
            return { pushed: 0, failed: 1 }
          },
          listCachedAccounts: async () => cache,
          listCachedWarehouses: async () => [], listCachedItems: async () => [], listCachedBankAccounts: async () => [],
          listOutbox: async () => outbox,
          listSalesInvoiceOutbox: async () => [], listPurchaseInvoiceOutbox: async () => [], listCheckOutbox: async () => [],
          queueJournalEntry: async payload => { window.__journalFixture.queued.push(payload); return 'fixture-local-id' },
          backupAuto: async () => ({}),
        }
      }, { desktop, accounts, origin, pushThrows: width === 1200 })
      await context.route('**/api/**', async route => {
        const request = route.request()
        const path = new URL(request.url()).pathname
        calls.push([request.method(), path])
        const send = body => route.fulfill({ json: body, headers: { 'access-control-allow-origin': '*' } })
        if (path === '/api/accounts') return send(accounts)
        if (path === '/api/items' || path === '/api/warehouses') return route.fulfill({ status: 403, json: { detail: 'دسترسی انبار ندارید' }, headers: { 'access-control-allow-origin': '*' } })
        if (path === '/api/accounts/tafsili-mode') return send({ mode: 'optional' })
        if (path === '/api/fiscal-years') return send(years)
        if (path === '/api/reports/income-statement') return send({ net_profit: '0', revenue: [], expenses: [] })
        if (path === '/api/reports/dashboard') return send({ monthly: [], top_items: [], top_customers: [] })
        if (path === '/api/alerts') return send({ items: [], total: 0 })
        if (path === '/api/journal-entries') {
          if (request.method() === 'POST') {
            const payload = request.postDataJSON()
            assert.equal(payload.entry_date, '2026-09-28')
            assert.equal(payload.status, 'temporary')
            assert.deepEqual(payload.lines.map(line => line.account_id), ['bank', 'capital'])
            assert.equal(payload.lines.reduce((sum, line) => sum + line.debit, 0), 100)
            assert.equal(payload.lines.reduce((sum, line) => sum + line.credit, 0), 100)
            posts++
            return send({ id: 'fixture-entry' })
          }
          return send({ items: [], next_cursor: null })
        }
        return send([])
      })
      // یک حالتِ وب با نقشهٔ کهنه، تا خودِ ۴۰۳ هم روی مسیرِ واقعیِ Dashboard سنجیده شود.
      await page.goto(`${origin}/tests/fixtures/journal-sync.html?theme=${theme}${!desktop && width === 1200 ? '&stale' : ''}`)
      if (width > 760) await page.locator('.topnav-menu .topnav-item').filter({ hasText: /^حسابداری$/ }).click()
      else {
        await page.locator('.topnav-hamburger').click()
        const group = page.locator('.mob-row--group').filter({ has: page.locator('.mob-row-label', { hasText: /^حسابداری$/ }) })
        if (await group.getAttribute('aria-expanded') !== 'true') await group.click()
        await page.locator('.mob-row--item').filter({ has: page.locator('.mob-row-label', { hasText: /^سند حسابداری$/ }) }).click()
      }
      await page.locator('.jg-table').waitFor()
      if (!desktop) {
        const inventoryCalls = calls.filter(([, path]) => path === '/api/items' || path === '/api/warehouses')
        assert.equal(inventoryCalls.length, width === 1200 ? 2 : 0)
      }
      assert.equal(await page.getByText('قبل از ثبت سند، یک‌بار').count(), 0)
      if (desktop) {
        assert.equal(await page.locator('.outbox-list').getByText(/۱۴۰۵\/۰۷\/۰۶/).count(), 1)
        assert.equal(await page.locator('.outbox-list').getByText(/detail/).count(), 0)
        const fixture = await page.evaluate(() => window.__journalFixture)
        assert.equal(fixture.pushes, 1)
        assert.deepEqual(fixture.pulls[0], { accounting: ['view', 'create'], checks_bank: ['view'] })
      }
      async function metrics(name) {
        const result = await page.evaluate(() => ({
          overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
          tables: document.querySelectorAll('table:not(.cards-on-mobile):not(.table-plain)').length,
          cells: document.querySelectorAll('table.cards-on-mobile td:not([data-label]):not(.card-title):not(.card-actions):not(.card-wide):not(.card-full):not(.card-hide)').length,
        }))
        const unexpected = errors.filter(error => !/Failed to load resource:.*403/.test(error))
        assert.deepEqual(result, { overflow: 0, tables: 0, cells: 0 }, `${desktop ? 'desktop-renderer' : 'web'} ${width} ${name}`)
        assert.deepEqual(unexpected, [], `${width} ${theme} console`)
        console.log(`${desktop ? 'desktop-renderer' : 'web'} ${width} ${theme} ${name}: overflow=0 consoleUnexpected=0 tables=0 cells=0`)
      }
      await metrics('limited-account-chart')
      await page.getByLabel('شرح سند', { exact: true }).fill('سند آزمایشی شبکه')
      await page.locator('[data-cell="0-0"] input[role=combobox]').fill('1101')
      await page.locator('[data-cell="0-0"] input[role=combobox]').press('Enter')
      await page.locator('[data-cell="0-2"] input').fill('100')
      await page.locator('[data-cell="1-0"] input[role=combobox]').fill('2101')
      await page.locator('[data-cell="1-0"] input[role=combobox]').press('Enter')
      await page.locator('[data-cell="1-3"] input').fill('100')
      if (desktop) {
        years = [{ ...years[0], end_date: '2026-03-22' }]
        await page.getByRole('button', { name: /ثبت سند/ }).click()
        await page.getByText(/سند هنوز وارد صف نشده است/).waitFor()
        assert.equal((await page.evaluate(() => window.__journalFixture.queued)).length, 0)
        assert.equal(await page.getByLabel('شرح سند', { exact: true }).inputValue(), 'سند آزمایشی شبکه')
        await metrics('invalid-date-keeps-draft')
        years = [{ ...years[0], end_date: '2027-03-20' }]
      }
      await page.getByRole('button', { name: /ثبت سند/ }).click()
      await page.getByText(desktop ? /سند در صف محلی ذخیره شد/ : /سندِ موقت ثبت شد/).waitFor()
      if (desktop) assert.equal((await page.evaluate(() => window.__journalFixture.queued)).length, 1)
      else assert.equal(posts, 1)
      await metrics('valid-entry')
      assert.equal(calls.some(([method]) => method !== 'GET' && method !== 'POST'), false)
      await context.close()
    }
  }
} finally { await browser.close() }
