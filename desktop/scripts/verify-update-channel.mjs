/**
 * آزمون واقعی کانال به‌روزرسانی — با خودِ electron-updater، نه با curl.
 *
 * اجرا:  npx electron scripts/verify-update-channel.mjs
 *
 * **چرا این با بررسی فایل‌ها فرق دارد:** اینکه latest.yml با کد ۲۰۰ سرو شود ثابت
 * نمی‌کند electron-updater آن را می‌فهمد. قالب YAML، مقایسه‌ی نسخه، و ساختن URL
 * فایل همه می‌توانند درست‌به‌نظر بیایند و کار نکنند. اینجا همان کتابخانه‌ای اجرا
 * می‌شود که در اپ واقعی اجرا می‌شود، روی همان کانال واقعی.
 *
 * پنجره‌ای ساخته نمی‌شود، پس روی سرور یا در CI هم اجرا می‌شود.
 */
import { app } from 'electron'
import { autoUpdater } from 'electron-updater'

// نسخه‌ای که وانمود می‌کنیم روی دستگاه مشتری نصب است. باید *قدیمی‌تر* از آخرین
// انتشار باشد وگرنه آزمون بی‌معنی است.
const PRETEND_VERSION = process.env.PRETEND_VERSION ?? '1.0.0'

app.on('ready', async () => {
  autoUpdater.forceDevUpdateConfig = true
  autoUpdater.autoDownload = false // فقط تشخیص را می‌سنجیم، ۱۱۶ مگابایت لازم نیست
  autoUpdater.currentVersion = PRETEND_VERSION

  console.log(`نسخه‌ی فرضیِ نصب‌شده: ${PRETEND_VERSION}`)
  console.log(`کانال: ${JSON.stringify(autoUpdater.getFeedURL() ?? 'از package.json')}`)

  let exitCode = 1
  try {
    const result = await autoUpdater.checkForUpdates()
    if (!result) {
      console.log('نتیجه: هیچ اطلاعاتی برنگشت')
    } else {
      const found = result.updateInfo.version
      console.log(`نسخه‌ی یافت‌شده روی کانال: ${found}`)
      console.log(`فایل: ${result.updateInfo.files?.[0]?.url}`)
      if (found !== PRETEND_VERSION) {
        console.log(`\n✓ کانال کار می‌کند: کلاینت ${PRETEND_VERSION} نسخه‌ی ${found} را می‌بیند`)
        exitCode = 0
      } else {
        console.log('\n✗ نسخه‌ی تازه‌ای تشخیص داده نشد')
      }
    }
  } catch (err) {
    console.log(`\n✗ خطا: ${err instanceof Error ? err.message : String(err)}`)
  }
  app.exit(exitCode)
})
