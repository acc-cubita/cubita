/**
 * ترجیحِ «مبالغ روی ویجت دیده شوند یا نه».
 *
 * ## چرا این تصمیم دستِ کاربر است و نه ما
 *
 * اپ قفلِ بیومتریک دارد، ولی آن قفل **خودکار** است: هر گوشی‌ای که اثرانگشت ثبت
 * کرده باشد، اپ را قفل می‌کند. اگر ویجت را به همان گره می‌زدیم، روی تقریباً هر
 * گوشیِ امروزی بی‌عدد می‌شد — یعنی ویجتی که دلیلِ وجودش دیدنِ عدد است، عدد نشان
 * نمی‌داد.
 *
 * از آن طرف ویجت روی صفحه‌ی خانه است و **قفل را دور می‌زند**: هر کسی گوشی را
 * بردارد گردشِ مالیِ کسب‌وکار را می‌بیند، بی‌آنکه اثرانگشتی لازم باشد.
 *
 * هیچ‌کدام از این دو را نمی‌شود به‌جای کاربر تصمیم گرفت، پس یک تاگلِ صریح در
 * «بیشتر» گذاشته شده. پیش‌فرض **روشن** است: کسی که خودش ویجت را به صفحه‌ی خانه
 * اضافه می‌کند دنبالِ عدد است، و ویجتی که با «••••» باز شود بیشتر شبیهِ خرابی
 * است تا حریمِ خصوصی.
 */
import { File, Paths } from 'expo-file-system'

const PREFS_FILE = 'cubita-widget-prefs.json'

export type WidgetPrefs = {
  showAmounts: boolean
}

export const DEFAULT_PREFS: WidgetPrefs = { showAmounts: true }

const file = (): File => new File(Paths.document, PREFS_FILE)

export async function readPrefs(): Promise<WidgetPrefs> {
  try {
    const f = file()
    if (!f.exists) return DEFAULT_PREFS
    const raw = JSON.parse(f.textSync()) as Partial<WidgetPrefs>
    // `typeof` و نه `!!`: فایلِ خراب یا نسخه‌ی قدیمی نباید تاگل را وارونه کند.
    return { showAmounts: typeof raw.showAmounts === 'boolean' ? raw.showAmounts : true }
  } catch {
    return DEFAULT_PREFS
  }
}

export async function writePrefs(prefs: WidgetPrefs): Promise<void> {
  try {
    const f = file()
    if (!f.exists) f.create({ intermediates: true })
    f.write(JSON.stringify(prefs))
  } catch {
    // ترجیحِ ذخیره‌نشده بدتر از کرش نیست؛ دفعه‌ی بعد پیش‌فرض می‌گیرد.
  }
}
