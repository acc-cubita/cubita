import { useEffect, useState } from 'react'
import {
  fetchGeneralLedger,
  fetchIncomeStatement,
  fetchJournalEntries,
  fetchTrialBalance,
  type JournalEntryRecord,
} from '../api'
import { StatCard } from '../components/StatCard'
import { TrendChart, type TrendSeries } from '../components/TrendChart'
import { ActivityFeed } from '../components/ActivityFeed'
import { Wallet, TrendingUp, PackageSearch, Inbox } from 'lucide-react'

const fa = (v: number) => v.toLocaleString('fa-IR')

export function OverviewPage({
  token,
  userName,
  pendingOutboxCount,
  itemsCount,
}: {
  token: string
  userName: string
  pendingOutboxCount: number
  itemsCount: number
}) {
  const [cashBalance, setCashBalance] = useState<number | null>(null)
  const [inventoryValue, setInventoryValue] = useState<number | null>(null)
  const [periodProfit, setPeriodProfit] = useState<number | null>(null)
  const [trendSeries, setTrendSeries] = useState<TrendSeries[]>([])
  const [entries, setEntries] = useState<JournalEntryRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [trialBalance, incomeStatement, journalEntries] = await Promise.all([
          fetchTrialBalance(token),
          fetchIncomeStatement(token),
          fetchJournalEntries(token),
        ])
        if (cancelled) return

        const cashRow = trialBalance.find((r) => r.account_code === '1101')
        const bankRow = trialBalance.find((r) => r.account_code === '1102')
        const inventoryRow = trialBalance.find((r) => r.account_code === '1105')

        setCashBalance((Number(cashRow?.balance ?? 0) || 0) + (Number(bankRow?.balance ?? 0) || 0))
        setInventoryValue(Number(inventoryRow?.balance ?? 0) || 0)
        setPeriodProfit(Number(incomeStatement.net_profit))
        setEntries(journalEntries)

        const series: TrendSeries[] = []
        if (cashRow) {
          const ledger = await fetchGeneralLedger(token, cashRow.account_id)
          series.push({
            key: 'cash',
            label: 'صندوق',
            color: 'var(--series-1)',
            points: ledger.lines.map((l) => ({ date: l.entry_date, value: Number(l.balance) })),
          })
        }
        if (bankRow) {
          const ledger = await fetchGeneralLedger(token, bankRow.account_id)
          series.push({
            key: 'bank',
            label: 'بانک',
            color: 'var(--series-2)',
            points: ledger.lines.map((l) => ({ date: l.entry_date, value: Number(l.balance) })),
          })
        }
        if (!cancelled) setTrendSeries(series)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'خطای ناشناخته')
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className="page">
      <div className="page-welcome">
        <h1>خوش آمدید، {userName}</h1>
        <p className="hint">
          خلاصه‌ی وضعیت مالی و عملیاتی همین الان — نقد و بانک، سود دوره، ارزش انبار و اسناد در صف ارسال. تازه با
          برنامه آشنا شدید؟ از نوار کناری وارد «راهنما» شوید.
        </p>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard
          icon={<Wallet size={18} />}
          label="موجودی نقد و بانک"
          value={cashBalance === null ? '—' : fa(cashBalance)}
          tone={cashBalance !== null && cashBalance < 0 ? 'danger' : 'default'}
        />
        <StatCard
          icon={<TrendingUp size={18} />}
          label="سود/زیان دوره جاری"
          value={periodProfit === null ? '—' : fa(periodProfit)}
          tone={periodProfit !== null ? (periodProfit >= 0 ? 'success' : 'danger') : 'default'}
        />
        <StatCard
          icon={<PackageSearch size={18} />}
          label="ارزش موجودی انبار"
          value={inventoryValue === null ? '—' : fa(inventoryValue)}
        />
        <StatCard
          icon={<Inbox size={18} />}
          label="اسناد در صف ارسال (آفلاین)"
          value={String(pendingOutboxCount)}
          tone={pendingOutboxCount > 0 ? 'warning' : 'default'}
          hint={`تعداد کالای کش‌شده: ${itemsCount}`}
        />
      </div>

      <div className="overview-columns">
        <section className="trend-section">
          <h2>روند نقدینگی</h2>
          <p className="section-card-desc">تغییرات موجودی صندوق و بانک در طول زمان.</p>
          <TrendChart series={trendSeries} />
        </section>

        <section className="activity-section">
          <h2>آخرین رویدادها</h2>
          <p className="section-card-desc">تازه‌ترین اسناد حسابداری ثبت‌شده، از هر ماژول.</p>
          <ActivityFeed entries={entries} />
        </section>
      </div>
    </div>
  )
}
