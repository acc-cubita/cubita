import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  Ban,
  ClipboardList,
  CreditCard,
  FileText,
  PackagePlus,
  Plus,
  Printer,
  RefreshCw,
  Save,
  ScrollText,
  Trash2,
  Undo2,
  X,
} from 'lucide-react'
import {
  can,
  createDirectWarehouseReceipt,
  createReceiptReturn,
  fetchAllWarehouseReceipts,
  fetchContacts,
  fetchReceiptPaymentContext,
  fetchReceiptReturnable,
  newIdempotencyKey,
  printWarehouseReceipt,
  WAREHOUSE_RECEIPT_TYPE_LABELS,
  RETURN_TYPE_LABELS,
  voidWarehouseReceipt,
  type ContactRecord,
  type MeResponse,
  type ReceiptPaymentContext,
  type ReceiptReturnableLine,
  type WarehouseReceiptFull,
} from '../api'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { NumberInput } from './NumberInput'
import { Pager, usePagination } from './Pager'
import { JournalEntryDrawer } from './JournalEntryDrawer'
import { formatJalali, todayIso } from '../lib/jalali'
import { AsyncBlock, Note, faAmount, type Msg } from '../pages/accounting/kit'
import { SearchSelect } from '../components/SearchSelect'

const faQty = (v: string | number) => Number(v || 0).toLocaleString('fa-IR')
const num = (v: string) => Number(v || 0)
const errText = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback)

/** وضعیتِ برگشتِ هر ردیف — از مقدارها مشتق است، نه یک بولینِ ذخیره‌شده. */
const RETURN_STATUS_LABELS: Record<ReceiptReturnableLine['return_status'], string> = {
  not_returned: 'برگشت نخورده',
  partially_returned: 'برگشتِ جزئی',
  fully_returned: 'کامل برگشت خورده',
}

type DraftLine = { key: number; itemId: string; qty: string; unitCost: string }

/**
 * تبِ «رسید انبار» در ماژولِ خرید.
 *
 * تا امروز رسید فقط از دلِ یک ردیفِ فاکتور ساخته می‌شد. بک‌اند از فصلِ «رسید انبار»
 * رسیدِ مستقیم، حمل، برگشتِ رسید، چاپ و میان‌برِ پرداخت را داشت ولی هیچ‌کدام راهی به
 * رابط نداشتند. این تب همان‌ها را می‌آورد — و **هیچ عددِ مالی‌ای را خودش حساب
 * نمی‌کند**: سهمِ حمل، فیِ تمام‌شده و خالص از سرور می‌آیند (§۲۳ §۲۷).
 */
export function WarehouseReceiptsTab({
  token,
  me,
  warehouses,
  items,
  onChanged,
  onCreatePayment,
  view,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onChanged: () => void
  onCreatePayment: (context: ReceiptPaymentContext) => void
  /** «فرم» یا «دفتر» یا هر دو (پیش‌فرض). منوی «تامین‌کنندگان و انبار» فرم را در
   *  «عملیات» و دفتر را در «فهرست» می‌گذارد؛ هر دو همین کامپوننت‌اند، نه نسخه‌ی دوم. */
  view?: 'form' | 'ledger'
}) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  useEffect(() => {
    void fetchContacts(token).then(setContacts).catch(() => {})
  }, [token])
  const suppliers = useMemo(() => contacts.filter((c) => c.is_supplier), [contacts])
  const contactName = useMemo(() => new Map(contacts.map((c) => [c.id, c.name])), [contacts])
  const warehouseName = useMemo(() => new Map(warehouses.map((w) => [w.id, w.name])), [warehouses])

  const [reloadKey, setReloadKey] = useState(0)
  const reload = useCallback(() => {
    setReloadKey((key) => key + 1)
    onChanged()
  }, [onChanged])
  const [returning, setReturning] = useState<WarehouseReceiptFull | null>(null)

  const showForm = view !== 'ledger'
  const showLedger = view !== 'form'

  return (
    <>
      {showForm && !can(me, 'invoices', 'create') && view === 'form' && (
        <p className="hint">مجوزِ ثبتِ رسید ندارید؛ رسیدهای ثبت‌شده در «فهرست رسیدها و حواله‌های انبار» هستند.</p>
      )}
      {showForm && can(me, 'invoices', 'create') && (
        <DirectReceiptForm
          token={token}
          warehouses={warehouses}
          items={items}
          suppliers={suppliers}
          contacts={contacts}
          onCreated={reload}
        />
      )}
      {showLedger && (
        <ReceiptLedger
          token={token}
          me={me}
          warehouses={warehouses}
          warehouseName={warehouseName}
          contactName={contactName}
          reloadKey={reloadKey}
          onReturn={setReturning}
          onCreatePayment={onCreatePayment}
          onChanged={reload}
        />
      )}
      {showLedger && returning && (
        <ReceiptReturnPanel
          key={returning.id}
          token={token}
          receipt={returning}
          contacts={contacts}
          warehouseName={warehouseName}
          onClose={() => setReturning(null)}
          onReturned={reload}
        />
      )}
    </>
  )
}

/* ───────────────────────────── رسیدِ مستقیم ───────────────────────────── */

function DirectReceiptForm({
  token,
  warehouses,
  items,
  suppliers,
  contacts,
  onCreated,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  suppliers: ContactRecord[]
  contacts: ContactRecord[]
  onCreated: () => void
}) {
  const nextKey = useRef(1)
  const [receiptType, setReceiptType] = useState('purchase_domestic')
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id ?? '')
  const [receiptDate, setReceiptDate] = useState(todayIso())
  const [contactId, setContactId] = useState('')
  const [taxRate, setTaxRate] = useState('')
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([{ key: 0, itemId: '', qty: '', unitCost: '' }])
  const [freightAmount, setFreightAmount] = useState('')
  const [freightTax, setFreightTax] = useState('')
  const [freightDuty, setFreightDuty] = useState('')
  const [carrierId, setCarrierId] = useState('')
  const [freightBasis, setFreightBasis] = useState('equal')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const requestKey = useRef(newIdempotencyKey())

  useEffect(() => {
    if (!warehouseId && warehouses[0]) setWarehouseId(warehouses[0].id)
  }, [warehouses, warehouseId])

  const goodsTotal = lines.reduce((sum, line) => sum + num(line.qty) * num(line.unitCost), 0)
  //: «جمع مبلغ حمل»ِ پنجره‌ی حمل (§۲۱) — جمعِ همان سه عددی که کاربر وارد کرده؛
  //: تسهیم و فیِ تمام‌شده را سرور می‌سازد.
  const freightWindowTotal = num(freightAmount) + num(freightTax) + num(freightDuty)

  const updateLine = (key: number, patch: Partial<DraftLine>) =>
    setLines((rows) => rows.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  const addLine = () => setLines((rows) => [...rows, { key: nextKey.current++, itemId: '', qty: '', unitCost: '' }])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setMsg(null)
    const payloadLines = lines
      .filter((line) => line.itemId && num(line.qty) > 0)
      .map((line) => ({ item_id: line.itemId, qty: num(line.qty), unit_cost: num(line.unitCost) }))
    if (!warehouseId) return setMsg({ text: 'انبار را انتخاب کنید.', kind: 'err' })
    if (payloadLines.length === 0) return setMsg({ text: 'دست‌کم یک ردیف با کالا و مقدار لازم است.', kind: 'err' })
    setBusy(true)
    try {
      const receipt = await createDirectWarehouseReceipt(
        token,
        {
          receipt_date: receiptDate,
          warehouse_id: warehouseId,
          receipt_type: receiptType,
          contact_id: contactId || null,
          carrier_id: carrierId || null,
          freight_amount: num(freightAmount),
          freight_tax: num(freightTax),
          freight_duty: num(freightDuty),
          freight_basis: freightBasis,
          tax_rate: num(taxRate),
          description,
          lines: payloadLines,
        },
        requestKey.current,
      )
      requestKey.current = newIdempotencyKey()
      setMsg({
        text: `رسید انبار شماره ${receipt.number.toLocaleString('fa-IR')} ثبت شد — خالص ${faAmount(receipt.net_amount)} ریال.`,
        kind: 'ok',
      })
      setLines([{ key: nextKey.current++, itemId: '', qty: '', unitCost: '' }])
      setFreightAmount('')
      setFreightTax('')
      setFreightDuty('')
      setCarrierId('')
      setDescription('')
      onCreated()
    } catch (err) {
      setMsg({ text: errText(err, 'ثبت رسید انبار ناموفق بود'), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={PackagePlus}
      title="رسید انبار مستقیم"
      description="ورودِ کالا بدونِ فاکتورِ خرید. سندِ حسابداری از خودِ رسید صادر می‌شود و حمل روی بهای ورود تسهیم می‌شود."
    >
      <form className="invoice-form" onSubmit={(event) => void submit(event)}>
        <label>
          نوع رسید
          <SearchSelect value={receiptType} onChange={(e) => setReceiptType(e.target.value)}>
            {Object.entries(WAREHOUSE_RECEIPT_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          انبار
          <SearchSelect value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </SearchSelect>
        </label>
        <label>
          تاریخ رسید
          <JalaliDatePicker value={receiptDate} onChange={setReceiptDate} />
        </label>
        <label>
          تحویل‌دهنده
          <SearchSelect value={contactId} onChange={(e) => setContactId(e.target.value)}>
            <option value="">— بدونِ تحویل‌دهنده (خریدِ نقدی) —</option>
            {suppliers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </SearchSelect>
        </label>
        <label>
          نرخ مالیات کالا (٪)
          <NumberInput allowDecimal value={taxRate} onChange={setTaxRate} />
        </label>
        <label>
          توضیحات
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>

        <div className="table-scroll form-wide">
          <table className="cards-on-mobile">
            <thead>
              <tr><th>کالا</th><th>مقدار</th><th>فی</th><th>مبلغ</th><th /></tr>
            </thead>
            <tbody>
              {lines.map((line) => (
                <tr key={line.key}>
                  <td className="card-title">
                    <SearchSelect value={line.itemId} onChange={(e) => updateLine(line.key, { itemId: e.target.value })}>
                      <option value="">— انتخاب کالا —</option>
                      {items.map((item) => (
                        <option key={item.id} value={item.id}>{item.name}{item.sku ? ` — ${item.sku}` : ''}</option>
                      ))}
                    </SearchSelect>
                  </td>
                  <td data-label="مقدار">
                    <NumberInput allowDecimal value={line.qty} onChange={(value) => updateLine(line.key, { qty: value })} />
                  </td>
                  <td data-label="فی">
                    <NumberInput value={line.unitCost} onChange={(value) => updateLine(line.key, { unitCost: value })} />
                  </td>
                  <td className="num" data-label="مبلغ">{faAmount(num(line.qty) * num(line.unitCost))}</td>
                  <td className="card-actions">
                    <button
                      type="button"
                      className="icon-btn-danger"
                      disabled={lines.length === 1}
                      onClick={() => setLines((rows) => rows.filter((row) => row.key !== line.key))}
                    >
                      <Trash2 size={13} /> حذف ردیف
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="form-wide">
          <button type="button" onClick={addLine}><Plus size={13} /> افزودن ردیف</button>
        </div>

        <div className="form-wide">
          <strong>اطلاعات حمل</strong>
          <p className="hint">
            مبلغ و عوارضِ حمل روی بهای ورودِ کالا تسهیم می‌شوند؛ مالیاتِ حمل اعتبارِ مالیاتی است و وارد بهای کالا نمی‌شود.
          </p>
        </div>
        <label>
          مبلغ حمل
          <NumberInput value={freightAmount} onChange={setFreightAmount} />
        </label>
        <label>
          مالیات حمل
          <NumberInput value={freightTax} onChange={setFreightTax} />
        </label>
        <label>
          عوارض حمل
          <NumberInput value={freightDuty} onChange={setFreightDuty} />
        </label>
        <label>
          حمل‌کننده
          <SearchSelect value={carrierId} onChange={(e) => setCarrierId(e.target.value)}>
            <option value="">— بدونِ حمل‌کننده (پرداختِ نقدی) —</option>
            {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </SearchSelect>
        </label>
        <label>
          مبنای تسهیم
          <SearchSelect value={freightBasis} onChange={(e) => setFreightBasis(e.target.value)}>
            <option value="equal">به نسبت مساوی</option>
          </SearchSelect>
        </label>
        <label>
          جمع مبلغ حمل
          <input type="text" readOnly value={faAmount(freightWindowTotal)} />
        </label>

        <div className="invoice-form-footer">
          <span className="hint">
            جمع کالا: {faAmount(goodsTotal)} ریال — سهمِ حملِ هر ردیف، فیِ تمام‌شده و خالص را سرور هنگامِ ثبت محاسبه می‌کند.
          </span>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={14} /> ثبتِ رسید انبار
          </button>
        </div>
      </form>
      <Note msg={msg} />
    </SectionCard>
  )
}

/* ───────────────────────────── دفترِ رسیدها ───────────────────────────── */

function ReceiptLedger({
  token,
  me,
  warehouses,
  warehouseName,
  contactName,
  reloadKey,
  onReturn,
  onCreatePayment,
  onChanged,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  warehouseName: Map<string, string>
  contactName: Map<string, string>
  reloadKey: number
  onReturn: (receipt: WarehouseReceiptFull) => void
  onCreatePayment: (context: ReceiptPaymentContext) => void
  onChanged: () => void
}) {
  const [typeFilter, setTypeFilter] = useState('')
  const [warehouseFilter, setWarehouseFilter] = useState('')
  const [rows, setRows] = useState<WarehouseReceiptFull[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [journalId, setJournalId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [localKey, setLocalKey] = useState(0)
  const canReturn = can(me, 'invoices', 'create')
  const canVoid = can(me, 'accounting', 'delete')

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    //: فیلتر سمتِ سرور است، نه مرورگر (قراردادِ صفحه‌ها §۷).
    fetchAllWarehouseReceipts(token, { receipt_type: typeFilter, warehouse_id: warehouseFilter })
      .then((data) => {
        if (alive) setRows(data)
      })
      .catch((err) => {
        if (alive) setError(errText(err, 'دریافت رسیدهای انبار ناموفق بود'))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [token, typeFilter, warehouseFilter, reloadKey, localKey])

  const sorted = useMemo(
    () => [...rows].sort((a, b) => b.receipt_date.localeCompare(a.receipt_date) || b.number - a.number),
    [rows],
  )
  const pg = usePagination(sorted, 10, `${typeFilter}|${warehouseFilter}`)

  async function handlePrint(receipt: WarehouseReceiptFull) {
    try {
      await printWarehouseReceipt(token, receipt.id)
    } catch (err) {
      setMsg({ text: errText(err, 'نمای چاپی دریافت نشد'), kind: 'err' })
    }
  }

  async function handlePayment(receipt: WarehouseReceiptFull) {
    setBusyId(receipt.id)
    setMsg(null)
    try {
      //: فقط زمینه منتقل می‌شود؛ اعلامیه پرداخت سندِ مستقلِ خزانه است (§۳۹).
      onCreatePayment(await fetchReceiptPaymentContext(token, receipt.id))
    } catch (err) {
      setMsg({ text: errText(err, 'آماده‌سازیِ اعلامیه پرداخت ناموفق بود'), kind: 'err' })
    } finally {
      setBusyId(null)
    }
  }

  async function handleVoid(receipt: WarehouseReceiptFull) {
    const reason = window.prompt(
      `ابطال رسید انبار شماره ${receipt.number.toLocaleString('fa-IR')}؟\n\n` +
        'رسید پاک نمی‌شود؛ حرکتِ جبرانی در کاردکس و سندِ برگشتی ثبت می‌شود.\nدلیل ابطال:',
    )
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMsg({ text: 'دلیل ابطال باید نوشته شود.', kind: 'err' })
      return
    }
    setBusyId(receipt.id)
    setMsg(null)
    try {
      await voidWarehouseReceipt(token, receipt.id, reason)
      setMsg({ text: `رسید انبار شماره ${receipt.number.toLocaleString('fa-IR')} باطل شد.`, kind: 'ok' })
      setLocalKey((key) => key + 1)
      onChanged()
    } catch (err) {
      setMsg({ text: errText(err, 'ابطال رسید انبار ناموفق بود'), kind: 'err' })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <SectionCard
      icon={ClipboardList}
      title="رسیدهای انبار"
      description="همه‌ی رسیدها — مستقیم یا از دلِ فاکتور — با اجزای خالص، چاپ، برگشت، پرداخت و سندِ حسابداری."
      actions={
        <button type="button" onClick={() => setLocalKey((key) => key + 1)}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      <div className="invoice-form">
        <label>
          نوع رسید
          <SearchSelect value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">همه‌ی نوع‌ها</option>
            {Object.entries(WAREHOUSE_RECEIPT_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </SearchSelect>
        </label>
        <label>
          انبار
          <SearchSelect value={warehouseFilter} onChange={(e) => setWarehouseFilter(e.target.value)}>
            <option value="">همه‌ی انبارها</option>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </SearchSelect>
        </label>
      </div>
      <Note msg={msg} />

      <AsyncBlock
        loading={loading}
        error={error}
        empty={sorted.length === 0}
        emptyText="رسیدی با این شرایط ثبت نشده است. رسیدِ مستقیم را از فرمِ بالا یا از ردیفِ فاکتورِ خرید صادر کنید."
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
                <th>کالا</th>
                <th>حمل</th>
                <th>مالیات</th>
                <th>خالص</th>
                <th>سند</th>
                <th>وضعیت</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((receipt) => {
                const voided = receipt.voided_at != null
                const open = openId === receipt.id
                const busy = busyId === receipt.id
                return (
                  <Fragment key={receipt.id}>
                    <tr style={voided ? { opacity: 0.55 } : undefined}>
                      <td className="card-title">رسید {receipt.number.toLocaleString('fa-IR')}</td>
                      <td data-label="تاریخ">{formatJalali(receipt.receipt_date)}</td>
                      <td data-label="نوع">{WAREHOUSE_RECEIPT_TYPE_LABELS[receipt.receipt_type] ?? receipt.receipt_type}</td>
                      <td data-label="انبار">{warehouseName.get(receipt.warehouse_id) ?? '—'}</td>
                      <td data-label="تحویل‌دهنده">{receipt.contact_id ? contactName.get(receipt.contact_id) ?? '—' : 'نقدی'}</td>
                      <td className="num" data-label="کالا">{faAmount(receipt.goods_amount)}</td>
                      <td className="num" data-label="حمل">{faAmount(receipt.freight_amount)}</td>
                      <td className="num" data-label="مالیات">{faAmount(receipt.tax_amount)}</td>
                      <td className="num" data-label="خالص"><strong>{faAmount(receipt.net_amount)}</strong></td>
                      {/* §۴۴ — «اثرِ حسابداری» جدا از «اثرِ انباری»، نه یک بولینِ مبهم. */}
                      <td data-label="سند">{receipt.journal_entry_id ? 'صادر شده' : 'بدونِ سند'}</td>
                      <td data-label="وضعیت">{voided ? 'باطل‌شده' : 'معتبر'}</td>
                      <td className="card-actions">
                        <button type="button" onClick={() => void handlePrint(receipt)}>
                          <Printer size={13} /> چاپ
                        </button>
                        <button type="button" onClick={() => setOpenId(open ? null : receipt.id)}>
                          <FileText size={13} /> {open ? 'بستنِ جزئیات' : 'جزئیات'}
                        </button>
                        {receipt.journal_entry_id && (
                          <button type="button" onClick={() => setJournalId(receipt.journal_entry_id)}>
                            <ScrollText size={13} /> سند حسابداری
                          </button>
                        )}
                        {!voided && canReturn && (
                          <button type="button" onClick={() => onReturn(receipt)}>
                            <Undo2 size={13} /> برگشت
                          </button>
                        )}
                        {!voided && receipt.contact_id && (
                          <button type="button" disabled={busy} onClick={() => void handlePayment(receipt)}>
                            <CreditCard size={13} /> اعلامیه پرداخت
                          </button>
                        )}
                        {!voided && canVoid && (
                          <button type="button" className="icon-btn-danger" disabled={busy} onClick={() => void handleVoid(receipt)}>
                            <Ban size={13} /> ابطال
                          </button>
                        )}
                      </td>
                    </tr>
                    {open && (
                      <tr>
                        <td className="card-full" colSpan={12}>
                          <ReceiptDetail receipt={receipt} contactName={contactName} />
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

/** ردیف‌های یک رسید — «فی» و «فی تمام‌شده» کنارِ هم، چون یکی نیستند (§۲۰). */
function ReceiptDetail({ receipt, contactName }: { receipt: WarehouseReceiptFull; contactName: Map<string, string> }) {
  return (
    <div>
      <p className="hint">
        حمل {faAmount(receipt.freight_amount)} · مالیات حمل {faAmount(receipt.freight_tax)} · عوارض حمل{' '}
        {faAmount(receipt.freight_duty)} · جمع مبلغ حمل {faAmount(receipt.freight_total)} · مبنای تسهیم: به نسبت مساوی
        {receipt.carrier_id ? ` · حمل‌کننده: ${contactName.get(receipt.carrier_id) ?? '—'}` : ''}
      </p>
      <div className="table-scroll">
        <table className="cards-on-mobile">
          <thead>
            <tr><th>ردیف</th><th>کالا</th><th>مقدار</th><th>فی</th><th>سهم حمل</th><th>فی تمام‌شده</th><th>مالیات</th></tr>
          </thead>
          <tbody>
            {receipt.lines.map((line, index) => (
              <tr key={line.id}>
                <td className="card-title">
                  {(line.seq || index + 1).toLocaleString('fa-IR')} — {line.item_name_snapshot || '—'}
                </td>
                <td data-label="کالا">{line.item_code_snapshot || '—'}</td>
                <td className="num" data-label="مقدار">{faQty(line.qty)} {line.unit_snapshot}</td>
                <td className="num" data-label="فی">{faAmount(line.unit_cost)}</td>
                <td className="num" data-label="سهم حمل">{faAmount(line.freight_share)}</td>
                <td className="num" data-label="فی تمام‌شده">{faAmount(Math.round(Number(line.landed_unit_cost)))}</td>
                <td className="num" data-label="مالیات">{faAmount(line.tax_amount_snapshot)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ───────────────────────────── برگشتِ رسید ───────────────────────────── */

function ReceiptReturnPanel({
  token,
  receipt,
  contacts,
  warehouseName,
  onClose,
  onReturned,
}: {
  token: string
  receipt: WarehouseReceiptFull
  contacts: ContactRecord[]
  warehouseName: Map<string, string>
  onClose: () => void
  onReturned: () => void
}) {
  const [rows, setRows] = useState<ReceiptReturnableLine[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [qty, setQty] = useState<Record<string, string>>({})
  const [agreed, setAgreed] = useState<Record<string, string>>({})
  const [returnType, setReturnType] = useState(RETURN_TYPE_LABELS[receipt.receipt_type] ? receipt.receipt_type : 'purchase_domestic')
  const [returnDate, setReturnDate] = useState(todayIso())
  const [receiverId, setReceiverId] = useState(receipt.contact_id ?? '')
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const requestKey = useRef(newIdempotencyKey())

  const load = useCallback(async () => {
    try {
      setRows(await fetchReceiptReturnable(token, receipt.id))
      setError(null)
    } catch (err) {
      setError(errText(err, 'دریافتِ اقلامِ قابلِ برگشت ناموفق بود'))
    }
  }, [token, receipt.id])

  useEffect(() => {
    void load()
  }, [load])

  const anyReturnable = (rows ?? []).some((row) => Number(row.remaining) > 0)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setMsg(null)
    const lines = (rows ?? [])
      .filter((row) => num(qty[row.warehouse_receipt_line_id] ?? '') > 0)
      .map((row) => {
        const agreedValue = agreed[row.warehouse_receipt_line_id]
        return {
          warehouse_receipt_line_id: row.warehouse_receipt_line_id,
          qty: num(qty[row.warehouse_receipt_line_id] ?? ''),
          agreed_unit_value: agreedValue ? num(agreedValue) : null,
        }
      })
    if (lines.length === 0) return setMsg({ text: 'مقدارِ برگشتِ دست‌کم یک ردیف را وارد کنید.', kind: 'err' })
    setBusy(true)
    try {
      const ret = await createReceiptReturn(
        token,
        {
          return_date: returnDate,
          warehouse_receipt_id: receipt.id,
          receiver_id: receiverId || null,
          return_type: returnType,
          description,
          lines,
        },
        requestKey.current,
      )
      requestKey.current = newIdempotencyKey()
      setMsg({
        text: `برگشت شماره ${(ret.number ?? 0).toLocaleString('fa-IR')} ثبت شد؛ رسیدِ اصلی دست نخورد و باقیمانده‌ها به‌روز شدند.`,
        kind: 'ok',
      })
      setQty({})
      setAgreed({})
      await load()
      onReturned()
    } catch (err) {
      setMsg({ text: errText(err, 'ثبت برگشت ناموفق بود'), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={Undo2}
      title={`برگشت رسید انبار شماره ${receipt.number.toLocaleString('fa-IR')}`}
      description={`کالا از «${warehouseName.get(receipt.warehouse_id) ?? 'انبار'}» خارج می‌شود و رسیدِ اصلی دست نمی‌خورد؛ هر ردیف فقط تا باقیمانده‌اش برگشت می‌خورد.`}
      actions={
        <button type="button" onClick={onClose}>
          <X size={13} /> بستن
        </button>
      }
    >
      <AsyncBlock loading={rows === null && !error} error={error}>
        <form className="invoice-form" onSubmit={(event) => void submit(event)}>
          <label>
            نوع برگشت
            <SearchSelect value={returnType} onChange={(e) => setReturnType(e.target.value)}>
              {Object.entries(RETURN_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </SearchSelect>
          </label>
          <label>
            تاریخ برگشت
            <JalaliDatePicker value={returnDate} onChange={setReturnDate} />
          </label>
          <label>
            تحویل‌گیرنده
            <SearchSelect value={receiverId} onChange={(e) => setReceiverId(e.target.value)}>
              <option value="">— بدونِ تحویل‌گیرنده (نقدی) —</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </SearchSelect>
          </label>
          <label>
            توضیحات
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          {!anyReturnable ? (
            <p className="hint form-wide">همه‌ی اقلامِ این رسید کامل برگشت خورده‌اند.</p>
          ) : (
            <div className="table-scroll form-wide">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>کالا</th>
                    <th>مقدار رسید</th>
                    <th>برگشت‌شده</th>
                    <th>باقیمانده</th>
                    <th>وضعیت</th>
                    <th>فی</th>
                    <th>فی تمام‌شده</th>
                    <th>مقدار برگشت</th>
                    <th>فیِ توافقی</th>
                  </tr>
                </thead>
                <tbody>
                  {(rows ?? []).map((row) => {
                    const id = row.warehouse_receipt_line_id
                    const closed = Number(row.remaining) <= 0
                    return (
                      <tr key={id} style={closed ? { opacity: 0.55 } : undefined}>
                        <td className="card-title">{row.item_name}{row.item_code ? ` — ${row.item_code}` : ''}</td>
                        <td className="num" data-label="مقدار رسید">{faQty(row.received)} {row.unit}</td>
                        <td className="num" data-label="برگشت‌شده">{faQty(row.already_returned)}</td>
                        <td className="num" data-label="باقیمانده"><strong>{faQty(row.remaining)}</strong></td>
                        <td data-label="وضعیت">{RETURN_STATUS_LABELS[row.return_status]}</td>
                        <td className="num" data-label="فی">{faAmount(row.unit_cost)}</td>
                        <td className="num" data-label="فی تمام‌شده">{faAmount(Math.round(Number(row.landed_unit_cost)))}</td>
                        <td data-label="مقدار برگشت">
                          <NumberInput
                            allowDecimal
                            value={qty[id] ?? ''}
                            onChange={(value) => setQty((old) => ({ ...old, [id]: value }))}
                          />
                        </td>
                        <td data-label="فیِ توافقی">
                          <NumberInput value={agreed[id] ?? ''} onChange={(value) => setAgreed((old) => ({ ...old, [id]: value }))} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <p className="hint form-wide">
            «فیِ توافقی» را خالی بگذارید تا برگشت به همان فیِ تمام‌شده ثبت شود. اگر با تأمین‌کننده مبلغِ دیگری توافق
            شده، ثبت رد می‌شود — سیاستِ حسابداریِ اختلافِ این دو هنوز تعریف نشده و کوبیتا حسابی برایش اختراع نمی‌کند.
          </p>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !anyReturnable}>
              <Save size={14} /> ثبتِ برگشت
            </button>
          </div>
        </form>
        <Note msg={msg} />
      </AsyncBlock>
    </SectionCard>
  )
}
