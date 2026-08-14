/**
 * بررسی کانال به‌روزرسانی: قالب، دسترس‌پذیری، و مقایسه‌ی نسخه.
 *
 * اجرا:  npm run verify-update-channel
 *
 * **آنچه این می‌سنجد:** همان دو کتابخانه‌ای که electron-updater برای خواندن
 * latest.yml و مقایسه‌ی نسخه استفاده می‌کند (js-yaml و semver)، روی همان URL
 * واقعی. یعنی قالب فایل، رسیدن به فایل نصب، تطابق sha512، و اینکه کلاینت قدیمی
 * نسخه‌ی تازه را «جدیدتر» می‌بیند.
 *
 * **آنچه نمی‌سنجد — و باید صادق بود:** خودِ اجرای electron-updater داخل اپ
 * بسته‌بندی‌شده. در این محیط require('electron') به شیم npm می‌رسد نه ماژول
 * داخلی، پس کتابخانه بالا نمی‌آید. تنها تأیید کامل، نصب نسخه‌ی قدیمی روی یک
 * ویندوز واقعی و دیدن ظاهر شدن نوار به‌روزرسانی است.
 */
const https = require('node:https')
const crypto = require('node:crypto')
const yaml = require('js-yaml')
const semver = require('semver')

const BASE = process.env.UPDATE_BASE || 'https://acc.cubita.ir/updates'
const PRETEND = process.env.PRETEND_VERSION || '1.0.0'

const get = (url, asBuffer = false) =>
  new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode} برای ${url}`)) }
      const chunks = []
      res.on('data', (c) => chunks.push(c))
      res.on('end', () => resolve(asBuffer ? Buffer.concat(chunks) : Buffer.concat(chunks).toString('utf8')))
    }).on('error', reject)
  })

;(async () => {
  const fail = (m) => { console.log(`FAIL ${m}`); process.exitCode = 1 }
  try {
    const raw = await get(`${BASE}/latest.yml`)
    const info = yaml.load(raw)
    console.log(`نسخه‌ی روی کانال: ${info.version}`)

    if (!info.version || !info.path || !info.sha512) return fail('latest.yml فیلدهای لازم را ندارد')
    if (!semver.gt(info.version, PRETEND)) return fail(`کلاینت ${PRETEND} نسخه‌ی ${info.version} را جدیدتر نمی‌بیند`)

    const fileUrl = `${BASE}/${info.path}`
    console.log(`دانلود ${info.path} برای بررسی sha512 …`)
    const bin = await get(fileUrl, true)
    const actual = crypto.createHash('sha512').update(bin).digest('base64')

    if (bin.length !== info.files[0].size) return fail(`اندازه ${bin.length} است ولی ${info.files[0].size} اعلام شده`)
    if (actual !== info.sha512) return fail('sha512 مطابقت ندارد — به‌روزرسانی بعد از دانلود رد می‌شود')

    console.log(`\nOK کلاینت ${PRETEND} نسخه‌ی ${info.version} را می‌بیند؛ فایل سالم و قابل دانلود است`)
  } catch (err) {
    fail(err.message)
  }
})()
