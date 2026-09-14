import { useCallback, useEffect, useRef, useState } from 'react'
import { Calculator, ClipboardList, TriangleAlert } from 'lucide-react'
import {
  createValuationRun,
  fetchValuationPreview,
  fetchValuationRunList,
  newIdempotencyKey,
  voidValuationRun,
  type ValuationPreview,
  type ValuationRun,
  type ValuationScope,
} from '../api'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { formatJalali, todayIso } from '../lib/jalali'
import { EmptyState } from './EmptyState'
import { ItemPicker } from './ItemPicker'
import { JalaliDatePicker } from './JalaliDatePicker'
import { SectionCard } from './SectionCard'

const fa = (v: string | number) => (Number(v) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })
const faMoney = (v: string | number) => Math.round(Number(v) || 0).toLocaleString('fa-IR')
const faNo = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('fa-IR', { useGrouping: false }))
const errText = (e: unknown) => (e instanceof Error ? e.message : 'خطای ناشناخته')
/** اثر بر ارزشِ موجودی با علامت — منفی یعنی بهای تمام‌شده بیشتر و موجودی کمتر. */
const signed = (v: string | number) => {
  const n = Math.round(Number(v) || 0)
  return n === 0 ? '—' : `${n > 0 ? '+' : '−'}${Math.abs(n).toLocaleString('fa-IR')}`
}
const doc = (s: { source_label: string; source_number: number | null }) =>
  s.source_number != null ? `${s.source_label} ${faNo(s.source_number)}` : s.source_label

/**
 * تبِ «قیمت‌گذاری اسناد» در انبار — نوبتِ دومِ فصلِ «قیمت‌گذاری اسناد انبار».
 *
 * **محاسبه چیزی نمی‌نویسد.** پیش‌نمایش بهای قبل و بعدِ هر حرکتِ منقضی و سندِ اصلاحی را
 * نشان می‌دهد؛ ثبت با توکنِ همان پیش‌نمایش است و اگر دفتر از آن لحظه عوض شده باشد رد می‌شود.
 * هر تغییرِ دامنه پیش‌نمایش را پاک می‌کند تا چیزی که ثبت می‌شود همانی باشد که دیده شده.
 *
 * فهرستِ اجراها در همین تب است (قاعده‌ی ماژول‌های تب‌دار): هر اجرا یک سندِ اصلاحی، و ابطال
 * فقط از آخرین اجرا.
 */
export function InventoryValuationPanel({
  token,
  warehouses,
  items,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
}) {
  const [limitFrom, setLimitFrom] = useState(false)
  const [dateFrom, setDateFrom] = useState(todayIso())
  const [dateTo, setDateTo] = useState(todayIso())
  const [warehouseId, setWarehouseId] = useState('')
  const [itemId, setItemId] = useState('')
  const [preview, setPreview] = useState<ValuationPreview | null>(null)
  const [previewScope, setPreviewScope] = useState<ValuationScope | null>(null)
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [runs, setRuns] = useState<ValuationRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [voidingId, setVoidingId] = useState<string | null>(null)
  const [voidReason, setVoidReason] = useState('')
  const idempotencyKey = useRef(newIdempotencyKey())

  const loadRuns = useCallback(async () => {
    setRunsLoading(true)
    setRunsError(null)
    try {
      setRuns(await fetchValuationRunList(token))
    } catch (e) {
      setRunsError(errText(e))
    } finally {
      setRunsLoading(false)
    }
  }, [token])

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

  //: پیش‌نمایشِ دامنه‌ی قبلی دیگر معتبر نیست.
  useEffect(() => {
    setPreview(null)
  }, [limitFrom, dateFrom, dateTo, warehouseId, itemId])

  async function calculate() {
    const scope: ValuationScope = {
      dateTo,
      dateFrom: limitFrom ? dateFrom : undefined,
      warehouseId: warehouseId || undefined,
      itemId: itemId || undefined,
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      setPreview(await fetchValuationPreview(token, scope))
      setPreviewScope(scope)
      idempotencyKey.current = newIdempotencyKey()
    } catch (e) {
      setPreview(null)
      setError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  async function commit() {
    if (!preview || !previewScope) return
    setBusy(true)
    setError(null)
    try {
      const run = await createValuationRun(token, previewScope, preview.token, description.trim(), idempotencyKey.current)
      setNotice(
        run.journal_entry_number != null
          ? `اجرای شماره ${faNo(run.number)} ثبت شد — سندِ اصلاحیِ شماره ${faNo(run.journal_entry_number)}.`
          : `اجرای شماره ${faNo(run.number)} ثبت شد؛ اصلاح‌ها در سطحِ حساب هم را پوشاندند و سندی لازم نشد.`,
      )
      setPreview(null)
      setDescription('')
      idempotencyKey.current = newIdempotencyKey()
      await loadRuns()
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  async function confirmVoid(run: ValuationRun) {
    setBusy(true)
    setRunsError(null)
    try {
      await voidValuationRun(token, run.id, voidReason.trim())
      setVoidingId(null)
      setVoidReason('')
      await loadRuns()
    } catch (e) {
      setRunsError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  const canCommit = !!preview && !preview.blocked && preview.move_count > 0 && !busy

  return (
    <>
      <SectionCard
        icon={Calculator}
        title="قیمت‌گذاری اسناد انبار"
        description="حرکت‌هایی را که بهای ثبت‌شده‌شان با میانگینِ همان تاریخ نمی‌خواند پیدا و با یک سندِ اصلاحی درست می‌کند — معمولاً چون سندی بعداً با تاریخِ گذشته ثبت یا باطل شده. اول «محاسبه»، پیش‌نمایش را ببینید، بعد ثبت کنید."
      >
        <div className="vr-scope">
          <label className="vr-check">
            <input type="checkbox" checked={limitFrom} onChange={(e) => setLimitFrom(e.target.checked)} />
            فقط از تاریخِ مشخص
          </label>
          {limitFrom && (
            <label>
              از تاریخ
              <JalaliDatePicker value={dateFrom} onChange={setDateFrom} />
            </label>
          )}
          <label>
            تا تاریخ (تاریخِ سندِ اصلاحی)
            <JalaliDatePicker value={dateTo} onChange={setDateTo} />
          </label>
          <label>
            انبار
            <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              <option value="">همه‌ی انبارها</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            کالا
            <ItemPicker items={items} value={itemId} onChange={setItemId} placeholder="— همه‌ی کالاها —" />
          </label>
          <div className="vr-actions">
            {itemId && (
              <button type="button" onClick={() => setItemId('')}>
                همه‌ی کالاها
              </button>
            )}
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void calculate()}>
              <Calculator size={14} /> {busy && !preview ? 'در حال محاسبه…' : 'محاسبه'}
            </button>
          </div>
        </div>
        <p className="hint">
          انبار فقط کالاها را انتخاب می‌کند؛ میانگین مالِ کلِ شرکت است و حرکاتِ همان کالا در همه‌ی انبارها اصلاح می‌شوند.
          ورودی‌ای که هنوز فی ندارد در تبِ «قیمت‌گذاری ورودی‌ها» قیمت می‌خورد؛ پس از آن، بهای خروج‌های بعدش همین‌جا اصلاح می‌شود.
        </p>
        {error && <div className="error">{error}</div>}
        {notice && <p className="vr-notice">{notice}</p>}

        {preview && (
          <div className="vr-preview">
            {preview.blocked && (
              <>
                <div className="error">
                  <TriangleAlert size={14} /> موجودیِ منفی در خطِ زمان — میانگینِ موزون روی آن تعریف ندارد و ثبت ممکن
                  نیست. اول این‌ها را اصلاح کنید یا کالایشان را از دامنه بیرون بگذارید.
                </div>
                <div className="table-scroll">
                  <table className="cards-on-mobile">
                    <thead>
                      <tr>
                        <th>کالا</th>
                        <th>انبار</th>
                        <th>تاریخ</th>
                        <th>مانده</th>
                        <th>پس از</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.negatives.map((n) => (
                        <tr key={`${n.item_id}-${n.warehouse_name}`}>
                          <td className="card-title">{n.item_name}</td>
                          <td data-label="انبار">{n.warehouse_name}</td>
                          <td data-label="تاریخ">{formatJalali(n.entry_date)}</td>
                          <td data-label="مانده" className="num">
                            <span className="status-badge tone-danger">{fa(n.qty)}</span>
                          </td>
                          <td data-label="پس از">{doc(n)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <div className="kardex-summary">
              <div className="kardex-stat">
                <span>حرکتِ منقضی</span>
                <strong>{faNo(preview.move_count)}</strong>
              </div>
              <div className="kardex-stat">
                <span>کالا</span>
                <strong>{faNo(preview.item_count)}</strong>
              </div>
              <div className="kardex-stat">
                <span>اثر بر ارزشِ موجودی</span>
                <strong>{signed(preview.total_delta)}</strong>
                <small>ریال</small>
              </div>
            </div>

            {preview.move_count === 0 ? (
              !preview.blocked && (
                <EmptyState
                  icon={Calculator}
                  text="در این دامنه حرکتِ منقضی‌ای نیست؛ ارزش‌گذاری با دفتر یکی است و سندِ اصلاحی لازم نیست."
                />
              )
            ) : (
              <>
                <h4 className="vr-heading">سندِ اصلاحی</h4>
                {preview.accounts.length === 0 ? (
                  <p className="muted">
                    اصلاح‌ها در سطحِ حساب هم را می‌پوشانند (مثلاً دو سرِ انتقالی میانِ انبارهای هم‌معین)؛ سندی صادر
                    نمی‌شود ولی بهای حرکات اصلاح می‌شود.
                  </p>
                ) : (
                  <div className="table-scroll">
                    <table className="cards-on-mobile">
                      <thead>
                        <tr>
                          <th>حساب</th>
                          <th>بدهکار</th>
                          <th>بستانکار</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.accounts.map((a) => (
                          <tr key={a.account_id}>
                            <td className="card-title">
                              <span className="ltr-cell">{a.code}</span> — {a.name}
                            </td>
                            <td data-label="بدهکار" className="num">{Number(a.debit) ? faMoney(a.debit) : '—'}</td>
                            <td data-label="بستانکار" className="num">{Number(a.credit) ? faMoney(a.credit) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <h4 className="vr-heading">حرکاتِ منقضی</h4>
                <div className="table-scroll">
                  <table className="cards-on-mobile">
                    <thead>
                      <tr>
                        <th>تاریخ</th>
                        <th>کالا</th>
                        <th>سند</th>
                        <th>انبار</th>
                        <th>مقدار</th>
                        <th>بهای ثبت‌شده</th>
                        <th>بهای درست</th>
                        <th>اثر</th>
                        <th>طرفِ مقابل</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.moves.map((m) => (
                        <tr key={m.stock_ledger_id}>
                          <td data-label="تاریخ">{formatJalali(m.entry_date)}</td>
                          <td className="card-title">{m.item_name}</td>
                          <td data-label="سند">{doc(m)}</td>
                          <td data-label="انبار">{m.warehouse_name}</td>
                          <td data-label="مقدار" className="num">{fa(m.qty)}</td>
                          <td data-label="بهای ثبت‌شده" className="num">{faMoney(m.previous_cost)}</td>
                          <td data-label="بهای درست" className="num">{faMoney(m.new_cost)}</td>
                          <td data-label="اثر" className="num">{signed(m.value_delta)}</td>
                          <td data-label="طرفِ مقابل">{m.counter_account_name || 'دو سرِ انتقال'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.moves_truncated && (
                  <p className="muted">
                    {`فقط ${faNo(preview.moves.length)} حرکتِ اول از ${faNo(preview.move_count)} نشان داده شده؛ سند از همه‌ی حرکات ساخته می‌شود.`}
                  </p>
                )}
              </>
            )}

            {preview.skipped.length > 0 && (
              <>
                <h4 className="vr-heading">حرکاتِ منقضی‌ای که این اجرا اصلاح نمی‌کند</h4>
                <div className="table-scroll">
                  <table className="cards-on-mobile">
                    <thead>
                      <tr>
                        <th>تاریخ</th>
                        <th>کالا</th>
                        <th>سند</th>
                        <th>مقدار</th>
                        <th>علت</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.skipped.map((s, i) => (
                        <tr key={`${s.source_type}-${s.entry_date}-${i}`}>
                          <td data-label="تاریخ">{formatJalali(s.entry_date)}</td>
                          <td className="card-title">{s.item_name}</td>
                          <td data-label="سند">{doc(s)}</td>
                          <td data-label="مقدار" className="num">{fa(s.qty)}</td>
                          <td className="card-wide" data-label="علت">{s.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <div className="vr-commit">
              <label>
                شرحِ سند
                <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="اختیاری" />
              </label>
              <button type="button" className="btn-primary" disabled={!canCommit} onClick={() => void commit()}>
                ثبتِ سندِ اصلاحی
              </button>
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard
        icon={ClipboardList}
        title="اجراهای ثبت‌شده"
        description="هر اجرا یک سندِ اصلاحی است. ابطال سندش را معکوس می‌کند و بهای حرکات به پیش از اجرا برمی‌گردد — فقط از آخرین اجرا."
      >
        {runsError && <div className="error">{runsError}</div>}
        {runsLoading ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : runs.length === 0 ? (
          <EmptyState icon={ClipboardList} text="هنوز اجرایی ثبت نشده است. از بالا «محاسبه» بزنید." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تا تاریخ</th>
                  <th>دامنه</th>
                  <th>حرکت</th>
                  <th>اثر</th>
                  <th>سندِ اصلاحی</th>
                  <th>ثبت‌کننده</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <RunRows
                    key={run.id}
                    run={run}
                    busy={busy}
                    voiding={voidingId === run.id}
                    reason={voidReason}
                    onReason={setVoidReason}
                    onStart={() => {
                      setVoidingId(run.id)
                      setVoidReason('')
                    }}
                    onCancel={() => setVoidingId(null)}
                    onConfirm={() => void confirmVoid(run)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}

function RunRows({
  run,
  busy,
  voiding,
  reason,
  onReason,
  onStart,
  onCancel,
  onConfirm,
}: {
  run: ValuationRun
  busy: boolean
  voiding: boolean
  reason: string
  onReason: (v: string) => void
  onStart: () => void
  onCancel: () => void
  onConfirm: () => void
}) {
  const scope = [
    run.date_from ? `از ${formatJalali(run.date_from)}` : 'از ابتدا',
    run.item_name || run.warehouse_name || 'همه‌ی کالاها',
  ].join(' · ')
  return (
    <>
      <tr>
        <td className="card-title">قیمت‌گذاری {faNo(run.number)}</td>
        <td data-label="تا تاریخ">{formatJalali(run.date_to)}</td>
        <td data-label="دامنه">{scope}</td>
        <td data-label="حرکت" className="num">{faNo(run.move_count)}</td>
        <td data-label="اثر" className="num">{signed(run.total_delta)}</td>
        <td data-label="سندِ اصلاحی">{run.journal_entry_number != null ? faNo(run.journal_entry_number) : 'بی‌سند'}</td>
        <td data-label="ثبت‌کننده">{run.created_by_name || '—'}</td>
        <td data-label="وضعیت">
          {run.voided_at ? (
            <span className="status-badge tone-danger" title={run.void_reason}>
              باطل{run.void_entry_number != null ? ` · معکوس ${faNo(run.void_entry_number)}` : ''}
            </span>
          ) : (
            <span className="status-badge tone-success">ثبت‌شده</span>
          )}
        </td>
        <td className="card-actions">
          {run.voidable && !voiding && (
            <button type="button" onClick={onStart}>
              ابطال
            </button>
          )}
        </td>
      </tr>
      {voiding && (
        <tr>
          <td className="card-full" colSpan={9}>
            <div className="vr-void">
              <input value={reason} onChange={(e) => onReason(e.target.value)} placeholder="علتِ ابطال" />
              <button type="button" className="btn-danger" disabled={busy || reason.trim().length < 2} onClick={onConfirm}>
                ابطالِ اجرا
              </button>
              <button type="button" onClick={onCancel}>
                انصراف
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
