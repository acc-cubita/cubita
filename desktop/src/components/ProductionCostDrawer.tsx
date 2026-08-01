import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, Factory } from 'lucide-react'
import type { ItemRecord, ProductionOrderRecord } from '../api'
import { formatJalali } from '../lib/jalali'

const fa = (v: string | number) => Math.round(Number(v || 0)).toLocaleString('fa-IR')
const faQty = (v: string | number) => Number(v || 0).toLocaleString('fa-IR')

/**
 * برگهٔ بهای تمام‌شدهٔ یک سفارشِ تولید — ریزِ مصرفِ هر جزء (مقدار × بهای واحد)، جمعِ
 * مواد، سربار، و بهای هر واحدِ محصول؛ همان اعدادِ اسنپ‌شات‌شده در لحظه‌ی تولید.
 */
export function ProductionCostDrawer({
  order, itemById, onClose,
}: {
  order: ProductionOrderRecord
  itemById: Map<string, ItemRecord>
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const productName = itemById.get(order.finished_item_id)?.name ?? '—'
  const totalCost = Number(order.component_cost) + Number(order.overhead_cost)

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <Factory size={17} />
            <div>
              <div className="drawer-title-main">برگهٔ بهای تمام‌شده: {productName}</div>
              <div className="drawer-title-sub">
                سفارش {order.number != null ? faQty(order.number) : '—'} · {formatJalali(order.production_date)} · {faQty(order.qty_produced)} واحد
              </div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          <div className="kardex-summary">
            <div className="kardex-stat"><span>بهای مواد اولیه</span><strong>{fa(order.component_cost)}</strong></div>
            <div className="kardex-stat"><span>سربار</span><strong>{fa(order.overhead_cost)}</strong></div>
            <div className="kardex-stat"><span>بهای کل</span><strong>{fa(totalCost)}</strong></div>
            <div className="kardex-stat"><span>بهای هر واحد</span><strong className="pos-in">{fa(order.unit_cost)}</strong></div>
          </div>

          <div className="entity-table-wrap">
            <table className="entity-table prod-cost-table">
              <thead>
                <tr><th>جزء (ماده اولیه)</th><th>مقدار</th><th>بهای واحد</th><th>جمع</th></tr>
              </thead>
              <tbody>
                {order.lines.map((l, i) => (
                  <tr key={i}>
                    <td className="entity-name">{itemById.get(l.component_item_id)?.name ?? '؟'}</td>
                    <td data-label="مقدار">{faQty(l.qty)}</td>
                    <td data-label="بهای واحد" className="money-cell">{fa(l.unit_cost)}</td>
                    <td data-label="جمع" className="money-cell"><strong>{fa(Number(l.qty) * Number(l.unit_cost))}</strong></td>
                  </tr>
                ))}
                <tr className="prod-cost-foot">
                  <td className="entity-name">جمعِ مواد اولیه</td>
                  <td data-label="مقدار"></td>
                  <td data-label="بهای واحد"></td>
                  <td data-label="جمع" className="money-cell"><strong>{fa(order.component_cost)}</strong></td>
                </tr>
                {Number(order.overhead_cost) > 0 && (
                  <tr className="prod-cost-foot">
                    <td className="entity-name">سربار / دستمزد</td>
                    <td data-label="مقدار"></td>
                    <td data-label="بهای واحد"></td>
                    <td data-label="جمع" className="money-cell"><strong>{fa(order.overhead_cost)}</strong></td>
                  </tr>
                )}
                <tr className="prod-cost-total">
                  <td className="entity-name">بهای هر واحدِ محصول (÷ {faQty(order.qty_produced)})</td>
                  <td data-label="مقدار"></td>
                  <td data-label="بهای واحد"></td>
                  <td data-label="جمع" className="money-cell"><strong>{fa(order.unit_cost)}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="field-hint">
            اجزا با میانگینِ موزونِ خودشان از انبار خارج شده‌اند؛ بهای هر واحد = (بهای مواد + سربار) ÷ تعدادِ تولید.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  )
}
