package ir.cubita.app.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import ir.cubita.app.R
import org.json.JSONObject
import java.io.File
import java.util.Calendar
import java.util.Locale

/**
 * ویجتِ صفحه‌ی خانه — «نبضِ کسب‌وکار».
 *
 * داده را **از API نمی‌گیرد**؛ فایلی را می‌خواند که خودِ اپ نوشته
 * (`src/widget/snapshot.ts`). دلیلش آنجا توضیح داده شده: توکن به نیتیو نمی‌رود و
 * یک عدد دو پیاده‌سازیِ واگرا پیدا نمی‌کند.
 *
 * مسیر روی دستگاه راستی‌آزمایی شده: `Paths.document`ِ expo-file-system دقیقاً
 * `context.filesDir` است.
 */
class CubitaWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
    ) {
        ids.forEach { id -> manager.updateAppWidget(id, buildViews(context)) }
    }

    companion object {
        private const val SNAPSHOT = "cubita-widget.json"

        /** نسخه‌ی قالبی که این کد می‌فهمد. بالاتر از این یعنی اپ جلوتر از ویجت است. */
        private const val SUPPORTED_VERSION = 1

        fun buildViews(context: Context): RemoteViews {
            val views = RemoteViews(context.packageName, R.layout.cubita_widget)
            val snap = readSnapshot(context)

            if (snap == null) {
                // **حالتِ خالی صریح است، نه صفر.** ویجتی که پیش از اولین ورود «۰
                // ریال» نشان بدهد دارد دروغ می‌گوید؛ کاربر فکر می‌کند فروش صفر
                // بوده، نه اینکه هنوز داده‌ای نیست.
                views.setTextViewText(R.id.widget_tenant, context.getString(R.string.widget_empty_title))
                views.setTextViewText(R.id.widget_sales, "—")
                views.setTextViewText(R.id.widget_profit, "—")
                views.setTextViewText(R.id.widget_alerts, "")
                views.setTextViewText(R.id.widget_stamp, context.getString(R.string.widget_empty_hint))
            } else {
                val show = snap.optBoolean("show_amounts", true)
                views.setTextViewText(R.id.widget_tenant, snap.optString("tenant", ""))
                views.setTextViewText(R.id.widget_sales, money(snap.optString("sales_30", ""), show))
                views.setTextViewText(R.id.widget_profit, money(snap.optString("net_profit", ""), show))

                val alerts = snap.optInt("alerts", 0)
                views.setTextViewText(
                    R.id.widget_alerts,
                    if (alerts > 0) context.getString(R.string.widget_alerts, faDigits(alerts.toString())) else "",
                )
                views.setTextViewText(R.id.widget_stamp, stamp(context, snap.optLong("saved_at", 0L)))

                // سود منفی قرمز، مثبت سبز — همان قراردادِ صفحه‌ی خانه‌ی اپ.
                val negative = snap.optString("net_profit", "").trim().startsWith("-")
                views.setTextColor(
                    R.id.widget_profit,
                    context.getColor(if (negative) R.color.widget_danger else R.color.widget_success),
                )
            }

            // لمسِ ویجت → بازکردنِ اپ.
            val launch = context.packageManager.getLaunchIntentForPackage(context.packageName)
            if (launch != null) {
                val pending = PendingIntent.getActivity(
                    context,
                    0,
                    launch,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
                views.setOnClickPendingIntent(R.id.widget_root, pending)
            }
            return views
        }

        /** همه‌ی ویجت‌های نصب‌شده را از نو می‌کشد. */
        fun refreshAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, CubitaWidget::class.java))
            ids.forEach { id -> manager.updateAppWidget(id, buildViews(context)) }
        }

        private fun readSnapshot(context: Context): JSONObject? = try {
            val f = File(context.filesDir, SNAPSHOT)
            if (!f.exists()) null
            else JSONObject(f.readText()).takeIf { it.optInt("v", 0) <= SUPPORTED_VERSION }
        } catch (e: Exception) {
            // فایلِ نیمه‌نوشته یا JSONِ خراب → حالتِ خالی، نه کرشِ لانچر.
            null
        }

        /** «۱۹۰۵۷۵۰۰۰» → «۱۹۰٬۵۷۵٬۰۰۰». اعشار دور ریخته می‌شود (مبلغِ ریالی). */
        private fun money(raw: String, show: Boolean): String {
            if (!show) return "•••"
            val v = raw.trim()
            if (v.isEmpty()) return "—"
            val negative = v.startsWith("-")
            val digits = v.removePrefix("-").substringBefore('.').ifEmpty { "0" }
            if (digits.any { !it.isDigit() }) return "—"
            val grouped = digits.reversed().chunked(3).joinToString("٬").reversed()
            return (if (negative) "−" else "") + faDigits(grouped)
        }

        private fun faDigits(s: String): String =
            s.map { if (it in '0'..'9') '۰' + (it - '0') else it }.joinToString("")

        /**
         * زمانِ عکس.
         *
         * **همیشه نوشته می‌شود.** ویجت فقط وقتی تازه می‌شود که اپ باز شود یا
         * اندروید `onUpdate` بزند؛ عددِ دیروز که امروزی به‌نظر برسد بدتر از نبودنش
         * است.
         */
        private fun stamp(context: Context, millis: Long): String {
            if (millis <= 0L) return ""
            val then = Calendar.getInstance().apply { timeInMillis = millis }
            val now = Calendar.getInstance()
            val sameDay = then.get(Calendar.YEAR) == now.get(Calendar.YEAR) &&
                then.get(Calendar.DAY_OF_YEAR) == now.get(Calendar.DAY_OF_YEAR)
            val hhmm = String.format(
                Locale.US,
                "%02d:%02d",
                then.get(Calendar.HOUR_OF_DAY),
                then.get(Calendar.MINUTE),
            )
            val days = ((now.timeInMillis - millis) / 86_400_000L).toInt()
            return when {
                sameDay -> context.getString(R.string.widget_stamp_today, faDigits(hhmm))
                days <= 1 -> context.getString(R.string.widget_stamp_yesterday, faDigits(hhmm))
                else -> context.getString(R.string.widget_stamp_days, faDigits(days.toString()))
            }
        }
    }
}
