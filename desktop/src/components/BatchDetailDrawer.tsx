import { useEffect, useState } from 'react'
import { X, Boxes, ScanBarcode, AlertTriangle, Trash2, Plus, Wand2, ShieldAlert, ShieldCheck, Route } from 'lucide-react'
import {
  addBatchSerials,
  adjustBatch,
  closeBatch,
  deleteBatchSerial,
  fetchBatchSerials,
  fetchBatchTrace,
  holdBatch,
  releaseBatchHold,
  setBatchSerialStatus,
  type BatchSerialRecord,
  type BatchTrace,
  type StockBatchRecord,
} from '../api'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'
import { SearchSelect } from '../components/SearchSelect'

const fa = (n: number | string) => Number(n).toLocaleString('fa-IR')

const REASONS: { key: 'defect' | 'shortage' | 'wastage'; label: string }[] = [
  { key: 'defect', label: 'معیوب' },
  { key: 'shortage', label: 'کسری' },
  { key: 'wastage', label: 'ضایعات' },
]

/**
 * جزئیاتِ یک بارِ ورودی: مدیریتِ سریالِ کارتن (دستی یا توالیِ خودکار) و ثبتِ
 * کسری/معیوب/ضایعات (که از موجودی و حسابداری کم می‌شود). با هر تغییر، `onChanged`
 * صدا می‌شود تا فهرستِ بارها تازه شود.
 */
export function BatchDetailDrawer({
  token,
  batch,
  itemName,
  onClose,
  onChanged,
}: {
  token: string
  batch: StockBatchRecord
  itemName: string
  onClose: () => void
  onChanged: () => void
}) {
  const [serials, setSerials] = useState<BatchSerialRecord[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // افزودنِ سریال — دو حالت
  const [mode, setMode] = useState<'manual' | 'sequence'>('manual')
  const [manualText, setManualText] = useState('')
  const [prefix, setPrefix] = useState('')
  const [start, setStart] = useState('')
  const [count, setCount] = useState('')
  const [pad, setPad] = useState('0')

  // تعدیلِ کسری/معیوب/ضایعات
  const [adjQty, setAdjQty] = useState('')
  const [adjReason, setAdjReason] = useState<'defect' | 'shortage' | 'wastage'>('defect')
  const [adjNotes, setAdjNotes] = useState('')
  const [adjDate, setAdjDate] = useState(todayIso())

  // انسداد/فراخوان و ردیابی (§۱۵ §۱۶)
  const [holdKind, setHoldKind] = useState<'blocked' | 'recalled'>('blocked')
  const [holdReason, setHoldReason] = useState('')
  const [trace, setTrace] = useState<BatchTrace | null>(null)

  async function loadSerials() {
    try {
      setSerials(await fetchBatchSerials(token, batch.id))
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }
  async function loadTrace() {
    try {
      setTrace(await fetchBatchTrace(token, batch.id))
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }
  useEffect(() => {
    void loadSerials()
    void loadTrace()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch.id])

  async function submitHold() {
    setMsg(null)
    setBusy(true)
    try {
      await holdBatch(token, batch.id, { hold_status: holdKind, reason: holdReason.trim() })
      setHoldReason('')
      onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function submitRelease() {
    setMsg(null)
    setBusy(true)
    try {
      await releaseBatchHold(token, batch.id)
      onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function submitClose() {
    setMsg(null)
    setBusy(true)
    try {
      await closeBatch(token, batch.id, !batch.is_closed)
      onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function addSerials() {
    setMsg(null)
    setBusy(true)
    try {
      if (mode === 'manual') {
        const list = manualText.split(/[\n,،]+/).map((s) => s.trim()).filter(Boolean)
        if (list.length === 0) { setMsg('حداقل یک سریال وارد کنید.'); setBusy(false); return }
        await addBatchSerials(token, batch.id, { serials: list })
        setManualText('')
      } else {
        const s = Number(start), c = Number(count)
        if (!c || c <= 0) { setMsg('تعدادِ توالی را وارد کنید.'); setBusy(false); return }
        await addBatchSerials(token, batch.id, { prefix, start: s || 0, count: c, pad: Number(pad) || 0 })
      }
      await loadSerials()
      onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function toggleStatus(s: BatchSerialRecord) {
    try {
      await setBatchSerialStatus(token, s.id, s.status === 'defect' ? 'ok' : 'defect')
      await loadSerials()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function removeSerial(id: string) {
    try {
      await deleteBatchSerial(token, id)
      await loadSerials()
      onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function submitAdjust() {
    setMsg(null)
    const q = Number(adjQty)
    if (!q || q <= 0) { setMsg('مقدار را وارد کنید.'); return }
    setBusy(true)
    try {
      await adjustBatch(token, batch.id, { qty: q, reason: adjReason, notes: adjNotes.trim() || undefined, adjustment_date: adjDate })
      setAdjQty('')
      setAdjNotes('')
      setMsg(`${REASONS.find((r) => r.key === adjReason)!.label} ثبت شد و از موجودی کم شد.`)
      onChanged()
      onClose()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  const defectSerials = serials.filter((s) => s.status === 'defect').length

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <div className="drawer-title-main">{itemName}</div>
            <div className="drawer-title-sub ltr-cell">بارِ «{batch.batch_number}»</div>
          </div>
          <div className="drawer-head-actions">
            <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
          </div>
        </div>

        <div className="drawer-body">
          {msg && <div className="hint">{msg}</div>}

          {/* خلاصه‌ی بار */}
          <div className="batch-summary">
            <div><span>ورودی</span><strong>{fa(batch.received_qty)}</strong></div>
            <div><span>باقی‌مانده</span><strong>{fa(batch.qty)}</strong></div>
            {/*
              §۴ — چهار عددِ جدا. «رزرو» و «قابلِ فروش» فقط وقتی نشان داده
              می‌شوند که واقعاً چیزی بگویند: انبارِ بی‌رزرو و بارِ سالم نباید
              دو خانه‌ی صفر ببیند و فکر کند چیزی از دستش رفته.
            */}
            {Number(batch.reserved_qty) > 0 && (
              <div><span>رزروشده</span><strong>{fa(batch.reserved_qty)}</strong></div>
            )}
            {Number(batch.sellable_qty) !== Number(batch.qty) && (
              <div>
                <span>قابلِ فروش</span>
                <strong className={Number(batch.sellable_qty) === 0 ? 'stock-over' : ''}>
                  {fa(batch.sellable_qty)}
                </strong>
              </div>
            )}
            <div className={Number(batch.defect_qty) > 0 ? 'batch-defect' : ''}><span>کسری/معیوب</span><strong>{fa(batch.defect_qty)}</strong></div>
            <div><span>قیمتِ خرید</span><strong>{fa(batch.unit_cost)}</strong></div>
            {Number(batch.consumer_price) > 0 && <div><span>قیمتِ مصرف</span><strong>{fa(batch.consumer_price)}</strong></div>}
            {Number(batch.consumer_price) > Number(batch.unit_cost) && Number(batch.unit_cost) > 0 && (
              <div>
                <span>حاشیه‌ی سود</span>
                <strong className="stock-ok">
                  {fa(Number(batch.consumer_price) - Number(batch.unit_cost))}
                  {' '}({(((Number(batch.consumer_price) - Number(batch.unit_cost)) / Number(batch.consumer_price)) * 100).toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)
                </strong>
              </div>
            )}
          </div>

          {/* سریالِ کارتن */}
          <section className="drawer-section">
            <h4><ScanBarcode size={15} /> سریالِ کارتن ({fa(serials.length)}{defectSerials > 0 ? ` — ${fa(defectSerials)} معیوب` : ''})</h4>
            <div className="seg-toggle">
              <button type="button" className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>دستی</button>
              <button type="button" className={mode === 'sequence' ? 'active' : ''} onClick={() => setMode('sequence')}>توالیِ خودکار</button>
            </div>

            {mode === 'manual' ? (
              <label className="batch-serial-input">
                سریال‌ها (هر خط یا با کاما جدا)
                <textarea value={manualText} onChange={(e) => setManualText(e.target.value)} rows={3} placeholder={'CTN-1001\nCTN-1002'} />
              </label>
            ) : (
              <div className="field-row batch-seq">
                <label>پیشوند<input type="text" value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="CTN-" /></label>
                <label>از شماره<NumberInput value={start} onChange={setStart} placeholder="۱" /></label>
                <label>تعداد<NumberInput value={count} onChange={setCount} placeholder="۵۰" /></label>
                <label>صفرِ چپ<NumberInput value={pad} onChange={setPad} placeholder="۳" /></label>
              </div>
            )}
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void addSerials()}>
              {mode === 'manual' ? <><Plus size={14} /> افزودن</> : <><Wand2 size={14} /> ساختِ توالی</>}
            </button>

            {serials.length > 0 && (
              <div className="batch-serial-list">
                {serials.map((s) => (
                  <div key={s.id} className={`batch-serial-chip${s.status === 'defect' ? ' defect' : ''}`}>
                    <span className="ltr-cell">{s.serial}</span>
                    <button type="button" title={s.status === 'defect' ? 'سالم' : 'معیوب'} onClick={() => void toggleStatus(s)}>
                      <AlertTriangle size={12} />
                    </button>
                    <button type="button" title="حذف" onClick={() => void removeSerial(s.id)}><Trash2 size={12} /></button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* کسری/معیوب/ضایعات */}
          <section className="drawer-section">
            <h4><AlertTriangle size={15} /> ثبتِ کسری / معیوب / ضایعات</h4>
            <p className="hint">مقدارِ واردشده از باقی‌مانده‌ی این بار و از موجودیِ انبار کم می‌شود و سندِ زیان ثبت می‌گردد.</p>
            <div className="field-row">
              <label>نوع
                <SearchSelect value={adjReason} onChange={(e) => setAdjReason(e.target.value as typeof adjReason)}>
                  {REASONS.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
                </SearchSelect>
              </label>
              <label>مقدار<NumberInput allowDecimal value={adjQty} onChange={setAdjQty} /></label>
            </div>
            <div className="field-row">
              <label>تاریخ<JalaliDatePicker value={adjDate} onChange={setAdjDate} /></label>
              <label>توضیح (اختیاری)<input type="text" value={adjNotes} onChange={(e) => setAdjNotes(e.target.value)} /></label>
            </div>
            <button type="button" className="btn-danger-soft" disabled={busy || Number(adjQty) <= 0} onClick={() => void submitAdjust()}>
              <Boxes size={14} /> ثبت و کسر از موجودی
            </button>
          </section>

          {/* انسداد، فراخوان، بستن (§۱۶) */}
          <section className="drawer-section">
            <h4><ShieldAlert size={15} /> انسداد و فراخوان</h4>
            <p className="hint">
              بارِ مسدود یا فراخوان‌شده همان‌جا در انبار می‌ماند — موجودیِ فیزیکی‌اش تکان نمی‌خورد.
              فقط دیگر «قابلِ فروش» شمرده نمی‌شود و تخصیصِ خودکار برش نمی‌دارد.
            </p>
            {batch.hold_status !== 'none' ? (
              <>
                <div className="fy-note">
                  <AlertTriangle size={14} />
                  <span>
                    {batch.hold_status === 'recalled' ? 'فراخوان‌شده' : 'مسدود'}
                    {batch.hold_reason ? ` — ${batch.hold_reason}` : ''}
                  </span>
                </div>
                <button type="button" disabled={busy} onClick={() => void submitRelease()}>
                  <ShieldCheck size={14} /> رفعِ انسداد
                </button>
              </>
            ) : (
              <>
                <div className="field-row">
                  <label>نوع
                    <SearchSelect value={holdKind} onChange={(e) => setHoldKind(e.target.value as typeof holdKind)}>
                      <option value="blocked">مسدود</option>
                      <option value="recalled">فراخوان‌شده</option>
                    </SearchSelect>
                  </label>
                  <label>دلیل
                    <input type="text" value={holdReason} onChange={(e) => setHoldReason(e.target.value)} placeholder="الزامی" />
                  </label>
                </div>
                <button
                  type="button"
                  className="btn-danger-soft"
                  disabled={busy || !holdReason.trim()}
                  onClick={() => void submitHold()}
                >
                  <ShieldAlert size={14} /> اعمال
                </button>
              </>
            )}
            <button type="button" disabled={busy} onClick={() => void submitClose()} style={{ marginInlineStart: 8 }}>
              {batch.is_closed ? 'بازکردنِ بار' : 'بستنِ بار'}
            </button>
          </section>

          {/* ردیابی (§۱۵ §۱۶) */}
          <section className="drawer-section">
            <h4><Route size={15} /> ردیابیِ بار</h4>
            {trace === null ? (
              <p className="muted">در حال بارگذاری…</p>
            ) : (
              <>
                <div className="batch-summary">
                  <div><span>رسیده</span><strong>{fa(trace.received_qty)}</strong></div>
                  <div><span>فروخته</span><strong>{fa(trace.sold_qty)}</strong></div>
                  {Number(trace.returned_qty) > 0 && (
                    <div><span>برگشتی</span><strong>{fa(trace.returned_qty)}</strong></div>
                  )}
                  {Number(trace.damaged_qty) > 0 && (
                    <div className="batch-defect"><span>کسری/معیوب</span><strong>{fa(trace.damaged_qty)}</strong></div>
                  )}
                  <div><span>مانده</span><strong>{fa(trace.remaining_qty)}</strong></div>
                </div>

                {trace.recipients.length > 0 && (
                  <>
                    <h5>تحویل‌گیرندگان</h5>
                    <div className="table-scroll">
                      <table className="entity-table cards-on-mobile">
                        <thead><tr><th>تحویل‌گیرنده</th><th>خروج</th><th>تاریخ</th></tr></thead>
                        <tbody>
                          {trace.recipients.map((r) => (
                            <tr key={`${r.contact_id}-${r.issue_number}`}>
                              <td className="card-title" data-label="تحویل‌گیرنده">{r.name}</td>
                              <td className="num" data-label="خروج">{fa(r.issue_number)}</td>
                              <td data-label="تاریخ">{formatJalali(r.issue_date)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}

                {trace.movements.length === 0 ? (
                  <p className="muted">این بار هنوز هیچ گردشی در دفترِ انبار ندارد.</p>
                ) : (
                  <div className="table-scroll">
                    <table className="entity-table cards-on-mobile">
                      <thead><tr><th>تاریخ</th><th>سند</th><th>مقدار</th></tr></thead>
                      <tbody>
                        {trace.movements.map((m, i) => (
                          <tr key={`${m.source_id ?? 'x'}-${i}`}>
                            <td className="card-title" data-label="تاریخ">{formatJalali(m.entry_date)}</td>
                            <td data-label="سند">{m.document}</td>
                            <td className="num" data-label="مقدار">
                              <span className={Number(m.qty) < 0 ? 'stock-over' : 'stock-ok'}>{fa(m.qty)}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
