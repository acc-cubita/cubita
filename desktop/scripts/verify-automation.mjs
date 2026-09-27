/** مرورگر واقعی در دو عرض؛ API شبیه‌سازی‌شده، آزمون قرارداد سرور در pytest. */
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'

const origin = process.env.AUTOMATION_TEST_ORIGIN || 'http://127.0.0.1:5184'
const browser = await chromium.launch({ headless: true })
const evidence = new URL('../.artifacts/automation/', import.meta.url)
await mkdir(evidence, { recursive: true })
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 950 } })
    await context.addInitScript(() => { window.print = () => {} })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()) })
    page.on('dialog', dialog => dialog.accept())
    let row = null
    let creations = 0
    let calls = 0
    let lastQuery = null
    const event = description => ({ id: `e${row.events.length}`, description, actor_name: 'همکار آزمایشی', action: 'test', created_at: '2026-09-27T10:00:00Z' })
    await context.route('**/api/automation/**', async route => {
      calls++
      const request = route.request()
      assert.equal(request.headers().authorization, 'Bearer fixture-only-token')
      const url = new URL(request.url())
      const path = url.pathname.replace('/api/automation', '')
      const method = request.method()
      const send = body => route.fulfill({ json: body })
      if (path === '/recipients') return send([{ id: 'self', name: 'همکار آزمایشی' }])
      if (path === '/letters' && method === 'GET') {
        lastQuery = url.searchParams
        return send({ items: row && !url.searchParams.get('q') ? [{ ...row, unread: true }] : [], next_cursor: null })
      }
      if (path === '/letters' && method === 'POST') {
        creations++
        row = { ...request.postDataJSON(), id: 'letter', number: null, status: 'draft', version: 1, can_edit: true, creator_name: 'همکار آزمایشی', created_by_id: 'self', created_at: '2026-09-27T10:00:00Z', registered_at: null, attachments: [], referrals: [], events: [] }
        row.events.push(event('پیش‌نویس ساخته شد.'))
        return send(row)
      }
      if (path === '/letters/letter/read') return send(row)
      if (path === '/letters/letter' && method === 'PUT') { row = { ...row, ...request.postDataJSON(), version: row.version + 1 }; return send(row) }
      if (path === '/letters/letter/attachments') {
        row.attachments.push({ id: 'file', filename: url.searchParams.get('filename'), size: 20, content_type: 'application/pdf', sha256: 'fixture' }); row.version++
        return send(row)
      }
      if (path === '/attachments/file' && method === 'GET') return route.fulfill({ contentType: 'application/pdf', headers: { 'content-disposition': 'attachment; filename=sample.pdf' }, body: '%PDF-test' })
      if (path === '/attachments/file' && method === 'DELETE') { row.attachments = []; row.version++; return send(row) }
      if (path === '/letters/letter/print') return route.fulfill({ contentType: 'text/html', body: '<!doctype html><html lang="fa" dir="rtl"><meta charset="UTF-8"><h1>نامهٔ آزمایشی اتوماسیون</h1></html>' })
      if (path === '/letters/letter/register') { assert.equal(request.postDataJSON().version, row.version); row.status = 'registered'; row.number = 1; row.version++; row.events.push(event('نامه ثبت قطعی شد.')); return send(row) }
      if (path === '/letters/letter/refer') {
        const data = request.postDataJSON()
        assert.deepEqual(data.recipients, ['self'])
        row.referrals.push({ id: 'ref', from_name: 'همکار آزمایشی', to_name: 'همکار آزمایشی', instruction: data.instruction, due_date: data.due_date, read_at: null, completed_at: null, response: '', can_complete: true })
        return send(row)
      }
      if (path === '/referrals/ref/complete') { row.referrals[0].response = request.postDataJSON().response; row.referrals[0].completed_at = '2026-09-27'; row.referrals[0].can_complete = false; return send(row) }
      if (path === '/letters/letter/archive') { row.status = 'archived'; row.version++; return send(row) }
      throw new Error(`Unexpected fixture request: ${method} ${path}`)
    })
    async function verify(name) {
      const metrics = await page.evaluate(() => ({
        overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
        tables: document.querySelectorAll('table:not(.cards-on-mobile):not(.table-plain)').length,
        cells: document.querySelectorAll('table.cards-on-mobile td:not([data-label]):not(.card-title):not(.card-actions):not(.card-wide):not(.card-full):not(.card-hide)').length,
      }))
      assert.deepEqual(metrics, { overflow: 0, tables: 0, cells: 0 }, `${width} ${name}`)
      assert.deepEqual(errors, [], `${width} console`)
      await page.screenshot({ path: new URL(`${width}-${name}.png`, evidence).pathname.replace(/^\/([A-Z]:)/, '$1'), fullPage: true })
      console.log(`${width} ${name}: overflow=0 console=0 tables=0 cells=0`)
    }
    await page.goto(`${origin}/tests/fixtures/automation.html`)
    await page.getByLabel('موضوع', { exact: true }).fill('نامهٔ آزمایشی اتوماسیون')
    await page.getByLabel('متن نامه', { exact: true }).fill('متن چندخطی\nبررسی ارجاع و پیوست')
    await verify('new')
    await page.getByRole('button', { name: 'ذخیره پیش‌نویس', exact: true }).click()
    await page.getByRole('button', { name: 'ویرایش پیش‌نویس' }).waitFor()
    assert.equal(creations, 1)
    await page.getByRole('button', { name: 'ویرایش پیش‌نویس' }).click()
    await page.getByLabel('فرستنده', { exact: true }).fill('دبیرخانهٔ نمونه')
    await page.getByRole('button', { name: 'ذخیره پیش‌نویس', exact: true }).click()
    await page.locator('input[type=file]').setInputFiles({ name: 'sample.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nfixture') })
    await page.getByText('sample.pdf', { exact: true }).waitFor()
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'دریافت', exact: true }).click()
    assert.equal((await download).suggestedFilename(), 'sample.pdf')
    await page.getByRole('button', { name: 'حذف پیوست', exact: true }).click()
    await page.getByText('این نامه پیوست ندارد.', { exact: true }).waitFor()
    await page.locator('input[type=file]').setInputFiles({ name: 'sample.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nfixture') })
    await page.getByText('sample.pdf', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'ثبت نهایی و شماره‌گذاری' }).click()
    await page.getByRole('heading', { name: 'ارجاع تازه' }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'ویرایش پیش‌نویس' }).count(), 0)
    assert.equal(await page.getByRole('button', { name: 'حذف پیوست' }).count(), 0)
    const popup = page.waitForEvent('popup')
    await page.getByRole('button', { name: 'چاپ نامه', exact: true }).click()
    const printed = await popup
    await printed.getByRole('heading', { name: 'نامهٔ آزمایشی اتوماسیون' }).waitFor()
    await printed.close()
    await page.getByLabel('همکار آزمایشی', { exact: true }).check()
    await page.getByLabel('دستور ارجاع', { exact: true }).fill('لطفاً بررسی و پاسخ ثبت شود.')
    await page.getByRole('button', { name: 'ارجاع به ۱ همکار' }).click()
    await page.getByLabel('پاسخ / گزارش اقدام').waitFor()
    assert.equal(await page.getByRole('button', { name: 'بایگانی نامه' }).isDisabled(), true)
    await verify('registered')
    await page.getByLabel('پاسخ / گزارش اقدام').fill('بررسی و تکمیل شد.')
    await page.getByRole('button', { name: 'ثبت پاسخ و تکمیل ارجاع' }).click()
    await page.getByText('بررسی و تکمیل شد.', { exact: false }).waitFor()
    await page.getByRole('button', { name: 'بایگانی نامه' }).click()
    await page.getByText('نامه بایگانی شد.', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'دبیرخانه و بایگانی', exact: true }).click()
    await page.getByRole('button', { name: 'باز کردن نامهٔ آزمایشی اتوماسیون' }).waitFor()
    await verify('registry')
    await page.getByLabel('جست‌وجوی موضوع، شماره یا طرف مکاتبه').fill('وجود ندارد')
    await page.getByRole('button', { name: 'اعمال فیلتر' }).click()
    await page.getByText('نامه‌ای با این شرایط پیدا نشد؛', { exact: false }).waitFor()
    assert.equal(lastQuery.get('q'), 'وجود ندارد')
    await page.route('**/api/automation/letters?*', route => route.fulfill({ status: 503, json: { detail: 'سرور آزمایشی در دسترس نیست؛ دوباره تلاش کنید.' } }), { times: 1 })
    await page.getByRole('button', { name: 'تازه‌سازی', exact: true }).click()
    await page.getByText('سرور آزمایشی در دسترس نیست؛ دوباره تلاش کنید.', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'تازه‌سازی', exact: true }).click()
    await page.getByText('نامه‌ای با این شرایط پیدا نشد؛', { exact: false }).waitFor()
    const beforeDenied = calls
    await page.goto(`${origin}/tests/fixtures/automation.html?denied`)
    await page.getByRole('alert').waitFor()
    assert.equal(calls, beforeDenied)
    await context.close()
  }
} finally { await browser.close() }
