import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, FileText } from 'lucide-react'
import { fetchContactStatement, type ContactStatement } from '../api'
import { formatJalali } from '../lib/jalali'
import { CardPaymentButton } from './CardPaymentDialog'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
const faSigned = (s: string) => {
  const n = Math.round(Number(s) || 0)
  if (n === 0) return '۰'
  return n < 0 ? `${Math.abs(n).toLocaleString('fa-IR')} بس` : `${n.toLocaleString('fa-IR')} بد`
}

const KIND_LABELS: Record<string, string> = {
  sales_invoice: 'فاکتور فروش', purchase_invoice: 'فاکتور خرید',
  sales_return: 'برگشت فروش', purchase_return: 'برگشت خرید',
  receipt: 'دریافت', payment: 'پرداخت', check: 'چک', opening: 'مانده اول دوره',
}

/**
 * صورت‌حسابِ طرف حساب (کارتِ حساب مشتری/تأمین‌کننده) — همه‌ی فاکتورها، دریافت/پرداخت‌ها
 * و چک‌ها با ماندهٔ در حال اجرا. مثبت = بدهکار (به ما بدهکار است)، منفی = بستانکار.
 */
export function ContactStatementDrawer({
  token, contact, onClose,
}: {
  token: string
  contact: { id: string; name: string }
  onClose: () => void
}) {
  const [data, setData] = useState<ContactStatement | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    return fetchContactStatement(token, contact.id)
      .then((r) => setData(r))
      .catch((e) => setError(e instanceof Error ? e.message : 'خطای ناشناخته'))
  }, [token, contact.id])

  useEffect(() => {
    void load()
  }, [load])

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
            <FileText size={17} />
            <div>
              <div className="drawer-title-main">صورت‌حساب: {contact.name}</div>
              <div className="drawer-title-sub">همه‌ی فاکتورها، دریافت/پرداخت و چک‌ها</div>
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
                <div className="kardex-stat"><span>ماندهٔ فعلی</span><strong>{faSigned(data.closing_balance)}</strong></div>
              </div>
              {Math.round(Number(data.closing_balance) || 0) > 0 && (
                <div className="drawer-collect">
                  <CardPaymentButton
                    token={token}
                    amount={Math.round(Number(data.closing_balance))}
                    contactId={contact.id}
                    description={`دریافتِ کارتی — ${contact.name}`}
                    className="btn-primary"
                    onPaid={() => void load()}
                  />
                </div>
              )}
              {data.lines.length === 0 ? (
                <p className="muted">این طرف حساب هیچ گردشی ندارد.</p>
              ) : (
                <div className="entity-table-wrap">
                  <div className="table-scroll">
                    <table className="entity-table kardex-table cards-on-mobile">
                      <thead>
                        <tr>
                          <th>تاریخ</th>
                          <th>نوع</th>
                          <th>شرح</th>
                          <th>بدهکار</th>
                          <th>بستانکار</th>
                          <th>مانده</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.lines.map((l, i) => (
                          <tr key={i}>
                            <td data-label="تاریخ">{formatJalali(l.txn_date)}</td>
                            <td data-label="نوع">{KIND_LABELS[l.kind] ?? l.kind}{l.number != null ? ` #${l.number.toLocaleString('fa-IR')}` : ''}</td>
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
