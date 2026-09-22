// اسکریپت تست واقعی: authSession.ts را زیر Electron واقعی (نه mock) با
// better-sqlite3 واقعی و بک‌اندِ واقعی اجرا می‌کند — دقیقاً همان الگوی
// test-sync.ts، برای همان دلیل: تستِ mock فقط منطق را می‌سنجد، نه اینکه SQL
// واقعاً روی better-sqlite3 اجرا می‌شود یا app.getPath واقعاً کار می‌کند.
//
// اجرا: npx esbuild electron/test-auth-session.ts --bundle --platform=node --external:electron --external:better-sqlite3 --outfile=dist-electron/test-auth-session.js --format=cjs
//       سپس: ELECTRON_RUN_AS_NODE=1 ./node_modules/.bin/electron.cmd dist-electron/test-auth-session.js
import { app } from 'electron'
import { initLocalDb } from './db.js'
import { bestEffortLogout, clearSession, currentRefreshToken, persistSession, restoreSession } from './authSession.js'

const API_BASE_URL = process.env.TEST_SYNC_API_URL ?? 'http://127.0.0.1:8000'
const TEST_EMAIL = process.env.TEST_SYNC_EMAIL ?? ''
const TEST_PASSWORD = process.env.TEST_SYNC_PASSWORD ?? ''

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(`✗ ${msg}`)
  console.log(`✓ ${msg}`)
}

async function main() {
  if (!TEST_EMAIL || !TEST_PASSWORD) {
    throw new Error('TEST_SYNC_EMAIL و TEST_SYNC_PASSWORD باید در محیط تنظیم شوند')
  }

  console.log('--- initLocalDb (better-sqlite3 واقعی) ---')
  initLocalDb()

  console.log('--- ۱. بدونِ نشست: restoreSession باید null بدهد ---')
  clearSession()
  assert((await restoreSession({ apiBaseUrl: API_BASE_URL })) === null, 'بدونِ نشستِ ذخیره‌شده null')

  console.log('--- ۲. login واقعی، persistSession، سپس restoreSession آنلاین ---')
  const loginRes = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
  })
  if (!loginRes.ok) throw new Error(`login failed: ${loginRes.status}`)
  const loginBody = (await loginRes.json()) as { access_token: string; refresh_token: string }
  assert(loginBody.refresh_token, 'login واقعاً refresh_token داد')

  persistSession(loginBody.access_token, loginBody.refresh_token, { placeholder: true })
  assert(currentRefreshToken() === loginBody.refresh_token, 'persistSession/currentRefreshToken هم‌خوان')

  const online = await restoreSession({ apiBaseUrl: API_BASE_URL })
  assert(online !== null, 'restoreSession با نشستِ واقعی null نداد')
  assert(online!.offline === false, 'مسیرِ آنلاین offline:false داد')
  assert(online!.session.access_token !== loginBody.access_token, 'accessِ رفرش‌شده با اصلی فرق دارد (رفرشِ واقعی رخ داد)')
  assert(online!.session.refresh_token !== loginBody.refresh_token, 'رفرشِ چرخشیِ واقعی — توکنِ قبلی دیگر همان نیست')
  assert(
    typeof (online!.session.me as { email?: string }).email === 'string',
    '/api/auth/me واقعاً فراخوانی شد و me را برگرداند',
  )

  console.log('--- ۳. قطعیِ شبکه‌ی واقعی (apiBaseUrl نامعتبر) — نشست دست‌نخورده بماند ---')
  const beforeOffline = currentRefreshToken()
  const offline = await restoreSession({ apiBaseUrl: 'http://127.0.0.1:1' }) // پورتی که هیچ‌چیز رویش گوش نمی‌دهد
  assert(offline !== null, 'قطعیِ شبکه null نداد (نشست باید برگردد)')
  assert(offline!.offline === true, 'قطعیِ شبکه offline:true داد')
  assert(currentRefreshToken() === beforeOffline, 'رفرشِ محلی با قطعیِ شبکه دست‌نخورده ماند')

  console.log('--- ۴. رفرشِ باطل/دستکاری‌شده → ۴۰۱ِ واقعی از سرور → نشست پاک شود ---')
  persistSession(loginBody.access_token, 'this-is-not-a-real-refresh-token', { placeholder: true })
  const rejected = await restoreSession({ apiBaseUrl: API_BASE_URL })
  assert(rejected === null, '۴۰۱ِ واقعیِ سرور نشست را پاک کرد (null)')
  assert(currentRefreshToken() === null, 'نشستِ محلی واقعاً پاک شد')

  console.log('--- ۵. bestEffortLogout با نشستِ واقعی ---')
  const relog = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
  })
  const relogBody = (await relog.json()) as { access_token: string; refresh_token: string }
  persistSession(relogBody.access_token, relogBody.refresh_token, { placeholder: true })
  await bestEffortLogout({ apiBaseUrl: API_BASE_URL })
  const afterLogoutRefresh = currentRefreshToken() // bestEffortLogout فقط سمتِ سرور باطل می‌کند؛ محلی جداست
  assert(afterLogoutRefresh === relogBody.refresh_token, 'bestEffortLogout محلی را پاک نمی‌کند (کارِ clearSession است)')
  const afterServerRevoke = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: relogBody.refresh_token }),
  })
  assert(afterServerRevoke.status === 401, 'رفرش بعد از bestEffortLogout سمتِ سرور واقعاً باطل شده')
  clearSession()

  console.log('\n=== همه‌ی سنجش‌های واقعی سبز ===')
  app.exit(0)
}

main().catch((err) => {
  console.error(err)
  app.exit(1)
})
