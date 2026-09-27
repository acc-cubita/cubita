import { Coins } from 'lucide-react'
import { CurrenciesPanel } from '../../components/CurrenciesPanel'
import { OpsPage } from './kit'

/**
 * صفحه‌های «فهرست» ماژولِ حسابداری.
 *
 * این‌ها عملیات نیستند، *داده‌ی ذخیره‌شده*اند — همان چیزی که کارتِ «فهرست» کنارِ
 * سایدبار به آن رهسپار می‌کند. سه‌تای اول پنل‌های موجود را می‌پوشانند به‌جای
 * بازنویسی: منطقِ بودجه و سندِ تکرارشونده و نرخِ ارز هیچ‌کدام عوض نشده، فقط جایشان
 * از تبِ درونِ صفحه به یک صفحه‌ی مستقل آمده.
 */

//: «اسناد تکرارشونده» با تمِ اکسلیِ سند حسابداری فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ
//: ورودِ صفحه عوض نشود.
export { RecurringListPage } from './RecurringPage'

//: «بودجه‌بندی» هم برگه‌ی اکسلیِ خودش را دارد (ماتریسِ حساب × ماه).
export { BudgetListPage } from './BudgetPage'

export function CurrencyListPage({ token }: { token: string }) {
  return (
    <OpsPage
      canvas
      icon={Coins}
      title="ارزها و نرخ ارز"
      description="ارزهای تعریف‌شده و نرخِ برابری‌شان با ریال در هر تاریخ. «صدور سند تسعیر ارز» از همین نرخ‌ها می‌خواند."
    >
      <CurrenciesPanel token={token} />
    </OpsPage>
  )
}

//: «دوره‌های بسته‌شده» با تمِ اکسلی فایلِ خودش را دارد.
export { PeriodCloseListPage } from './PeriodCloseListPage'
