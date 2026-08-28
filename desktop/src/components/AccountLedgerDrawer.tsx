import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, BookOpen } from 'lucide-react'
import { fetchGeneralLedger, type GeneralLedger } from '../api'
import { formatJalali } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
const faSigned = (s: string) => {
  const n = Math.round(Number(s) || 0)
  return n < 0 ? `(${Math.abs(n).toLocaleString('fa-IR')})` : n.toLocaleString('fa-IR')
}

/**
 * کارتِ حساب (دفتر کل یک حساب) — همه‌ی گردشِ بدهکار/بستانکار با ماندهٔ در حال اجرا.
 * درجا از گزارشِ دفتر کل خوانده می‌شود و روی موبایل کارت می‌شود.
 */
export function AccountLedgerDrawer({
  token,
  account,
  onClose,
}: {
  token: string
  account: { id: string; code: string; name: string }
  onClose: () => void
}) {
  const [data, setData] = useState<GeneralLedger | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchGeneralLedger(token, account.id)
      .then((r) => { if (alive) setData(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
  }, [token, account.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <BookOpen size={17} />
            <div>
              <div className="drawer-title-main">کارتِ حساب: {account.name}</div>
              <div className="drawer-title-sub ltr-cell">{account.code}</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          {error && <div className="error">{error}</div>}
          {!data && !error && <p className="muted">در حال بارگذاری…</p>}
          {data && (
            <>
              <div className="kardex-summary">
                <div className="kardex-stat"><span>ماندهٔ اول دوره</span><strong>{faSigned(data.opening_balance)}</strong></div>
                <div className="kardex-stat"><span>ماندهٔ پایان</span><strong>{faSigned(data.closing_balance)}</strong></div>
              </div>
              {data.lines.length === 0 ? (
                <p className="muted">این حساب هیچ گردشی ندارد.</p>
              ) : (
                <div className="entity-table-wrap">
                  <div className="table-scroll">
                    <table className="entity-table kardex-table cards-on-mobile">
                      <thead>
                        <tr>
                          <th>تاریخ</th>
                          <th>سند</th>
                          <th>شرح</th>
                          <th>بدهکار</th>
                          <th>بستانکار</th>
                          <th>مانده</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.lines.map((l, i) => (
                          <tr key={i}>
                            <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                            <td data-label="سند" className="ltr-cell">{l.entry_number != null ? l.entry_number.toLocaleString('fa-IR') : '—'}</td>
                            <td data-label="شرح">{l.description || '—'}</td>
                            <td data-label="بدهکار" className="money-cell">{Number(l.debit) > 0 ? fa(Number(l.debit)) : '—'}</td>
                            <td data-label="بستانکار" className="money-cell">{Number(l.credit) > 0 ? fa(Number(l.credit)) : '—'}</td>
                            <td data-label="مانده" className="money-cell"><strong>{faSigned(l.balance)}</strong></td>
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
