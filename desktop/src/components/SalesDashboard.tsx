import { useEffect, useState } from 'react'
import { BarChart3, Package, Users } from 'lucide-react'
import { fetchSalesDashboard, type SalesDashboard as SalesDashboardData } from '../api'
import { MonthlyBarsChart } from './MonthlyBarsChart'
import { RankBars, type RankRow } from './RankBars'

const faInt = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')

export function SalesDashboard({ token }: { token: string }) {
  const [data, setData] = useState<SalesDashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchSalesDashboard(token, 12)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : 'خطای ناشناخته'))
    return () => {
      cancelled = true
    }
  }, [token])

  if (error) return <div className="error">{error}</div>
  if (!data) return <p className="hint">در حال بارگذاری تحلیل فروش...</p>

  const itemRows: RankRow[] = data.top_items.map((it) => ({
    id: it.item_id,
    label: it.name,
    value: Number(it.revenue),
    sub: `تعداد فروش: ${faInt(it.qty)}`,
  }))
  const customerRows: RankRow[] = data.top_customers.map((c) => ({
    id: c.contact_id,
    label: c.name,
    value: Number(c.total),
  }))

  return (
    <div className="dashboard-analytics">
      <section className="trend-section">
        <h2><BarChart3 size={16} /> روند فروش و خرید (۱۲ ماه اخیر)</h2>
        <p className="section-card-desc">مقایسه‌ی ماه‌به‌ماهِ جمعِ فروش و خرید، به تفکیک ماه شمسی.</p>
        <MonthlyBarsChart monthly={data.monthly} />
      </section>

      <div className="overview-columns">
        <section className="activity-section">
          <h2><Package size={16} /> پرفروش‌ترین کالاها</h2>
          <p className="section-card-desc">بر اساس درآمدِ فروش در ۱۲ ماه اخیر.</p>
          <RankBars rows={itemRows} tone="var(--series-1)" />
        </section>
        <section className="activity-section">
          <h2><Users size={16} /> بهترین مشتریان</h2>
          <p className="section-card-desc">بر اساس جمعِ خرید در ۱۲ ماه اخیر.</p>
          <RankBars rows={customerRows} tone="var(--series-2)" />
        </section>
      </div>
    </div>
  )
}
