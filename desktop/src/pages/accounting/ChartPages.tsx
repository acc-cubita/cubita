import { ListTree } from 'lucide-react'
import { AccountTreePanel } from '../../components/AccountTreePanel'
import { useNavSection } from '../../components/navContext'
import { OpsPage } from './kit'

/**
 * چهار عملیاتِ *ساختار*: درختواره، انتقالِ حساب به سرفصلِ دیگر، تفصیلیِ سایر، و مرورِ حساب‌ها.
 *
 * سه‌تای اول ساختار را می‌سازند و چهارمی همان ساختار را با عدد نشان می‌دهد. جدا
 * نگه‌داشتنِ «مرور» از «درختواره» عمدی است: درختواره ابزارِ *ویرایش* است و مرور ابزارِ
 * *خواندن*؛ یک صفحه‌ی مشترک هر دو کار را بد انجام می‌داد.
 *
 * «سرفصل جدید» و «فهرست حساب‌ها» (بازچینیِ ۱۴۰۵/۰۷/۰۳) صفحه‌ی جدا نیستند: افزودن و نمای تخت
 * هر دو درونِ درختواره‌اند — دو صفحه برای یک داده یعنی حسابدار حدس بزند کدام را باز کند.
 */

// ═════════════════════ ۱) درختواره حساب‌ها ═════════════════════

export function ChartOfAccountsPage({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const nav = useNavSection()
  return (
    <OpsPage
      canvas
      icon={ListTree}
      title="درختواره حساب‌ها"
      description="ساختارِ کاملِ چارت با مانده‌ی هر حساب: افزودن، ویرایش، غیرفعال‌کردن و جست‌وجو — درختی یا تخت. قالب‌های صنفی و حذفِ حساب در تنظیمات ← کدینگ است."
    >
      {/* «سرفصل جدید» و «فهرست حساب‌ها»ی قدیمی با بخشِ `new`/`flat` به همین‌جا می‌رسند. */}
      <AccountTreePanel
        token={token}
        onChanged={onChanged}
        startAdding={nav?.activePage === 'acctchart' && nav.section === 'new'}
        startFlat={nav?.activePage === 'acctchart' && nav.section === 'flat'}
      />
    </OpsPage>
  )
}

// ═════════════════ ۲) انتقال حساب به سرفصل دیگر ═════════════════
//: برگه‌ی اکسلیِ جابه‌جایی فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { ReclassifyPage } from './ReclassifyPage'

// ═══════════════════════ ۴) تفصیلی سایر ═══════════════════════
//: برگه‌ی اکسلیِ ویرایشِ درجا فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { AnalyticsPage } from './AnalyticsPage'

// ═══════════════════════ ۵) مرور حساب‌ها ═══════════════════════
//: کاوشگرِ حرفه‌ای (UI-02) فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ
//: ورودِ صفحه عوض نشود.
export { AccountBrowsePage } from './AccountBrowser'
