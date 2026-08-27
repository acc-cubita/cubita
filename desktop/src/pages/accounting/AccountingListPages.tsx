import { Archive, Coins, Repeat, Target } from 'lucide-react'
import type { AccountCache } from '../../electron.d'
import { BudgetPanel } from '../../components/BudgetPanel'
import { CurrenciesPanel } from '../../components/CurrenciesPanel'
import { RecurringEntriesPanel } from '../../components/RecurringEntriesPanel'
import { SectionCard } from '../../components/SectionCard'
import { fetchPeriodCloses } from '../../api'
import { formatJalali } from '../../lib/jalali'
import { AsyncBlock, OpsPage, fa, faInt, useAsync } from './kit'

/**
 * صفحه‌های «فهرست» ماژولِ حسابداری.
 *
 * این‌ها عملیات نیستند، *داده‌ی ذخیره‌شده*اند — همان چیزی که کارتِ «فهرست» کنارِ
 * سایدبار به آن رهسپار می‌کند. سه‌تای اول پنل‌های موجود را می‌پوشانند به‌جای
 * بازنویسی: منطقِ بودجه و سندِ تکرارشونده و نرخِ ارز هیچ‌کدام عوض نشده، فقط جایشان
 * از تبِ درونِ صفحه به یک صفحه‌ی مستقل آمده.
 */

export function RecurringListPage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  return (
    <OpsPage
      icon={Repeat}
      title="اسناد تکرارشونده"
      description="سندهایی که در فاصله‌های مشخص خودکار ثبت می‌شوند — اجاره، حقوقِ ثابت، اقساط."
    >
      <RecurringEntriesPanel token={token} accounts={accounts} />
    </OpsPage>
  )
}

export function BudgetListPage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  return (
    <OpsPage
      icon={Target}
      title="بودجه‌بندی"
      description="رقمِ برنامه‌ریزی‌شده‌ی هر حساب در هر ماه. مقایسه‌ی بودجه با عملکرد در «گزارش‌ها» است."
    >
      <BudgetPanel token={token} accounts={accounts} />
    </OpsPage>
  )
}

export function CurrencyListPage({ token }: { token: string }) {
  return (
    <OpsPage
      icon={Coins}
      title="ارزها و نرخ ارز"
      description="ارزهای تعریف‌شده و نرخِ برابری‌شان با ریال در هر تاریخ. «صدور سند تسعیر ارز» از همین نرخ‌ها می‌خواند."
    >
      <CurrenciesPanel token={token} />
    </OpsPage>
  )
}

export function PeriodCloseListPage({ token }: { token: string }) {
  const closes = useAsync(() => fetchPeriodCloses(token), [token])
  const rows = closes.data ?? []

  return (
    <OpsPage
      icon={Archive}
      title="دوره‌های بسته‌شده"
      description="هر بار که حساب‌های سود و زیان بسته شده‌اند، یک ردیف اینجاست. تاریخِ آخرین بستن، مرزِ ثبتِ سند است."
    >
      <SectionCard
        icon={Archive}
        title="تاریخچه‌ی بستنِ دوره"
        description={`${faInt(rows.length)} دوره`}
      >
        <AsyncBlock
          loading={closes.loading}
          error={closes.error}
          empty={rows.length === 0}
          emptyText="هنوز هیچ دوره‌ای بسته نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخِ بستن</th>
                  <th>سود/زیانِ خالص</th>
                  <th>یادداشت</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td className="card-title" data-label="تاریخِ بستن">
                      {formatJalali(c.closing_date)}
                    </td>
                    <td
                      data-label="سود/زیانِ خالص"
                      className={`num ${Number(c.net_profit) < 0 ? 'pos-out' : 'pos-in'}`}
                    >
                      {fa(c.net_profit)}
                    </td>
                    <td data-label="یادداشت">{c.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
