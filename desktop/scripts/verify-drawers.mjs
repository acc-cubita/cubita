/**
 * راستی‌آزماییِ سطح‌هایی که `verify-pages.mjs` نمی‌بیند: **کشوها**.
 *
 * آن اسکریپت صفحه‌ها را باز می‌کند و چهار عدد می‌گیرد؛ ولی کشو فقط با کلیکِ روی
 * یک ردیف باز می‌شود، پس جدول‌هایش هرگز سنجیده نمی‌شدند — و قراردادِ
 * `cards-on-mobile` + `data-label` دقیقاً همان‌جا شکستنی است.
 *
 * همان چهار سنجه، همان دو عرض:
 *   سرریزِ افقی ۰ · جدولِ بی‌کلاسِ کارتی ۰ · سلولِ بی‌برچسب ۰ · خطای کنسول ۰
 *
 * استفاده:
 *   CUBITA_EMAIL=… CUBITA_PASSWORD=… node scripts/verify-drawers.mjs
 *   CUBITA_STORE_EMAIL=… برای کارتِ کاتالوگ که حسابِ فروشگاه می‌خواهد
 */
import { chromium } from 'playwright'

const BASE = process.env.CUBITA_WEB ?? 'http://localhost:5173/'
const EMAIL = process.env.CUBITA_EMAIL
const PASSWORD = process.env.CUBITA_PASSWORD
const STORE_EMAIL = process.env.CUBITA_STORE_EMAIL
const STORE_PASSWORD = process.env.CUBITA_STORE_PASSWORD ?? PASSWORD

if (!EMAIL || !PASSWORD) {
  console.error('CUBITA_EMAIL و CUBITA_PASSWORD را ست کنید.')
  process.exit(2)
}

const args = process.argv.slice(2)
const flag = (n) => {
  const i = args.indexOf(`--${n}`)
  return i === -1 ? null : args[i + 1]
}
const widths = flag('width') ? [Number(flag('width'))] : [1440, 390]

let failed = 0

/** همان کاوشگرِ `verify-pages.mjs` — عمداً کپیِ دقیق، تا دو معیار واگرا نشوند. */
const probe = (page) =>
  page.evaluate(() => {
    const de = document.documentElement
    const tables = [...document.querySelectorAll('table')]
    const plain = (t) => t.classList.contains('table-plain')
    const skip = new Set(['card-title', 'card-actions', 'card-wide', 'card-full', 'card-hide'])
    return {
      overflow: de.scrollWidth - de.clientWidth,
      tables: tables.length,
      notCarded: tables.filter((t) => !t.classList.contains('cards-on-mobile') && !plain(t)).length,
      unlabelled: tables.reduce((n, t) => {
        if (plain(t)) return n
        const cells = [...t.querySelectorAll('tbody td')]
        return n + cells.filter((c) => !c.hasAttribute('data-label') && ![...c.classList].some((k) => skip.has(k))).length
      }, 0),
    }
  })

async function login(page, email, password) {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.fill('input[type="email"]', email)
  await page.fill('input[type="password"]', password)
  await page.click('button[type="submit"]')
  await page.waitForTimeout(3500)
}

/**
 * رفتن به یک ماژولِ نوارِ بالا، بعد یک تبِ درونش.
 *
 * زیرِ ۱۰۲۴ نوار جایش را به کشوی همبرگری می‌دهد و ردیف‌های شاخه‌ی بسته
 * `visibility: hidden`اند — پس اول گروه باز می‌شود، وگرنه کلیک روی عنصرِ
 * نامرئی تایم‌اوت می‌شود.
 */
async function goto(page, { nav, tab, group, item, section }) {
  const mobile = await page.locator('.topnav-hamburger').first().isVisible().catch(() => false)

  if (!mobile) {
    //: بالای ۱۰۲۴ هر ماژول یک `.topnav-item` است و بخش‌هایش `.mod-op`.
    //: نامِ نوارِ بالا با نامِ گروهِ کشوی موبایل یکی نیست («پخشِ من» در نوار،
    //: زیرِ گروهِ «بازارِ عمده‌فروشی» در کشو)، پس هر دو صریح داده می‌شوند.
    await page.locator('.topnav-item', { hasText: nav }).first().click()
    await page.waitForTimeout(1600)
    if (tab) {
      await page.locator('.mod-op', { hasText: tab }).first().click()
      await page.waitForTimeout(2200)
    }
    return
  }

  //: کشوی موبایل سه لایه است — گروه ← آیتم ← بخش — و ردیفِ شاخه‌ی بسته
  //: `visibility: hidden` دارد، پس هر لایه باید پیش از کلیکِ بعدی باز شود.
  const label = (cls, text) =>
    page.locator(cls).filter({ has: page.locator('.mob-row-label', { hasText: text }) }).first()

  await page.locator('.topnav-hamburger').first().click()
  await page.waitForTimeout(500)

  const g = label('.mob-row--group', group)
  if ((await g.getAttribute('aria-expanded')) !== 'true') {
    await g.click()
    await page.waitForTimeout(500)
  }

  const it = label('.mob-row--item', item ?? section)
  //: `aria-expanded` تهی یعنی ردیف مستقیم به صفحه می‌رود؛ غیرتهی یعنی ماژولِ
  //: تب‌دار است و اول باز می‌شود، بعد بخشش انتخاب.
  if ((await it.getAttribute('aria-expanded')) === null) {
    await it.click()
  } else {
    if ((await it.getAttribute('aria-expanded')) !== 'true') {
      await it.click()
      await page.waitForTimeout(450)
    }
    //: بی نامِ بخش، **اولین بخشِ دیدنی** انتخاب می‌شود — همان کاری که کاربر
    //: می‌کند. (`hasText: ''` به هر ردیفی می‌خورد، از جمله نامرئی‌ها، و کلیک
    //: روی نامرئی تایم‌اوت می‌دهد.)
    const sec = section
      ? label('.mob-row--section', section)
      : page.locator('.mob-row--section:visible').first()
    await sec.click()
  }
  await page.waitForTimeout(2200)
}

async function measure(page, label, errors, before) {
  const p = await probe(page)
  const fresh = errors.slice(before)
  const bad = p.overflow > 0 || p.notCarded > 0 || p.unlabelled > 0 || fresh.length > 0
  if (bad) failed++
  const note = fresh.length ? `، خطا: ${fresh[0].slice(0, 70)}` : ''
  console.log(
    `  [${bad ? 'FAIL' : ' OK '}] ${label} — سرریز ${p.overflow}، جدول ${p.tables}، ` +
      `بی‌کارت ${p.notCarded}، بی‌برچسب ${p.unlabelled}${note}`,
  )
}

for (const width of widths) {
  const browser = await chromium.launch()

  // ── حسابِ پخش‌کننده: کشوی تخصیصِ کاتالوگ و برگه‌ی جمع‌آوری ──────────
  {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
    await login(page, EMAIL, PASSWORD)
    console.log(`\n── عرض ${width}px ──`)

    // کشوی «بارها» روی یک قلمِ کاتالوگ (§۵ §۶)
    try {
      await goto(page, { nav: 'پخشِ من',
                         group: 'بازارِ عمده‌فروشی', item: 'پخشِ من' })
      let before = errors.length
      await page.locator('button', { hasText: 'بارها' }).first().click()
      await page.waitForTimeout(2200)
      await measure(page, 'کشوی تخصیصِ بار به کاتالوگ', errors, before)
      // این کشوها Escape را نمی‌گیرند (برخلافِ ۹ کشوی دیگر)، پس پوشش باز
      // می‌ماند و کلیکِ بعدی را می‌بلعد — با دکمه‌ی بستن بسته می‌شود.
      await page.locator('.drawer-close').first().click().catch(() => {})
      await page.waitForTimeout(600)
    } catch (err) {
      failed++
      console.log(`  [FAIL] کشوی تخصیصِ بار — باز نشد (${String(err).slice(0, 70)})`)
    }

    // برگه‌ی جمع‌آوری روی یک خروجِ انبار (§۱۲).
    // **تبِ فهرست، نه عملیات**: `WarehouseIssuesTab` دفتر را فقط وقتی رندر
    // می‌کند که `view !== 'form'`، و تبِ «حواله انبار» فرمِ ثبت است.
    try {
      await goto(page, { nav: 'تامین‌کنندگان و انبار', tab: 'فهرست رسیدها و حواله‌های انبار',
                         group: 'تامین‌کنندگان و انبار', item: 'فهرست رسیدها و حواله‌های انبار' })
      const before = errors.length
      await page.locator('button', { hasText: 'جمع‌آوری' }).first().click()
      await page.waitForTimeout(2200)
      await measure(page, 'برگه‌ی جمع‌آوری', errors, before)
      // این کشوها Escape را نمی‌گیرند (برخلافِ ۹ کشوی دیگر)، پس پوشش باز
      // می‌ماند و کلیکِ بعدی را می‌بلعد — با دکمه‌ی بستن بسته می‌شود.
      await page.locator('.drawer-close').first().click().catch(() => {})
      await page.waitForTimeout(600)
    } catch (err) {
      failed++
      console.log(`  [FAIL] برگه‌ی جمع‌آوری — باز نشد (${String(err).slice(0, 70)})`)
    }
    await page.close()
  }

  // ── حسابِ فروشگاه: کارتِ کاتالوگ (§۳۰ — قابلِ سفارش و اشانتیون) ──────
  if (STORE_EMAIL) {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
    try {
      await login(page, STORE_EMAIL, STORE_PASSWORD)
      const before = errors.length
      await goto(page, { nav: 'بازارِ خرید',
                         group: 'بازارِ عمده‌فروشی', item: 'بازارِ خرید' })
      await measure(page, 'کارتِ کاتالوگ (حسابِ فروشگاه)', errors, before)
    } catch (err) {
      failed++
      console.log(`  [FAIL] کارتِ کاتالوگ — باز نشد (${String(err).slice(0, 70)})`)
    }
    await page.close()
  } else {
    console.log('  [skip] کارتِ کاتالوگ — CUBITA_STORE_EMAIL ست نشده')
  }

  await browser.close()
}

console.log(failed ? `\n${failed} سطح مشکل دارد.` : '\nهر سه سطح سالم.')
process.exit(failed ? 1 : 0)
