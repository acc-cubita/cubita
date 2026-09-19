import { Fragment, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Ban, ClipboardList, FileText, PackagePlus, Printer, RefreshCw, Save, ScrollText } from 'lucide-react'
import {
  can,
  createIssueReturn,
  fetchContacts,
  fetchIssueReturn,
  fetchIssueReturnBasis,
  fetchIssueReturnBasisDetail,
  fetchIssueReturnLedger,
  ISSUE_RETURN_PREFILL_KEY,
  ISSUE_RETURN_TYPE_LABELS,
  newIdempotencyKey,
  printIssueReturn,
  voidIssueReturn,
  type ContactRecord,
  type IssueReturnBasis,
  type IssueReturnBasisDoc,
  type IssueReturnPrefill,
  type IssueReturnRecord,
  type IssueReturnRow,
  type IssueReturnType,
  type MeResponse,
} from '../api'
import type { WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { NumberInput } from './NumberInput'
import { Pager, usePagination } from './Pager'
import { JournalEntryDrawer } from './JournalEntryDrawer'
import { formatJalali, todayIso } from '../lib/jalali'
import { AsyncBlock, Note, faAmount, type Msg } from '../pages/accounting/kit'
import { SearchSelect } from '../components/SearchSelect'

const faQty = (v: string | number | null | undefined) =>
  Number(v || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })
const faNum = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('fa-IR'))
const errText = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback)

const TYPES: IssueReturnType[] = ['sale', 'consumption', 'other']
const BASIS_LABELS: Record<string, string> = { sales_return: 'برگشت از فروش', issue: 'خروج انبار' }

/** نوعِ برگشت می‌گوید مبنا چیست و کدام حساب برمی‌گردد — نه فقط یک برچسب. */
const TYPE_HINTS: Record<IssueReturnType, string> = {
  sale:
    'کالایی که بابت فروش رفته بود دوباره وارد انبار می‌شود. اگر فروش فاکتور دارد، مبنا «برگشت از فروش» است — اول آن را در ماژولِ فروش ثبت کنید تا طلبِ مشتری هم برگردد. خروجِ فروشی که هنوز فاکتور ندارد مستقیم مبنا می‌شود.',
  consumption:
    'کالایی که برای مصرف بیرون رفته و مصرف نشده برمی‌گردد. همان حسابی که خروج بدهکار کرده بود بستانکار می‌شود؛ نه فاکتوری ساخته می‌شود و نه درآمدی.',
  other: 'برگشتِ یک خروجِ «سایر» — با همان حسابی که آن خروج خورده بود.',
}

function readPrefill(): IssueReturnPrefill | null {
  try {
    const raw = sessionStorage.getItem(ISSUE_RETURN_PREFILL_KEY)
    return raw ? (JSON.parse(raw) as IssueReturnPrefill) : null
  } catch {
    return null
  }
}

/**
 * تبِ «برگشت خروج انبار» در ماژولِ انبار.
 *
 * کالایی که با یک خروج رفته، با این سند برمی‌گردد — نه با ویرایشِ خروج و نه با تعدیلِ
 * دستی. فاکتور برگشتی سندِ تجاری است؛ این‌جا فقط ورودِ فیزیکیِ کالا ثبت می‌شود و
 * هر ردیف به خروجی که برمی‌گرداند گره می‌خورد.
 */
export function IssueReturnsTab({
  token,
  me,
  warehouses,
  onChanged,
  view,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  onChanged: () => void
  /** «فرم» یا «دفتر» یا هر دو (پیش‌فرض). منوی «تامین‌کنندگان و انبار» فرم را در
   *  «عملیات» و دفتر را در «فهرست» می‌گذارد؛ هر دو همین کامپوننت‌اند، نه نسخه‌ی دوم. */
  view?: 'form' | 'ledger'
}) {
  //: «ثبت برگشت به انبار» از دفترِ فاکتورهای برگشتی — یک بار خوانده و مصرف می‌شود.
  //: فقط فرم مصرفش می‌کند؛ نمای دفتر نباید پیش‌پرِ فرم را پاک کند.
  const [prefill] = useState(() => (view === 'ledger' ? null : readPrefill()))
  useEffect(() => {
    if (prefill) sessionStorage.removeItem(ISSUE_RETURN_PREFILL_KEY)
  }, [prefill])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  useEffect(() => {
    void fetchContacts(token).then(setContacts).catch(() => {})
  }, [token])
  const [reloadKey, setReloadKey] = useState(0)
  const reload = () => {
    setReloadKey((key) => key + 1)
    onChanged()
  }

  return (
    <>
      {view === 'form' && !can(me, 'inventory', 'create') && (
        <p className="hint">مجوزِ ثبتِ برگشت ندارید؛ برگشت‌های ثبت‌شده در «برگشت‌های خروج انبار» هستند.</p>
      )}
      {view !== 'ledger' && can(me, 'inventory', 'create') && (
        <ReturnForm token={token} warehouses={warehouses} contacts={contacts} initial={prefill} onCreated={reload} />
      )}
      {view !== 'form' && (
        <IssueReturnLedger token={token} me={me} warehouses={warehouses} reloadKey={reloadKey} onChanged={reload} />
      )}
    </>
  )
}

/* ───────────────────────────── فرمِ برگشت ───────────────────────────── */

function ReturnForm({
  token,
  warehouses,
  contacts,
  initial,
  onCreated,
}: {
  token: string
  warehouses: WarehouseCache[]
  contacts: ContactRecord[]
  initial: IssueReturnPrefill | null
  onCreated: () => void
}) {
  const [returnType, setReturnType] = useState<IssueReturnType>(initial?.return_type ?? 'sale')
  const [docs, setDocs] = useState<IssueReturnBasisDoc[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [docsKey, setDocsKey] = useState(0)
  const [basisKey, setBasisKey] = useState(initial ? `${initial.kind}:${initial.id}` : '')
  const [basis, setBasis] = useState<IssueReturnBasis | null>(null)
  const [qty, setQty] = useState<Record<string, string>>({})
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id ?? '')
  const [delivererId, setDelivererId] = useState('')
  const [returnDate, setReturnDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  //: کلید به *این* برگشت گره می‌خورد و فقط پس از موفقیت نو می‌شود (§۴۵).
  const requestKey = useRef(newIdempotencyKey())

  useEffect(() => {
    let alive = true
    setDocsLoading(true)
    fetchIssueReturnBasis(token, returnType)
      .then((rows) => {
        if (alive) setDocs(rows)
      })
      .catch(() => {
        if (alive) setDocs([])
      })
      .finally(() => {
        if (alive) setDocsLoading(false)
      })
    return () => {
      alive = false
    }
  }, [token, returnType, docsKey])

  useEffect(() => {
    if (!basisKey) {
      setBasis(null)
      setQty({})
      return
    }
    const [kind, id] = basisKey.split(':')
    let alive = true
    fetchIssueReturnBasisDetail(token, kind, id)
      .then((data) => {
        if (!alive) return
        setBasis(data)
        //: پیش‌فرض همان باقیمانده است؛ کاربر کمش می‌کند وقتی فقط بخشی برگشته.
        setQty(Object.fromEntries(data.lines.map((l) => [l.basis_line_id, Number(l.remaining) > 0 ? String(Number(l.remaining)) : ''])))
        if (data.warehouse_id) setWarehouseId(data.warehouse_id)
        setDelivererId(data.party_id ?? '')
      })
      .catch((err) => {
        if (alive) setMsg({ text: errText(err, 'دریافتِ ردیف‌های مبنا ناموفق بود'), kind: 'err' })
      })
    return () => {
      alive = false
    }
  }, [token, basisKey])

  const chosen = useMemo(
    () => (basis?.lines ?? []).filter((line) => Number(qty[line.basis_line_id]) > 0),
    [basis, qty],
  )
  const totalCost = chosen.reduce((sum, line) => sum + Number(qty[line.basis_line_id]) * Number(line.unit_cost), 0)
  const needsDeliverer = returnType === 'sale' && basis?.kind === 'issue'
  const movedWarehouse = basis?.warehouse_id && warehouseId && basis.warehouse_id !== warehouseId

  function changeType(next: IssueReturnType) {
    setReturnType(next)
    setBasisKey('')
    setMsg(null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!basis) return setMsg({ text: 'مبنای برگشت را انتخاب کنید.', kind: 'err' })
    if (!warehouseId) return setMsg({ text: 'انباری که کالا به آن برمی‌گردد را انتخاب کنید.', kind: 'err' })
    if (chosen.length === 0) return setMsg({ text: 'مقدارِ برگشتِ حداقل یک ردیف را وارد کنید.', kind: 'err' })
    const over = chosen.find((line) => Number(qty[line.basis_line_id]) > Number(line.remaining))
    if (over) {
      return setMsg({
        text: `مقدارِ برگشتِ «${over.item_name}» بیش از باقیمانده (${faQty(over.remaining)}) است.`,
        kind: 'err',
      })
    }
    if (needsDeliverer && !delivererId) return setMsg({ text: 'تحویل‌دهنده را انتخاب کنید.', kind: 'err' })

    setBusy(true)
    try {
      const saved = await createIssueReturn(
        token,
        {
          return_date: returnDate,
          return_type: returnType,
          warehouse_id: warehouseId,
          deliverer_id: delivererId || null,
          description: description.trim(),
          lines: chosen.map((line) =>
            basis.kind === 'sales_return'
              ? { sales_return_line_id: line.basis_line_id, qty: Number(qty[line.basis_line_id]) }
              : { warehouse_issue_line_id: line.basis_line_id, qty: Number(qty[line.basis_line_id]) },
          ),
        },
        requestKey.current,
      )
      setMsg({
        text: `برگشت خروج انبار شماره ${faNum(saved.number)} ثبت شد — بهای کالای برگشتی ${faAmount(saved.total_cost)} ریال.`,
        kind: 'ok',
      })
      requestKey.current = newIdempotencyKey()
      setBasisKey('')
      setDescription('')
      setDocsKey((key) => key + 1)
      onCreated()
    } catch (err) {
      setMsg({ text: errText(err, 'ثبتِ برگشت خروج انبار ناموفق بود'), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  if (warehouses.length === 0) {
    return (
      <SectionCard icon={PackagePlus} title="برگشت خروج انبار">
        <p className="hint">برای ثبتِ برگشت، ابتدا یک انبار تعریف کنید.</p>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      icon={PackagePlus}
      title="برگشت خروج انبار"
      description="کالایی که با یک خروج رفته بود و حالا واقعاً به انبار برمی‌گردد — کامل یا بخشی از آن."
    >
      <form className="invoice-form" onSubmit={(e) => void submit(e)}>
        <label>
          نوع برگشت
          <SearchSelect value={returnType} onChange={(e) => changeType(e.target.value as IssueReturnType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>{ISSUE_RETURN_TYPE_LABELS[t]}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          مبنا
          <SearchSelect value={basisKey} onChange={(e) => setBasisKey(e.target.value)} disabled={docsLoading}>
            <option value="">{docsLoading ? 'در حال بارگذاری…' : '— انتخاب کنید —'}</option>
            {docs.map((doc) => (
              <option key={`${doc.kind}:${doc.id}`} value={`${doc.kind}:${doc.id}`}>
                {BASIS_LABELS[doc.kind]} {faNum(doc.number)} — {formatJalali(doc.doc_date)}
                {doc.party_name ? ` — ${doc.party_name}` : ''} (مانده {faQty(doc.remaining_qty)})
              </option>
            ))}
          </SearchSelect>
        </label>
        <label>
          انبار
          <SearchSelect value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          {needsDeliverer ? 'تحویل‌دهنده' : 'تحویل‌دهنده (اختیاری)'}
          <SearchSelect value={delivererId} onChange={(e) => setDelivererId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {contacts.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={returnDate} onChange={setReturnDate} />
        </label>
        <label className="field-full">
          توضیحات
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <p className="hint field-full">{TYPE_HINTS[returnType]}</p>
        {!docsLoading && docs.length === 0 && (
          <p className="hint field-full">
            {returnType === 'sale'
              ? 'سندی با کالای قابلِ برگشت پیدا نشد. برای کالای فاکتورشده اول «برگشت از فروش» را ثبت کنید؛ در حالتِ «خودکار» همان سند کالا را هم برمی‌گرداند.'
              : `خروجِ «${ISSUE_RETURN_TYPE_LABELS[returnType]}»ی با باقیمانده‌ی قابلِ برگشت پیدا نشد.`}
          </p>
        )}
        {movedWarehouse && (
          <p className="hint field-full">
            کالا به انباری غیر از انبارِ خروج برمی‌گردد؛ سند با حسابِ موجودیِ همین انبار زده می‌شود.
          </p>
        )}

        {basis && (
          <div className="table-scroll field-full">
            <table className="invoice-lines cards-on-mobile">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>کد کالا</th>
                  <th>مقدار مبنا</th>
                  <th>برگشت‌خورده</th>
                  <th>باقیمانده</th>
                  <th>مقدار برگشت</th>
                  <th>فی</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {basis.lines.map((line) => {
                  const value = qty[line.basis_line_id] ?? ''
                  const done = Number(line.remaining) <= 0
                  return (
                    <tr key={line.basis_line_id} style={done ? { opacity: 0.55 } : undefined}>
                      <td className="card-title">
                        {line.item_name} {line.unit ? `(${line.unit})` : ''}
                      </td>
                      <td data-label="کد کالا">{line.item_code || '—'}</td>
                      <td className="num" data-label="مقدار مبنا">{faQty(line.qty)}</td>
                      <td className="num" data-label="برگشت‌خورده">{faQty(line.returned)}</td>
                      <td className="num" data-label="باقیمانده">{faQty(line.remaining)}</td>
                      <td data-label="مقدار برگشت">
                        <NumberInput
                          allowDecimal
                          value={value}
                          disabled={done}
                          onChange={(v) => setQty((prev) => ({ ...prev, [line.basis_line_id]: v }))}
                        />
                      </td>
                      <td className="num" data-label="فی">{faAmount(line.unit_cost)}</td>
                      <td className="num" data-label="مبلغ">
                        {faAmount(Math.round(Number(value || 0) * Number(line.unit_cost)))}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="invoice-form-footer">
          {basis && <span className="hint">بهای کالای برگشتی: {faAmount(Math.round(totalCost))} ریال</span>}
          <button type="submit" className="btn-primary" disabled={busy || !basis}>
            <Save size={14} /> ثبت برگشت
          </button>
        </div>
      </form>
      <Note msg={msg} />
    </SectionCard>
  )
}

/* ───────────────────────────── فهرستِ برگشت‌ها ───────────────────────────── */

/** دفترِ برگشت‌های خروج — یک فهرست برای هر سه نوع، با فیلترِ نوع (§۳۴ §۳۵). */
export function IssueReturnLedger({
  token,
  me,
  warehouses,
  reloadKey = 0,
  onChanged,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  reloadKey?: number
  onChanged: () => void
}) {
  const [typeFilter, setTypeFilter] = useState('')
  const [warehouseFilter, setWarehouseFilter] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [rows, setRows] = useState<IssueReturnRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [journalId, setJournalId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [localKey, setLocalKey] = useState(0)
  const canVoid = can(me, 'accounting', 'delete')

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fetchIssueReturnLedger(token, { return_type: typeFilter, warehouse_id: warehouseFilter, state: stateFilter })
      .then((data) => {
        if (alive) setRows(data)
      })
      .catch((err) => {
        if (alive) setError(errText(err, 'دریافتِ فهرستِ برگشت‌ها ناموفق بود'))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [token, typeFilter, warehouseFilter, stateFilter, reloadKey, localKey])

  const pg = usePagination(rows, 10, `${typeFilter}|${warehouseFilter}|${stateFilter}`)

  async function handlePrint(row: IssueReturnRow, template: 'standard' | 'a5') {
    try {
      await printIssueReturn(token, row.id, template)
    } catch (err) {
      setMsg({ text: errText(err, 'نمای چاپی دریافت نشد'), kind: 'err' })
    }
  }

  async function handleVoid(row: IssueReturnRow) {
    const label = `برگشت خروج انبار شماره ${faNum(row.number)}`
    const reason = window.prompt(
      `ابطالِ ${label}؟\n\nخروجِ اصلی و فاکتور برگشتی دست نمی‌خورند؛ کالا دوباره از انبار کم و سندِ معکوس ثبت می‌شود.\nدلیل ابطال:`,
    )
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMsg({ text: 'دلیل ابطال باید نوشته شود.', kind: 'err' })
      return
    }
    setBusyId(row.id)
    setMsg(null)
    try {
      await voidIssueReturn(token, row.id, reason)
      setMsg({ text: `${label} باطل شد.`, kind: 'ok' })
      setLocalKey((key) => key + 1)
      onChanged()
    } catch (err) {
      setMsg({ text: errText(err, 'ابطال ناموفق بود'), kind: 'err' })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <SectionCard
      icon={ClipboardList}
      title="برگشت‌های خروج انبار"
      description="هر برگشت — فروش، مصرف و سایر — با مبنایش، تحویل‌دهنده، بهای کالا، سند و چاپ."
      actions={
        <button type="button" onClick={() => setLocalKey((key) => key + 1)}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      <div className="invoice-form">
        <label>
          نوع
          <SearchSelect value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">همه‌ی نوع‌ها</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>{ISSUE_RETURN_TYPE_LABELS[t]}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          انبار
          <SearchSelect value={warehouseFilter} onChange={(e) => setWarehouseFilter(e.target.value)}>
            <option value="">همه‌ی انبارها</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          وضعیت
          <SearchSelect value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
            <option value="">همه</option>
            <option value="active">معتبر</option>
            <option value="voided">باطل‌شده</option>
          </SearchSelect>
        </label>
      </div>
      <Note msg={msg} />

      <AsyncBlock
        loading={loading}
        error={error}
        empty={rows.length === 0}
        emptyText="برگشتی با این شرایط ثبت نشده است. برگشت را از فرمِ بالا یا با «برگشت از فروش» در حالتِ خودکار ثبت کنید."
      >
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>شماره</th>
                <th>تاریخ</th>
                <th>نوع</th>
                <th>انبار</th>
                <th>تحویل‌دهنده</th>
                <th>مبنا</th>
                <th>مقدار</th>
                <th>مبلغ</th>
                <th>سند</th>
                <th>صادرکننده</th>
                <th>وضعیت</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((row) => {
                const voided = row.voided_at != null
                const open = openId === row.id
                const automatic = row.origin === 'sales_return'
                const basis = [
                  ...row.sales_return_numbers.map((n) => `برگشت از فروش ${faNum(n)}`),
                  ...row.issue_numbers.map((n) => `خروج ${faNum(n)}`),
                ].join(' · ')
                return (
                  <Fragment key={row.id}>
                    <tr style={voided ? { opacity: 0.55 } : undefined}>
                      <td className="card-title">برگشت {faNum(row.number)}</td>
                      <td data-label="تاریخ">{formatJalali(row.return_date)}</td>
                      <td data-label="نوع">
                        {row.type_label}
                        {automatic ? ' (از برگشت فروش)' : ''}
                      </td>
                      <td data-label="انبار">{row.warehouse_name || '—'}</td>
                      <td data-label="تحویل‌دهنده">{row.deliverer_name || '—'}</td>
                      <td className="card-wide" data-label="مبنا">{basis || '—'}</td>
                      <td className="num" data-label="مقدار">
                        {faQty(row.total_qty)} ({faNum(row.line_count)} قلم)
                      </td>
                      <td className="num" data-label="مبلغ">{faAmount(row.total_cost)}</td>
                      <td data-label="سند">
                        {row.journal_entry_number != null
                          ? `سند ${faNum(row.journal_entry_number)} — ${formatJalali(row.journal_entry_date)}`
                          : 'بدونِ سند'}
                      </td>
                      <td data-label="صادرکننده">{row.created_by_name || '—'}</td>
                      <td data-label="وضعیت">{voided ? 'باطل‌شده' : 'معتبر'}</td>
                      <td className="card-actions">
                        <button type="button" onClick={() => void handlePrint(row, 'standard')}>
                          <Printer size={13} /> چاپ
                        </button>
                        <button type="button" onClick={() => void handlePrint(row, 'a5')}>
                          <Printer size={13} /> چاپ A5
                        </button>
                        <button type="button" onClick={() => setOpenId(open ? null : row.id)}>
                          <FileText size={13} /> {open ? 'بستنِ جزئیات' : 'جزئیات'}
                        </button>
                        {row.journal_entry_id && (
                          <button type="button" onClick={() => setJournalId(row.journal_entry_id)}>
                            <ScrollText size={13} /> سند حسابداری
                          </button>
                        )}
                        {/* برگشتی که «برگشت از فروش» ساخته فقط همراهِ همان سند باطل می‌شود. */}
                        {!voided && canVoid && !automatic && (
                          <button
                            type="button"
                            className="icon-btn-danger"
                            disabled={busyId === row.id}
                            onClick={() => void handleVoid(row)}
                          >
                            <Ban size={13} /> ابطال
                          </button>
                        )}
                      </td>
                    </tr>
                    {open && (
                      <tr>
                        <td className="card-full" colSpan={12}>
                          <ReturnDetail token={token} returnId={row.id} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </AsyncBlock>

      {journalId && <JournalEntryDrawer token={token} entryId={journalId} onClose={() => setJournalId(null)} />}
    </SectionCard>
  )
}

/** ردیف‌های یک برگشت — با خروجِ مبدأ و حسابی که واقعاً بستانکار شد. */
function ReturnDetail({ token, returnId }: { token: string; returnId: string }) {
  const [record, setRecord] = useState<IssueReturnRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchIssueReturn(token, returnId)
      .then((data) => {
        if (alive) setRecord(data)
      })
      .catch((err) => {
        if (alive) setError(errText(err, 'جزئیاتِ برگشت دریافت نشد'))
      })
    return () => {
      alive = false
    }
  }, [token, returnId])

  return (
    <AsyncBlock loading={!record && !error} error={error} empty={record?.lines.length === 0} emptyText="این برگشت ردیفی ندارد.">
      {record && (
        <>
          {record.description && <p className="hint">{record.description}</p>}
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>ردیف و کالا</th>
                  <th>کد کالا</th>
                  <th>مقدار اصلی</th>
                  <th>مقدار فرعی</th>
                  <th>فی</th>
                  <th>مبلغ</th>
                  <th>حساب معین</th>
                  <th>مبنا</th>
                  <th>توضیحات</th>
                </tr>
              </thead>
              <tbody>
                {record.lines.map((line) => (
                  <tr key={line.id}>
                    <td className="card-title">
                      {faNum(line.seq || null)} — {line.item_name_snapshot}
                    </td>
                    <td data-label="کد کالا">{line.item_code_snapshot || '—'}</td>
                    <td className="num" data-label="مقدار اصلی">
                      {faQty(line.qty)} {line.unit_snapshot}
                    </td>
                    <td className="num" data-label="مقدار فرعی">
                      {line.secondary_qty != null ? `${faQty(line.secondary_qty)} ${line.secondary_unit_snapshot}` : '—'}
                    </td>
                    <td className="num" data-label="فی">{faAmount(line.unit_cost)}</td>
                    <td className="num" data-label="مبلغ">{faAmount(line.amount)}</td>
                    <td data-label="حساب معین">
                      {line.account_code ? `${line.account_code} — ${line.account_name}` : '—'}
                    </td>
                    <td data-label="مبنا">
                      {[
                        line.sales_return_number != null ? `برگشت از فروش ${faNum(line.sales_return_number)}` : '',
                        line.issue_number != null ? `خروج ${faNum(line.issue_number)}` : '',
                      ]
                        .filter(Boolean)
                        .join(' · ') || '—'}
                    </td>
                    <td data-label="توضیحات">{line.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </AsyncBlock>
  )
}
