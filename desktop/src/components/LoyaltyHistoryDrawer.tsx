import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Gift } from 'lucide-react'
import { fetchLoyaltyTransactions, type LoyaltyTxnRecord } from '../api'
import { formatJalali } from '../lib/jalali'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * تاریخچه‌ی امتیازِ یک مشتری — کسب/مصرفِ امتیاز با ماندهٔ در حال اجرا. درجا از
 * `/api/crm/loyalty/transactions?contact_id=` خوانده می‌شود.
 */
export function LoyaltyHistoryDrawer({
  token, contact, onClose,
}: {
  token: string
  contact: { id: string; name: string }
  onClose: () => void
}) {
  const [txns, setTxns] = useState<LoyaltyTxnRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchLoyaltyTransactions(token, contact.id)
      .then((r) => { if (alive) setTxns(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
  }, [token, contact.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // ماندهٔ در حال اجرا: از قدیمی به جدید، سپس معکوس برای نمایش
  const rows = useMemo(() => {
    const list = [...(txns ?? [])].sort((a, b) => (a.txn_date < b.txn_date ? -1 : 1))
    let run = 0
    const withRun = list.map((t) => { run += t.points; return { ...t, running: run } })
    return withRun.reverse()
  }, [txns])
  const balance = rows.length ? rows[0].running : 0
  const earned = (txns ?? []).filter((t) => t.points > 0).reduce((s, t) => s + t.points, 0)
  const redeemed = (txns ?? []).filter((t) => t.points < 0).reduce((s, t) => s - t.points, 0)

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <Gift size={17} />
            <div>
              <div className="drawer-title-main">تاریخچه‌ی امتیاز: {contact.name}</div>
              <div className="drawer-title-sub">کسب و مصرفِ امتیازِ باشگاه</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          {error && <div className="error">{error}</div>}
          {!txns && !error && <p className="muted">در حال بارگذاری…</p>}
          {txns && (
            <>
              <div className="kardex-summary">
                <div className="kardex-stat"><span>کل کسب‌شده</span><strong className="pos-in">{fa(earned)}</strong></div>
                <div className="kardex-stat"><span>کل مصرف‌شده</span><strong className="pos-out">{fa(redeemed)}</strong></div>
                <div className="kardex-stat"><span>ماندهٔ فعلی</span><strong>{fa(balance)}</strong></div>
              </div>
              {rows.length === 0 ? (
                <p className="muted">این مشتری هنوز امتیازی ندارد.</p>
              ) : (
                <div className="entity-table-wrap">
                  <div className="table-scroll">
                    <table className="entity-table kardex-table cards-on-mobile">
                      <thead>
                        <tr><th>تاریخ</th><th>بابت</th><th>امتیاز</th><th>مانده</th></tr>
                      </thead>
                      <tbody>
                        {rows.map((t) => (
                          <tr key={t.id}>
                            <td data-label="تاریخ">{formatJalali(t.txn_date)}</td>
                            <td data-label="بابت">{t.reason || '—'}</td>
                            <td data-label="امتیاز" className={`money-cell ${t.points >= 0 ? 'pos-in' : 'pos-out'}`}>
                              {t.points >= 0 ? '+' : '−'}{fa(Math.abs(t.points))}
                            </td>
                            <td data-label="مانده" className="money-cell"><strong>{fa(t.running)}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
