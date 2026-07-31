import { useEffect, useState } from 'react'
import { FileText, Plus, Trash2, Save, Store } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { createSalesQuotation, fetchContacts, fetchStockLevels, type ContactRecord, type StockLevel } from '../api'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

interface DraftLine {
  itemId: string
  qty: string
  unitPrice: string
}

const fa = (n: number) => n.toLocaleString('fa-IR')

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

  // مشتری: از فهرستِ اشخاص یا دستی
  const [customerMode, setCustomerMode] = useState<'list' | 'manual'>('list')
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = useState('')
  const [customerName, setCustomerName] = useState('')

  // موجودی: خواندن از انبار یا دستی
  const [stockMode, setStockMode] = useState<'warehouse' | 'manual'>('warehouse')
  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  // مشتری‌ها زنده خوانده می‌شوند؛ آفلاین که نشد، فهرست خالی و کاربر می‌تواند دستی وارد کند.
  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.type !== 'supplier')))
      .catch(() => setContacts([]))
  }, [token])

  // موجودیِ انبار زنده خوانده می‌شود؛ آفلاین که نشد، حالتِ «از انبار» چیزی نشان نمی‌دهد.
  useEffect(() => {
    fetchStockLevels(token)
      .then(setStockLevels)
      .catch(() => setStockLevels([]))
  }, [token])

  function unitOf(itemId: string): string {
    return items.find((it) => it.id === itemId)?.unit || ''
  }

  // موجودیِ در دسترسِ یک کالا در انبارِ انتخاب‌شده.
  function availableStock(itemId: string): number | null {
    if (!itemId || !effectiveWarehouseId) return null
    const row = stockLevels.find((s) => s.item_id === itemId && s.warehouse_id === effectiveWarehouseId)
    return row ? Number(row.qty) : 0
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  // انتخابِ کالا: قیمتِ واحد خودکار از قیمتِ فروشِ همان کالا در انبار پر می‌شود (قابلِ ویرایش).
  function chooseLineItem(index: number, itemId: string) {
    if (!itemId) {
      updateLine(index, { itemId: '', unitPrice: '' })
      return
    }
    const it = items.find((x) => x.id === itemId)
    const price = it ? Number(it.sales_price) : 0
    updateLine(index, { itemId, unitPrice: price ? String(price) : '' })
  }

  // بازگرداندنِ قیمت به قیمتِ انبار (دکمه‌ی کنارِ قیمت).
  function useInventoryPrice(index: number, itemId: string) {
    const it = items.find((x) => x.id === itemId)
    if (it) updateLine(index, { unitPrice: String(Number(it.sales_price)) })
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
        contact_id: customerMode === 'list' ? (contactId || null) : null,
        customer_name: customerMode === 'manual' ? (customerName.trim() || null) : null,
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
      setContactId('')
      setCustomerName('')
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
          {/* ── مشتری: از فهرست یا دستی ── */}
          <label>
            مشتری
            <div className="seg-toggle">
              <button type="button" className={customerMode === 'list' ? 'active' : ''} onClick={() => setCustomerMode('list')}>از فهرست اشخاص</button>
              <button type="button" className={customerMode === 'manual' ? 'active' : ''} onClick={() => setCustomerMode('manual')}>دستی</button>
            </div>
            {customerMode === 'list' ? (
              <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
                <option value="">— بدون مشتری —</option>
                {contacts.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            ) : (
              <input type="text" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="نام مشتری را بنویسید" />
            )}
          </label>

          <label>
            انبار
            <select value={effectiveWarehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
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

          {/* ── حالتِ موجودی ── */}
          <label>
            موجودی
            <div className="seg-toggle">
              <button type="button" className={stockMode === 'warehouse' ? 'active' : ''} onClick={() => setStockMode('warehouse')}>از موجودی انبار</button>
              <button type="button" className={stockMode === 'manual' ? 'active' : ''} onClick={() => setStockMode('manual')}>دستی</button>
            </div>
          </label>

          <div className="table-scroll">
          <table className="invoice-lines">
            <thead>
              <tr>
                <th>کالا</th>
                <th>تعداد</th>
                {stockMode === 'warehouse' && <th>موجودی انبار</th>}
                <th>قیمت واحد</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => {
                const avail = stockMode === 'warehouse' ? availableStock(line.itemId) : null
                const over = avail != null && Number(line.qty) > avail
                return (
                  <tr key={i}>
                    <td>
                      <select value={line.itemId} onChange={(e) => chooseLineItem(i, e.target.value)}>
                        <option value="">— انتخاب کالا —</option>
                        {items.map((it) => (<option key={it.id} value={it.id}>{it.name}</option>))}
                      </select>
                    </td>
                    <td>
                      <div className="qty-with-unit">
                        <input type="number" min="0" step="any" value={line.qty} onChange={(e) => updateLine(i, { qty: e.target.value })} />
                        {line.itemId && <span className="unit-suffix">{unitOf(line.itemId)}</span>}
                      </div>
                    </td>
                    {stockMode === 'warehouse' && (
                      <td>
                        {line.itemId ? (
                          <div className="stock-cell">
                            <span className={over ? 'stock-over' : 'stock-ok'}>{avail != null ? fa(avail) : '—'} {unitOf(line.itemId)}</span>
                            {avail != null && avail > 0 && (
                              <button type="button" className="link-like" onClick={() => updateLine(i, { qty: String(avail) })}>استفاده</button>
                            )}
                            {over && <div className="stock-warn">بیش از موجودی</div>}
                          </div>
                        ) : '—'}
                      </td>
                    )}
                    <td>
                      <div className="qty-with-unit">
                        <input
                          type="number"
                          min="0"
                          value={line.unitPrice}
                          onChange={(e) => updateLine(i, { unitPrice: e.target.value })}
                          title={line.itemId ? `قیمت هر ${unitOf(line.itemId)}` : 'قیمت واحد'}
                        />
                        {line.itemId && (
                          <button type="button" className="link-like" title="قیمتِ انبار" onClick={() => useInventoryPrice(i, line.itemId)}>
                            <Store size={12} />
                          </button>
                        )}
                      </div>
                    </td>
                    <td>
                      <button type="button" className="icon-btn-danger" onClick={() => removeLine(i)} disabled={lines.length === 1} aria-label="حذف ردیف">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <span className="invoice-total">جمع کل: {fa(total)} ریال</span>
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
