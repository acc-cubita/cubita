import { useEffect, useMemo, useState } from 'react'
import { Users, Crown, Heart, AlertTriangle, Sparkles, Moon, CircleUser, RefreshCw } from 'lucide-react'
import { fetchSegments, type CustomerSegment, type RfmResult, type SegmentCustomer } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'

const fa = (n: number | string) => Math.round(Number(n)).toLocaleString('fa-IR')

const SEGMENT_META: Record<CustomerSegment, { label: string; tone: string; icon: typeof Crown; hint: string }> = {
  champion: { label: 'قهرمانان', tone: 'success', icon: Crown, hint: 'اخیر، پرتکرار و پرخرید — بهترین‌ها' },
  loyal: { label: 'وفادار', tone: 'success', icon: Heart, hint: 'خریدِ منظم و پیوسته' },
  at_risk: { label: 'در معرضِ ریزش', tone: 'warning', icon: AlertTriangle, hint: 'قبلاً فعال بودند، حالا سرد شده‌اند' },
  new: { label: 'تازه‌وارد', tone: 'default', icon: Sparkles, hint: 'به‌تازگی اولین خریدشان را کرده‌اند' },
  dormant: { label: 'خفته', tone: 'danger', icon: Moon, hint: 'مدت‌هاست خرید نکرده‌اند' },
  regular: { label: 'عادی', tone: 'default', icon: CircleUser, hint: 'سایرِ مشتریان' },
}
const SEGMENT_ORDER: CustomerSegment[] = ['champion', 'loyal', 'at_risk', 'new', 'dormant', 'regular']

function Rfm({ score }: { score: number }) {
  return <span className={`rfm-pip rfm-pip-${score}`} title={`امتیاز ${fa(score)} از ۵`}>{fa(score)}</span>
}

export function SegmentsPanel({ token }: { token: string }) {
  const [data, setData] = useState<RfmResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<CustomerSegment | 'all'>('all')

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchSegments(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    void refresh()
  }, [])

  const byKey = useMemo(() => {
    const m = new Map<CustomerSegment, { count: number; monetary: number }>()
    for (const s of data?.summary ?? []) m.set(s.segment, { count: s.count, monetary: Number(s.monetary) })
    return m
  }, [data])

  const filtered = useMemo<SegmentCustomer[]>(
    () => (data?.customers ?? []).filter((c) => filter === 'all' || c.segment === filter),
    [data, filter],
  )
  const pg = usePagination(filtered, 12, filter)

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div className="segment-grid">
        {SEGMENT_ORDER.map((key) => {
          const meta = SEGMENT_META[key]
          const Icon = meta.icon
          const s = byKey.get(key)
          const active = filter === key
          return (
            <button
              key={key}
              type="button"
              className={`segment-card tone-${meta.tone}${active ? ' active' : ''}`}
              onClick={() => setFilter(active ? 'all' : key)}
              title={meta.hint}
            >
              <div className="segment-card-head">
                <Icon size={17} />
                <span className="segment-card-label">{meta.label}</span>
              </div>
              <div className="segment-card-count">{fa(s?.count ?? 0)}</div>
              <div className="segment-card-sub">{s ? `${fa(s.monetary)} ریال` : '—'}</div>
            </button>
          )
        })}
      </div>

      <SectionCard
        icon={Users}
        title="مشتریان بر اساسِ رفتارِ خرید (RFM)"
        description={
          filter === 'all'
            ? `${fa(data?.total_customers ?? 0)} مشتری — تازگی (R)، تعداد (F)، مبلغ (M)`
            : `دسته‌ی «${SEGMENT_META[filter].label}» — ${fa(filtered.length)} مشتری`
        }
        actions={
          <button type="button" onClick={() => void refresh()} disabled={loading}>
            <RefreshCw size={13} className={loading ? 'spin' : ''} /> به‌روزرسانی
          </button>
        }
      >
        {filtered.length === 0 ? (
          <EmptyState icon={Users} text={loading ? 'در حال محاسبه…' : 'مشتریِ دارای خرید برای این دسته نیست.'} />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table segments-table">
              <thead>
                <tr>
                  <th>مشتری</th>
                  <th>دسته</th>
                  <th>R</th>
                  <th>F</th>
                  <th>M</th>
                  <th>آخرین خرید</th>
                  <th>تعداد</th>
                  <th>مجموع خرید</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((c) => {
                  const meta = SEGMENT_META[c.segment]
                  return (
                    <tr key={c.contact_id}>
                      <td data-label="مشتری">
                        <div className="entity-cell">
                          <div className="entity-avatar tone-customer">{c.contact_name.trim().charAt(0) || '؟'}</div>
                          <div className="entity-name">{c.contact_name}</div>
                        </div>
                      </td>
                      <td data-label="دسته"><span className={`status-badge tone-${meta.tone}`}>{meta.label}</span></td>
                      <td data-label="R"><Rfm score={c.r} /></td>
                      <td data-label="F"><Rfm score={c.f} /></td>
                      <td data-label="M"><Rfm score={c.m} /></td>
                      <td data-label="آخرین خرید">
                        {c.last_purchase ? formatJalali(c.last_purchase) : '—'}
                        <div className="entity-sub">{fa(c.recency_days)} روز پیش</div>
                      </td>
                      <td data-label="تعداد" className="money-cell">{fa(c.frequency)}</td>
                      <td data-label="مجموع خرید" className="money-cell"><strong>{fa(c.monetary)}</strong></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
    </>
  )
}
