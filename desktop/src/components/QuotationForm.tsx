import { useState } from 'react'
import { FileText, Plus, Trash2, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { createSalesQuotation } from '../api'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

interface DraftLine {
  itemId: string
  qty: string
  unitPrice: string
}

export function QuotationForm({
  token,
  warehouses,
  items,
  onCreated,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onCreated: () => void
}) {
  const [warehouseId, setWarehouseId] = useState('')
  const [quotationDate, setQuotationDate] = useState(todayIso())
  const [validUntil, setValidUntil] = useState('')
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([{ itemId: '', qty: '1', unitPrice: '' }])
  const [message, setMessage] = useState<string | null>(null)

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '1', unitPrice: '' }])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  const total = lines.reduce((sum, line) => sum + (Number(line.qty) || 0) * (Number(line.unitPrice) || 0), 0)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    if (!effectiveWarehouseId) {
      setMessage('ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.')
      return
    }
    const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیف معتبر (کالا + تعداد) لازم است.')
      return
    }

    try {
      await createSalesQuotation(token, {
        quotation_date: quotationDate,
        valid_until: validUntil || null,
        warehouse_id: effectiveWarehouseId,
        description,
        lines: validLines.map((l) => ({
          item_id: l.itemId,
          qty: Number(l.qty),
          unit_price: Number(l.unitPrice) || 0,
          description: '',
        })),
      })
      setLines([{ itemId: '', qty: '1', unitPrice: '' }])
      setDescription('')
      setMessage('پیش‌فاکتور ثبت شد.')
      onCreated()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={FileText} title="ثبت پیش‌فاکتور فروش">
      {warehouses.length === 0 || items.length === 0 ? (
        <p className="hint">قبل از ثبت پیش‌فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا انبار و کالاها در دسترس باشند.</p>
      ) : (
        <form className="invoice-form" onSubmit={handleSubmit}>
          <label>
            انبار
            <select value={effectiveWarehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ پیشنهاد
            <JalaliDatePicker value={quotationDate} onChange={setQuotationDate} />
          </label>
          <label>
            اعتبار تا
            <JalaliDatePicker value={validUntil} onChange={setValidUntil} placeholder="بدون محدودیت" />
          </label>
          <label>
            توضیحات
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          <table className="invoice-lines">
            <thead>
              <tr>
                <th>کالا</th>
                <th>تعداد</th>
                <th>قیمت واحد</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i}>
                  <td>
                    <select value={line.itemId} onChange={(e) => updateLine(i, { itemId: e.target.value })}>
                      <option value="">— انتخاب کالا —</option>
                      {items.map((it) => (
                        <option key={it.id} value={it.id}>
                          {it.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={line.qty}
                      onChange={(e) => updateLine(i, { qty: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      value={line.unitPrice}
                      onChange={(e) => updateLine(i, { unitPrice: e.target.value })}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn-danger"
                      onClick={() => removeLine(i)}
                      disabled={lines.length === 1}
                      aria-label="حذف ردیف"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <span className="invoice-total">جمع کل: {total.toLocaleString('fa-IR')}</span>
            <button type="submit" className="btn-primary">
              <Save size={14} /> ثبت پیش‌فاکتور
            </button>
          </div>

          {message && <div className="hint">{message}</div>}
        </form>
      )}
    </SectionCard>
  )
}
