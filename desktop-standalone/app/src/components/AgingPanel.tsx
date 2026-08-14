import { useCallback, useEffect, useState } from 'react'
import { CalendarClock, RefreshCw, FileText } from 'lucide-react'
import { fetchAging, type AgingReport } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

/**
 * سنینِ مطالبات/بدهی — ماندهٔ باز به تفکیکِ بازه‌ی سررسید (جاری/۳۱–۶۰/۶۱–۹۰/۹۰+).
 * ابزارِ پیگیریِ وصولِ مطالبات و مدیریتِ پرداختِ بدهی‌ها.
 */
export function AgingPanel({
  token,
  onStatement,
}: {
  token: string
  onStatement: (c: { id: string; name: string }) => void
}) {
  const [kind, setKind] = useState<'receivable' | 'payable'>('receivable')
  const [data, setData] = useState<AgingReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null); setData(null)
    try {
      setData(await fetchAging(token, kind))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token, kind])

  useEffect(() => { void refresh() }, [refresh])

  return (
    <SectionCard
      icon={CalendarClock}
      title="سنینِ مطالبات و بدهی"
      description={kind === 'receivable' ? 'ماندهٔ طلبِ ما از مشتریان، به تفکیکِ سنِ سررسید.' : 'ماندهٔ بدهیِ ما به تأمین‌کنندگان، به تفکیکِ سنِ سررسید.'}
      actions={
        <div className="check-actions">
          <div className="seg-toggle">
            <button type="button" className={kind === 'receivable' ? 'active' : ''} onClick={() => setKind('receivable')}>مطالبات</button>
            <button type="button" className={kind === 'payable' ? 'active' : ''} onClick={() => setKind('payable')}>بدهی</button>
          </div>
          <button onClick={() => void refresh()}><RefreshCw size={13} /></button>
        </div>
      }
    >
      {error && <div className="error">{error}</div>}
      {data == null && !error ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : data && data.rows.length === 0 ? (
        <EmptyState icon={CalendarClock} text={kind === 'receivable' ? 'مطالباتِ بازی نیست.' : 'بدهیِ بازی نیست.'} />
      ) : data ? (
        <div className="entity-table-wrap">
          <table className="entity-table aging-table">
            <thead>
              <tr>
                <th>طرف حساب</th>
                <th>جاری</th>
                <th>۳۱–۶۰ روز</th>
                <th>۶۱–۹۰ روز</th>
                <th>+۹۰ روز</th>
                <th>جمع</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.contact_id}>
                  <td data-label="طرف حساب" className="entity-name">{r.contact_name}</td>
                  <td data-label="جاری" className="money-cell">{fa(Number(r.current))}</td>
                  <td data-label="۳۱–۶۰ روز" className="money-cell">{Number(r.d31_60) > 0 ? fa(Number(r.d31_60)) : '—'}</td>
                  <td data-label="۶۱–۹۰ روز" className="money-cell">{Number(r.d61_90) > 0 ? fa(Number(r.d61_90)) : '—'}</td>
                  <td data-label="+۹۰ روز" className="money-cell">
                    {Number(r.over_90) > 0 ? <span className="status-badge tone-danger">{fa(Number(r.over_90))}</span> : '—'}
                  </td>
                  <td data-label="جمع" className="money-cell"><strong>{fa(Number(r.total))}</strong></td>
                  <td className="aging-action">
                    <button type="button" onClick={() => onStatement({ id: r.contact_id, name: r.contact_name })}><FileText size={13} /> صورت‌حساب</button>
                  </td>
                </tr>
              ))}
              <tr className="aging-total-row">
                <td data-label="طرف حساب"><strong>جمعِ کل</strong></td>
                <td data-label="جاری" className="money-cell"><strong>{fa(Number(data.total_current))}</strong></td>
                <td data-label="۳۱–۶۰ روز" className="money-cell"><strong>{fa(Number(data.total_31_60))}</strong></td>
                <td data-label="۶۱–۹۰ روز" className="money-cell"><strong>{fa(Number(data.total_61_90))}</strong></td>
                <td data-label="+۹۰ روز" className="money-cell"><strong>{fa(Number(data.total_over_90))}</strong></td>
                <td data-label="جمع" className="money-cell"><strong>{fa(Number(data.grand_total))}</strong></td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : null}
    </SectionCard>
  )
}
