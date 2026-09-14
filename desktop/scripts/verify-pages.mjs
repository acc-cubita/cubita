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
import { navTargets } from './lib/navTargets.mjs'

//: **نبودِ مرورگر باید مثلِ نبودِ اعتبارنامه پیام بدهد، نه stack trace.**
//:
//: `playwright` حالا در `package.json` اعلام شده، ولی `npm ci` فقط بسته‌ی npm را
//: می‌آورد — باینریِ مرورگر قدمِ جداگانه‌ای است. تا پیش از این، اجرای اسکریپت
//: روی ماشینی که آن قدم را نزده بود یک خطای خامِ داخلیِ playwright می‌داد و
//: خواننده حدس می‌زد اسکریپت خراب است.
async function launch() {
  try {
    return await chromium.launch()
  } catch (err) {
    if (/Executable doesn't exist|please run|browserType.launch/i.test(String(err?.message))) {
      console.error('مرورگرِ chromium نصب نیست. یک‌بار اجرا کنید:')
      console.error('  npx playwright install chromium')
      process.exit(2)
    }
    throw err
  }
}

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

/**
 * [گروهِ ناوبری، برچسبِ صفحه] — **از خودِ `navModel` خوانده می‌شود، نه دستی.**
 *
 * تا پیش از این فهرست دستی بود و موردی رشد کرده بود: «دریافت و پرداخت» ۱۸
 * صفحه داشت و «حسابداری» ۳ تا — با ۲۲ منو. صفحه‌ی «گزارش ترازها» در فهرست نبود،
 * و دقیقاً همان صفحه بود که با یک خطای رندر سفید می‌شد و به تولید رسید.
 *
 * فهرستِ دستی یعنی پوششی که به یادِ آدم‌ها بند است. حالا هر صفحه‌ای که به
 * ناوبری اضافه شود خودبه‌خود این‌جا می‌آید.
 */
const TARGETS = navTargets().map((t) => [t.heading, t.label])

const widths = flag('width') ? [Number(flag('width'))] : [1440, 390]
const only = flag('page')

let failed = 0

for (const width of widths) {
  const browser = await launch()
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
