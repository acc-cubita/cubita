import { useEffect, useMemo, useState } from 'react'
import { CalendarClock, PackagePlus, Trash2, AlertTriangle, ScanBarcode } from 'lucide-react'
import {
  createStockBatch,
  deleteStockBatch,
  fetchBatchReconciliation,
  fetchItemsLive,
  fetchStockBatches,
  fetchWarehousesLive,
  type BatchReconciliationRow,
  type ItemRecord,
  type StockBatchRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { JalaliDatePicker } from './JalaliDatePicker'
import { BatchDetailDrawer } from './BatchDetailDrawer'
import { formatJalali, todayIso } from '../lib/jalali'
import { SearchSelect } from '../components/SearchSelect'

//: چرا مانده‌ی این بار از دفتر درنمی‌آید. عمداً می‌گوید «چه کار کنم»، نه فقط «خطا».
const REASON_LABEL: Record<string, string> = {
  manual: 'بارِ دستی است و حرکتِ انباری ندارد — عدد از ثبتِ خودتان می‌آید.',
  ambiguous: 'سندِ ورودش بیش از یک ردیفِ این کالا داشت، پس انتساب خودکار انجام نشد.',
  pre_tracking: 'پیش از ردیابیِ بچ ثبت شده؛ خروج‌هایش بار نداشته‌اند.',
}

//: واژگانِ §۳ — همه **محاسبه‌شده** سمتِ سرور، نه ستونِ ذخیره‌شده.
const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  draft: { label: 'پیش‌نویس', tone: 'tone-muted' },
  qc_pending: { label: 'در انتظارِ کنترل', tone: 'tone-warning' },
  available: { label: 'قابلِ فروش', tone: 'tone-success' },
  partially_reserved: { label: 'بخشی رزرو', tone: 'tone-warning' },
  fully_reserved: { label: 'کاملاً رزرو', tone: 'tone-warning' },
  near_expiry: { label: 'نزدیکِ انقضا', tone: 'tone-warning' },
  blocked: { label: 'مسدود', tone: 'tone-danger' },
  recalled: { label: 'فراخوان‌شده', tone: 'tone-danger' },
  expired: { label: 'منقضی', tone: 'tone-danger' },
  depleted: { label: 'تمام‌شده', tone: 'tone-muted' },
  closed: { label: 'بسته', tone: 'tone-muted' },
}

const SOURCE_LABEL: Record<string, { label: string; tone: string }> = {
  purchase_invoice: { label: 'خرید', tone: 'tone-success' },
  marketplace: { label: 'بازار', tone: 'tone-success' },
  manual: { label: 'دستی', tone: 'tone-muted' },
}

const fa = (n: number) => n.toLocaleString('fa-IR')

function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  const ms = new Date(iso).getTime() - Date.now()
  return Math.ceil(ms / 86_400_000)
}

export function BatchesPanel({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [batches, setBatches] = useState<StockBatchRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [detail, setDetail] = useState<StockBatchRecord | null>(null)
  const [recon, setRecon] = useState<BatchReconciliationRow[]>([])
  const [onlyMismatch, setOnlyMismatch] = useState(false)

  const reconById = useMemo(() => new Map(recon.map((r) => [r.batch_id, r])), [recon])
  //: صفحه‌بندی روی فهرستِ **فیلترشده** می‌نشیند، وگرنه فیلتر فقط صفحه‌ی جاری را
  //: می‌تراشد و کاربر فکر می‌کند مغایرتی نمانده.
  const shown = useMemo(
    () => (onlyMismatch ? batches.filter((b) => reconById.has(b.id)) : batches),
    [batches, onlyMismatch, reconById],
  )
  const pg = usePagination(shown, 10)

  const [itemId, setItemId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [batchNumber, setBatchNumber] = useState('')
  const [expiry, setExpiry] = useState('')
  const [production, setProduction] = useState('')
  const [qty, setQty] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [consumerPrice, setConsumerPrice] = useState('')
  const [received, setReceived] = useState(todayIso())

  async function refresh() {
    setError(null)
    try {
      const [its, ws, bs, rc] = await Promise.all([
        fetchItemsLive(token),
        fetchWarehousesLive(token),
        fetchStockBatches(token),
        fetchBatchReconciliation(token),
      ])
      setItems(its.filter((i) => !i.is_service && i.is_active))
      setWarehouses(ws)
      if (ws[0] && !warehouseId) setWarehouseId(ws[0].id)
      setBatches(bs)
      setRecon(rc)
      // اگر درایورِ جزئیات باز است، همان بار را تازه نگه دار (مقدار/معیوب به‌روز شود)
      setDetail((cur) => (cur ? bs.find((b) => b.id === cur.id) ?? null : null))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const itemById = useMemo(() => new Map(items.map((i) => [i.id, i])), [items])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!itemId || !warehouseId || !batchNumber.trim()) {
      setMsg('کالا، انبار و شماره‌ی بچ الزامی است.')
      return
    }
    try {
      await createStockBatch(token, {
        item_id: itemId,
        warehouse_id: warehouseId,
        batch_number: batchNumber.trim(),
        expiry_date: expiry || null,
        production_date: production || null,
        qty: Number(qty) || 0,
        unit_cost: Number(unitCost) || 0,
        consumer_price: Number(consumerPrice) || 0,
        received_date: received,
      })
      setBatchNumber('')
      setExpiry('')
      setProduction('')
      setQty('')
      setUnitCost('')
      setConsumerPrice('')
      setMsg('بار ثبت شد.')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function remove(id: string) {
    await deleteStockBatch(token, id)
    await refresh()
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={PackagePlus} title="ثبتِ بارِ دستی" description="معمولاً بارها با فاکتورِ خرید خودکار ساخته می‌شوند؛ این فرم برای بارِ دستی (مثلاً موجودیِ اول دوره) است.">
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            کالا
            <SearchSelect value={itemId} onChange={(e) => setItemId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {items.map((i) => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </SearchSelect>
          </label>
          <div className="field-row">
            <label>
              انبار
              <SearchSelect value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </SearchSelect>
            </label>
            <label>
              شماره‌ی بچ/سری
              <input type="text" value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} placeholder="مثلاً L-1403-05" />
            </label>
          </div>
          <div className="field-row">
            <label>
              تعداد
              <NumberInput allowDecimal value={qty} onChange={setQty} />
            </label>
            <label>
              قیمتِ خرید (واحد)
              <NumberInput value={unitCost} onChange={setUnitCost} placeholder="۰" />
            </label>
          </div>
          <div className="field-row">
            <label>
              قیمتِ مصرف‌کننده
              <NumberInput value={consumerPrice} onChange={setConsumerPrice} placeholder="برای حاشیه‌ی سود" />
            </label>
            {(() => {
              const buy = Number(unitCost) || 0, sell = Number(consumerPrice) || 0
              if (buy > 0 && sell > buy) {
                const pct = ((sell - buy) / sell) * 100
                return <div className="hint" style={{ alignSelf: 'end' }}>سود: {fa(sell - buy)} ({pct.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)</div>
              }
              return <div />
            })()}
          </div>
          <div className="field-row">
            <label>
              تاریخِ تولید
              <JalaliDatePicker value={production || todayIso()} onChange={setProduction} />
            </label>
            <label>
              تاریخِ انقضا
              <JalaliDatePicker value={expiry || todayIso()} onChange={setExpiry} />
            </label>
          </div>
          <label>
            تاریخِ ورود
            <JalaliDatePicker value={received} onChange={setReceived} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><PackagePlus size={14} /> ثبتِ بچ</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard
        icon={CalendarClock}
        title="بارهای ورودی (بچ)"
        description={`${fa(batches.length)} بار — هر خرید خودکار یک بار می‌سازد. روی «مدیریت» بزنید تا سریالِ کارتن اضافه یا کسری/معیوب ثبت کنید.`}
      >
        {error && <div className="error">{error}</div>}
        {/*
          گزارش است، نه گارد: هیچ‌کدامِ این ردیف‌ها جلوی کاری را نمی‌گیرند. فقط
          می‌گویند عددِ کدام بار هنوز از ستونِ قدیمی می‌آید — و بارهای تازه از
          همان اول از دفتر مشتق می‌شوند، پس این فهرست کوتاه و کوتاه‌تر می‌شود.
        */}
        {recon.length > 0 && (
          <section className="fy-note">
            <AlertTriangle size={14} />
            <span>
              مانده‌ی {fa(recon.length)} بار از دفترِ انبار محاسبه نشده و تخمینی است — این‌ها پیش از
              ردیابیِ بچ ثبت شده‌اند یا حرکتِ انباری ندارند.
            </span>
            <button type="button" onClick={() => setOnlyMismatch((v) => !v)}>
              {onlyMismatch ? 'نمایشِ همه' : 'فقط همین‌ها'}
            </button>
          </section>
        )}
        {shown.length === 0 ? (
          <EmptyState
            icon={CalendarClock}
            text={
              onlyMismatch
                ? 'هیچ بارِ تخمینی‌ای نمانده — مانده‌ی همه‌ی بارها از دفتر محاسبه می‌شود.'
                : 'باری ثبت نشده — با ثبتِ فاکتورِ خرید خودکار ساخته می‌شود.'
            }
          />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr><th>کالا</th><th>بار</th><th>منشأ</th><th>وضعیت</th><th>ورودی</th><th>مانده</th><th>قابلِ فروش</th><th>کسری</th><th>سریال</th><th>انقضا</th><th></th></tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((b) => {
                    const d = daysUntil(b.expiry_date)
                    const soon = d !== null && d <= 30
                    const expired = d !== null && d < 0
                    const src = SOURCE_LABEL[b.source_type] ?? SOURCE_LABEL.manual
                    const defect = Number(b.defect_qty)
                    const mismatch = reconById.get(b.id)
                    const st = STATUS_LABEL[b.status] ?? STATUS_LABEL.available
                    return (
                      <tr key={b.id}>
                        <td className="entity-name card-title" data-label="کالا">{itemById.get(b.item_id)?.name ?? '—'}</td>
                        <td className="ltr-cell" data-label="بار">{b.batch_number}</td>
                        <td data-label="منشأ"><span className={`status-badge ${src.tone}`}>{src.label}</span></td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${st.tone}`}>{st.label}</span>
                        </td>
                        <td className="num" data-label="ورودی">{fa(Number(b.received_qty))}</td>
                        <td className="num" data-label="مانده">
                          <strong>{fa(Number(b.qty))}</strong>
                          {/* عددِ نامطمئن نباید مثلِ عددِ دقیق دیده شود. */}
                          {b.qty_source === 'legacy' && (
                            <span
                              className="status-badge tone-warning"
                              title={REASON_LABEL[mismatch?.reason ?? ''] ?? 'مانده از دفترِ انبار محاسبه نشده است.'}
                            >
                              <AlertTriangle size={12} /> تخمینی
                            </span>
                          )}
                        </td>
                        <td className="num" data-label="قابلِ فروش">
                          {/* §۲۹ — «قابلِ فروش» با «موجودی» یکی نیست: بارِ نزدیک به انقضا
                              موجودی دارد ولی فروختنی نیست. جدا نشان داده می‌شود. */}
                          {Number(b.sellable_qty) < Number(b.qty)
                            ? <strong className="stock-over">{fa(Number(b.sellable_qty))}</strong>
                            : fa(Number(b.sellable_qty))}
                        </td>
                        <td data-label="کسری" className={defect > 0 ? 'stock-over' : undefined}>{defect > 0 ? fa(defect) : '—'}</td>
                        <td data-label="سریال">{b.serial_count > 0 ? fa(b.serial_count) : '—'}</td>
                        <td data-label="انقضا">
                          {b.expiry_date ? (
                            <span className={`status-badge ${expired ? 'tone-danger' : soon ? 'tone-warning' : 'tone-success'}`}>
                              {(expired || soon) && <AlertTriangle size={12} />}
                              {formatJalali(b.expiry_date)}
                              {d !== null && (expired ? ' (منقضی)' : soon ? ` (${fa(d)} روز)` : '')}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="card-actions">
                          <div className="check-actions">
                            <button type="button" onClick={() => setDetail(b)}><ScanBarcode size={13} /> مدیریت</button>
                            <button type="button" className="icon-btn-danger" onClick={() => void remove(b.id)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>

      {detail && (
        <BatchDetailDrawer
          token={token}
          batch={detail}
          itemName={itemById.get(detail.item_id)?.name ?? '—'}
          onClose={() => setDetail(null)}
          onChanged={() => void refresh()}
        />
      )}
    </div>
  )
}
