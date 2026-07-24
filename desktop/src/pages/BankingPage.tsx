import { Inbox, Landmark, ScrollText, GitCompareArrows } from 'lucide-react'
import type { AccountCache, BankAccountCache, OutboxEntry } from '../electron.d'
import { CheckForm } from '../components/CheckForm'
import { OutboxList } from '../components/OutboxList'
import { ChecksList } from '../components/ChecksList'
import { BankingPanel } from '../components/BankingPanel'
import { ReconciliationPanel } from '../components/ReconciliationPanel'
import { SectionCard } from '../components/SectionCard'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

export function BankingPage({
  token,
  accounts,
  bankAccounts,
  outbox,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  bankAccounts: BankAccountCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
}) {
  return (
    <div className="page">
      <PageHeader
        icon={Landmark}
        title="چک و بانک"
        description="چک‌های دریافتنی/پرداختنی و حساب‌های بانکی را از ثبت تا وصول یا خرج‌شدن پیگیری کنید."
      />
      <Tabs
        tabs={[
          {
            key: 'checks',
            label: 'چک‌ها',
            icon: ScrollText,
            content: (
              <>
                <CheckForm token={token} onQueued={onQueued} />
                {isElectron && (
                  <SectionCard
                    icon={Inbox}
                    title="صف چک‌های ارسال‌نشده"
                    description="چک‌هایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
                  >
                    <OutboxList entries={outbox} emptyHint="چکی در صف نیست." />
                  </SectionCard>
                )}
                <ChecksList token={token} bankAccounts={bankAccounts} />
              </>
            ),
          },
          {
            key: 'accounts',
            label: 'حساب‌های بانکی',
            icon: Landmark,
            content: <BankingPanel token={token} accounts={accounts} bankAccounts={bankAccounts} />,
          },
          {
            key: 'reconciliation',
            label: 'تطبیق بانکی',
            icon: GitCompareArrows,
            content: <ReconciliationPanel token={token} bankAccounts={bankAccounts} />,
          },
        ]}
      />
    </div>
  )
}
