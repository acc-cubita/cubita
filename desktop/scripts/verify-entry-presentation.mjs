// Real shared components + list opener, only intercepted sample GETs. No live API/DB.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const origin = process.env.ENTRY_QA_ORIGIN ?? 'http://127.0.0.1:5532'
const output = path.resolve('../_deploy/entry-presentation-qa')
fs.mkdirSync(output, { recursive: true })
const entry = {
  id: 'sample', number: 2, atf_number: 102, sub_number: 'A-25', entry_date: '2026-09-29',
  description: 'انتقال از صندوق به بانک', source_type: 'manual', source: null, created_by_name: 'مریم احمدی',
  status: 'temporary', finalized_at: null, voided_at: null, reverses_entry_id: null,
  lines: [
    { id: '1', account_id: 'bank', account_code: '1102', account_name: 'بانک', debit: '10000000', credit: '0', description: 'واریز وجه به حساب بانکی' },
    { id: '2', account_id: 'cash', account_code: '1101', account_name: 'صندوق', debit: '0', credit: '10000000', description: 'خروج وجه از صندوق' },
  ],
}
const browser = await chromium.launch({ headless: true })
const results = []
try {
  for (const [width, theme] of [[1440, 'tipalti'], [1440, 'light'], [1440, 'dark'], [1200, 'tipalti'], [390, 'tipalti'], [390, 'light'], [390, 'dark']]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' })
    await context.addInitScript(() => { window.cubitaConfig = { edition: 'enterprise', serverUrl: location.origin, version: '1.9.7-QA' } })
    let mode = 'simple', detailRequests = 0, writes = 0
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url())
      if (request.method() !== 'GET') { writes++; return route.abort() }
      const sample = structuredClone(entry)
      let body
      if (url.pathname === '/api/fiscal-years') body = []
      else if (url.pathname === '/api/journal-entries/summary') body = { entry_count: 1, line_count: 2, total_debit: '10000000', total_credit: '10000000' }
      else if (url.pathname === '/api/journal-entries') body = { items: [sample], next_cursor: null }
      else if (url.pathname === '/api/journal-entries/sample') {
        detailRequests++
        if (mode === 'error') return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'سرور موقتاً در دسترس نیست؛ 2026-09-29' }) })
        if (mode === 'rich') {
          sample.description = 'شرح چندخطیِ سند برای بررسی خوانایی، عرض ستون‌ها و سازگاری با پوسته.\nاین برگه فقط خواندنی است و ارقام را گرد نمی‌کند.'
          sample.status = 'permanent'
          Object.assign(sample.lines[0], { analytic_id: 'analytic', analytic_code: '31', analytic_name: 'قرارداد تجهیز شعبه', cost_center_id: 'center', cost_center_code: '12', cost_center_name: 'شعبهٔ تهران', currency_code: 'USD', fx_amount: '12.3456', fx_rate: '81000.5', tracking_no: 'REF-1405-45', tracking_date: '2026-09-29' })
          sample.lines[1].description = 'شرح طولانیِ ردیف برای بررسی شکستن متن و جلوگیری از سرریز در صفحهٔ کوچک'
        } else if (mode === 'large') {
          sample.lines[0].debit = '999999999999999999'
          sample.lines[1].credit = '999999999999999998'
        } else if (mode === 'empty') sample.lines = []
        body = sample
      } else throw new Error(`Unexpected QA API: ${url.pathname}`)
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    })
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', event => { if (event.type() === 'error' && !event.text().includes('503')) errors.push(event.text()) })
    await page.goto(`${origin}/tests/fixtures/entry-presentation.html?theme=${theme}`)
    await page.getByText('ثبت‌کننده: مریم احمدی', { exact: true }).waitFor()
    if (theme === 'tipalti' && (width === 1440 || width === 390)) {
      await page.screenshot({ path: path.join(output, `${width}-${theme}-creator-list.png`) })
    }
    const open = async nextMode => {
      mode = nextMode
      await page.getByText('انتقال از صندوق به بانک', { exact: true }).click()
      await page.getByRole('dialog', { name: 'جزئیات سند حسابداری' }).waitFor()
    }
    const close = async () => { await page.getByRole('button', { name: 'بستن جزئیات سند' }).click() }
    const metrics = async variant => {
      const result = await page.evaluate(() => {
        const dialog = document.querySelector('.journal-entry-panel'), table = dialog.querySelector('.entry-lines')
        const rect = element => element.getBoundingClientRect()
        const heads = table?.querySelectorAll('thead th'), sums = table?.querySelectorAll('.entry-totals .num')
        const alignment = table && getComputedStyle(table.querySelector('thead')).display !== 'none'
          ? [...sums].flatMap((cell, index) => {
            const head = heads[heads.length - 2 + index]
            return [Math.round(rect(cell).left - rect(head).left), Math.round(rect(cell).right - rect(head).right)]
          }) : [0, 0, 0, 0]
        return {
          overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth, dialog.scrollWidth - dialog.clientWidth, dialog.querySelector('.drawer-body').scrollWidth - dialog.querySelector('.drawer-body').clientWidth),
          tables: dialog.querySelectorAll('table:not(.cards-on-mobile):not(.table-plain)').length,
          cells: dialog.querySelectorAll('table td:not([data-label])').length,
          alignment,
          focus: dialog.contains(document.activeElement),
        }
      })
      assert.equal(result.overflow, 0); assert.equal(result.tables, 0); assert.equal(result.cells, 0)
      assert.deepEqual(result.alignment, [0, 0, 0, 0]); assert.equal(result.focus, true)
      assert.deepEqual(errors, []); assert.equal(writes, 0)
      await page.screenshot({ path: path.join(output, `${width}-${theme}-${variant}.png`) })
      if (width === 390 && await page.locator('.entry-lines').count() > 0) {
        await page.locator('.drawer-body').evaluate(element => { element.scrollTop = element.scrollHeight })
        await page.locator('.entry-balance').waitFor({ state: 'visible' })
        await page.screenshot({ path: path.join(output, `${width}-${theme}-${variant}-footer.png`) })
        await page.locator('.drawer-body').evaluate(element => { element.scrollTop = 0 })
      }
      results.push({ width, theme, variant, ...result, console: errors.length, writes })
      console.log(`${width} ${theme} ${variant}: overflow=0 alignment=0 tables=0 cells=0 console=0 writes=0`)
    }
    await open('simple')
    await page.getByText('سند تراز است', { exact: true }).waitFor()
    const dialog = page.getByRole('dialog')
    assert.equal(await dialog.getByText('بانک', { exact: true }).count(), 1)
    assert.equal(await dialog.getByText('۱۴۰۵/۰۷/۰۷', { exact: true }).count(), 1)
    assert.equal(await dialog.getByText('ثبت‌کننده: مریم احمدی', { exact: true }).count(), 1)
    await page.keyboard.press('Tab'); await metrics('simple')
    await page.keyboard.press('Escape'); assert.equal(await page.getByRole('dialog').count(), 0)
    await open('rich'); await page.getByText('قرارداد تجهیز شعبه', { exact: false }).waitFor()
    await metrics('rich'); await close()
    await open('large'); await page.getByText('اختلاف بدهکار و بستانکار: ۱ ریال', { exact: true }).waitFor()
    await metrics('large'); await close()
    await open('empty'); await page.getByText('ردیفی برای این سند دریافت نشد.', { exact: false }).waitFor()
    await metrics('empty'); await close()
    await open('error'); await page.getByRole('alert').waitFor()
    assert.equal(await dialog.getByText('سرور موقتاً در دسترس نیست؛ ۱۴۰۵/۰۷/۰۷', { exact: true }).count(), 1)
    const before = detailRequests; mode = 'simple'
    await page.getByRole('button', { name: 'تلاش دوباره' }).click()
    await page.getByText('سند تراز است', { exact: true }).waitFor()
    assert.equal(detailRequests, before + 1); await metrics('retry')
    await context.close()
  }
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2))
} finally { await browser.close() }
