import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, ClipboardCheck, ListChecks, Plus, Printer, Save, Tag, XCircle } from 'lucide-react'
import type { WarehouseCache } from '../electron.d'
import {
  cancelStockCount,
  createStockCount,
  fetchStockCount,
  fetchStockCountDrift,
  fetchStockCounts,
  postStockCount,
  printCountTags,
  setStockCounts,
  type CountDrift,
  type StockCountSession,
  type StockCountStatus,
  type StockCountSummary,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const STATUS_LABEL: Record<StockCountStatus, string> = {
  open: 'باز',
  posted: 'ثبت‌شده',
  cancelled: 'لغوشده',
}
const STATUS_TONE: Record<StockCountStatus, string> = {
  open: 'tone-warning',
  posted: 'tone-success',
  cancelled: 'tone-danger',
}

const faInt = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
const faQty = (v: string | number) => Number(v).toLocaleString('fa-IR')

/**
 * انبارگردانی — سه کار از یک منطق:
 *  - `tags`: ساختِ جلسه (عکس از موجودیِ سیستمی) و چاپِ برگه‌های شمارش.
 *  - `variance`: واردکردنِ شمارش، دیدنِ مغایرت و ثبتِ نهایی (سندِ تعدیل).
 *  - `list`: همه‌ی جلسه‌ها با وضعیتشان.
 * بی‌`mode` همان نمای یک‌جای قدیمی است. `sessionId` جلسه‌ای است که کاربر از تبِ
 * دیگری برای شمارش باز کرده؛ `onOpenSession` او را به تبِ «ثبت مغایرت» می‌برد.
 */
export function StockCountPanel({
  token,
  warehouses,
  mode,
  sessionId = null,
  onOpenSession,
}: {
  token: string
  warehouses: WarehouseCache[]
  mode?: 'tags' | 'variance' | 'list'
  sessionId?: string | null
  onOpenSession?: (id: string) => void
}) {
  const [sessions, setSessions] = useState<StockCountSummary[]>([])
  const [selected, setSelected] = useState<StockCountSession | null>(null)
  const [counts, setCounts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [drift, setDrift] = useState<CountDrift[]>([])

  const [warehouseId, setWarehouseId] = useState('')
  const [countDate, setCountDate] = useState(todayIso())
  const [notes, setNotes] = useState('')

  async function refreshList() {
    try {
      setSessions(await fetchStockCounts(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refreshList()
  }, [])


  const loadDraft = useCallback((session: StockCountSession) => {
    setSelected(session)
    //: ردیفِ نشمرده **خالی** می‌ماند، نه صفر. رشته‌ی خالی تنها بازنماییِ
    //: «هنوز نشمرده‌ام» است؛ صفر یعنی «شمردم، هیچ نبود» و کسریِ واقعی می‌سازد.
    setCounts(
      Object.fromEntries(
        session.lines.map((l) => [l.id, l.counted_qty === null ? '' : String(Number(l.counted_qty))]),
      ),
    )
    setMessage(null)
  }, [])

  const openSession = useCallback(
    async (id: string) => {
      setError(null)
      try {
        loadDraft(await fetchStockCount(token, id))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'خطای ناشناخته')
      }
    },
    [token, loadDraft],
  )

  //: «ثبت مغایرت» با جلسه‌ای باز می‌شود که کاربر از تبِ دیگر انتخاب کرده؛ اگر
  //: نکرده، با تازه‌ترین جلسه‌ی باز — همان که به احتمالِ زیاد در حالِ شمارشش است.
  const [autoOpened, setAutoOpened] = useState(false)
  useEffect(() => {
    if (mode !== 'variance' || autoOpened) return
    if (sessionId) {
      setAutoOpened(true)
      void openSession(sessionId)
      return
    }
    const latestOpen = sessions.find((x) => x.status === 'open')
    if (latestOpen) {
      setAutoOpened(true)
      void openSession(latestOpen.id)
    }
  }, [mode, sessionId, sessions, autoOpened, openSession])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setMessage(null)
    const wid = warehouseId || warehouses[0]?.id
    if (!wid) {
      setError('ابتدا یک انبار انتخاب کنید.')
      return
    }
    try {
      const session = await createStockCount(token, { warehouse_id: wid, count_date: countDate, notes })
      loadDraft(session)
      setNotes('')
      if (mode === 'tags') setMessage(`جلسه‌ی انبارگردانیِ «${session.warehouse_name}» ساخته شد. برگه‌های شمارش را چاپ کنید.`)
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  //: `''` → `null` می‌رود، نه `0`. اگر این‌جا صفر فرستاده شود، جلسه‌ای که
  //: نیمه‌کاره ثبت شود موجودیِ همه‌ی کالاهای نشمرده را از انبار بیرون می‌ریزد.
  function countPayload() {
    if (!selected) return []
    return selected.lines.map((l) => {
      const raw = (counts[l.id] ?? (l.counted_qty === null ? '' : String(l.counted_qty))).trim()
      return { line_id: l.id, counted_qty: raw === '' ? null : Number(raw) }
    })
  }

  async function handleSaveCounts() {
    if (!selected) return
    setMessage(null)
    try {
      const updated = await setStockCounts(token, selected.id, countPayload())
      loadDraft(updated)
      setMessage('شمارش‌ها ذخیره شد.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handlePost() {
    if (!selected) return
    setMessage(null)
    // شمارش‌های ویرایش‌شده اول ذخیره، بعد ثبت — تا آنچه کاربر می‌بیند همان چیزی باشد که اعمال می‌شود.
    try {
      await setStockCounts(token, selected.id, countPayload())
      const posted = await postStockCount(token, selected.id)
      loadDraft(posted)
      setDrift([])
      setMessage('انبارگردانی ثبت شد و سند تعدیل صادر شد.')
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleCancel() {
    if (!selected) return
    try {
      const cancelled = await cancelStockCount(token, selected.id)
      loadDraft(cancelled)
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function openTags(id = selected?.id) {
    if (!id) return
    try {
      //: همان مسیرِ چاپِ بقیه‌ی اسناد — نه یک راهِ دومِ مخصوصِ این صفحه.
      await printCountTags(token, id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function checkDrift() {
    if (!selected) return
    setError(null)
    try {
      const rows = await fetchStockCountDrift(token, selected.id)
      setDrift(rows)
      if (rows.length === 0) setMessage('از زمانِ شمارش، هیچ کالایی حرکت نکرده است.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const editable = selected?.status === 'open'
  // صفحه‌بندیِ جلسه‌های انبارگردانی (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const sessionsPg = usePagination(sessions, 10)

  // مغایرت و ارزش را زنده از شمارشِ در حال ویرایش حساب می‌کنیم تا کاربر همان لحظه ببیند.
  const liveRows = useMemo(() => {
    if (!selected) return []
    return selected.lines.map((l) => {
      const raw = (counts[l.id] ?? (l.counted_qty === null ? '' : String(l.counted_qty))).trim()
      //: نشمرده = `null`، نه صفر. مغایرتش هم `null` است تا جدول «بدون اختلاف»
      //: نشان ندهد در حالی که اصلاً سراغش نرفته‌ایم.
      const counted = raw === '' ? null : Number(raw)
      const variance = counted === null ? null : counted - Number(l.system_qty)
      return { line: l, counted, variance, value: variance === null ? 0 : variance * Number(l.unit_cost) }
    })
  }, [selected, counts])

  const totalVarianceValue = liveRows.reduce((s, r) => s + r.value, 0)
  const varianceCount = liveRows.filter((r) => r.variance !== null && r.variance !== 0).length
  const countedCount = liveRows.filter((r) => r.counted !== null).length

  //: کنشِ ردیف: در نمای یک‌جا جلسه همین‌جا باز می‌شود؛ در منوی تازه به تبِ «ثبت مغایرت» می‌رود.
  const openOrGo = (id: string) => (onOpenSession && mode !== 'variance' ? onOpenSession(id) : void openSession(id))
  const sessionsTable = (
    rows: StockCountSummary[],
    actions: (s: StockCountSummary) => React.ReactNode,
    pager: React.ReactNode = null,
    emptyText = 'هنوز جلسه‌ای ثبت نشده.',
  ) => (
    <>
      {rows.length === 0 ? (
        <EmptyState icon={ClipboardCheck} text={emptyText} />
      ) : (
        <div className="entity-table-wrap">
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>انبار</th>
                  <th>تاریخ</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id} className={selected?.id === s.id ? 'row-selected' : undefined}>
                    <td className="entity-name card-title" data-label="انبار">{s.warehouse_name}</td>
                    <td data-label="تاریخ">{formatJalali(s.count_date)}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${STATUS_TONE[s.status]}`}>{STATUS_LABEL[s.status]}</span>
                    </td>
                    <td className="card-actions">
                      {actions(s)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pager}
        </div>
      )}
    </>
  )
  const openButton = (s: StockCountSummary) => (
    <button type="button" onClick={() => openOrGo(s.id)}>
      {s.status === 'open' ? 'شمارش و ثبت مغایرت' : 'باز کردن'}
    </button>
  )
  const createForm = (
    <form className="invoice-form form-full" onSubmit={handleCreate}>
      <label>
        انبار
        <select value={warehouseId || warehouses[0]?.id || ''} onChange={(e) => setWarehouseId(e.target.value)}>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        تاریخ شمارش
        <JalaliDatePicker value={countDate} onChange={setCountDate} />
      </label>
      <label>
        توضیحات
        <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="اختیاری" />
      </label>
      <div className="invoice-form-footer">
        <button type="submit" className="btn-primary">
          <Plus size={14} /> ایجاد جلسه و عکس‌برداری
        </button>
      </div>
    </form>
  )
  const countCard = (
    <SectionCard
      icon={ClipboardCheck}
      title={selected ? `شمارش انبار «${selected.warehouse_name}»` : 'شمارش'}
      description={
        selected
          ? `${formatJalali(selected.count_date)} — ${STATUS_LABEL[selected.status]}`
          : 'یک جلسه را از فهرست باز کنید یا جلسه‌ی تازه بسازید.'
      }
      actions={
        selected ? (
          <div className="check-actions">
            {/* برگه‌ی شمارش عمداً موجودیِ سیستمی را نشان نمی‌دهد — شمارنده
                نباید با عددِ سیستم سوگیر شود. */}
            <button type="button" onClick={() => void openTags()}>
              <Printer size={13} /> برگه‌های شمارش
            </button>
            {editable && (
              <>
                <button type="button" onClick={() => void checkDrift()}>
                  <AlertTriangle size={13} /> بررسی حرکت پس از شمارش
                </button>
                <button type="button" onClick={() => void handleSaveCounts()}>
                  <Save size={13} /> ذخیره
                </button>
                <button type="button" className="btn-primary" onClick={() => void handlePost()}>
                  <CheckCircle2 size={13} /> ثبت نهایی
                </button>
                <button type="button" className="icon-btn-danger" onClick={() => void handleCancel()}>
                  <XCircle size={13} /> لغو
                </button>
              </>
            )}
          </div>
        ) : undefined
      }
    >
      {!selected ? (
        <EmptyState icon={ClipboardCheck} text="جلسه‌ای انتخاب نشده." />
      ) : (
        <>
          {drift.length > 0 && (
            <div className="fy-note">
              <strong>{faInt(drift.length)} کالا پس از ثبتِ شمارششان حرکت کرده‌اند.</strong>{' '}
              اختلافشان همچنان درست حساب می‌شود — مبنایش وضعیتِ لحظه‌ی شمارش است — ولی اگر
              می‌خواهید شمارشِ تازه‌تری داشته باشید، دوباره بشمارید و ذخیره کنید:{' '}
              {drift.map((d) => d.item_name).join('، ')}
            </div>
          )}
          <div className="stat-inline">
            <span>شمرده‌شده: <strong>{faInt(countedCount)}</strong> از {faInt(liveRows.length)}</span>
            <span>ردیف‌های دارای مغایرت: <strong>{faInt(varianceCount)}</strong></span>
            <span className={totalVarianceValue < 0 ? 'text-danger' : totalVarianceValue > 0 ? 'text-success' : ''}>
              ارزش خالص مغایرت: <strong>{faInt(totalVarianceValue)}</strong> ریال
            </span>
          </div>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>کالا</th>
                    <th>سیستمی</th>
                    <th>شمارش</th>
                    <th>مغایرت</th>
                    <th>ارزش مغایرت</th>
                  </tr>
                </thead>
                <tbody>
                  {liveRows.map(({ line, variance, value }) => (
                    <tr key={line.id}>
                      <td className="card-title" data-label="کالا">
                        <div className="entity-name">{line.item_name}</div>
                        <div className="entity-sub">{line.item_sku} · {line.unit}</div>
                      </td>
                      <td data-label="سیستمی">{faQty(line.system_qty)}</td>
                      <td data-label="شمارش">
                        {editable ? (
                          <NumberInput
                            allowDecimal
                            className="count-input"
                            value={counts[line.id] ?? ''}
                            onChange={(v) => setCounts((prev) => ({ ...prev, [line.id]: v }))}
                          />
                        ) : (
                          line.counted_qty === null ? (
                            <span className="muted">نشمرده</span>
                          ) : (
                            faQty(line.counted_qty)
                          )
                        )}
                      </td>
                      {/* نشمرده مغایرتِ صفر نیست — خط تیره است. وگرنه جدول
                          «بدون اختلاف» نشان می‌دهد در حالی که سراغش نرفته‌ایم. */}
                      <td
                        data-label="مغایرت"
                        className={variance === null ? 'muted' : variance < 0 ? 'text-danger' : variance > 0 ? 'text-success' : ''}
                      >
                        {variance === null ? '—' : `${variance > 0 ? '+' : ''}${faQty(variance)}`}
                      </td>
                      <td data-label="ارزش مغایرت" className={value < 0 ? 'text-danger' : value > 0 ? 'text-success' : ''}>
                        {variance === null ? '—' : faInt(value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {message && <div className="hint">{message}</div>}
        </>
      )}
    </SectionCard>
  )
  const openSessions = sessions.filter((x) => x.status === 'open')

  if (mode === 'tags') {
    return (
      <SectionCard
        icon={Tag}
        title="تگ انبارگردانی"
        description="جلسه بسازید تا از موجودیِ سیستمیِ انبار عکس گرفته شود، بعد برگه‌های شمارش را چاپ کنید. برگه عمداً عددِ سیستم را ندارد."
      >
        {createForm}
        {message && <div className="hint">{message}</div>}
        <h3 className="panel-subhead"><ListChecks size={15} /> جلسه‌های باز</h3>
        {sessionsTable(
          openSessions,
          (s) => (
            <div className="check-actions">
              <button type="button" onClick={() => void openTags(s.id)}>
                <Printer size={13} /> برگه‌های شمارش
              </button>
              {openButton(s)}
            </div>
          ),
          null,
          'جلسه‌ی بازی نیست؛ با فرمِ بالا یکی بسازید.',
        )}
        {error && <div className="error">{error}</div>}
      </SectionCard>
    )
  }

  if (mode === 'variance') {
    return (
      <>
        <SectionCard
          icon={ClipboardCheck}
          title="ثبت مغایرت انبارگردانی"
          description="جلسه را انتخاب کنید، شمارشِ فیزیکی را وارد کنید و مغایرت را ثبت کنید؛ سندِ تعدیل خودکار صادر می‌شود."
        >
          {sessions.length === 0 ? (
            <EmptyState icon={ClipboardCheck} text="هنوز جلسه‌ای نیست؛ از «تگ انبارگردانی» یکی بسازید." />
          ) : (
            <label className="form-full">
              جلسه‌ی انبارگردانی
              <select value={selected?.id ?? ''} onChange={(e) => e.target.value && void openSession(e.target.value)}>
                <option value="">— انتخاب جلسه —</option>
                {sessions.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.warehouse_name} — {formatJalali(x.count_date)} — {STATUS_LABEL[x.status]}
                  </option>
                ))}
              </select>
            </label>
          )}
          {error && <div className="error">{error}</div>}
        </SectionCard>
        {countCard}
      </>
    )
  }

  if (mode === 'list') {
    return (
      <SectionCard
        icon={ListChecks}
        title="فهرست انبارگردانی‌ها"
        description="همه‌ی جلسه‌های انبارگردانی با وضعیتشان — باز، ثبت‌شده یا لغوشده."
      >
        {sessionsTable(
          sessionsPg.pageItems,
          openButton,
          <Pager page={sessionsPg.page} pageCount={sessionsPg.pageCount} onChange={sessionsPg.setPage} />,
        )}
        {error && <div className="error">{error}</div>}
      </SectionCard>
    )
  }

  return (
    <div className="split-2col">
      <SectionCard
        icon={ClipboardCheck}
        title="جلسه‌ی انبارگردانی جدید"
        description="از موجودی سیستمیِ همه‌ی کالاهای انبار عکس‌برداری می‌شود؛ سپس شمارش فیزیکی را وارد کنید."
      >
        {createForm}

        <h3 className="panel-subhead"><ListChecks size={15} /> جلسه‌های اخیر</h3>
        {sessionsTable(
          sessionsPg.pageItems,
          openButton,
          <Pager page={sessionsPg.page} pageCount={sessionsPg.pageCount} onChange={sessionsPg.setPage} />,
        )}
        {error && <div className="error">{error}</div>}
      </SectionCard>

      {countCard}
    </div>
  )
}
