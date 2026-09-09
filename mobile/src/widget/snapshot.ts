/**
 * عکسِ داده‌ی ویجتِ صفحه‌ی خانه.
 *
 * ## چرا ویجت خودش به API وصل نمی‌شود
 *
 * راهِ بدیهی این بود که کدِ کوتلینِ ویجت خودش درخواست بزند. سه چیز را دوباره
 * می‌خواست: توکنِ JWT از `expo-secure-store` به نیتیو می‌رفت (سطحِ حمله‌ی تازه)،
 * منطقِ رفرشِ ۴۰۱ و آفلاین دوباره در کوتلین نوشته می‌شد، و از آن بدتر **دو
 * پیاده‌سازیِ مستقل از یک عدد** می‌داشتیم که با هم واگرا می‌شوند.
 *
 * به‌جایش اپ هر بار که داده می‌گیرد یک فایلِ کوچک می‌نویسد و ویجت فقط همان را
 * می‌خواند. `Paths.document` روی دستگاه دقیقاً `context.filesDir` است (روی
 * امولاتور راستی‌آزمایی شد: `/data/data/ir.cubita.app/files/`)، پس کوتلین بدونِ
 * هیچ پلِ نیتیوی می‌خواندش.
 *
 * **هزینه‌اش صادقانه گفته می‌شود:** ویجت به‌اندازه‌ی آخرین باری که اپ باز شده
 * تازه است. برای همین `saved_at` هم نوشته می‌شود و ویجت زمان را نشان می‌دهد —
 * عددِ کهنه‌ای که تازه به‌نظر برسد، برای نرم‌افزارِ حسابداری از نبودِ عدد بدتر
 * است (همان قاعده‌ی سقفِ ۲۴ ساعتِ کشِ فازِ ۳).
 */
import { File, Paths } from 'expo-file-system'

const WIDGET_FILE = 'cubita-widget.json'

/**
 * نسخه‌ی قالب — **باید با `SUPPORTED_VERSION` در `widget/CubitaWidget.kt` یکی
 * بماند.** کوتلین عددِ بزرگ‌تر را رد می‌کند و حالتِ خالی نشان می‌دهد، به‌جای
 * اینکه میدانی را که نمی‌شناسد صفر بخواند.
 */
const SNAPSHOT_VERSION = 1

export type WidgetSnapshot = {
  v: number
  /** میلی‌ثانیه‌ی یونیکس — زمانِ نوشتنِ عکس. */
  saved_at: number
  tenant: string
  /** فروشِ ۳۰ روزِ اخیر (ریال، با مالیات). */
  sales_30: string
  /** سود/زیانِ دوره. علامتش معنا دارد. */
  net_profit: string
  /** شمارِ هشدارهای نیازِ رسیدگی. */
  alerts: number
  /** آیا مبالغ روی صفحه‌ی خانه نشان داده شوند؟ تصمیمِ خودِ کاربر. */
  show_amounts: boolean
}

const file = (): File => new File(Paths.document, WIDGET_FILE)

/**
 * عکس را می‌سازد.
 *
 * جدا از نوشتن نگه داشته شده تا بدونِ فایل‌سیستم تست‌پذیر باشد — و چون همین‌جا
 * است که «کدام عدد روی ویجت می‌رود» تصمیم گرفته می‌شود.
 */
export function buildSnapshot(input: {
  tenant: string | null | undefined
  sales30: string | null | undefined
  netProfit: string | null | undefined
  alerts: number | null | undefined
  showAmounts: boolean
  now?: number
}): WidgetSnapshot {
  return {
    v: SNAPSHOT_VERSION,
    saved_at: input.now ?? Date.now(),
    tenant: input.tenant ?? '',
    // رشته می‌ماند نه عدد: مبالغ ریالی از `Number.MAX_SAFE_INTEGER` رد می‌شوند و
    // تبدیلِ بی‌دلیل، رقمِ آخر را بی‌صدا گرد می‌کند.
    sales_30: input.sales30 ?? '',
    net_profit: input.netProfit ?? '',
    alerts: Math.max(0, Math.trunc(input.alerts ?? 0)),
    show_amounts: input.showAmounts,
  }
}

/** عکس را روی دیسک می‌نویسد. خطا بلعیده می‌شود — ویجت هرگز نباید اپ را بشکند. */
export async function writeSnapshot(snap: WidgetSnapshot): Promise<void> {
  try {
    const f = file()
    if (!f.exists) f.create({ intermediates: true })
    f.write(JSON.stringify(snap))
  } catch {
    // نوشتنِ ویجت کارِ جانبی است؛ شکستش نباید صفحه‌ی خانه را از کار بیندازد.
  }
}

/**
 * عکس را پاک می‌کند.
 *
 * **هنگامِ خروج حتماً صدا زده می‌شود.** وگرنه روی گوشیِ مشترک، ویجتِ صفحه‌ی خانه
 * اعدادِ کسب‌وکارِ کاربرِ قبلی را نشان می‌دهد — همان قاعده‌ای که کشِ آفلاین دارد.
 */
export async function clearSnapshot(): Promise<void> {
  try {
    const f = file()
    if (f.exists) f.delete()
  } catch {
    // پاک‌نشدن نباید جلوی خروج را بگیرد.
  }
}
