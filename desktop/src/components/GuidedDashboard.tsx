import { useEffect, useState } from 'react'
import { Wallet, TrendingUp, PackageSearch, Inbox } from 'lucide-react'
import { fetchIncomeStatement, fetchTrialBalance } from '../api'
import type { MeResponse } from '../api'
import type { PageKey } from './Sidebar'
import { StatCard } from './StatCard'
import { AlertsPanel } from './AlertsPanel'
import { ModuleSearch } from './ModuleSearch'
import { LauncherBoard } from './LauncherBoard'

const fa = (v: number) => v.toLocaleString('fa-IR')

/**
 * داشبوردِ «نسخه‌ی جدید» (پوسته‌ی guided): اقدام‌محور. سه بخش — چند KPIِ کلیدی،
 * «شروعِ کارِ تازه» (کارت‌هایی که خودِ کاربر از میانِ ماژول‌ها چیده، `LauncherBoard`)،
 * و «کارهای نیازمندِ رسیدگی» (همان AlertsPanelِ موجود). داده‌ها و پنل‌ها از همان
 * منابعِ overview بازاستفاده می‌شوند.
 */
export function GuidedDashboard({
  token,
  me,
  userName,
  pendingOutboxCount,
  itemsCount,
  onNavigate,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  userName: string
  pendingOutboxCount: number
  itemsCount: number
  onNavigate: (page: PageKey, section?: string) => void
  onMeUpdated: (me: MeResponse) => void
}) {
  const [cashBalance, setCashBalance] = useState<number | null>(null)
  const [inventoryValue, setInventoryValue] = useState<number | null>(null)
  const [periodProfit, setPeriodProfit] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchTrialBalance(token), fetchIncomeStatement(token)])
      .then(([trialBalance, incomeStatement]) => {
        if (cancelled) return
        const cash = Number(trialBalance.find((r) => r.account_code === '1101')?.balance ?? 0) || 0
        const bank = Number(trialBalance.find((r) => r.account_code === '1102')?.balance ?? 0) || 0
        const inventory = Number(trialBalance.find((r) => r.account_code === '1105')?.balance ?? 0) || 0
        setCashBalance(cash + bank)
        setInventoryValue(inventory)
        setPeriodProfit(Number(incomeStatement.net_profit))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className="page guided-dash">
      <div className="guided-welcome">
        <h1>خوش آمدید، {userName}</h1>
        <p className="hint">یک کار را از «شروعِ کارِ تازه» شروع کنید، یا کارهای نیازمندِ رسیدگی را ببینید.</p>
      </div>

      {/* بالای KPIها عمدی است: کسی که داشبورد را باز می‌کند معمولاً می‌خواهد
          *جایی برود*، نه عددی بخواند. */}
      <ModuleSearch me={me} onNavigate={onNavigate} />

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

      <LauncherBoard token={token} me={me} onMeUpdated={onMeUpdated} onNavigate={onNavigate} />

      <AlertsPanel token={token} />
    </div>
  )
}
