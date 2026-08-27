import { chromium } from 'playwright'
const S = process.env.SHOT_DIR
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })
const errors = []
page.on('pageerror', e => errors.push(String(e).slice(0, 160)))
await page.goto('http://localhost:5173', { waitUntil: 'networkidle' })
await page.fill('input[type=email]', 'acc.cubita@gmail.com')
await page.fill('input[type=password]', '0919Nima!')
await page.click('button[type=submit]')
await page.waitForSelector('.topnav-inner', { timeout: 20000 })

async function go(label) {
  await page.click('.topnav-hamburger')
  await page.waitForTimeout(500)
  const ok = await page.evaluate((lb) => {
    const b = [...document.querySelectorAll('button, a')].find(e => e.textContent.trim() === lb)
    if (b) { b.click(); return true }
    return false
  }, label)
  await page.waitForTimeout(1600)
  const over = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  console.log(`${label}: ${ok ? 'باز شد' : 'پیدا نشد'} | سرریزِ افقی: ${over}`)
  return ok
}
for (const p of ['گروه جدید', 'محل‌های جغرافیایی', 'طرف حساب جدید', 'عملیات اول دوره']) await go(p)
await page.screenshot({ path: `${S}/co-mobile.png` })
console.log('خطاها:', errors.length ? errors : 'ندارد')
await browser.close()
