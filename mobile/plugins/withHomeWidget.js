/**
 * ویجتِ صفحه‌ی خانه را به پروژه‌ی اندروید تزریق می‌کند.
 *
 * ## چرا افزونه و نه ویرایشِ مستقیمِ `android/`
 *
 * `expo prebuild` پوشه‌ی `android/` را **پاک و از نو می‌سازد**. هر فایلی که
 * دستی آنجا گذاشته شود با آن می‌رود. این تله را یک بار سرِ کلیدِ امضا خوردیم
 * (`scripts/restore-signing.mjs`) و یک بار سرِ مانیفستِ دوربین
 * (`withOptionalCamera.js`). پس منبعِ حقیقتِ ویجت `mobile/widget/` است — بیرونِ
 * `android/`، داخلِ مخزن — و این افزونه هر بار کپی‌اش می‌کند.
 *
 * سه کار می‌کند:
 * ۱. سورسِ کوتلین را در `android/app/src/main/java/ir/cubita/app/widget/` می‌گذارد.
 * ۲. منابع (layout/xml/values/drawable) را در `android/app/src/main/res/` می‌ریزد.
 * ۳. `<receiver>` را به مانیفست اضافه می‌کند.
 */
const fs = require('fs')
const path = require('path')
const { withAndroidManifest, withDangerousMod } = require('expo/config-plugins')

const PKG_PATH = 'ir/cubita/app/widget'
const RECEIVER = 'ir.cubita.app.widget.CubitaWidget'

/** کپیِ بازگشتیِ یک پوشه. */
function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true })
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const src = path.join(from, entry.name)
    const dst = path.join(to, entry.name)
    if (entry.isDirectory()) copyDir(src, dst)
    else fs.copyFileSync(src, dst)
  }
}

const withWidgetFiles = (config) =>
  withDangerousMod(config, [
    'android',
    (cfg) => {
      const root = cfg.modRequest.projectRoot
      const android = cfg.modRequest.platformProjectRoot
      const source = path.join(root, 'widget')

      if (!fs.existsSync(source)) {
        throw new Error(
          `withHomeWidget: پوشه‌ی «${source}» نیست. بدونِ آن ویجت بی‌صدا از بیلد جا می‌ماند.`,
        )
      }

      const javaDir = path.join(android, 'app/src/main/java', PKG_PATH)
      fs.mkdirSync(javaDir, { recursive: true })
      fs.copyFileSync(
        path.join(source, 'CubitaWidget.kt'),
        path.join(javaDir, 'CubitaWidget.kt'),
      )
      copyDir(path.join(source, 'res'), path.join(android, 'app/src/main/res'))
      return cfg
    },
  ])

const withWidgetReceiver = (config) =>
  withAndroidManifest(config, (cfg) => {
    const app = cfg.modResults.manifest.application?.[0]
    if (!app) throw new Error('withHomeWidget: <application> در مانیفست پیدا نشد')

    app.receiver = app.receiver || []
    // idempotent: `prebuild` ممکن است چند بار اجرا شود.
    if (app.receiver.some((r) => r?.$?.['android:name'] === RECEIVER)) return cfg

    app.receiver.push({
      $: {
        'android:name': RECEIVER,
        // `false` چون هیچ اپِ دیگری نباید بتواند به‌روزرسانی‌اش را تحریک کند؛
        // اکشنِ سیستمیِ APPWIDGET_UPDATE با این هم به‌درستی می‌رسد.
        'android:exported': 'false',
      },
      'intent-filter': [
        { action: [{ $: { 'android:name': 'android.appwidget.action.APPWIDGET_UPDATE' } }] },
      ],
      'meta-data': [
        {
          $: {
            'android:name': 'android.appwidget.provider',
            'android:resource': '@xml/cubita_widget_info',
          },
        },
      ],
    })
    return cfg
  })

module.exports = (config) => withWidgetReceiver(withWidgetFiles(config))
