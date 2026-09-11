import { useCallback, useEffect, useState } from 'react'
import { PackageX, PackagePlus, RefreshCw, History, CheckCircle2 } from 'lucide-react'
import { fetchLowStock, fetchOverStock, type LowStockRow, type OverStockRow } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'

const faQty = (s: string) => (Number(s) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

/**
 * «نیازمندِ سفارش» — کالاهایی که موجودیِ کلشان به/زیرِ آستانه رسیده. بحرانی‌ترین
 * (بیشترین کمبود) اول. با کلیک روی «کاردکس» تاریخچه‌ی حرکاتِ همان کالا باز می‌شود.
 *
 * **نقطه‌ی سفارش و حداقلِ موجودی دو مفهومِ جدا هستند** و ستونِ «آستانه» می‌گوید
 * کدام‌یک این ردیف را آورده؛ یکی‌کردنشان یعنی کاربر نفهمد چرا هشدار گرفته.
 */
export function LowStockPanel({
  token,
  onKardex,
}: {
  token: string
  onKardex: (item: { id: string; name: string; sku: string }) => void
}) {
  const [rows, setRows] = useState<LowStockRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setRows(await fetchLowStock(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  return (
    <SectionCard
      icon={PackageX}
      title="نیازمندِ سفارش"
      description="کالاهایی که موجودی‌شان به/زیرِ نقطه‌ی سفارش رسیده — به‌ترتیبِ بیشترین کمبود."
      actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
    >
      {error && <div className="error">{error}</div>}
      {rows == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={CheckCircle2} text="همه‌ی کالاها بالای نقطه‌ی سفارش‌اند — چیزی برای سفارش نیست." />
      ) : (
        <div className="entity-table-wrap">
          <div className="table-scroll">
            <table className="entity-table lowstock-table cards-on-mobile">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>موجودی فعلی</th>
                  <th>آستانه</th>
                  <th>کمبود</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.item_id}>
                    <td data-label="کالا" className="entity-name">
                      {r.name}
                      <span className="unit-suffix"> · {r.sku}</span>
                    </td>
                    <td data-label="موجودی فعلی" className="money-cell">
                      <span className={Number(r.qty_on_hand) <= 0 ? 'stock-warn' : ''}>{faQty(r.qty_on_hand)} {r.unit}</span>
                    </td>
                    <td data-label="آستانه" className="money-cell">
                      {faQty(r.trigger === 'min' ? r.min_stock : r.reorder_point)}
                      <div className="entity-sub">
                        {r.trigger === 'min' ? 'حداقل موجودی' : 'نقطه‌ی سفارش'}
                      </div>
                    </td>
                    <td data-label="کمبود" className="money-cell">
                      <span className="status-badge tone-warning">{faQty(r.shortfall)} {r.unit}</span>
                    </td>
                    <td className="lowstock-action card-actions">
                      <button type="button" onClick={() => onKardex({ id: r.item_id, name: r.name, sku: r.sku })}>
                        <History size={13} /> کاردکس
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SectionCard>
  )
}


/**
 * «مازاد موجودی» — کالاهایی که موجودیشان از حداکثر گذشته.
 *
 * **سدِ تراکنش نیست.** حداکثرِ موجودی جلوی ورودِ کالا را نمی‌گیرد؛ این فهرست
 * فقط می‌گوید کجا بیش از سیاستِ شرکت کالا انباشته شده.
 */
export function OverStockPanel({
  token,
  onKardex,
}: {
  token: string
  onKardex: (item: { id: string; name: string; sku: string }) => void
}) {
  const [rows, setRows] = useState<OverStockRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setRows(await fetchOverStock(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  return (
    <SectionCard
      icon={PackagePlus}
      title="مازاد موجودی"
      description="کالاهایی که موجودی‌شان از حداکثر گذشته — سیگنالِ برنامه‌ریزی، نه خطا."
      actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
    >
      {error && <div className="error">{error}</div>}
      {rows == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={CheckCircle2} text="هیچ کالایی از حداکثرِ موجودی عبور نکرده." />
      ) : (
        <div className="entity-table-wrap">
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>موجودی فعلی</th>
                  <th>حداکثر</th>
                  <th>مازاد</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.item_id}>
                    <td data-label="کالا" className="entity-name">
                      {r.name}
                      <span className="unit-suffix"> · {r.sku}</span>
                    </td>
                    <td data-label="موجودی فعلی" className="money-cell">{faQty(r.qty_on_hand)} {r.unit}</td>
                    <td data-label="حداکثر" className="money-cell">{faQty(r.max_stock)}</td>
                    <td data-label="مازاد" className="money-cell">
                      <span className="status-badge tone-warning">{faQty(r.excess)} {r.unit}</span>
                    </td>
                    <td className="card-actions">
                      <button type="button" onClick={() => onKardex({ id: r.item_id, name: r.name, sku: r.sku })}>
                        <History size={13} /> کاردکس
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
