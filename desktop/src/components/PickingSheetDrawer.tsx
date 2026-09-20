import { useEffect, useState } from 'react'
import { X, ClipboardList, MapPin, AlertTriangle } from 'lucide-react'
import { fetchPickingSheet, type PickingRow } from '../api'
import { EmptyState } from './EmptyState'
import { formatJalali } from '../lib/jalali'

const fa = (n: number | string) => Number(n).toLocaleString('fa-IR')

function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000)
}

/**
 * برگه‌ی جمع‌آوری (§۱۲) — انباردار باید بداند **کدام بار** و **کجا**.
 *
 * هیچ داده‌ی تازه‌ای نمی‌سازد: بار، انقضا و محلِ قرارگیری همه از قبل روی حرکتِ
 * دفتر و خودِ بار هستند. این فقط کنارِ هم می‌گذاردشان.
 *
 * کالای بی‌ردیابی همان برگه را می‌گیرد، فقط ستونِ بارش خالی است — §۲۸ می‌گوید
 * هیچ‌کدام از این قابلیت‌ها نباید اجباری شود.
 */
export function PickingSheetDrawer({
  token,
  issueId,
  issueNumber,
  onClose,
}: {
  token: string
  issueId: string
  issueNumber: number | string | null
  onClose: () => void
}) {
  const [rows, setRows] = useState<PickingRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchPickingSheet(token, issueId)
      .then((r) => alive && setRows(r))
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'خطای ناشناخته'))
    return () => {
      alive = false
    }
  }, [token, issueId])

  // بستن با Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const anyBatch = (rows ?? []).some((r) => r.batch_id !== null)

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <div className="drawer-title-main">برگه‌ی جمع‌آوری</div>
            <div className="drawer-title-sub">
              خروجِ انبار {issueNumber == null ? '' : `شماره ${fa(issueNumber)}`}
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          {error && <div className="error">{error}</div>}
          {rows === null ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : rows.length === 0 ? (
            <EmptyState icon={ClipboardList} text="این خروج ردیفِ انباری ندارد." />
          ) : (
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>کالا</th>
                    <th>تعداد</th>
                    {/* ستونِ بار فقط وقتی می‌آید که واقعاً باری در کار باشد. */}
                    {anyBatch && <th>بار</th>}
                    {anyBatch && <th>انقضا</th>}
                    {anyBatch && <th>محلِ قرارگیری</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const d = daysUntil(r.expiry_date)
                    const soon = d !== null && d <= 30
                    return (
                      <tr key={`${r.item_id}-${r.batch_id ?? 'x'}-${i}`}>
                        <td className="card-title" data-label="کالا">{r.item_name}</td>
                        <td className="num" data-label="تعداد">
                          <strong>{fa(r.qty)}</strong> {r.unit}
                        </td>
                        {anyBatch && (
                          <td className="ltr-cell" data-label="بار">{r.batch_number || '—'}</td>
                        )}
                        {anyBatch && (
                          <td data-label="انقضا">
                            {r.expiry_date ? (
                              <span className={`status-badge ${soon ? 'tone-warning' : 'tone-success'}`}>
                                {soon && <AlertTriangle size={12} />}
                                {formatJalali(r.expiry_date)}
                              </span>
                            ) : '—'}
                          </td>
                        )}
                        {anyBatch && (
                          <td className="ltr-cell" data-label="محلِ قرارگیری">
                            {r.location ? (<><MapPin size={12} /> {r.location}</>) : '—'}
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
