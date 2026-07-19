import { useRef, useState } from 'react'
import { ShoppingCart, Plus, Trash2, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { createSalesInvoiceDirect, newIdempotencyKey } from '../api'
import { isElectron } from '../platform'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

interface DraftLine {
  itemId: string
  qty: string
  unitPrice: string
}

export function SalesInvoiceForm({
  token,
  warehouses,
  items,
  onQueued,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onQueued: () => void
}) {
  const [warehouseId, setWarehouseId] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(todayIso())
  const [lines, setLines] = useState<DraftLine[]>([{ itemId: '', qty: '1', unitPrice: '' }])
  const [message, setMessage] = useState<string | null>(null)
  // کلید یکتاسازی به *این فاکتور* گره می‌خورد، نه به هر تلاش شبکه‌ای.
  //
  // اگر ثبت با خطا برگردد و کاربر دوباره دکمه را بزند، همان کلید می‌رود — چون
  // ممکن است سرور نوبت اول کارش را کرده باشد و فقط پاسخ گم شده باشد. کلید تازه
  // در آن حالت یعنی فاکتور دوم. کلید فقط بعد از موفقیت قطعی نو می‌شود.
  const idempotencyKey = useRef(newIdempotencyKey())

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

    const payload = {
      invoice_date: invoiceDate,
      warehouse_id: effectiveWarehouseId,
      lines: validLines.map((l) => ({
        item_id: l.itemId,
        qty: Number(l.qty),
        unit_price: Number(l.unitPrice) || 0,
      })),
    }

    try {
      if (isElectron) {
        await window.cubita.queueSalesInvoice(payload)
        setMessage('فاکتور در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createSalesInvoiceDirect(token, payload, idempotencyKey.current)
        setMessage('فاکتور با موفقیت ثبت شد.')
      }
      idempotencyKey.current = newIdempotencyKey() // فاکتور بعدی، کلید تازه
      setLines([{ itemId: '', qty: '1', unitPrice: '' }])
      onQueued()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={ShoppingCart} title="ثبت فاکتور فروش">
      {warehouses.length === 0 || items.length === 0 ? (
        <p className="hint">قبل از ثبت فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا انبار و کالاها در دسترس باشند.</p>
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
            تاریخ فاکتور
            <JalaliDatePicker value={invoiceDate} onChange={setInvoiceDate} />
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
            <button type="submit" className="btn-primary"><Save size={14} /> ثبت فاکتور</button>
          </div>

          {message && <div className="hint">{message}</div>}
        </form>
      )}
    </SectionCard>
  )
}
