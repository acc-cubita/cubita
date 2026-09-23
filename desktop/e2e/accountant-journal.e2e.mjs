/**
 * E2E — ثبتِ سندِ حرفه‌ای، از ورود تا ذخیره روی سرور (UI-01 §۴۹).
 *
 * چارچوب همان `playwright`ی است که در `devDependencies` هست و `verify-pages.mjs`
 * هم با آن کار می‌کند — چارچوبِ دومی (`@playwright/test`، …) اضافه نشد. اسکریپتِ
 * سادهِ Node با `node:assert`: یک سناریو، گام‌به‌گام، و عکس از لحظه‌ی شکست.
 *
 * **از بازشدنِ صفحه‌ی سند به بعد، ماوس ممنوع است.** هیچ `click`ی بعد از گامِ
 * «سند حسابداری» نیست؛ همه‌چیز `keyboard.press`/`keyboard.type` است.
 *
 * پیش‌نیاز: بک‌اند روی `E2E_API` و وب روی `E2E_WEB`، و کسب‌وکارِ آزمایشی از
 * `provision.py` — روی پایگاه‌داده‌ی دورریختنی. در CI همه را جابِ `e2e` می‌سازد.
 *
 *     E2E_EMAIL=… E2E_PASSWORD=… node e2e/accountant-journal.e2e.mjs
 */
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const WEB = process.env.E2E_WEB ?? 'http://localhost:5173/'
const API = process.env.E2E_API ?? 'http://localhost:8000'
const EMAIL = process.env.E2E_EMAIL
const PASSWORD = process.env.E2E_PASSWORD
const OUT = process.env.E2E_OUT ?? 'e2e-artifacts'
const AMOUNT = 20_000_000

assert.ok(EMAIL && PASSWORD, 'E2E_EMAIL و E2E_PASSWORD لازم‌اند')

// ── دو حسابِ ساده از خودِ سرور: بی تفصیلیِ اجباری، بی پیگیری، بی ارز ──
async function api(path, init = {}) {
  const r = await fetch(API + path, init)
  const body = await r.json().catch(() => null)
  assert.ok(r.ok, `${init.method ?? 'GET'} ${path} → ${r.status} ${JSON.stringify(body)?.slice(0, 200)}`)
  return body
}
const { access_token: token } = await api('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
})
const auth = { headers: { Authorization: `Bearer ${token}` } }
const plain = (await api('/api/accounts', auth)).filter(
  (a) => !a.is_group && a.is_active && !a.accepts_tafsili && !a.has_tracking && !a.is_fx,
)
assert.ok(plain.length >= 2, 'چارتِ آزمایشی دو حسابِ ساده ندارد')
const [A, B] = plain
console.log(`حساب‌ها: ${A.code} ${A.name} / ${B.code} ${B.name}`)

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
let step = 'آغاز'

const focusedCell = () =>
  page.evaluate(() => document.activeElement?.closest('[data-cell]')?.getAttribute('data-cell') ?? null)

/** حساب را فقط با کیبورد انتخاب می‌کند: تایپِ کد روی دکمه، ↓ تا گزینه‌ی درست، Enter. */
async function pickAccount(account) {
  await page.keyboard.press(account.code[0]) // حرفِ اول پاپ‌آور را باز می‌کند
  await page.locator('.item-picker-search input').waitFor()
  await page.keyboard.type(account.code.slice(1))
  const want = `${account.code} — ${account.name}`
  for (let i = 0; i < 30; i++) {
    const active = (await page.locator('.item-picker-opt.active').first().textContent())?.trim()
    if (active?.startsWith(want)) break
    await page.keyboard.press('ArrowDown')
  }
  assert.equal((await page.locator('.item-picker-opt.active').first().textContent())?.trim().startsWith(want), true, `گزینه‌ی ${want} پیدا نشد`)
  await page.keyboard.press('Enter')
  await page.locator('.item-picker-pop').waitFor({ state: 'detached' })
}

try {
  step = 'ورود'
  await page.goto(WEB, { waitUntil: 'networkidle' })
  await page.fill('input[type="email"]', EMAIL)
  await page.fill('input[type="password"]', PASSWORD)
  await page.click('button[type="submit"]')
  await page.waitForSelector('.topnav-menu .topnav-item', { timeout: 30_000 })

  step = 'حالت حسابدار از منوی کاربر'
  await page.click('.topnav-user')
  const radio = page.locator('.topnav-user-panel [role="radio"]', { hasText: 'حالت حسابدار' })
  await radio.click()
  assert.equal(await radio.getAttribute('aria-checked'), 'true')
  await page.keyboard.press('Escape')

  step = 'سند حسابداری — کلیک روی «حسابداری» به خودِ سند می‌رود'
  await page.locator('.topnav-menu .topnav-item', { hasText: /^حسابداری$/ }).click()
  await page.waitForSelector('[data-cell="0-0"]')
  // ── از این‌جا فقط کیبورد ────────────────────────────────────────────────
  await page.waitForFunction(() => document.activeElement?.closest('[data-cell]')?.getAttribute('data-cell') === '0-0', null, {
    timeout: 5_000,
  })

  step = 'ردیفِ ۱: حساب، شرح، بدهکار'
  await pickAccount(A)
  assert.equal(await focusedCell(), '0-0', 'بعد از انتخاب، فوکوس روی خودِ خانه‌ی حساب برنمی‌گردد')
  await page.keyboard.press('Enter') // → شرح
  await page.keyboard.type('E2E آزمون')
  await page.keyboard.press('Enter') // → بدهکار
  await page.keyboard.type(String(AMOUNT))
  await page.keyboard.press('Enter') // → بستانکار
  await page.keyboard.press('Enter') // ردیفِ تازه
  await page.waitForFunction(() => document.activeElement?.closest('[data-cell]')?.getAttribute('data-cell') === '1-0')

  step = 'ردیفِ ۲: حساب، و Enter روی بدهکارِ خالی = باقی‌مانده'
  await pickAccount(B)
  await page.keyboard.press('Enter') // → شرح
  await page.keyboard.press('Enter') // → بدهکار (خالی)
  assert.equal(await focusedCell(), '1-2')
  await page.keyboard.press('Enter') // باقی‌مانده می‌نشیند و فوکوس جلو می‌رود
  await page.waitForFunction(() => document.activeElement?.closest('[data-cell]')?.getAttribute('data-cell') === '2-0')
  const credit = await page.locator('[data-cell="1-3"] input').inputValue()
  assert.equal(credit.replace(/[^\d۰-۹]/g, '').replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0)), String(AMOUNT))

  step = 'Ctrl+S'
  await page.keyboard.press('Control+KeyS')
  await page.getByText('ثبت شد', { exact: false }).first().waitFor({ timeout: 15_000 })

  step = 'سند روی سرور'
  const { items } = await api('/api/journal-entries?limit=20', auth)
  const entry = items.find(
    (e) => e.lines.some((l) => l.account_id === A.id) && e.lines.some((l) => l.account_id === B.id),
  )
  assert.ok(entry, 'سند در فهرستِ سرور نیست')
  const sum = (side) => entry.lines.reduce((s, l) => s + Number(l[side]), 0)
  assert.equal(sum('debit'), AMOUNT)
  assert.equal(sum('credit'), AMOUNT)
  assert.ok(Number.isInteger(entry.number) && entry.number > 0, `شماره‌ی سند از سرور: ${entry.number}`)
  assert.deepEqual(errors, [], `خطای صفحه: ${errors.join(' | ')}`)

  console.log(`✓ سند ${entry.number} ثبت شد — بدهکار = بستانکار = ${AMOUNT.toLocaleString('en')} — فقط با کیبورد`)
} catch (err) {
  mkdirSync(OUT, { recursive: true })
  await page.screenshot({ path: `${OUT}/failure.png`, fullPage: true }).catch(() => {})
  console.error(`✗ گامِ «${step}» شکست خورد:\n${err?.stack ?? err}`)
  process.exitCode = 1
} finally {
  await browser.close()
}
