import { useEffect, useMemo, useState } from 'react'
import { Inbox, Landmark, ScrollText, GitCompareArrows, CalendarClock, Wallet } from 'lucide-react'
import { fetchChecks, type CheckRecord } from '../api'
import type { AccountCache, BankAccountCache, OutboxEntry } from '../electron.d'
import { StatCard } from '../components/StatCard'
import { CheckForm } from '../components/CheckForm'

const faMoney = (n: number) => n.toLocaleString('fa-IR')
const ACTIVE_CHECK = new Set(['in_hand', 'deposited', 'issued'])
import { OutboxList } from '../components/OutboxList'
import { ChecksList } from '../components/ChecksList'
import { BankAccountsPanel } from '../components/BankAccountsPanel'
import { PettyCashPanel } from '../components/PettyCashPanel'
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
  const [checks, setChecks] = useState<CheckRecord[]>([])
  useEffect(() => {
    void fetchChecks(token).then(setChecks).catch(() => {})
  }, [])
  const kpis = useMemo(() => {
    const active = checks.filter((c) => ACTIVE_CHECK.has(c.status))
    const recv = active.filter((c) => c.type === 'receivable')
    const pay = active.filter((c) => c.type === 'payable')
    const soon = new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10)
    const dueSoon = active.filter((c) => c.due_date <= soon).length
    return {
      banks: bankAccounts.length,
      recvCount: recv.length,
      recvSum: recv.reduce((s, c) => s + Number(c.amount), 0),
      payCount: pay.length,
      paySum: pay.reduce((s, c) => s + Number(c.amount), 0),
      dueSoon,
    }
  }, [checks, bankAccounts])

  return (
    <div className="page">
      <PageHeader
        icon={Landmark}
        title="چک و بانک"
        description="چک‌های دریافتنی/پرداختنی و حساب‌های بانکی را از ثبت تا وصول یا خرج‌شدن پیگیری کنید."
      />

      <div className="stat-grid">
        <StatCard icon={<Landmark size={18} />} label="حساب‌های بانکی" value={faMoney(kpis.banks)} />
        <StatCard icon={<ScrollText size={18} />} label="چک دریافتنیِ باز" value={faMoney(kpis.recvCount)} tone="success" hint={`${faMoney(kpis.recvSum)} ریال`} />
        <StatCard icon={<ScrollText size={18} />} label="چک پرداختنیِ باز" value={faMoney(kpis.payCount)} hint={`${faMoney(kpis.paySum)} ریال`} />
        <StatCard
          icon={<CalendarClock size={18} />}
          label="نزدیکِ سررسید (۷ روز)"
          value={faMoney(kpis.dueSoon)}
          tone={kpis.dueSoon > 0 ? 'warning' : 'default'}
        />
      </div>

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
            content: <BankAccountsPanel token={token} accounts={accounts} />,
          },
          {
            key: 'petty',
            label: 'تنخواه‌گردان',
            icon: Wallet,
            content: <PettyCashPanel token={token} accounts={accounts} />,
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
