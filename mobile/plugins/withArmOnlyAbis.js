/**
 * کدِ نیتیوِ x86 را از APKِ انتشار بیرون می‌گذارد.
 *
 * ## مسئله‌ای که حل می‌کند
 *
 * APKِ منتشرشده‌ی v9 حجمش **۱۱۸.۵ مگابایت** بود. تفکیکش:
 *
 *     arm64-v8a      ۲۵.۵ MB   گوشی‌های امروزی
 *     armeabi-v7a    ۱۷.۵ MB   گوشی‌های قدیمی‌تر
 *     x86            ۲۷.۶ MB   ← فقط امولاتور
 *     x86_64         ۲۷.۰ MB   ← فقط امولاتور
 *
 * یعنی **۵۴.۶ مگابایت — تقریباً نیمی از حجمِ دانلود — کتابخانه‌ی نیتیوی است که
 * روی هیچ گوشیِ واقعی اجرا نمی‌شود.** هر کاربرِ کافه‌بازار آن را با اینترنتِ
 * موبایل دانلود می‌کند و هرگز یک بایتش را اجرا نمی‌کند.
 *
 * ## چرا فیلترِ ساده و نه `splits`
 *
 * `splits { abi }` به‌ازای هر معماری یک APK می‌سازد و کاربرِ arm64 را به ~۴۰ MB
 * می‌رساند — بهتر، ولی یعنی چند APK در کافه‌بازار با versionCodeهای متفاوت.
 * پیچیدگیِ انتشار و ریسکِ رسیدنِ APKِ اشتباه به دستگاه را می‌آورد، در برابرِ
 * ۲۴ مگابایت. یک APKِ ۶۴ مگابایتیِ همه‌گوشی‌ها ساده‌تر و بی‌ریسک‌تر است.
 *
 * ## چرا با `-PallAbis` برمی‌گردند
 *
 * امولاتورِ توسعه روی ویندوز x86_64 است. اگر این معماری‌ها همیشه حذف شوند،
 * **آزمونِ چشمی روی امولاتور از کار می‌افتد** — همان حلقه‌ای که تا امروز
 * بیشترِ باگ‌های این اپ را پیدا کرده. پس:
 *
 *     ./gradlew assembleRelease -PallAbis     ← برای امولاتور
 *     ./gradlew assembleRelease               ← برای انتشار
 *
 * ## چرا افزونه
 *
 * `expo prebuild` فایلِ `android/app/build.gradle` را از نو می‌سازد. ویرایشِ
 * دستی با آن می‌رود — همان تله‌ای که سرِ کلیدِ امضا خوردیم.
 */
const { withAppBuildGradle } = require('expo/config-plugins')

const MARKER = 'abiFilters'

const BLOCK = `
        // معماری‌های x86 فقط برای امولاتورند و روی هیچ گوشی‌ای اجرا نمی‌شوند؛
        // نگه‌داشتنشان یعنی ~۵۵ مگابایت دانلودِ بی‌مصرف برای هر کاربر.
        // برای آزمون روی امولاتور: ./gradlew assembleRelease -PallAbis
        ndk {
            abiFilters = project.hasProperty('allAbis')
                ? ['armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64']
                : ['armeabi-v7a', 'arm64-v8a']
        }
`

module.exports = (config) =>
  withAppBuildGradle(config, (cfg) => {
    if (cfg.modResults.language !== 'groovy') {
      throw new Error('withArmOnlyAbis: فقط build.gradleِ groovy پشتیبانی می‌شود')
    }
    // idempotent — `prebuild` ممکن است چند بار اجرا شود.
    if (cfg.modResults.contents.includes(MARKER)) return cfg

    const anchor = '    defaultConfig {\n'
    if (!cfg.modResults.contents.includes(anchor)) {
      // بی‌صدا رد نمی‌شویم: APKِ دو‌برابری چیزی است که تا وقتی کسی حجمش را
      // اندازه نگیرد دیده نمی‌شود.
      throw new Error('withArmOnlyAbis: بلوکِ defaultConfig در build.gradle پیدا نشد')
    }
    cfg.modResults.contents = cfg.modResults.contents.replace(anchor, anchor + BLOCK)
    return cfg
  })
