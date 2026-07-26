import { useMemo } from 'react'
import { Inbox, ListTree, BookOpen, CalendarCheck, Building2, Target, FolderKanban, Repeat, Coins, Wallet, TrendingUp, TrendingDown } from 'lucide-react'
import type { AccountCache, OutboxEntry } from '../electron.d'
import { StatCard } from '../components/StatCard'
import { JournalEntryForm } from '../components/JournalEntryForm'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { PeriodClosePanel } from '../components/PeriodClosePanel'
import { FixedAssetsPanel } from '../components/FixedAssetsPanel'
import { BudgetPanel } from '../components/BudgetPanel'
import { CostCentersPanel } from '../components/CostCentersPanel'
import { RecurringEntriesPanel } from '../components/RecurringEntriesPanel'
import { CurrenciesPanel } from '../components/CurrenciesPanel'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

export function AccountingPage({
  token,
  accounts,
  outbox,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
}) {
  const kpis = useMemo(() => {
    const by = (t: string) => accounts.filter((a) => a.type === t).length
    return { total: accounts.length, assets: by('asset'), income: by('income'), expense: by('expense') }
  }, [accounts])

  return (
    <div className="page">
      <PageHeader
        icon={BookOpen}
        title="حسابداری"
        description="قلب سیستم دوطرفه: هر فاکتور یا رویداد مالی خودکار اینجا سند می‌خورد. برای موارد خاص هم می‌توانید سند دستی بزنید."
      />

      <div className="stat-grid">
        <StatCard icon={<ListTree size={18} />} label="کل حساب‌ها" value={kpis.total.toLocaleString('fa-IR')} />
        <StatCard icon={<Wallet size={18} />} label="حساب‌های دارایی" value={kpis.assets.toLocaleString('fa-IR')} />
        <StatCard icon={<TrendingUp size={18} />} label="حساب‌های درآمد" value={kpis.income.toLocaleString('fa-IR')} tone="success" />
        <StatCard icon={<TrendingDown size={18} />} label="حساب‌های هزینه" value={kpis.expense.toLocaleString('fa-IR')} tone="warning" />
      </div>

      <Tabs
        tabs={[
          {
            key: 'journal',
            label: 'ثبت سند',
            icon: BookOpen,
            content: (
              <>
                <JournalEntryForm token={token} accounts={accounts} onQueued={onQueued} />
                {isElectron && (
                  <SectionCard
                    icon={Inbox}
                    title="صف اسناد حسابداری ارسال‌نشده"
                    description="سندهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
                  >
                    <OutboxList entries={outbox} emptyHint="سندی در صف نیست." />
                  </SectionCard>
                )}
              </>
            ),
          },
          {
            key: 'chart',
            label: 'چارت حساب‌ها',
            icon: ListTree,
            content: (
              <SectionCard
                icon={ListTree}
                title={isElectron ? 'چارت حساب‌ها (کش محلی — کار آفلاین)' : 'چارت حساب‌ها'}
                description="ساختار درختی تمام حساب‌های مالی کسب‌وکار؛ پایه‌ی همه‌ی گزارش‌ها و اسناد است."
              >
                {accounts.length === 0 ? (
                  <EmptyState
                    icon={ListTree}
                    text={isElectron ? 'برای دریافت اولین کپی چارت حساب، دکمه‌ی «هم‌گام‌سازی» را بزنید.' : 'چارت حسابی ثبت نشده.'}
                  />
                ) : (
                  <div className="entity-table-wrap">
                    <table className="entity-table">
                      <thead>
                        <tr>
                          <th>کد</th>
                          <th>نام</th>
                          <th>نوع</th>
                        </tr>
                      </thead>
                      <tbody>
                        {accounts.map((a) => (
                          <tr key={a.id} className={a.is_group ? 'group-row' : ''}>
                            <td className="ltr-cell">{a.code}</td>
                            <td className={a.is_group ? '' : 'entity-name'}>{a.name}</td>
                            <td>{a.type}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </SectionCard>
            ),
          },
          {
            key: 'assets',
            label: 'دارایی ثابت',
            icon: Building2,
            content: <FixedAssetsPanel token={token} />,
          },
          {
            key: 'budget',
            label: 'بودجه‌بندی',
            icon: Target,
            content: <BudgetPanel token={token} accounts={accounts} />,
          },
          {
            key: 'cost-centers',
            label: 'مراکز هزینه',
            icon: FolderKanban,
            content: <CostCentersPanel token={token} />,
          },
          {
            key: 'recurring',
            label: 'اسناد تکرارشونده',
            icon: Repeat,
            content: <RecurringEntriesPanel token={token} accounts={accounts} />,
          },
          {
            key: 'currencies',
            label: 'ارزها و نرخ ارز',
            icon: Coins,
            content: <CurrenciesPanel token={token} />,
          },
          {
            key: 'close',
            label: 'بستن دوره‌ی مالی',
            icon: CalendarCheck,
            content: <PeriodClosePanel token={token} />,
          },
        ]}
      />
    </div>
  )
}
