/**
 * دوربین را «اختیاری» اعلام می‌کند.
 *
 * ## مسئله‌ای که حل می‌کند
 *
 * به‌محضِ اینکه مجوزِ `android.permission.CAMERA` در مانیفست باشد، اندروید
 * **خودش** نتیجه می‌گیرد که اپ به سخت‌افزارِ دوربین *نیاز* دارد:
 *
 *     uses-implied-feature: name='android.hardware.camera'
 *       reason='requested android.permission.CAMERA permission'
 *
 * پیامدش سه چیز است:
 *
 * ۱. فروشگاه (کافه‌بازار/Play) اپ را «نیازمندِ دوربین» فهرست می‌کند و روی
 *    دستگاه‌های بدونِ دوربین اصلاً نصب نمی‌شود.
 * ۲. بازبینِ فروشگاه می‌بیند نرم‌افزارِ *حسابداری* بدونِ دوربین اجرا نمی‌شود و
 *    به‌درستی می‌پرسد چرا.
 * ۳. و مهم‌تر: **این ادعا غلط است.** اسکنِ بارکد در کوبیتا شتاب‌دهنده است نه
 *    شرط؛ ورودِ دستیِ بارکد همیشه در دسترس است (`src/scan/BarcodeScanner.tsx`)
 *    و کلِ انبارگردانی بدونِ دوربین کار می‌کند.
 *
 * پس صریحاً `required="false"` اعلام می‌شود — هم درست‌تر، هم دلیلِ اعتراضِ
 * فروشگاه را از بین می‌برد.
 *
 * ## چرا افزونه و نه ویرایشِ دستیِ مانیفست
 *
 * `expo prebuild` پوشه‌ی `android/` را پاک و از نو می‌سازد. هر ویرایشِ دستی با
 * آن می‌رود — همان تله‌ای که سرِ کلیدِ امضا خوردیم
 * (`scripts/restore-signing.mjs`). افزونه بخشی از تولیدِ مانیفست است، پس هر بار
 * دوباره اعمال می‌شود.
 */
const { withAndroidManifest } = require('expo/config-plugins')

/** ویژگی‌هایی که باید «موجود ولی غیرضروری» اعلام شوند. */
const OPTIONAL_FEATURES = [
  'android.hardware.camera',
  // خودکارفوکوس هم به همین شکل ضمنی می‌شود و همان مشکل را دارد.
  'android.hardware.camera.autofocus',
]

const withOptionalCamera = (config) =>
  withAndroidManifest(config, (cfg) => {
    const manifest = cfg.modResults.manifest
    manifest['uses-feature'] = manifest['uses-feature'] || []

    for (const name of OPTIONAL_FEATURES) {
      const existing = manifest['uses-feature'].find((f) => f?.$?.['android:name'] === name)
      if (existing) {
        existing.$['android:required'] = 'false'
      } else {
        manifest['uses-feature'].push({
          $: { 'android:name': name, 'android:required': 'false' },
        })
      }
    }
    return cfg
  })

module.exports = withOptionalCamera
