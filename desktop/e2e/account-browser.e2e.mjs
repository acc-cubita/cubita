/**
 * E2E — مرور حساب‌ها (UI-02 §۳۷، §۳۹، §۴۰): درخت → بانک ملی → گردش → سند → برگشت.
 *
 * همان چارچوبِ `accountant-journal.e2e.mjs`: `playwright`ِ `devDependencies` و
 * `node:assert`، یک سناریو گام‌به‌گام، عکس از لحظه‌ی شکست.
 *
 * **داده از خودِ سرور ساخته می‌شود:** یک شاخه‌ی کوچک با نام‌های یکتا زیرِ ریشه‌ی
 * «دارایی‌ها» (دارایی جاری / موجودی نقد و بانک / بانک ملی، صندوق) و یک سندِ
 * «بانک ملی بدهکار ۲۰ میلیون / فروش بستانکار». رقم‌هایی که در رابط دیده می‌شوند با
 * رقم‌های `/api/accounting/balance-tree` مقایسه می‌شوند — رابط نباید چیزی جز
 * آن‌چه سرور گفته نشان دهد.
 *
 * **از بازشدنِ صفحه به بعد، ماوس ممنوع است** — فقط کیبورد.
 *
 *     E2E_EMAIL=… E2E_PASSWORD=… node e2e/account-browser.e2e.mjs
 *
 * `E2E_CHROMIUM` (اختیاری): مسیرِ کرومیومِ از پیش نصب‌شده، وقتی نسخه‌اش با
 * `playwright`ِ پروژه نمی‌خواند.
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
const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
const post = (path, body) => api(path, { method: 'POST', headers, body: JSON.stringify(body) })

// ── چارتِ آزمون: نامِ یکتا برای هر اجرا؛ کد را قاعده‌ی کدینگِ خودِ سرور می‌دهد ──
const tag = String(Date.now()).slice(-6)
async function acc(name, type, parent, is_group = false) {
  const { code } = await api(`/api/accounts/next-code${parent ? `?parent_id=${parent.id}` : ''}`, { headers })
  return post('/api/accounts', { code, name: `${name} ${tag}`, type, is_group, parent_id: parent?.id ?? null })
}
//: زیرِ ریشه‌های موجودِ چارت («دارایی‌ها»، «درآمدها») — کدِ ریشه یک‌رقمی است و چند
//: اجرای پیاپی نُه جای خالیِ آن را زود پر می‌کرد.
const chart = await api('/api/accounts', { headers })
const root = (type) => chart.find((a) => a.type === type && a.is_group && !a.parent_id)
const assets = root('asset')
const income = root('income')
assert.ok(assets && income, 'چارتِ آزمایشی ریشه‌ی دارایی/درآمد ندارد')
const current = await acc('دارایی جاری مرور', 'asset', assets, true)
const cash = await acc('موجودی نقد و بانک مرور', 'asset', current, true)
const melli = await acc('بانک ملی مرور', 'asset', cash)
await acc('صندوق مرور', 'asset', cash)
const salesGroup = await acc('درآمد مرور', 'income', income, true)
const sales = await acc('فروش مرور', 'income', salesGroup)

const today = new Date().toISOString().slice(0, 10)
const entry = await post('/api/journal-entries', {
  entry_date: today,
  description: `E2E مرور ${tag}`,
  lines: [
    { account_id: melli.id, debit: AMOUNT, credit: 0, description: 'واریز' },
    { account_id: sales.id, debit: 0, credit: AMOUNT, description: 'فروش' },
  ],
})
console.log(`چارت و سندِ ${entry.number} ساخته شد (${tag})`)

const faNum = (n) => Number(n).toLocaleString('fa-IR')

const browser = await chromium.launch(process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {})
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
let step = 'آغاز'

const selectedId = () =>
  page.evaluate(() => document.querySelector('[role="treeitem"][aria-selected="true"]')?.id.replace('ab-node-', '') ?? null)
const active = () =>
  page.evaluate(() => {
    const el = document.activeElement
    return el?.getAttribute('role') ?? el?.className ?? null
  })

/** صفحه‌ای را از فرمان‌یاب (Ctrl+K) باز می‌کند — Enter فقط وقتی که گزینه‌ی فعال همان است. */
async function goTo(title) {
  await page.keyboard.press('Control+KeyK')
  await page.locator('.cmdk input').waitFor()
  //: فرمان‌یاب عبارتِ قبلی را نگه می‌دارد؛ بی‌این، عبارتِ تازه به تهِ آن می‌چسبید.
  await page.keyboard.press('Control+KeyA')
  await page.keyboard.type(title)
  await page.locator('.cmdk-item.is-active .cmdk-item-title', { hasText: new RegExp(`^${title}$`) }).waitFor()
  await page.keyboard.press('Enter')
  await page.locator('.cmdk').waitFor({ state: 'detached' })
}

async function openBrowser() {
  await goTo('مرور حساب‌ها')
  await page.locator('[role="tree"]').waitFor({ timeout: 15_000 })
}

try {
  step = 'ورود'
  await page.goto(WEB, { waitUntil: 'networkidle' })
  await page.fill('input[type="email"]', EMAIL)
  await page.fill('input[type="password"]', PASSWORD)
  await page.click('button[type="submit"]')
  await page.waitForSelector('.topnav-menu .topnav-item', { timeout: 30_000 })
  // ── از این‌جا فقط کیبورد ────────────────────────────────────────────────

  step = 'مرور حساب‌ها از فرمان‌یاب (Ctrl+K)'
  await openBrowser()
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'tree')

  step = 'جست‌وجو: «/» و «بانک ملی مرور» → مسیر'
  await page.keyboard.press('/')
  await page.keyboard.type(`بانک ملی مرور ${tag}`)
  const hit = page.locator('.ab-hit').first()
  await hit.waitFor()
  assert.equal(
    (await page.locator('.ab-hit-path').first().textContent())?.trim(),
    `${assets.name} / دارایی جاری مرور ${tag} / موجودی نقد و بانک مرور ${tag}`,
  )

  step = 'Enter → نمایش در درخت'
  await page.keyboard.press('Enter')
  await page.waitForFunction((id) => document.querySelector(`#ab-node-${id}[aria-selected="true"]`), melli.id)
  assert.equal(await active(), 'tree')

  step = 'مانده‌ی والدها = عددِ سرور'
  const serverTree = await api(`/api/accounting/balance-tree`, { headers })
  const byId = new Map(serverTree.map((n) => [n.account_id, n]))
  for (const a of [melli, cash, current]) {
    assert.equal(Number(byId.get(a.id).closing), AMOUNT, `سرور: ${a.name}`)
    const text = await page.locator(`#ab-node-${a.id} .ab-bal`).textContent()
    assert.ok(text.includes(faNum(AMOUNT)) && text.includes('بد'), `رابط: ${a.name} → ${text}`)
  }
  //: ریشه داده‌ی اجراهای دیگر را هم دارد؛ رقمش هرچه هست باید همان رقمِ سرور باشد.
  const rootRaw = Number(byId.get(assets.id).closing)
  const rootText = await page.locator(`#ab-node-${assets.id} .ab-bal`).textContent()
  assert.ok(rootRaw === 0 ? rootText.includes('—') : rootText.includes(faNum(Math.abs(rootRaw))), `ریشه → ${rootText}`)

  step = 'Enter → گردش (صفحه‌بندیِ سرور)'
  const ledgerReq = page.waitForRequest((r) => r.url().includes(`/api/reports/general-ledger/${melli.id}`) && r.url().includes('limit='))
  await page.keyboard.press('Enter')
  await ledgerReq
  await page.waitForFunction(() => document.activeElement?.classList.contains('ab-ledger-scroll'))
  const firstLine = page.locator('.ab-ledger-table tbody tr.acc-row--clickable').first()
  assert.ok((await firstLine.textContent()).includes(faNum(entry.number)), 'ردیفِ سند در گردش نیست')

  step = 'Enter → سند کامل'
  await page.keyboard.press('Enter')
  const drawer = page.locator('.drawer-panel')
  await drawer.waitFor()
  await page.waitForFunction(() => document.querySelector('.drawer-panel .entry-card, .drawer-panel table'))
  assert.ok((await drawer.textContent()).includes(faNum(entry.number)))

  step = 'Esc → برگشت به همان گردش و همان حساب'
  await page.keyboard.press('Escape')
  await drawer.waitFor({ state: 'detached' })
  assert.equal(await selectedId(), melli.id)
  await page.waitForFunction(() => document.activeElement?.classList.contains('ab-ledger-scroll'))

  step = 'Esc → برگشت به درخت'
  await page.keyboard.press('Escape')
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'tree')
  await page.keyboard.press('Escape') // یک سطح بالا
  assert.equal(await selectedId(), cash.id)
  await page.keyboard.press('ArrowLeft') // باز است → اولین فرزند
  assert.equal(await selectedId(), melli.id)

  step = 'رفتن به صفحه‌ی دیگر و برگشت: زمینه می‌ماند'
  await goTo('گزارش ترازها')
  await page.locator('[role="tree"]').waitFor({ state: 'detached' })
  await openBrowser()
  await page.waitForFunction((id) => document.querySelector(`#ab-node-${id}[aria-selected="true"]`), melli.id)
  assert.ok(await page.locator(`#ab-node-${cash.id}[aria-expanded="true"]`).count(), 'گره‌ی باز بسته شده')

  step = 'سرریزِ افقی در ۱۳۶۶ و ۱۹۲۰'
  for (const width of [1366, 1920]) {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 })
    await page.waitForTimeout(200)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    assert.ok(overflow <= 0, `سرریزِ افقی در ${width}: ${overflow}px`)
    mkdirSync(OUT, { recursive: true })
    await page.screenshot({ path: `${OUT}/account-browser-${width}.png` })
  }

  assert.deepEqual(errors, [], `خطای صفحه: ${errors.join(' | ')}`)
  console.log(`✓ مرور حساب: درخت → بانک ملی → گردش → سند ${entry.number} → برگشت — فقط با کیبورد`)
} catch (err) {
  mkdirSync(OUT, { recursive: true })
  await page.screenshot({ path: `${OUT}/account-browser-failure.png`, fullPage: true }).catch(() => {})
  console.error(`✗ گامِ «${step}» شکست خورد:\n${err?.stack ?? err}`)
  process.exitCode = 1
} finally {
  await browser.close()
}
