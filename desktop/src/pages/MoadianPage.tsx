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
    <>
      <PageHeader
        icon={FileSpreadsheet}
        title="سامانه مؤدیان"
        description="ارسالِ صورتحساب الکترونیکی به کارپوشه‌ی سازمان امور مالیاتی و پیگیریِ وضعیتِ آن‌ها."
      />
      <MoadianPanel token={token} />
    </>
  )
}
