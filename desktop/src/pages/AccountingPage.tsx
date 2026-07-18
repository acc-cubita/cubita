import { Inbox, ListTree, BookOpen } from 'lucide-react'
import type { AccountCache, OutboxEntry } from '../electron.d'
import { JournalEntryForm } from '../components/JournalEntryForm'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { PeriodClosePanel } from '../components/PeriodClosePanel'
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
  return (
    <div className="page">
      <PageHeader
        icon={BookOpen}
        title="حسابداری"
        description="قلب سیستم دوطرفه: هر فاکتور یا رویداد مالی خودکار اینجا سند می‌خورد. برای موارد خاص هم می‌توانید سند دستی بزنید."
      />
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
          <table>
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
                  <td>{a.code}</td>
                  <td>{a.name}</td>
                  <td>{a.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <PeriodClosePanel token={token} />
    </div>
  )
}
