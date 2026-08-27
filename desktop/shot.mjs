import { chromium } from 'playwright'
const S = process.env.SHOT_DIR
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1.4 })
const errors = []
page.on('pageerror', e => errors.push(String(e).slice(0, 200)))
await page.goto('http://localhost:5173', { waitUntil: 'networkidle' })
await page.fill('input[type=email]', 'acc.cubita@gmail.com')
await page.fill('input[type=password]', '0919Nima!')
await page.click('button[type=submit]')
await page.waitForSelector('.topnav-inner', { timeout: 20000 })

// رفتن به گروهِ «شرکت»
await page.evaluate(() => [...document.querySelectorAll('.topnav-item')].find(e => e.textContent.includes('شرکت'))?.click())
await page.waitForTimeout(1400)
await page.screenshot({ path: `${S}/co-panels.png`, fullPage: false })
console.log('عملیات:', await page.evaluate(() => [...document.querySelectorAll('.mod-panel')].map(p => p.innerText.replace(/\n+/g, ' | ').slice(0, 400))))

async function open(label, file) {
  const ok = await page.evaluate((lb) => {
    const b = [...document.querySelectorAll('button, a')].find(e => e.textContent.trim() === lb)
    if (b) { b.click(); return true }
    return false
  }, label)
  await page.waitForTimeout(1800)
  if (ok) await page.screenshot({ path: `${S}/${file}`, fullPage: true })
  console.log(`${label}: ${ok ? 'باز شد' : 'پیدا نشد ✗'}`)
}
await open('گروه جدید', 'co-group.png')
await page.evaluate(() => [...document.querySelectorAll('.topnav-item')].find(e => e.textContent.includes('شرکت'))?.click())
await page.waitForTimeout(1000)
await open('عملیات پایان سال', 'co-yearend.png')
await page.evaluate(() => [...document.querySelectorAll('.topnav-item')].find(e => e.textContent.includes('شرکت'))?.click())
await page.waitForTimeout(1000)
await open('گزارش‌ساز', 'co-builder.png')
console.log('خطاهای صفحه:', errors.length ? errors : 'ندارد')
await browser.close()
