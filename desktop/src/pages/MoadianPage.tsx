import { FileSpreadsheet } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { MoadianPanel } from '../components/MoadianPanel'

/**
 * سامانه مؤدیان — ماژولِ مستقل.
 *
 * پیش‌تر یک تب داخلِ «فروش» بود؛ با بازچینیِ ماژول‌ها به یک ماژولِ اصلی ارتقا یافت.
 * خودِ پنل عیناً همان کامپوننتِ قبلی است، پس رفتار و تنظیماتِ کارپوشه تغییری نکرده.
 */
export function MoadianPage({ token }: { token: string }) {
  return (
    // پوسته‌ی کارتیِ صفحه — بدونِ آن محتوا روی پس‌زمینه‌ی برنامه شناور می‌ماند.
    <div className="page panels">
      <PageHeader
        icon={FileSpreadsheet}
        title="سامانه مؤدیان"
        description="ارسالِ صورتحساب الکترونیکی به کارپوشه‌ی سازمان امور مالیاتی و پیگیریِ وضعیتِ آن‌ها."
      />
      {/* پنل داخلِ یک پنلِ میانی می‌نشیند، نه مستقیم زیرِ پوسته: قاعده‌ی پوسته‌ی
          «راهنما» نوارِ آمارِ *فرزندِ مستقیمِ* صفحه را پنهان می‌کند، و KPIهای مؤدیان
          (وضعیتِ ارسال، در صف، ردشده) تنها جای دیدنشان همین صفحه است. */}
      <section className="moadian-body">
        <MoadianPanel token={token} />
      </section>
    </div>
  )
}
