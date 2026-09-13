#!/usr/bin/env node
/**
 * راستی‌آزماییِ بصریِ صفحه‌ها — همان چهار عددی که ممیزِ ایستا نمی‌تواند بگیرد.
 *
 * ممیز (`audit-pages.mjs`) کد را می‌خواند؛ این یکی صفحه را **باز می‌کند** و می‌سنجد:
 *   • سرریزِ افقی (باید ۰ باشد، در هر عرض)
 *   • خطای کنسول (باید نباشد)
 *   • جدولِ بدونِ نمای کارتی (باید ۰ باشد)
 *   • سلولِ بدونِ برچسب در نمای کارتی (باید ۰ باشد)
 *
 * پیش‌نیاز: بک‌اندِ محلی روی ۸۰۰۰ و ویت روی ۵۱۷۳ بالا باشند.
 *
 *   node scripts/verify-pages.mjs                    # ۱۴۴۰ و ۳۹۰
 *   node scripts/verify-pages.mjs --width 390        # فقط یک عرض
 *   node scripts/verify-pages.mjs --page "انبار"     # فقط یک صفحه
 *
 * خروجِ ناصفر یعنی دستِ‌کم یک صفحه مشکل دارد.
 */
import { chromium } from 'playwright'

const args = process.argv.slice(2)
const flag = (name) => {
  const i = args.indexOf(`--${name}`)
  return i === -1 ? null : args[i + 1]
}

// اعتبارنامه از محیط می‌آید، نه از مخزن — حتی حسابِ توسعه‌ی محلی هم رمزش را
// در گیت نمی‌گذاریم.
const EMAIL = process.env.CUBITA_EMAIL
const PASSWORD = process.env.CUBITA_PASSWORD
const BASE = process.env.CUBITA_WEB ?? 'http://localhost:5173/'

if (!EMAIL || !PASSWORD) {
  console.error('CUBITA_EMAIL و CUBITA_PASSWORD را ست کنید (حسابِ توسعه‌ی محلی).')
  process.exit(2)
}

/** [گروهِ ناوبری، برچسبِ صفحه] — نماینده‌های هر ماژول. */
const TARGETS = [
  ['مشتریان و فروش', 'فروش'],
  //: صفحه‌های تازه‌ی فصل‌های «برگشت از فروش» و «اعلامیه قیمت». بدونِ این سه،
  //: اجرای این اسکریپت فقط صفحه‌ی ماژولِ فروش را می‌دید و گریدِ ماتریسِ قیمت —
  //: پهن‌ترین جدولِ تازه‌ی پروژه — هرگز در ۳۹۰ باز نمی‌شد.
  ['مشتریان و فروش', 'اعلامیه قیمت'],
  ['مشتریان و فروش', 'اعلامیه‌های قیمت'],
  ['مشتریان و فروش', 'علت برگشت کالا'],
  ['مشتریان و فروش', 'اشخاص'],
  ['مشتریان و فروش', 'باشگاه مشتریان'],
  ['تامین‌کنندگان و انبار', 'خرید'],
  //: بخشِ «رسید انبار» درست بعد از «خرید»: روی دسکتاپ کارتِ عملیاتِ همان صفحه
  //: بازش می‌کند. فرمِ رسیدِ مستقیم با پنجره‌ی حمل و دفترِ رسیدها این‌جاست.
  ['تامین‌کنندگان و انبار', 'رسید انبار'],
  ['تامین‌کنندگان و انبار', 'انبار'],
  //: تبِ «خروج انبار» — فرمِ چهارنوعی، جدولِ موجودیِ پیش/پس و دفترِ خروج‌ها.
  ['تامین‌کنندگان و انبار', 'خروج انبار'],
  //: تبِ «برگشت خروج انبار» — فرمِ مبنا با باقیمانده و دفترِ برگشت‌ها.
  ['تامین‌کنندگان و انبار', 'برگشت خروج انبار'],
  ['دریافت و پرداخت', 'فرآیند دریافت و پرداخت'],
  ['دریافت و پرداخت', 'رسید دریافت'],
  ['دریافت و پرداخت', 'اعلامیه پرداخت'],
  ['دریافت و پرداخت', 'عملیات بانکی چک دریافتنی'],
  ['دریافت و پرداخت', 'تسویه حساب طرف مقابل'],
  ['دریافت و پرداخت', 'استرداد چک'],
  ['دریافت و پرداخت', 'وصول چک پرداختنی'],
  ['دریافت و پرداخت', 'جستجوی چک'],
  ['دریافت و پرداخت', 'تسویه کارت خوان'],
  ['دریافت و پرداخت', 'صورت حساب بانکی'],
  ['دریافت و پرداخت', 'مغایرت بانکی'],
  ['دریافت و پرداخت', 'صندوق'],
  ['دریافت و پرداخت', 'حساب بانکی'],
  ['دریافت و پرداخت', 'دستگاه کارت خوان'],
  ['دریافت و پرداخت', 'دسته چک'],
  ['دریافت و پرداخت', 'تنخواه دار'],
  ['دریافت و پرداخت', 'صورت هزینه تنخواه'],
  ['دریافت و پرداخت', 'مرور عملیات بانکی'],
  ['دارایی ثابت', 'دارایی ثابت'],
  ['حسابداری', 'درختواره حساب‌ها'],
  ['حسابداری', 'سند حسابداری'],
  ['حسابداری', 'گزارش‌ها'],
  ['حقوق و دستمزد', 'حقوق و دستمزد'],
  ['سامانه مؤدیان', 'سامانه مؤدیان'],
  ['شرکت', 'مرکز هزینه'],
  ['شرکت', 'عملیات اول دوره'],
  ['تنظیمات', 'سال مالی'],
]

const widths = flag('width') ? [Number(flag('width'))] : [1440, 390]
const only = flag('page')

let failed = 0

for (const width of widths) {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })

  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.fill('input[type="email"]', EMAIL)
  await page.fill('input[type="password"]', PASSWORD)
  await page.click('button[type="submit"]')
  await page.waitForTimeout(3500)

  const mobile = await page.locator('.topnav-hamburger').first().isVisible().catch(() => false)
  console.log(`\n── عرض ${width}px ${mobile ? '(موبایل)' : '(دسکتاپ)'} ──`)

  for (const [group, label] of TARGETS) {
    if (only && label !== only) continue
    const before = errors.length
    try {
      if (mobile) {
        await page.locator('.topnav-hamburger').first().click()
        await page.waitForTimeout(450)
        await page.locator('.topnav-mobile-item', { hasText: label }).first().click()
      } else {
        let navigated = false
        let item = page.locator('.mod-op', { hasText: label }).first()
        if (!(await item.isVisible().catch(() => false))) {
          // گروهِ تک‌صفحه‌ای در نوارِ بالا مستقیم به همان صفحه می‌رود و `.mod-op` ندارد.
          for (const text of [group, label]) {
            const nav = page.getByText(text, { exact: true }).first()
            if (await nav.isVisible().catch(() => false)) {
              await nav.click().catch(() => {})
              navigated = true
              await page.waitForTimeout(1100)
              break
            }
          }
          item = page.locator('.mod-op', { hasText: label }).first()
        }
        if (await item.isVisible().catch(() => false)) {
          await item.click()
        } else if (!navigated) {
          // نه منوی عملیات پیدا شد و نه نامِ گروه در نوارِ بالا — یعنی هیچ
          // کلیکی نشد. تا امروز اسکریپت در این حالت بی‌صدا ادامه می‌داد و
          // **صفحه‌ی قبلی** را می‌سنجید، پس صفحه‌ای که هرگز باز نشده بود `OK`
          // می‌گرفت. (سنجشِ `.page-header` این‌جا کار نمی‌کند: پوسته‌ی «راهنما»
          // آن را پنهان می‌کند، پس در DOM هست ولی `isVisible` نیست.)
          throw new Error('منوی این صفحه در ناوبری پیدا نشد')
        }
      }
      await page.waitForTimeout(2200)
    } catch (err) {
      // باز نشدنِ صفحه **شکست** است، نه یادداشت: صفحه‌ای که کاربر نمی‌تواند
      // بازش کند دقیقاً همان چیزی است که این اسکریپت باید بگیرد. تا امروز
      // شمرده نمی‌شد و یک اجرای کاملاً ناموفق «همه‌ی صفحه‌ها سالم» می‌گفت.
      failed++
      console.log(`  [FAIL] ${label} — باز نشد (${String(err).slice(0, 60)})`)
      // کشوی موبایل باز مانده و کلیکِ بعدی می‌بنددش؛ بدونِ این، یک شکست همه‌ی
      // صفحه‌های بعدی را هم با خودش می‌برد.
      await page.keyboard.press('Escape').catch(() => {})
      await page.waitForTimeout(300)
      continue
    }

    const probe = await page.evaluate(() => {
      const de = document.documentElement
      const tables = [...document.querySelectorAll('table')]
      const plain = (t) => t.classList.contains('table-plain')
      return {
        overflow: de.scrollWidth - de.clientWidth,
        tables: tables.length,
        notCarded: tables.filter((t) => !t.classList.contains('cards-on-mobile') && !plain(t)).length,
        unlabelled: tables.reduce(
          (n, t) =>
            n +
            (plain(t)
              ? 0
              : [...t.querySelectorAll('tbody td')].filter(
                  (td) =>
                    !td.hasAttribute('data-label') &&
                    !/card-title|card-actions|card-hide|card-full|acc-row-actions/.test(td.className) &&
                    !td.hasAttribute('colspan'),
                ).length),
          0,
        ),
      }
    })

    const fresh = errors.slice(before)
    const bad = probe.overflow > 0 || probe.notCarded > 0 || probe.unlabelled > 0 || fresh.length > 0
    if (bad) failed++
    console.log(
      `  [${bad ? 'FAIL' : ' OK '}] ${label} — سرریز ${probe.overflow}، جدول ${probe.tables}` +
        `، بی‌کارت ${probe.notCarded}، بی‌برچسب ${probe.unlabelled}` +
        (fresh.length ? `، خطا: ${fresh[0].slice(0, 70)}` : ''),
    )
  }

  await browser.close()
}

console.log(failed === 0 ? '\nهمه‌ی صفحه‌ها سالم.\n' : `\n${failed} صفحه مشکل دارد.\n`)
process.exit(failed === 0 ? 0 : 1)
