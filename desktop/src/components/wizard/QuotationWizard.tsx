import { useState } from 'react'
import { Plus, Trash2, Store } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../../electron.d'
import type { SalesQuotationRecord } from '../../api'
import { useQuotationDraft, type QuotationDraft } from '../../lib/quotationDraft'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { ItemPicker } from '../ItemPicker'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** ویزاردِ «ثبت/ویرایشِ پیش‌فاکتور» برای نسخه‌ی جدید. همان منطقِ فرمِ کلاسیک
 *  ([useQuotationDraft]) در سه مرحله‌ی تاییدشونده + پیش‌نمایشِ زنده. */
export function QuotationWizard({
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
  const [resetTick, setResetTick] = useState(0)

  if (warehouses.length === 0 || items.length === 0) {
    return (
      <section className="taskflow">
        <h2 className="taskflow-title">ثبت پیش‌فاکتور فروش</h2>
        <p className="hint">قبل از ثبت پیش‌فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا انبار و کالاها در دسترس باشند.</p>
      </section>
    )
  }

  const steps: WizardStep[] = [
    {
      key: 'header',
      title: 'مشتری و سربرگ',
      subtitle: 'مشتری، انبار و تاریخِ پیشنهاد را مشخص کنید.',
      canAdvance: !!q.effectiveWarehouseId,
      blockHint: 'ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.',
      body: <HeaderStep q={q} warehouses={warehouses} />,
    },
    {
      key: 'lines',
      title: 'اقلام',
      subtitle: 'کالاها، تعداد و قیمتِ پیشنهادی را وارد کنید.',
      canAdvance: q.linesValid,
      blockHint: 'حداقل یک ردیف با کالا و تعداد لازم است.',
      body: <LinesStep q={q} items={items} />,
    },
    {
      key: 'review',
      title: 'بازبینی و ثبت',
      subtitle: 'یک‌بار مرور کنید، بعد ثبت را بزنید.',
      body: <ReviewStep q={q} items={items} warehouses={warehouses} />,
    },
  ]

  return (
    <TaskFlow
      title={editing ? `ویرایشِ پیش‌فاکتور${editing.number != null ? ' شماره ' + editing.number.toLocaleString('fa-IR') : ''}` : 'ثبت پیش‌فاکتور فروش'}
      steps={steps}
      submitLabel={editing ? 'ذخیرهٔ ویرایش' : 'ثبت پیش‌فاکتور'}
      submitting={q.submitting}
      message={q.message}
      resetKey={`${editing?.id ?? 'new'}-${resetTick}`}
      preview={<LivePreview q={q} warehouses={warehouses} />}
      onSubmit={() => {
        void q.submit().then((ok) => {
          if (ok) setResetTick((t) => t + 1)
        })
      }}
    />
  )
}

function HeaderStep({ q, warehouses }: { q: QuotationDraft; warehouses: WarehouseCache[] }) {
  return (
    <div className="invoice-form">
      <div className="field-pair">
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
          {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
        </select>
      </label>
      </div>
      <label>
        تاریخ پیشنهاد
        <JalaliDatePicker value={q.quotationDate} onChange={q.setQuotationDate} />
      </label>
      <label>
        اعتبار تا
        <JalaliDatePicker value={q.validUntil} onChange={q.setValidUntil} placeholder="بدون محدودیت" />
      </label>
      <label className="field-full">
        توضیحات
        <input type="text" value={q.description} onChange={(e) => q.setDescription(e.target.value)} />
      </label>
      <label>
        موجودی
        <div className="seg-toggle">
          <button type="button" className={q.stockMode === 'warehouse' ? 'active' : ''} onClick={() => q.setStockMode('warehouse')}>از موجودی انبار</button>
          <button type="button" className={q.stockMode === 'manual' ? 'active' : ''} onClick={() => q.setStockMode('manual')}>دستی</button>
        </div>
      </label>
    </div>
  )
}

function LinesStep({ q, items }: { q: QuotationDraft; items: ItemCache[] }) {
  return (
    <>
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
      <div>
        <button type="button" onClick={q.addLine}>
          <Plus size={14} /> افزودن ردیف
        </button>
      </div>
    </>
  )
}

function ReviewStep({ q, items, warehouses }: { q: QuotationDraft; items: ItemCache[]; warehouses: WarehouseCache[] }) {
  const customer = q.customerMode === 'list' ? q.contacts.find((c) => c.id === q.contactId)?.name : q.customerName
  const warehouse = warehouses.find((w) => w.id === q.effectiveWarehouseId)
  const validLines = q.lines.filter((l) => l.itemId && Number(l.qty) > 0)
  return (
    <div className="review-step">
      <div className="review-facts">
        <div className="live-preview-row"><span>مشتری</span><strong>{customer || 'بدون مشتری'}</strong></div>
        <div className="live-preview-row"><span>انبار</span><strong>{warehouse?.name ?? '—'}</strong></div>
        <div className="live-preview-row"><span>تاریخ پیشنهاد</span><strong>{q.quotationDate}</strong></div>
        {q.validUntil && <div className="live-preview-row"><span>اعتبار تا</span><strong>{q.validUntil}</strong></div>}
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>کالا</th><th>تعداد</th><th>قیمت واحد</th><th>مبلغ</th></tr>
          </thead>
          <tbody>
            {validLines.map((line, i) => {
              const it = items.find((x) => x.id === line.itemId)
              const amount = (Number(line.qty) || 0) * (Number(line.unitPrice) || 0)
              return (
                <tr key={i}>
                  <td>{it?.name ?? '—'}</td>
                  <td>{Number(line.qty).toLocaleString('fa-IR')} {it?.unit ?? ''}</td>
                  <td>{Number(line.unitPrice || 0).toLocaleString('fa-IR')}</td>
                  <td>{amount.toLocaleString('fa-IR')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LivePreview({ q, warehouses }: { q: QuotationDraft; warehouses: WarehouseCache[] }) {
  const customer = q.customerMode === 'list' ? q.contacts.find((c) => c.id === q.contactId)?.name : q.customerName
  const warehouse = warehouses.find((w) => w.id === q.effectiveWarehouseId)
  const lineCount = q.lines.filter((l) => l.itemId && Number(l.qty) > 0).length
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ پیش‌فاکتور</p>
      <div className="live-preview-row"><span>مشتری</span><strong>{customer || 'بدون مشتری'}</strong></div>
      <div className="live-preview-row"><span>انبار</span><strong>{warehouse?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>تاریخ</span><strong>{q.quotationDate}</strong></div>
      {q.validUntil && <div className="live-preview-row"><span>اعتبار تا</span><strong>{q.validUntil}</strong></div>}
      <div className="live-preview-row"><span>تعداد اقلام</span><strong>{lineCount.toLocaleString('fa-IR')}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>جمع کل</span><strong>{fa(q.total)}</strong></div>
    </div>
  )
}
