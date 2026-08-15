import { useCallback, useEffect, useState } from 'react'
import { Percent, Wallet, AlertCircle, Users, Check } from 'lucide-react'
import {
  fetchMpCommissionOverview,
  fetchMpCommissions,
  settleMpCommission,
  type MpCommissionOverview,
  type MpCommissionPeriod,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'

const faMoney = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
// "1405-05" → "۱۴۰۵/۰۵"
const faPeriod = (p: string) =>
  p.replace('-', '/').replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)])

/** پنلِ سوپرادمین — کمیسیونِ ۲٪ِ پلتفرم از پخش‌کننده‌های بازار. فقط مالکِ سامانه. */
export function MarketplaceCommissionPage({ token }: { token: string }) {
  const [rows, setRows] = useState<MpCommissionPeriod[]>([])
  const [overview, setOverview] = useState<MpCommissionOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [o, r] = await Promise.all([fetchMpCommissionOverview(token), fetchMpCommissions(token)])
      setOverview(o)
      setRows(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطای ناشناخته')
    }
  }, [token])
  useEffect(() => {
    void refresh()
  }, [refresh])

  const ratePct = overview ? (overview.rate * 100).toLocaleString('fa-IR') : '۲'

  async function settle(r: MpCommissionPeriod) {
    const note = window.prompt(
      `تسویه‌ی کمیسیونِ «${r.distributor_name}» برای ماهِ ${faPeriod(r.period)} به مبلغِ ${faMoney(r.pending_amount)} ریال.\n` +
        'مرجعِ واریز (شماره‌ی پیگیری/شبا) را وارد کنید:',
      '',
    )
    if (note === null) return
    const key = `${r.distributor_tenant_id}|${r.period}`
    setBusy(key)
    setError(null)
    try {
      await settleMpCommission(token, {
        distributor_tenant_id: r.distributor_tenant_id,
        period: r.period,
        note,
      })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطای ناشناخته')
    } finally {
      setBusy(null)
    }
  }

  const pendingRows = rows.filter((r) => r.status === 'pending')
  const settledRows = rows.filter((r) => r.status === 'settled')

  return (
    <div className="page panels">
      <PageHeader
        icon={Percent}
        title="کمیسیونِ بازار (۲٪)"
        description={`${ratePct}٪ از جمعِ سفارش‌های قطعی‌شده‌ی هر پخش‌کننده، کمیسیونِ پلتفرم است. پخش‌کننده ماهانه به حسابِ ما واریز می‌کند و شما پس از دریافت، «تسویه» می‌زنید.`}
      />

      <div className="stat-grid">
        <StatCard icon={<Wallet size={18} />} label="کلِ کمیسیون" value={faMoney(overview?.total_amount ?? 0)} hint="ریال" />
        <StatCard
          icon={<AlertCircle size={18} />}
          label="دریافت‌نشده"
          value={faMoney(overview?.pending_amount ?? 0)}
          tone={(overview?.pending_amount ?? 0) > 0 ? 'warning' : 'success'}
          hint="ریال — طلبِ ما"
        />
        <StatCard icon={<Check size={18} />} label="تسویه‌شده" value={faMoney(overview?.settled_amount ?? 0)} tone="success" hint="ریال" />
        <StatCard icon={<Users size={18} />} label="پخش‌کننده‌ها" value={faMoney(overview?.distributor_count ?? 0)} />
      </div>

      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={AlertCircle}
        title="در انتظارِ دریافت"
        description="ماه‌هایی که کمیسیونشان هنوز واریز/تسویه نشده. پس از دریافتِ واریزِ پخش‌کننده، «تسویه» را بزنید."
      >
        {pendingRows.length === 0 ? (
          <EmptyState icon={Check} text="کمیسیونِ دریافت‌نشده‌ای نیست." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>پخش‌کننده</th>
                  <th>ماه</th>
                  <th>سفارش‌ها</th>
                  <th>جمعِ فاکتورها</th>
                  <th>کمیسیونِ ۲٪</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pendingRows.map((r) => {
                  const key = `${r.distributor_tenant_id}|${r.period}`
                  return (
                    <tr key={key}>
                      <td className="entity-name card-title">{r.distributor_name}</td>
                      <td data-label="ماه">{faPeriod(r.period)}</td>
                      <td data-label="سفارش‌ها">{faMoney(r.order_count)}</td>
                      <td className="money-cell" data-label="جمعِ فاکتورها">{faMoney(r.total_base)}</td>
                      <td className="money-cell" data-label="کمیسیونِ ۲٪">{faMoney(r.pending_amount)}</td>
                      <td className="card-actions">
                        <button type="button" className="btn-primary" disabled={busy === key} onClick={() => void settle(r)}>
                          <Check size={13} /> تسویه
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <SectionCard icon={Check} title="تسویه‌شده‌ها" description="ماه‌هایی که کمیسیونشان دریافت و تسویه شده.">
        {settledRows.length === 0 ? (
          <EmptyState icon={Wallet} text="هنوز موردی تسویه نشده است." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>پخش‌کننده</th>
                  <th>ماه</th>
                  <th>سفارش‌ها</th>
                  <th>کمیسیونِ ۲٪</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {settledRows.map((r) => (
                  <tr key={`${r.distributor_tenant_id}|${r.period}`}>
                    <td className="entity-name card-title">{r.distributor_name}</td>
                    <td data-label="ماه">{faPeriod(r.period)}</td>
                    <td data-label="سفارش‌ها">{faMoney(r.order_count)}</td>
                    <td className="money-cell" data-label="کمیسیونِ ۲٪">{faMoney(r.total_amount)}</td>
                    <td data-label="وضعیت">
                      <span className="status-badge tone-success">تسویه‌شده</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
