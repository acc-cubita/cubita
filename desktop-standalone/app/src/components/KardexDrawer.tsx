import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, History, ArrowDownToLine, ArrowUpFromLine, Boxes } from 'lucide-react'
import { fetchKardex, type KardexReport } from '../api'
import { formatJalali } from '../lib/jalali'

const fa = (n: number) => n.toLocaleString('fa-IR')
const faQty = (s: string) => (Number(s) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

/**
 * کاردکسِ یک کالا — تاریخچه‌ی همه‌ی ورود/خروج با موجودیِ در حال اجرا و بهای هر حرکت.
 * درجا از دفترِ موجودی خوانده می‌شود (همان اندپوینتِ گزارش‌ها) و روی موبایل به‌صورتِ
 * کارت نمایش داده می‌شود تا جدولِ افقی فشرده نشود.
 */
export function KardexDrawer({
  token,
  item,
  onClose,
}: {
  token: string
  item: { id: string; name: string; sku: string }
  onClose: () => void
}) {
  const [data, setData] = useState<KardexReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchKardex(token, item.id)
      .then((r) => { if (alive) setData(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
  }, [token, item.id])

  // بستن با Escape
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
            <History size={17} />
            <div>
              <div className="drawer-title-main">کاردکس: {item.name}</div>
              <div className="drawer-title-sub ltr-cell">{item.sku}{data ? ` · ${data.unit}` : ''}</div>
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
                <div className="kardex-stat"><span>موجودی اول</span><strong>{faQty(data.opening_qty)}</strong></div>
                <div className="kardex-stat"><ArrowDownToLine size={14} /><span>کل ورود</span><strong className="pos-in">{faQty(data.total_in)}</strong></div>
                <div className="kardex-stat"><ArrowUpFromLine size={14} /><span>کل خروج</span><strong className="pos-out">{faQty(data.total_out)}</strong></div>
                <div className="kardex-stat"><Boxes size={14} /><span>موجودی پایان</span><strong>{faQty(data.closing_qty)}</strong></div>
              </div>

              {data.lines.length === 0 ? (
                <p className="muted">هیچ حرکتی برای این کالا ثبت نشده.</p>
              ) : (
                <div className="entity-table-wrap">
                  <table className="entity-table kardex-table">
                    <thead>
                      <tr>
                        <th>تاریخ</th>
                        <th>شرح</th>
                        <th>ورود</th>
                        <th>خروج</th>
                        <th>بهای واحد</th>
                        <th>مانده</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.lines.map((l, i) => (
                        <tr key={i}>
                          <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                          <td data-label="شرح">{l.source_label}</td>
                          <td data-label="ورود" className="pos-in">{Number(l.qty_in) > 0 ? faQty(l.qty_in) : '—'}</td>
                          <td data-label="خروج" className="pos-out">{Number(l.qty_out) > 0 ? faQty(l.qty_out) : '—'}</td>
                          <td data-label="بهای واحد" className="money-cell">{fa(Number(l.unit_cost))}</td>
                          <td data-label="مانده" className="money-cell"><strong>{faQty(l.balance_qty)}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
