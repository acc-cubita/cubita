import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, BookOpen } from 'lucide-react'
import { fetchGeneralLedger, type GeneralLedger, type ReportFilters } from '../api'
import { formatJalali } from '../lib/jalali'
import { JournalEntryDrawer } from './JournalEntryDrawer'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
const faSigned = (s: string) => {
  const n = Math.round(Number(s) || 0)
  return n < 0 ? `(${Math.abs(n).toLocaleString('fa-IR')})` : n.toLocaleString('fa-IR')
}

/**
 * کارتِ حساب (دفتر کل یک حساب) — همه‌ی گردشِ بدهکار/بستانکار با ماندهٔ در حال اجرا.
 * درجا از گزارشِ دفتر کل خوانده می‌شود و روی موبایل کارت می‌شود.
 *
 * **پله‌ی میانیِ drill-down.** بالادستش تراز و مرور حساب‌هاست و پایین‌دستش خودِ
 * سند: هر ردیف کلیک‌شدنی است و `JournalEntryDrawer` را باز می‌کند، تا هیچ عددی
 * بن‌بست نباشد (§۱۱ §۲۸).
 *
 * `filters` همان دامنه‌ای است که صفحه‌ی بالادست دارد. اگر فرستاده نشود، دفتر کلِ
 * تاریخ را نشان می‌دهد — که برای بازکردن از چارت یا فهرستِ بانک درست است، ولی
 * برای تراز نه: آن‌جا کاربر عددی را دیده که دامنه داشت و انتظار دارد همان را
 * توضیح‌داده ببیند.
 */
export function AccountLedgerDrawer({
  token,
  account,
  filters,
  onClose,
}: {
  token: string
  account: { id: string; code: string; name: string }
  filters?: ReportFilters
  onClose: () => void
}) {
  const [data, setData] = useState<GeneralLedger | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [entryId, setEntryId] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchGeneralLedger(token, account.id, filters)
      .then((r) => { if (alive) setData(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, account.id, JSON.stringify(filters ?? {})])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const hasFx = (data?.lines ?? []).some((l) => l.currency_code)
  const hasTracking = (data?.lines ?? []).some((l) => l.tracking_no)

  return createPortal(
    <>
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
                {data.fx_totals.map((t) => (
                  <div className="kardex-stat" key={t.currency_code}>
                    <span>خالصِ {t.currency_code}</span><strong>{faSigned(t.amount)}</strong>
                  </div>
                ))}
              </div>
              {data.lines.length === 0 ? (
                <p className="muted">این حساب در این دامنه هیچ گردشی ندارد.</p>
              ) : (
                <>
                <p className="hint">روی هر ردیف کلیک کنید تا سندش باز شود.</p>
                <div className="entity-table-wrap">
                  <div className="table-scroll">
                    <table className="entity-table kardex-table cards-on-mobile">
                      <thead>
                        <tr>
                          <th>تاریخ</th>
                          <th>سند</th>
                          <th>شرح</th>
                          {hasFx && <th>ارز</th>}
                          {hasTracking && <th>پیگیری</th>}
                          <th>بدهکار</th>
                          <th>بستانکار</th>
                          <th>مانده</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.lines.map((l) => (
                          <tr
                            key={l.line_id}
                            className="acc-row--clickable"
                            onClick={() => setEntryId(l.entry_id)}
                          >
                            <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                            <td data-label="سند" className="ltr-cell">{l.entry_number != null ? l.entry_number.toLocaleString('fa-IR') : '—'}</td>
                            <td data-label="شرح">{l.description || '—'}</td>
                            {hasFx && (
                              <td data-label="ارز" className="num">
                                {l.currency_code ? `${fa(Number(l.fx_amount ?? 0))} ${l.currency_code}` : '—'}
                              </td>
                            )}
                            {hasTracking && (
                              <td data-label="پیگیری">
                                {l.tracking_no ? <span dir="ltr">{l.tracking_no}</span> : '—'}
                              </td>
                            )}
                            <td data-label="بدهکار" className="money-cell">{Number(l.debit) > 0 ? fa(Number(l.debit)) : '—'}</td>
                            <td data-label="بستانکار" className="money-cell">{Number(l.credit) > 0 ? fa(Number(l.credit)) : '—'}</td>
                            <td data-label="مانده" className="money-cell"><strong>{faSigned(l.balance)}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
    {entryId && (
      <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />
    )}
    </>,
    document.body,
  )
}
