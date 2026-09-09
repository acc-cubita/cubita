/**
 * بازگرداندنِ کلیدِ امضای انتشار پس از `expo prebuild`.
 *
 * ## چرا این فایل وجود دارد
 *
 * `npx expo prebuild` پوشه‌ی `android/` را **پاک و از نو می‌سازد**. کلیدِ امضای
 * انتشار (`android/app/cubita-release.keystore`)، `android/keystore.properties`
 * و بلوکِ `signingConfigs.release` در `android/app/build.gradle` هیچ‌کدام
 * ساخته‌شده‌ی prebuild نیستند — دستی‌اند. پس هر بار پاک می‌شوند.
 *
 * و **با گم شدنِ آن کلید، دیگر هرگز نمی‌توان آپدیتِ همین اپ را منتشر کرد** — نه
 * در کافه‌بازار، نه با فیدِ درجای خودمان. اندروید آپدیتی را که با کلیدِ دیگری
 * امضا شده باشد نمی‌پذیرد؛ تنها راه، اپِ تازه با نامِ بسته‌ی تازه است، یعنی
 * از دست دادنِ همه‌ی نصب‌های موجود.
 *
 * پس نسخه‌ی مرجعِ کلید در `mobile/release/signing/` نگه داشته می‌شود — بیرون از
 * `android/`، جایی که prebuild دستش نمی‌رسد (و در `.gitignore`).
 *
 * ## استفاده
 *
 *     npx expo prebuild --platform android
 *     node scripts/restore-signing.mjs
 *
 * اگر `release/signing/` نباشد، اسکریپت هشدار می‌دهد و بی‌صدا رد می‌شود — کلونِ
 * تازه بدونِ کلید هم باید بتواند نسخه‌ی debug بسازد.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const VAULT = path.join(ROOT, 'release', 'signing')
const ANDROID = path.join(ROOT, 'android')
const GRADLE = path.join(ANDROID, 'app', 'build.gradle')

const SIGNING_BLOCK = `        release {
            def propsFile = rootProject.file('keystore.properties')
            if (propsFile.exists()) {
                def props = new Properties()
                propsFile.withInputStream { props.load(it) }
                storeFile file(props['storeFile'])
                storePassword props['storePassword']
                keyAlias props['keyAlias']
                keyPassword props['keyPassword']
            }
        }
`

// prebuild این را می‌گذارد؛ باید با انتخابِ شرطی جایگزین شود.
const TEMPLATE_RELEASE_SIGNING = /\s*\/\/ Caution! In production[\s\S]*?signingConfig signingConfigs\.debug/
const CONDITIONAL_SIGNING =
  "\n            signingConfig rootProject.file('keystore.properties').exists() ? signingConfigs.release : signingConfigs.debug"

function fail(msg) {
  console.error(`✗ ${msg}`)
  process.exit(1)
}

if (!fs.existsSync(ANDROID)) fail('پوشه‌ی android/ نیست. اول `npx expo prebuild` را اجرا کنید.')

if (!fs.existsSync(VAULT)) {
  console.warn(
    '⚠ release/signing/ پیدا نشد — کلیدِ انتشار بازگردانده نشد.\n' +
      '  ساختِ debug کار می‌کند، ولی نسخه‌ی release با کلیدِ debug امضا می‌شود\n' +
      '  و به‌دردِ انتشار نمی‌خورد.',
  )
  process.exit(0)
}

// ── ۱. فایل‌های کلید ────────────────────────────────────────────────────────
const copies = [
  ['cubita-release.keystore', path.join(ANDROID, 'app', 'cubita-release.keystore')],
  ['keystore.properties', path.join(ANDROID, 'keystore.properties')],
]
for (const [name, dest] of copies) {
  const src = path.join(VAULT, name)
  if (!fs.existsSync(src)) fail(`${name} در release/signing/ نیست.`)
  fs.copyFileSync(src, dest)
  console.log(`✓ ${path.relative(ROOT, dest)}`)
}

// ── ۲. بلوکِ امضا در build.gradle ───────────────────────────────────────────
let gradle = fs.readFileSync(GRADLE, 'utf8')

if (gradle.includes("rootProject.file('keystore.properties')")) {
  console.log('✓ build.gradle از قبل بلوکِ امضا را دارد')
} else {
  // بلوکِ release را بلافاصله بعد از بلوکِ debug می‌نشانیم.
  const anchor = "            keyPassword 'android'\n        }\n"
  if (!gradle.includes(anchor)) fail('ساختارِ signingConfigs در build.gradle شناخته نشد؛ دستی اضافه کنید.')
  gradle = gradle.replace(anchor, anchor + SIGNING_BLOCK)

  if (!TEMPLATE_RELEASE_SIGNING.test(gradle)) {
    fail('بلوکِ signingConfig نسخه‌ی release پیدا نشد؛ دستی اصلاح کنید.')
  }
  gradle = gradle.replace(TEMPLATE_RELEASE_SIGNING, CONDITIONAL_SIGNING)

  fs.writeFileSync(GRADLE, gradle)
  console.log('✓ android/app/build.gradle — بلوکِ امضای release بازگردانده شد')
}

console.log('\nامضای انتشار آماده است.')
