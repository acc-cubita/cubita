import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  Ban,
  ClipboardList,
  FilePlus2,
  FileText,
  PackageMinus,
  Plus,
  Printer,
  RefreshCw,
  Save,
  ScrollText,
  Trash2,
} from 'lucide-react'
import {
  can,
  createDirectWarehouseIssue,
  createStockTransfer,
  fetchAccountsLive,
  fetchContacts,
  fetchIssueInvoiceContext,
  fetchSalesQuotations,
  fetchStockLevels,
  fetchWarehouseIssue,
  fetchWarehouseIssueLedger,
  newIdempotencyKey,
  printStockTransfer,
  printWarehouseIssue,
  voidStockTransfer,
  voidWarehouseIssue,
  WAREHOUSE_ISSUE_TYPE_LABELS,
  type ContactRecord,
  type IssueInvoiceContext,
  type MeResponse,
  type SalesQuotationRecord,
  type StockLevel,
  type WarehouseIssueRecord,
  type WarehouseIssueRow,
} from '../api'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { NumberInput } from './NumberInput'
import { Pager, usePagination } from './Pager'
import { JournalEntryDrawer } from './JournalEntryDrawer'
import { formatJalali, todayIso } from '../lib/jalali'
import { AsyncBlock, Note, faAmount, type Msg } from '../pages/accounting/kit'

const faQty = (v: string | number | null | undefined) =>
  Number(v || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })
const faNum = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('fa-IR'))
const errText = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback)

type IssueKind = 'sale' | 'consumption' | 'other' | 'transfer'
const KINDS: IssueKind[] = ['sale', 'consumption', 'other', 'transfer']
type DraftLine = { key: number; itemId: string; qty: string; accountId: string; description: string }
type AccountOption = { id: string; code: string; name: string }

/** نوعِ خروج فقط برچسب نیست — معنای اقتصادیِ خروج را می‌گوید (§۲). */
const KIND_HINTS: Record<IssueKind, string> = {
  sale:
    'کالا برای فروش تحویل می‌شود و بهای تمام‌شده‌اش همین حالا سند می‌خورد. قیمتِ فروش مالِ فاکتور است: فاکتور را بعداً از ردیفِ همین خروج صادر کنید.',
  consumption:
    'کالا در خودِ کسب‌وکار مصرف می‌شود. نه فاکتوری ساخته می‌شود و نه درآمدی؛ بها به حسابی می‌رود که انتخاب می‌کنید.',
  other: 'خروجی که فروش یا مصرف نیست. همان کنترلِ موجودی و همان سند را دارد؛ حساب را انتخاب کنید.',
  transfer:
    'کالا به انبارِ مقصد می‌رود و موجودیِ کلِ شرکت عوض نمی‌شود. اگر دو انبار دو معینِ متفاوت دارند، سندِ جابه‌جایی هم ثبت می‌شود.',
}

/**
 * تبِ «خروج انبار» در ماژولِ انبار.
 *
 * تا فصلِ «خروج انبار» خروج فقط از دلِ ردیفِ فاکتورِ فروش ساخته می‌شد؛ مصرف و سایر
 * جز «تعدیلِ دستی» راهی نداشتند. این تب هر چهار نوع را از یک فرم و یک فهرست
 * می‌آورد — و انتقال را از موتورِ خودش ثبت می‌کند، نه نسخه‌ی دومی از آن.
 */
export function WarehouseIssuesTab({
  token,
  me,
  warehouses,
  items,
  onChanged,
  onCreateInvoice,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onChanged: () => void
  onCreateInvoice: (context: IssueInvoiceContext) => void
}) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  useEffect(() => {
    void fetchContacts(token).then(setContacts).catch(() => {})
  }, [token])
  const [reloadKey, setReloadKey] = useState(0)
  const reload = useCallback(() => {
    setReloadKey((key) => key + 1)
    onChanged()
  }, [onChanged])

  return (
    <>
      {can(me, 'inventory', 'create') && (
        <IssueForm token={token} warehouses={warehouses} items={items} contacts={contacts} onCreated={reload} />
      )}
      <WarehouseIssueLedger
        token={token}
        me={me}
        warehouses={warehouses}
        reloadKey={reloadKey}
        onCreateInvoice={onCreateInvoice}
        onChanged={reload}
      />
    </>
  )
}

/* ───────────────────────────── فرمِ خروج ───────────────────────────── */

function IssueForm({
  token,
  warehouses,
  items,
  contacts,
  onCreated,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  contacts: ContactRecord[]
  onCreated: () => void
}) {
  const seq = useRef(1)
  const blank = (): DraftLine => ({ key: seq.current++, itemId: '', qty: '', accountId: '', description: '' })
  const [kind, setKind] = useState<IssueKind>('sale')
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id ?? '')
  const [destinationId, setDestinationId] = useState('')
  const [issueDate, setIssueDate] = useState(todayIso())
  const [receiverId, setReceiverId] = useState('')
  const [quotationId, setQuotationId] = useState('')
  const [accountId, setAccountId] = useState('')
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<DraftLine[]>(() => [blank()])
  const [accounts, setAccounts] = useState<AccountOption[]>([])
  const [quotations, setQuotations] = useState<SalesQuotationRecord[]>([])
  const [stock, setStock] = useState<StockLevel[]>([])
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  //: کلید به *این* خروج گره می‌خورد و فقط پس از موفقیت نو می‌شود (§۴۶).
  const requestKey = useRef(newIdempotencyKey())

  useEffect(() => {
    void fetchAccountsLive(token)
      .then((rows) =>
        setAccounts(
          rows
            .filter((a) => !a.is_group)
            .map((a) => ({ id: a.id, code: a.code, name: a.name }))
            .sort((a, b) => a.code.localeCompare(b.code)),
        ),
      )
      .catch(() => setAccounts([]))
    void fetchSalesQuotations(token)
      .then((rows) => setQuotations(rows.filter((q) => q.status !== 'rejected')))
      .catch(() => setQuotations([]))
  }, [token])

  const refreshStock = useCallback(() => {
    void fetchStockLevels(token).then(setStock).catch(() => setStock([]))
  }, [token])
  useEffect(() => {
    refreshStock()
  }, [refreshStock])

  const goods = useMemo(() => items.filter((i) => !i.is_service), [items])
  const itemById = useMemo(() => new Map(items.map((i) => [i.id, i])), [items])
  const receivers = useMemo(() => contacts.filter((c) => c.type !== 'supplier'), [contacts])
  const receiverQuotations = useMemo(
    () => quotations.filter((q) => !receiverId || !q.contact_id || q.contact_id === receiverId),
    [quotations, receiverId],
  )
  const needsAccount = kind === 'consumption' || kind === 'other'

  function updateLine(key: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line) => (line.key === key ? { ...line, ...patch } : line)))
  }

  //: §۱۲ §۱۳ — موجودیِ پیش و پس از خروج برای کمک به اپراتور. منبعِ حقیقت دفترِ انبار
  //: است و سرور دوباره، زیرِ قفل، می‌سنجد؛ این جدول فقط زودتر خبر می‌دهد.
  const support = useMemo(() => {
    const requested = new Map<string, number>()
    for (const line of lines) {
      if (line.itemId && Number(line.qty) > 0) {
        requested.set(line.itemId, (requested.get(line.itemId) ?? 0) + Number(line.qty))
      }
    }
    return [...requested.entries()].map(([itemId, qty]) => {
      const here = Number(stock.find((s) => s.item_id === itemId && s.warehouse_id === warehouseId)?.qty ?? 0)
      const total = stock.filter((s) => s.item_id === itemId).reduce((sum, s) => sum + Number(s.qty), 0)
      return { itemId, qty, here, total, after: here - qty }
    })
  }, [lines, stock, warehouseId])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    const valid = lines.filter((line) => line.itemId && Number(line.qty) > 0)
    if (!warehouseId) return setMsg({ text: 'انبار را انتخاب کنید.', kind: 'err' })
    if (valid.length === 0) return setMsg({ text: 'حداقل یک ردیف با کالا و مقدار لازم است.', kind: 'err' })
    if (kind === 'sale' && !receiverId) return setMsg({ text: 'برای خروجِ فروش، تحویل‌گیرنده را انتخاب کنید.', kind: 'err' })
    if (kind === 'transfer' && (!destinationId || destinationId === warehouseId)) {
      return setMsg({ text: 'انبارِ مقصدی متفاوت از انبارِ مبدأ انتخاب کنید.', kind: 'err' })
    }
    if (needsAccount && !accountId && valid.some((line) => !line.accountId)) {
      return setMsg({ text: 'برای خروجِ «مصرف» و «سایر» حساب معین را انتخاب کنید.', kind: 'err' })
    }

    setBusy(true)
    try {
      if (kind === 'transfer') {
        const transfer = await createStockTransfer(
          token,
          {
            transfer_date: issueDate,
            from_warehouse_id: warehouseId,
            to_warehouse_id: destinationId,
            description: description.trim(),
            lines: valid.map((line) => ({ item_id: line.itemId, qty: Number(line.qty) })),
          },
          requestKey.current,
        )
        setMsg({ text: `انتقال بین انبار شماره ${faNum(transfer.number)} ثبت شد.`, kind: 'ok' })
      } else {
        const issue = await createDirectWarehouseIssue(
          token,
          {
            issue_date: issueDate,
            issue_type: kind,
            warehouse_id: warehouseId,
            receiver_id: kind === 'sale' ? receiverId : null,
            source_quotation_id: kind === 'sale' && quotationId ? quotationId : null,
            account_id: needsAccount && accountId ? accountId : null,
            description: description.trim(),
            lines: valid.map((line) => ({
              item_id: line.itemId,
              qty: Number(line.qty),
              account_id: needsAccount && line.accountId ? line.accountId : null,
              description: line.description.trim(),
            })),
          },
          requestKey.current,
        )
        setMsg({
          text: `خروج انبار شماره ${faNum(issue.number)} ثبت شد — بهای کالا ${faAmount(issue.total_cost)} ریال.`,
          kind: 'ok',
        })
      }
      requestKey.current = newIdempotencyKey()
      setLines([blank()])
      setDescription('')
      setQuotationId('')
      refreshStock()
      onCreated()
    } catch (err) {
      setMsg({ text: errText(err, 'ثبتِ خروج انبار ناموفق بود'), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  if (warehouses.length === 0 || goods.length === 0) {
    return (
      <SectionCard icon={PackageMinus} title="خروج انبار">
        <p className="hint">برای ثبتِ خروج به یک انبار و یک کالای غیرخدماتی نیاز است.</p>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      icon={PackageMinus}
      title="خروج انبار"
      description="کالایی که واقعاً از انبار بیرون می‌رود — برای فروش، مصرف، سایر، یا انتقال به انبارِ دیگر."
    >
      <form className="invoice-form" onSubmit={(e) => void submit(e)}>
        <label>
          نوع خروج
          <select value={kind} onChange={(e) => setKind(e.target.value as IssueKind)}>
            {KINDS.map((k) => (
              <option key={k} value={k}>{WAREHOUSE_ISSUE_TYPE_LABELS[k]}</option>
            ))}
          </select>
        </label>
        <label>
          {kind === 'transfer' ? 'انبار مبدأ' : 'انبار'}
          <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </label>
        {kind === 'transfer' && (
          <label>
            انبار مقصد
            <select value={destinationId} onChange={(e) => setDestinationId(e.target.value)}>
              <option value="">— انتخاب کنید —</option>
              {warehouses
                .filter((w) => w.id !== warehouseId)
                .map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
            </select>
          </label>
        )}
        <label>
          تاریخ
          <JalaliDatePicker value={issueDate} onChange={setIssueDate} />
        </label>
        {kind === 'sale' && (
          <label>
            تحویل‌گیرنده
            <select value={receiverId} onChange={(e) => setReceiverId(e.target.value)}>
              <option value="">— انتخاب کنید —</option>
              {receivers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
        )}
        {kind === 'sale' && receiverQuotations.length > 0 && (
          <label>
            پیش‌فاکتور (اختیاری)
            <select value={quotationId} onChange={(e) => setQuotationId(e.target.value)}>
              <option value="">— بدونِ پیش‌فاکتور —</option>
              {receiverQuotations.map((q) => (
                <option key={q.id} value={q.id}>
                  پیش‌فاکتور {faNum(q.number)} — {formatJalali(q.quotation_date)}
                </option>
              ))}
            </select>
          </label>
        )}
        {needsAccount && (
          <label>
            حساب معین
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">— انتخاب کنید —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
          </label>
        )}
        <label className="field-full">
          توضیحات
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <p className="hint field-full">{KIND_HINTS[kind]}</p>

        <div className="table-scroll field-full">
          <table className="invoice-lines cards-on-mobile">
            <thead>
              <tr>
                <th>کالا</th>
                <th>مقدار</th>
                <th>واحد</th>
                {needsAccount && <th>حساب معین ردیف</th>}
                <th>توضیحات</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => (
                <tr key={line.key}>
                  <td data-label="کالا">
                    <select value={line.itemId} onChange={(e) => updateLine(line.key, { itemId: e.target.value })}>
                      <option value="">— انتخاب کالا —</option>
                      {goods.map((it) => (
                        <option key={it.id} value={it.id}>{it.sku} — {it.name}</option>
                      ))}
                    </select>
                  </td>
                  <td data-label="مقدار">
                    <NumberInput allowDecimal value={line.qty} onChange={(v) => updateLine(line.key, { qty: v })} />
                  </td>
                  <td data-label="واحد">{itemById.get(line.itemId)?.unit || '—'}</td>
                  {needsAccount && (
                    <td data-label="حساب معین ردیف">
                      <select value={line.accountId} onChange={(e) => updateLine(line.key, { accountId: e.target.value })}>
                        <option value="">— حسابِ سربرگ —</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                        ))}
                      </select>
                    </td>
                  )}
                  <td data-label="توضیحات">
                    <input
                      type="text"
                      value={line.description}
                      onChange={(e) => updateLine(line.key, { description: e.target.value })}
                    />
                  </td>
                  <td className="card-actions">
                    <button
                      type="button"
                      className="icon-btn-danger"
                      aria-label="حذف ردیف"
                      disabled={lines.length === 1}
                      onClick={() => setLines((prev) => prev.filter((l) => l.key !== line.key))}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {support.length > 0 && (
          <div className="table-scroll field-full">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>موجودی این انبار</th>
                  <th>موجودی کل</th>
                  <th>مقدار خروج</th>
                  <th>پس از خروج</th>
                </tr>
              </thead>
              <tbody>
                {support.map((row) => (
                  <tr key={row.itemId}>
                    <td className="card-title">{itemById.get(row.itemId)?.name ?? '—'}</td>
                    <td className="num" data-label="موجودی این انبار">{faQty(row.here)}</td>
                    <td className="num" data-label="موجودی کل">{faQty(row.total)}</td>
                    <td className="num" data-label="مقدار خروج">{faQty(row.qty)}</td>
                    <td className="num" data-label="پس از خروج">
                      {row.after < 0 ? <span className="error">کسری {faQty(-row.after)}</span> : faQty(row.after)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="invoice-form-footer">
          <button type="button" onClick={() => setLines((prev) => [...prev, blank()])}>
            <Plus size={14} /> افزودن ردیف
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={14} /> {kind === 'transfer' ? 'ثبت انتقال' : 'ثبت خروج'}
          </button>
        </div>
      </form>
      <Note msg={msg} />
    </SectionCard>
  )
}

/* ───────────────────────────── فهرستِ خروج‌ها ───────────────────────────── */

/**
 * دفترِ خروج‌ها — یک فهرست برای هر چهار نوع (§۳۶ §۳۷).
 *
 * `presetType="transfer"` همین فهرست را زیرِ تبِ «انتقال بین انبار» می‌نشاند؛ نمای دومی
 * از داده‌ی انتقال ساخته نمی‌شود.
 */
export function WarehouseIssueLedger({
  token,
  me,
  warehouses,
  presetType,
  reloadKey = 0,
  onCreateInvoice,
  onChanged,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  presetType?: 'transfer'
  reloadKey?: number
  onCreateInvoice: (context: IssueInvoiceContext) => void
  onChanged: () => void
}) {
  const transfersOnly = presetType === 'transfer'
  const [typeFilter, setTypeFilter] = useState('')
  const [warehouseFilter, setWarehouseFilter] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [rows, setRows] = useState<WarehouseIssueRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [journalId, setJournalId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [localKey, setLocalKey] = useState(0)
  const canVoid = can(me, 'accounting', 'delete')
  const canInvoice = can(me, 'invoices', 'create')
  const effectiveType = transfersOnly ? 'transfer' : typeFilter

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    //: فیلتر سمتِ سرور است، نه مرورگر (قراردادِ صفحه‌ها §۷).
    fetchWarehouseIssueLedger(token, { issue_type: effectiveType, warehouse_id: warehouseFilter, state: stateFilter })
      .then((data) => {
        if (alive) setRows(data)
      })
      .catch((err) => {
        if (alive) setError(errText(err, 'دریافتِ فهرستِ خروج‌ها ناموفق بود'))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [token, effectiveType, warehouseFilter, stateFilter, reloadKey, localKey])

  const pg = usePagination(rows, 10, `${effectiveType}|${warehouseFilter}|${stateFilter}`)
  const columns = transfersOnly ? 10 : 12

  async function handlePrint(row: WarehouseIssueRow, template: 'standard' | 'a5') {
    try {
      if (row.kind === 'transfer') await printStockTransfer(token, row.id, template)
      else await printWarehouseIssue(token, row.id, template)
    } catch (err) {
      setMsg({ text: errText(err, 'نمای چاپی دریافت نشد'), kind: 'err' })
    }
  }

  async function handleInvoice(row: WarehouseIssueRow) {
    setBusyId(row.id)
    setMsg(null)
    try {
      //: فقط زمینه منتقل می‌شود؛ فاکتور سندِ مستقلِ فروش می‌ماند (§۱۶ §۱۷).
      onCreateInvoice(await fetchIssueInvoiceContext(token, row.id))
    } catch (err) {
      setMsg({ text: errText(err, 'آماده‌سازیِ فاکتور فروش ناموفق بود'), kind: 'err' })
    } finally {
      setBusyId(null)
    }
  }

  async function handleVoid(row: WarehouseIssueRow) {
    const label = `${row.type_label} شماره ${faNum(row.number)}`
    const reason = window.prompt(
      `ابطالِ ${label}؟\n\nسند پاک نمی‌شود؛ حرکتِ جبرانی در کاردکس و سندِ برگشتی ثبت می‌شود.\nدلیل ابطال:`,
    )
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMsg({ text: 'دلیل ابطال باید نوشته شود.', kind: 'err' })
      return
    }
    setBusyId(row.id)
    setMsg(null)
    try {
      if (row.kind === 'transfer') await voidStockTransfer(token, row.id, reason)
      else await voidWarehouseIssue(token, row.id, reason)
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
      title={transfersOnly ? 'انتقال‌های بین انبار' : 'خروج‌های انبار'}
      description={
        transfersOnly
          ? 'همان فهرستِ خروج‌ها با نوعِ «انتقال بین انبار» — با انبارِ مقصد، چاپِ مجوز و ابطال.'
          : 'هر خروج — فروش، مصرف، سایر و انتقال — با تحویل‌گیرنده یا انبارِ مقصد، فاکتور، سند و چاپِ مجوز.'
      }
      actions={
        <button type="button" onClick={() => setLocalKey((key) => key + 1)}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      <div className="invoice-form">
        {!transfersOnly && (
          <label>
            نوع
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">همه‌ی نوع‌ها</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>{WAREHOUSE_ISSUE_TYPE_LABELS[k]}</option>
              ))}
            </select>
          </label>
        )}
        <label>
          {transfersOnly ? 'انبار مبدأ' : 'انبار'}
          <select value={warehouseFilter} onChange={(e) => setWarehouseFilter(e.target.value)}>
            <option value="">همه‌ی انبارها</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </label>
        <label>
          وضعیت
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
            <option value="">همه</option>
            <option value="active">معتبر</option>
            <option value="voided">باطل‌شده</option>
          </select>
        </label>
      </div>
      <Note msg={msg} />

      <AsyncBlock
        loading={loading}
        error={error}
        empty={rows.length === 0}
        emptyText={
          transfersOnly
            ? 'انتقالی با این شرایط ثبت نشده است.'
            : 'خروجی با این شرایط ثبت نشده است. خروج را از فرمِ بالا یا از ردیفِ فاکتورِ فروش ثبت کنید.'
        }
      >
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>شماره</th>
                <th>تاریخ</th>
                {!transfersOnly && <th>نوع</th>}
                <th>{transfersOnly ? 'انبار مبدأ' : 'انبار'}</th>
                <th>{transfersOnly ? 'انبار مقصد' : 'تحویل‌گیرنده / مقصد'}</th>
                {!transfersOnly && <th>فاکتور و پیش‌فاکتور</th>}
                <th>مقدار</th>
                <th>بها</th>
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
                const busy = busyId === row.id
                const isIssue = row.kind === 'issue'
                const invoiceable = isIssue && row.issue_type === 'sale' && !row.sales_invoice_id && !voided
                return (
                  <Fragment key={`${row.kind}-${row.id}`}>
                    <tr style={voided ? { opacity: 0.55 } : undefined}>
                      <td className="card-title">
                        {row.type_label} {faNum(row.number)}
                      </td>
                      <td data-label="تاریخ">{formatJalali(row.doc_date)}</td>
                      {!transfersOnly && (
                        <td data-label="نوع">
                          {row.type_label}
                          {isIssue && row.origin === 'invoice' ? ' (از فاکتور)' : ''}
                        </td>
                      )}
                      <td data-label={transfersOnly ? 'انبار مبدأ' : 'انبار'}>{row.warehouse_name || '—'}</td>
                      <td data-label={transfersOnly ? 'انبار مقصد' : 'تحویل‌گیرنده / مقصد'}>
                        {row.kind === 'transfer' ? `به ${row.destination_warehouse_name || '—'}` : row.receiver_name || '—'}
                      </td>
                      {!transfersOnly && (
                        <td data-label="فاکتور و پیش‌فاکتور">
                          {row.sales_invoice_number != null
                            ? `فاکتور ${faNum(row.sales_invoice_number)}`
                            : isIssue && row.issue_type === 'sale'
                              ? 'بدونِ فاکتور'
                              : '—'}
                          {row.quotation_number != null ? ` · پیش‌فاکتور ${faNum(row.quotation_number)}` : ''}
                        </td>
                      )}
                      <td className="num" data-label="مقدار">
                        {faQty(row.total_qty)} ({faNum(row.line_count)} قلم)
                      </td>
                      <td className="num" data-label="بها">{faAmount(row.total_cost)}</td>
                      <td data-label="سند">
                        {row.journal_entry_number != null ? `سند ${faNum(row.journal_entry_number)}` : 'بدونِ سند'}
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
                        {isIssue && (
                          <button type="button" onClick={() => setOpenId(open ? null : row.id)}>
                            <FileText size={13} /> {open ? 'بستنِ جزئیات' : 'جزئیات'}
                          </button>
                        )}
                        {row.journal_entry_id && (
                          <button type="button" onClick={() => setJournalId(row.journal_entry_id)}>
                            <ScrollText size={13} /> سند حسابداری
                          </button>
                        )}
                        {invoiceable && canInvoice && (
                          <button type="button" disabled={busy} onClick={() => void handleInvoice(row)}>
                            <FilePlus2 size={13} /> صدور فاکتور فروش
                          </button>
                        )}
                        {!voided && canVoid && (
                          <button
                            type="button"
                            className="icon-btn-danger"
                            disabled={busy}
                            onClick={() => void handleVoid(row)}
                          >
                            <Ban size={13} /> ابطال
                          </button>
                        )}
                      </td>
                    </tr>
                    {open && isIssue && (
                      <tr>
                        <td className="card-full" colSpan={columns}>
                          <IssueDetail token={token} issueId={row.id} />
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

/** ردیف‌های یک خروج — مقدارِ اصلی و فرعی، بها و «حساب معین»ی که واقعاً سند خورد (§۹). */
function IssueDetail({ token, issueId }: { token: string; issueId: string }) {
  const [issue, setIssue] = useState<WarehouseIssueRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchWarehouseIssue(token, issueId)
      .then((data) => {
        if (alive) setIssue(data)
      })
      .catch((err) => {
        if (alive) setError(errText(err, 'جزئیاتِ خروج دریافت نشد'))
      })
    return () => {
      alive = false
    }
  }, [token, issueId])

  return (
    <AsyncBlock loading={!issue && !error} error={error} empty={issue?.lines.length === 0} emptyText="این خروج ردیفی ندارد.">
      {issue && (
        <>
          {issue.description && <p className="hint">{issue.description}</p>}
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>ردیف و کالا</th>
                  <th>کد کالا</th>
                  <th>مقدار اصلی</th>
                  <th>مقدار فرعی</th>
                  <th>فی</th>
                  <th>بها</th>
                  <th>حساب معین</th>
                  <th>توضیحات</th>
                </tr>
              </thead>
              <tbody>
                {issue.lines.map((line) => (
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
                    <td className="num" data-label="بها">{faAmount(line.amount)}</td>
                    <td data-label="حساب معین">
                      {line.account_code ? `${line.account_code} — ${line.account_name}` : '—'}
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
