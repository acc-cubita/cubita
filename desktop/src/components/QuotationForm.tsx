import { FileText, Plus, Trash2, Save, Store } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import type { SalesQuotationRecord } from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ItemPicker } from './ItemPicker'
import { useQuotationDraft } from '../lib/quotationDraft'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** فرمِ کلاسیکِ «ثبت/ویرایشِ پیش‌فاکتور» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [useQuotationDraft] است تا با ویزاردِ نسخه‌ی جدید یک‌دست بماند. */
export function QuotationForm({
  token,
  warehouses,
  items,
  onCreated,
  editing = null,
  onDoneEditing,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onCreated: () => void
  editing?: SalesQuotationRecord | null
  onDoneEditing?: () => void
}) {
  const q = useQuotationDraft({ token, warehouses, items, onCreated, editing, onDoneEditing })

  return (
    <SectionCard
      icon={FileText}
      title={editing ? `ویرایشِ پیش‌فاکتور${editing.number != null ? ' شماره ' + editing.number.toLocaleString('fa-IR') : ''}` : 'ثبت پیش‌فاکتور فروش'}
    >
      {warehouses.length === 0 || items.length === 0 ? (
        <p className="hint">قبل از ثبت پیش‌فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا انبار و کالاها در دسترس باشند.</p>
      ) : (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void q.submit()
          }}
        >
          {/* ── مشتری: از فهرست یا دستی ── */}
          <label>
            مشتری
            <div className="seg-toggle">
              <button type="button" className={q.customerMode === 'list' ? 'active' : ''} onClick={() => q.setCustomerMode('list')}>از فهرست اشخاص</button>
              <button type="button" className={q.customerMode === 'manual' ? 'active' : ''} onClick={() => q.setCustomerMode('manual')}>دستی</button>
            </div>
            {q.customerMode === 'list' ? (
              <select value={q.contactId} onChange={(e) => q.setContactId(e.target.value)}>
                <option value="">— بدون مشتری —</option>
                {q.contacts.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            ) : (
              <input type="text" value={q.customerName} onChange={(e) => q.setCustomerName(e.target.value)} placeholder="نام مشتری را بنویسید" />
            )}
          </label>

          <label>
            انبار
            <select value={q.effectiveWarehouseId} onChange={(e) => q.setWarehouseId(e.target.value)}>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </label>
          <label>
            تاریخ پیشنهاد
            <JalaliDatePicker value={q.quotationDate} onChange={q.setQuotationDate} />
          </label>
          <label>
            اعتبار تا
            <JalaliDatePicker value={q.validUntil} onChange={q.setValidUntil} placeholder="بدون محدودیت" />
          </label>
          <label>
            توضیحات
            <input type="text" value={q.description} onChange={(e) => q.setDescription(e.target.value)} />
          </label>

          {/* ── حالتِ موجودی ── */}
          <label>
            موجودی
            <div className="seg-toggle">
              <button type="button" className={q.stockMode === 'warehouse' ? 'active' : ''} onClick={() => q.setStockMode('warehouse')}>از موجودی انبار</button>
              <button type="button" className={q.stockMode === 'manual' ? 'active' : ''} onClick={() => q.setStockMode('manual')}>دستی</button>
            </div>
          </label>

          <div className="table-scroll">
            <table className="invoice-lines">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>تعداد</th>
                  {q.stockMode === 'warehouse' && <th>موجودی انبار</th>}
                  <th>قیمت واحد</th>
                  <th>مبلغ</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {q.lines.map((line, i) => {
                  const service = q.isService(line.itemId)
                  const avail = q.stockMode === 'warehouse' && !service ? q.availableStock(line.itemId) : null
                  const over = avail != null && Number(line.qty) > avail
                  return (
                    <tr key={i}>
                      <td data-label="کالا">
                        <ItemPicker items={items} value={line.itemId} onChange={(id) => q.chooseLineItem(i, id)} />
                      </td>
                      <td data-label="تعداد">
                        <div className="qty-with-unit">
                          <NumberInput allowDecimal value={line.qty} onChange={(v) => q.updateLine(i, { qty: v })} />
                          {line.itemId && <span className="unit-suffix">{q.unitOf(line.itemId)}</span>}
                        </div>
                      </td>
                      {q.stockMode === 'warehouse' && (
                        <td data-label="موجودی انبار">
                          {!line.itemId ? '—' : service ? (
                            <span className="unit-suffix">خدمات (بدون موجودی)</span>
                          ) : (
                            <div className="stock-cell">
                              <span className={over ? 'stock-over' : 'stock-ok'}>{avail != null ? fa(avail) : '—'} {q.unitOf(line.itemId)}</span>
                              {avail != null && avail > 0 && (
                                <button type="button" className="link-like" onClick={() => q.updateLine(i, { qty: String(avail) })}>استفاده</button>
                              )}
                              {over && <div className="stock-warn">بیش از موجودی</div>}
                            </div>
                          )}
                        </td>
                      )}
                      <td data-label="قیمت واحد">
                        <div className="qty-with-unit">
                          <NumberInput
                            value={line.unitPrice}
                            onChange={(v) => q.updateLine(i, { unitPrice: v })}
                            title={line.itemId ? `قیمت هر ${q.unitOf(line.itemId)}` : 'قیمت واحد'}
                          />
                          {line.itemId && (
                            <button type="button" className="link-like" title="قیمتِ انبار" onClick={() => q.useInventoryPrice(i, line.itemId)}>
                              <Store size={12} />
                            </button>
                          )}
                        </div>
                      </td>
                      <td data-label="مبلغ">
                        <span className={`line-amount${line.itemId ? '' : ' muted'}`}>
                          {line.itemId ? ((Number(line.qty) || 0) * (Number(line.unitPrice) || 0)).toLocaleString('fa-IR') : '—'}
                        </span>
                      </td>
                      <td>
                        <button type="button" className="icon-btn-danger" onClick={() => q.removeLine(i)} disabled={q.lines.length === 1} aria-label="حذف ردیف">
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
            <button type="button" onClick={q.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <span className="invoice-total">جمع کل: {fa(q.total)} ریال</span>
            {editing && (
              <button type="button" onClick={() => { q.resetForm(); q.setMessage(null); onDoneEditing?.() }}>
                انصراف از ویرایش
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={q.submitting}>
              <Save size={14} /> {editing ? 'ذخیرهٔ ویرایش' : 'ثبت پیش‌فاکتور'}
            </button>
          </div>

          {q.message && <div className="hint">{q.message}</div>}
        </form>
      )}
    </SectionCard>
  )
}
