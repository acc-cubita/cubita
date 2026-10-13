import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createRequire } from 'node:module'
const { chromium } = createRequire(process.env.CUBITA_PLAYWRIGHT_PACKAGE || new URL('../../desktop/package.json', import.meta.url))('playwright')
const url = process.env.CUBITA_DOWNLOAD_QA_URL || 'http://127.0.0.1:4199/download/'
const output = process.env.CUBITA_DOWNLOAD_QA_OUTPUT || '../_deploy/windows-selector-qa'
fs.mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
let checks = 0
try {
  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, userAgent: 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 Chrome/109.0.0.0 Safari/537.36' })
    await page.addInitScript(() => Object.defineProperty(navigator, 'userAgentData', { value: undefined, configurable: true }))
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    const section = page.locator('#windows-download')
    const windows = section.getByLabel('نسخهٔ ویندوز')
    const bits = section.getByLabel('معماری ویندوز')
    await page.waitForFunction(() => document.querySelector('#windows-download select')?.value === '8.1')
    assert.equal(await bits.inputValue(), '64'); checks++
    for (const os of ['7', '8', '8.1', '10-11']) {
      for (const arch of ['32', '64']) {
        await windows.selectOption(os); await bits.selectOption(arch)
        const link = section.locator('a[download]')
        assert.equal(await link.count(), 1)
        {
          const href = await link.getAttribute('href')
          const expected = arch === '32' || os === '7' || os === '8'
            ? `https://acc.cubita.ir/updates/enterprise/legacy/Cubita-Enterprise-Legacy-${arch === '32' ? 'x86' : 'x64'}-Setup-1.9.17.exe`
            : os === '8.1' ? 'https://acc.cubita.ir/updates/enterprise/windows81/Cubita-Enterprise-Windows81-Setup-1.9.16.exe' : 'https://acc.cubita.ir/updates/enterprise/Cubita-Enterprise-Setup.exe'
          assert.equal(href, expected)
          assert.match(await link.innerText(), arch === '32' ? /۳۲ بیتی/ : /۶۴ بیتی/)
          if (os === '10-11' && arch === '32') assert.match(await section.getByRole('status').innerText(), /ویندوز ۱۱ نسخهٔ ۳۲ بیتی ندارد/)
        }
        checks++
      }
    }
    await windows.selectOption('8.1'); await bits.selectOption('64')
    assert.match(await section.innerText(), /آزمون نصب و اجرای واقعی.*هنوز تکمیل نشده/)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    assert.deepEqual(errors, [])
    await section.screenshot({ path: `${output}/selector-${width}.png` })
    checks += 3
    await windows.selectOption('7'); await bits.selectOption('32')
    assert.match(await section.getByRole('status').innerText(), /آزمایشی.*Service Pack 1/)
    assert.match(await section.getByRole('status').innerText(), /آزمون نصب و اجرای واقعی.*هنوز تکمیل نشده/)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    await section.screenshot({ path: `${output}/legacy-x86-${width}.png` })
    checks += 3
    await page.close()
  }
  for (const marker of ['WOW64', '', 'ARM64']) {
    const page = await browser.newPage({ userAgent: `Mozilla/5.0 (Windows NT 6.1; ${marker}) AppleWebKit/537.36 Chrome/109.0.0.0 Safari/537.36` })
    await page.addInitScript(() => Object.defineProperty(navigator, 'userAgentData', { value: undefined, configurable: true }))
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction(() => document.querySelector('#windows-download select')?.value === '7')
    assert.equal(await page.getByLabel('معماری ویندوز').inputValue(), marker === 'WOW64' ? '64' : '')
    checks++; await page.close()
  }
  const page = await browser.newPage({ userAgent: 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/109.0.0.0 Safari/537.36' })
  await page.addInitScript(() => {
    window.releaseHints = null
    Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: { getHighEntropyValues: () => new Promise(resolve => { window.releaseHints = resolve }) } })
  })
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction(() => window.releaseHints !== null)
  await page.getByLabel('نسخهٔ ویندوز').selectOption('8')
  await page.getByLabel('معماری ویندوز').selectOption('32')
  await page.evaluate(() => window.releaseHints({ platform: 'Windows', architecture: 'x86', bitness: '64', wow64: true }))
  await page.waitForTimeout(100)
  assert.equal(await page.getByLabel('نسخهٔ ویندوز').inputValue(), '8')
  assert.equal(await page.getByLabel('معماری ویندوز').inputValue(), '32')
  checks++; await page.close()
  console.log(`PASS: ${checks} Windows download checks; widths 390/1440; no actual installer download`)
} finally { await browser.close() }
