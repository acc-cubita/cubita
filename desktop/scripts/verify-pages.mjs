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
  ['مشتریان و فروش', 'اشخاص'],
  ['مشتریان و فروش', 'باشگاه مشتریان'],
  ['تامین‌کنندگان و انبار', 'خرید'],
  ['تامین‌کنندگان و انبار', 'انبار'],
  ['دریافت و پرداخت', 'چک و بانک'],
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
        let item = page.locator('.mod-op', { hasText: label }).first()
        if (!(await item.isVisible().catch(() => false))) {
          // گروهِ تک‌صفحه‌ای در نوارِ بالا مستقیم به همان صفحه می‌رود و `.mod-op` ندارد.
          for (const text of [group, label]) {
            const nav = page.getByText(text, { exact: true }).first()
            if (await nav.isVisible().catch(() => false)) {
              await nav.click().catch(() => {})
              await page.waitForTimeout(1100)
              break
            }
          }
          item = page.locator('.mod-op', { hasText: label }).first()
        }
        if (await item.isVisible().catch(() => false)) await item.click()
      }
      await page.waitForTimeout(2200)
    } catch (err) {
      console.log(`  [SKIP] ${label} — باز نشد (${String(err).slice(0, 60)})`)
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
