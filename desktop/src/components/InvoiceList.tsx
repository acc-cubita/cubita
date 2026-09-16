import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { Ban, FileText, Printer, FileDown, ChevronDown, ChevronLeft, Copy, PackageCheck, CreditCard } from 'lucide-react'
import {
  can,
  createWarehouseIssueIdempotent,
  createWarehouseReceiptIdempotent,
  downloadPurchaseInvoicePdf,
  downloadSalesInvoicePdf,
  fetchContacts,
  fetchWarehouseIssues,
  fetchWarehouseReceipts,
  fetchPurchaseInvoices,
  fetchPurchaseInvoicesOfKind,
  fetchSalesInvoices,
  newIdempotencyKey,
  printPurchaseInvoice,
  printSalesInvoice,
  issueSalesInvoiceJournal,
  voidPurchaseInvoice,
  voidSalesInvoice,
  voidWarehouseReceipt,
  voidWarehouseIssue,
  type ContactRecord,
  type MeResponse,
  type PurchaseInvoiceKind,
  type PurchaseInvoiceRecord,
  type SalesInvoiceRecord,
  type WarehouseReceiptRecord,
  type WarehouseIssueRecord,
} from '../api'
import type { WarehouseCache } from '../electron.d'
import { JalaliDatePicker } from './JalaliDatePicker'
import { NumberInput } from './NumberInput'
import { todayIso } from '../lib/jalali'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'
import { JournalEntryDrawer } from './JournalEntryDrawer'

export type AnyInvoice = SalesInvoiceRecord | PurchaseInvoiceRecord
type NamedItem = { id: string; name: string }

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

/** فهرست فاکتورها با جزئیاتِ بازشونده، سودِ ناخالص (فروش)، چاپ، PDF، ابطال و رونوشت.
 *
 * تا امروز فاکتور ثبت‌شده فقط خلاصه فهرست می‌شد؛ برای دیدنِ اقلام باید چاپ می‌کردی و
 * سود هیچ‌جا دیده نمی‌شد. حالا هر ردیف باز می‌شود و ردیف‌ها + بهای تمام‌شده + سود را
 * نشان می‌دهد.
 */
export function InvoiceList({
  token,
  me,
  kind,
  items,
  onDuplicate,
  warehouses = [],
  onCreatePayment,
  purchaseKind,
}: {
  token: string
  me: MeResponse
  kind: 'sales' | 'purchase'
  items: NamedItem[]
  /** رونوشتِ فاکتور — فرمِ فاکتور (فروش یا خرید) را با اقلامِ همین فاکتور پیش‌پر می‌کند. */
  onDuplicate?: (invoice: AnyInvoice) => void
  warehouses?: WarehouseCache[]
  onCreatePayment?: (invoice: PurchaseInvoiceRecord) => void
  /** فقط برای خرید: `goods` = فاکتور خرید، `service` = فاکتور خرید خدمات. خالی = هر دو. */
  purchaseKind?: PurchaseInvoiceKind
}) {
  const isSales = kind === 'sales'
  const isService = !isSales && purchaseKind === 'service'
  const docLabel = isSales ? 'فاکتور فروش' : isService ? 'فاکتور خرید خدمات' : 'فاکتور خرید'
  const [rows, setRows] = useState<AnyInvoice[] | null>(null)
  const [contactNames, setContactNames] = useState<Map<string, string>>(new Map())
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [journalEntryId, setJournalEntryId] = useState<string | null>(null)

  const canVoid = can(me, 'invoices', 'delete')
  const canVoidWarehouseReceipt = can(me, 'accounting', 'delete')
  const canIssueSalesJournal = can(me, 'accounting', 'create')
  const canCreateWarehouseIssue = can(me, 'inventory', 'create')
  const itemName = (id: string) => items.find((i) => i.id === id)?.name ?? id
  //: فاکتور خرید خدمات چهار ستونِ بیشتر دارد — مالیات تکلیفی، بیمه، خالصِ پرداختنی و
  //: سند؛ فصل می‌گوید کسورات در فهرست هم باید دیده و جمع شوند، نه فقط در جزئیات.
  const columnCount = isSales ? 8 : isService ? 11 : 7
  // صفحه‌بندیِ فهرستِ فاکتورها (۱۰ در هر صفحه)؛ با تعویضِ نوع (فروش/خرید) به اولِ فهرست برمی‌گردد.
  const pg = usePagination(rows ?? [], 10, kind)

  async function refresh() {
    try {
      const data = isSales
        ? await fetchSalesInvoices(token)
        : purchaseKind
          ? await fetchPurchaseInvoicesOfKind(token, purchaseKind)
          : await fetchPurchaseInvoices(token)
      setRows(data)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    fetchContacts(token)
      .then((rows: ContactRecord[]) => setContactNames(new Map(rows.map((c) => [c.id, c.name]))))
      .catch(() => setContactNames(new Map()))
  }, [token, kind, purchaseKind])

  function partyLabel(row: AnyInvoice): string {
    if (!row.contact_id) return isSales ? 'مشتری نقدی' : 'تأمین‌کننده نقدی'
    return contactNames.get(row.contact_id) ?? '—'
  }

  async function handlePrint(id: string) {
    setMessage(null)
    try {
      await (isSales ? printSalesInvoice(token, id) : printPurchaseInvoice(token, id))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handlePdf(row: AnyInvoice) {
    setMessage(null)
    try {
      await (isSales
        ? downloadSalesInvoicePdf(token, row.id, row.number)
        : downloadPurchaseInvoicePdf(token, row.id, row.number))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleIssueJournal(row: SalesInvoiceRecord) {
    setBusy(true)
    setMessage(null)
    try {
      const updated = await issueSalesInvoiceJournal(token, row.id)
      setMessage('سند حسابداری فروش صادر شد؛ هیچ حرکت انبار یا وصولی ساخته نشد.')
      setJournalEntryId(updated.journal_entry_id)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'صدور سند حسابداری ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  async function handleVoid(row: AnyInvoice) {
    // دلیل اجباری است و سرور هم آن را الزام می‌کند؛ اینجا فقط زودتر پرسیده می‌شود
    // تا کاربر بعد از یک رفت‌وبرگشت شبکه پیام خطا نگیرد.
    const reason = window.prompt(
      `ابطال ${docLabel} شماره ${row.number}؟\n\n` +
        'فاکتور پاک نمی‌شود؛ یک سند معکوس ثبت می‌شود و اثر مالی و انباری‌اش برمی‌گردد.\n' +
        'دلیل ابطال:',
    )
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMessage('دلیل ابطال باید نوشته شود.')
      return
    }

    setBusy(true)
    setMessage(null)
    try {
      const res = await (isSales
        ? voidSalesInvoice(token, row.id, reason)
        : voidPurchaseInvoice(token, row.id, reason))
      setMessage(res.reversal_entry_id
        ? `فاکتور باطل شد. سند معکوس شماره ${res.reversal_entry_number} ثبت شد.`
        : 'فاکتور سندنشده با ثبت دلیل لغو شد؛ چون اثر حسابداری نداشت، سند معکوس ساخته نشد.')
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'ابطال ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={FileText}
      title={isSales ? 'فاکتورهای فروش' : isService ? 'فاکتورهای خرید خدمات' : 'فاکتورهای خرید'}
      description={
        isService
          ? 'مبلغ = جمعِ فاکتور؛ «خالص پرداختنی» پس از کسرِ مالیات تکلیفی و بیمه است و مانده و اعلامیه‌ی پرداخت از همان حساب می‌شوند. برای اصلاح، فاکتور را باطل کنید.'
          : 'روی هر ردیف بزنید تا اقلام و جزئیات باز شود. برای اصلاح اشتباه، فاکتور را باطل کنید — حذف نمی‌شود و سند معکوسش ثبت می‌گردد.'
      }
    >
      {message && <div className="hint">{message}</div>}

      {rows == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={FileText} text="هنوز فاکتوری ثبت نشده." />
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile">
          <thead>
            <tr>
              <th style={{ width: 28 }}></th>
              <th>شماره</th>
              <th>تاریخ</th>
              <th>طرف حساب</th>
              <th>مبلغ</th>
              {isSales && <th>سود ناخالص</th>}
              {isService && <th>مالیات تکلیفی</th>}
              {isService && <th>بیمه</th>}
              {isService && <th>خالص پرداختنی</th>}
              {isService && <th>سند حسابداری</th>}
              <th>وضعیت</th>
              <th>عملیات</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((row) => {
              const isOpen = expanded === row.id
              const net = Number(row.total_amount)
              const rounding = isSales ? Number((row as SalesInvoiceRecord).rounding) : 0
              const grand = isSales ? Number((row as SalesInvoiceRecord).final_amount) : net + Number(row.tax_amount) + rounding
              const profit = isSales ? net - Number((row as SalesInvoiceRecord).total_cost) : 0
              const margin = isSales && net > 0 ? (profit / net) * 100 : 0
              const journalId = isSales
                ? (row as SalesInvoiceRecord).journal_entry_id
                : (row as PurchaseInvoiceRecord).journal_entry_id
              return (
              <Fragment key={row.id}>
              <tr
                style={row.voided_at ? { opacity: 0.55 } : undefined}
                className="invoice-row"
                onClick={() => setExpanded(isOpen ? null : row.id)}
              >
                <td className="card-hide">{isOpen ? <ChevronDown size={15} /> : <ChevronLeft size={15} />}</td>
                <td data-label="شماره">{row.number ?? '—'}</td>
                <td data-label="تاریخ">{formatJalali(row.invoice_date)}</td>
                <td className="entity-name card-title" data-label="طرف حساب">{partyLabel(row)}</td>
                <td
                  data-label="مبلغ"
                  title={
                    Number(row.tax_amount) > 0
                      ? `خالص ${fa(net)} + مالیات ${fa(Number(row.tax_amount))}`
                      : undefined
                  }
                >
                  {fa(grand)}
                </td>
                {isSales && (
                  <td data-label="سود" className={profit >= 0 ? 'stock-ok' : 'stock-over'}>
                    {fa(profit)}
                    <span className="unit-suffix"> ({margin.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)</span>
                  </td>
                )}
                {isService && (
                  <td className="num" data-label="مالیات تکلیفی">
                    {Number((row as PurchaseInvoiceRecord).withholding_total) ? fa(Number((row as PurchaseInvoiceRecord).withholding_total)) : '—'}
                  </td>
                )}
                {isService && (
                  <td className="num" data-label="بیمه">
                    {Number((row as PurchaseInvoiceRecord).insurance_total) ? fa(Number((row as PurchaseInvoiceRecord).insurance_total)) : '—'}
                  </td>
                )}
                {isService && (
                  <td className="num" data-label="خالص پرداختنی">{fa(Number((row as PurchaseInvoiceRecord).payable_amount))}</td>
                )}
                {isService && (
                  <td data-label="سند حسابداری">
                    {(row as PurchaseInvoiceRecord).journal_entry_number
                      ? `${(row as PurchaseInvoiceRecord).journal_entry_number!.toLocaleString('fa-IR')}${(row as PurchaseInvoiceRecord).journal_entry_date ? ` — ${formatJalali((row as PurchaseInvoiceRecord).journal_entry_date!)}` : ''}`
                      : '—'}
                  </td>
                )}
                <td data-label="وضعیت">
                  {row.voided_at ? <span title={row.void_reason}>باطل شده</span> : isSales ? (
                    <span>
                      {({ unposted: 'سندنشده', posted: 'سندشده' } as const)[(row as SalesInvoiceRecord).accounting_status]}
                      {' / '}
                      {({ not_applicable: 'بدون خروج', not_issued: 'خروج‌نشده', partially_issued: 'خروج جزئی', fully_issued: 'خروج کامل' } as const)[(row as SalesInvoiceRecord).fulfillment_status]}
                      {' / '}
                      {({ unsettled: 'تسویه‌نشده', partially_settled: 'تسویه جزئی', fully_settled: 'تسویه کامل' } as const)[(row as SalesInvoiceRecord).financial_status]}
                    </span>
                  ) : (
                    <span>
                      {/* فاکتوری که کالایی برای تحویل ندارد (فقط خدمت) وضعیتِ تحویل ندارد. */}
                      {(row as PurchaseInvoiceRecord).inventory_status !== 'not_applicable' && (
                        <>
                          {({ not_received: 'تحویل‌نشده', partially_received: 'تحویل جزئی', fully_received: 'تحویل کامل', not_applicable: '' } as const)[(row as PurchaseInvoiceRecord).inventory_status]}
                          {' / '}
                        </>
                      )}
                      {({ unsettled: 'تسویه‌نشده', partially_settled: 'تسویه جزئی', fully_settled: 'تسویه کامل' } as const)[(row as PurchaseInvoiceRecord).financial_status]}
                    </span>
                  )}
                </td>
                <td className="card-actions" onClick={(e) => e.stopPropagation()} data-label="عملیات">
                  <div className="check-actions">
                    <button type="button" onClick={() => void handlePrint(row.id)}>
                      <Printer size={13} /> چاپ
                    </button>
                    <button type="button" onClick={() => void handlePdf(row)}>
                      <FileDown size={13} /> PDF
                    </button>
                    {journalId && (
                      <button type="button" onClick={() => setJournalEntryId(journalId)}>
                        <FileText size={13} /> سند حسابداری
                      </button>
                    )}
                    {isSales && !journalId && !row.voided_at && canIssueSalesJournal && (
                      <button type="button" disabled={busy} onClick={() => void handleIssueJournal(row as SalesInvoiceRecord)}>
                        <FileText size={13} /> صدور سند حسابداری
                      </button>
                    )}
                    {onDuplicate && !row.voided_at && (
                      <button type="button" onClick={() => onDuplicate(row)}>
                        <Copy size={13} /> رونوشت
                      </button>
                    )}
                    {!isSales && !row.voided_at && Number((row as PurchaseInvoiceRecord).remaining_amount) > 0 && onCreatePayment && (
                      <button type="button" onClick={() => onCreatePayment(row as PurchaseInvoiceRecord)}>
                        <CreditCard size={13} /> اعلامیه پرداخت
                      </button>
                    )}
                    {canVoid && !row.voided_at && (
                      <button
                        type="button"
                        className="icon-btn-danger"
                        disabled={busy}
                        onClick={() => void handleVoid(row)}
                      >
                        <Ban size={13} /> ابطال
                      </button>
                    )}
                  </div>
                </td>
              </tr>
              {isOpen && (
                <tr className="invoice-detail-row">
                  <td className="card-full" colSpan={columnCount}>
                    <InvoiceDetail row={row} isSales={isSales} itemName={itemName} token={token} warehouses={warehouses} canVoidWarehouseReceipt={canVoidWarehouseReceipt} canCreateWarehouseIssue={canCreateWarehouseIssue} onChanged={refresh} />
                  </td>
                </tr>
              )}
              </Fragment>
              )
            })}
          </tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
      {journalEntryId && (
        <JournalEntryDrawer token={token} entryId={journalEntryId} onClose={() => setJournalEntryId(null)} />
      )}
    </SectionCard>
  )
}

/** جزئیاتِ یک فاکتور — اقلام، جمع‌ها، و کنش‌های چاپ/PDF/سند/ابطال/خروجِ انبار.
 *
 *  **صادر شده تا `SalesInvoiceListPage` هم بتواند صدایش بزند.** آن صفحه فیلتر
 *  دارد و جزئیات نداشت؛ این کامپوننت جزئیات داشت و فیلتر نه — و شاخه‌ی
 *  `isSales`ش سال‌ها نوشته بود و هرگز اجرا نشد، چون هر دو فراخوانِ
 *  `InvoiceList` خرید بودند. نسخه‌ی دومی از این نشانه‌گذاری ساخته نشد. */
export function InvoiceDetail({
  row,
  isSales,
  itemName,
  token,
  warehouses,
  canVoidWarehouseReceipt,
  canCreateWarehouseIssue,
  onChanged,
}: {
  row: AnyInvoice
  isSales: boolean
  itemName: (id: string) => string
  token: string
  warehouses: WarehouseCache[]
  canVoidWarehouseReceipt: boolean
  canCreateWarehouseIssue: boolean
  onChanged: () => Promise<void>
}) {
  const net = Number(row.total_amount)
  const tax = Number(row.tax_amount)
  const discount = Number(row.total_discount)
  const headerDiscount = Number(row.invoice_discount) // هر دو نوع (فروش/خرید) این را دارند
  const rounding = isSales ? Number((row as SalesInvoiceRecord).rounding) : 0
  const additions = Number(row.total_additions)
  const duties = Number(row.total_duties)
  const cost = isSales ? Number((row as SalesInvoiceRecord).total_cost) : 0
  const profit = net - cost
  const margin = net > 0 ? (profit / net) * 100 : 0

  const creator = row.created_by_name
    ? `${row.created_by_name}${row.created_by_role ? ` (${row.created_by_role})` : ''}`
    : null

  //: واسطه و کارمزدش فقط در فاکتور فروش معنا دارند. مبلغ همان چیزی است که در
  //: لحظه‌ی ثبت قفل شده، نه محاسبه‌ی دوباره از نرخِ امروزِ واسطه.
  const brokerName = isSales ? (row as SalesInvoiceRecord).broker_name : null
  const brokerCommission = isSales ? Number((row as SalesInvoiceRecord).broker_commission) : 0
  const salespersonName = isSales ? (row as SalesInvoiceRecord).salesperson_name : null
  const saleTypeName = isSales ? (row as SalesInvoiceRecord).sale_type_name : null

  return (
    <div className="invoice-detail">
      {creator && <div className="invoice-detail-desc">ثبت‌کننده: {creator}</div>}
      {salespersonName && (
        <div className="invoice-detail-desc">
          فروشنده: {salespersonName}
          {saleTypeName && ` — نوع فروش: ${saleTypeName}`}
        </div>
      )}
      {!salespersonName && saleTypeName && (
        <div className="invoice-detail-desc">نوع فروش: {saleTypeName}</div>
      )}
      {brokerName && (
        <div className="invoice-detail-desc">
          واسطه: {brokerName}
          {brokerCommission > 0 && ` — کارمزد: ${fa(brokerCommission)}`}
        </div>
      )}
      {row.description && <div className="invoice-detail-desc">شرح: {row.description}</div>}
      {isSales && (row as SalesInvoiceRecord).customer_name2 && (
        <div className="invoice-detail-desc">نام دوم مشتری: {(row as SalesInvoiceRecord).customer_name2}</div>
      )}
      {isSales && (row as SalesInvoiceRecord).delivery_location && (
        <div className="invoice-detail-desc">محل تحویل: {(row as SalesInvoiceRecord).delivery_location}</div>
      )}
      {isSales && (
        <div className="invoice-detail-desc">
          شرایط تسویه: {({ cash: 'نقدی', credit: 'نسیه', mixed: 'نقدی/نسیه' } as const)[(row as SalesInvoiceRecord).settlement_terms]}
          {(row as SalesInvoiceRecord).statement_date && ` — سررسید: ${formatJalali((row as SalesInvoiceRecord).statement_date!)}`}
        </div>
      )}
      {!isSales && (row as PurchaseInvoiceRecord).supplier_invoice_number && (
        <div className="invoice-detail-desc">شماره فاکتور تأمین‌کننده: {(row as PurchaseInvoiceRecord).supplier_invoice_number}</div>
      )}
      {!isSales && (row as PurchaseInvoiceRecord).related_payment_count > 0 && (
        <div className="invoice-detail-desc">
          اعلامیه‌های پرداخت فعالِ مرتبط: {(row as PurchaseInvoiceRecord).related_payment_count.toLocaleString('fa-IR')}
        </div>
      )}
      <div className="table-scroll">
        <table className="invoice-detail-table cards-on-mobile">
          <thead>
            <tr>
              <th>کالا</th>
              {!isSales && <th>معین هزینه</th>}
              <th>تعداد</th>
              <th>{isSales ? 'قیمت واحد' : 'بهای واحد'}</th>
              <th>تخفیف</th>
              {isSales && <th>اضافات/عوارض</th>}
              <th>خالص</th>
              {isSales && <th>بهای تمام‌شده</th>}
              {isSales && <th>سود</th>}
            </tr>
          </thead>
          <tbody>
            {row.lines.map((line) => {
              const qty = Number(line.qty)
              const price = isSales ? Number((line as SalesInvoiceRecord['lines'][number]).unit_price) : Number((line as PurchaseInvoiceRecord['lines'][number]).unit_cost)
              const lineDiscount = Number(line.discount)
              const lineNet = qty * price - lineDiscount
              const unitCost = isSales ? Number((line as SalesInvoiceRecord['lines'][number]).unit_cost) : 0
              const lineCost = qty * unitCost
              const lineProfit = lineNet - lineCost
              const purchaseLine = line as PurchaseInvoiceRecord['lines'][number]
              return (
                <tr key={line.id}>
                  <td className="entity-name" data-label="کالا">{itemName(line.item_id)}</td>
                  {!isSales && (
                    <td data-label="معین هزینه">
                      {/* Snapshotِ لحظه‌ی ثبت؛ برای کالا خالی است چون بهایش به موجودی نشسته. */}
                      {purchaseLine.expense_account_name
                        ? `${purchaseLine.expense_account_code} — ${purchaseLine.expense_account_name}`
                        : '—'}
                    </td>
                  )}
                  <td data-label="تعداد">{qty.toLocaleString('fa-IR')}</td>
                  <td data-label={isSales ? 'قیمت واحد' : 'بهای واحد'}>{fa(price)}</td>
                  <td data-label="تخفیف">{lineDiscount ? fa(lineDiscount) : '—'}</td>
                  {isSales && <td data-label="اضافات/عوارض">{fa(Number(line.addition) + Number(line.duty_amount))}</td>}
                  <td data-label="خالص">{fa(lineNet)}</td>
                  {isSales && <td data-label="بهای تمام‌شده">{fa(lineCost)}</td>}
                  {isSales && <td className={lineProfit >= 0 ? 'stock-ok' : 'stock-over'} data-label="سود">{fa(lineProfit)}</td>}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="invoice-detail-totals">
        {discount > 0 && <span>جمع تخفیف: {fa(discount)}</span>}
        {headerDiscount > 0 && <span>از آن، تخفیف کل فاکتور: {fa(headerDiscount)}</span>}
        <span>جمع خالص: {fa(net)}</span>
        {additions > 0 && <span>اضافات: {fa(additions)}</span>}
        {duties > 0 && <span>عوارض: {fa(duties)}</span>}
        {tax > 0 && <span>مالیات: {fa(tax)}</span>}
        {rounding !== 0 && <span>گِرد کردن: {fa(rounding)}</span>}
        {!isSales && (row as PurchaseInvoiceRecord).deductions?.length > 0 ? (
          <>
            {/* با کسورات، جمعِ فاکتور و بدهی به تأمین‌کننده دو عددند (فصلِ خرید خدمات §۲۷). */}
            <span>جمع فاکتور: {fa(Number((row as PurchaseInvoiceRecord).final_amount))}</span>
            {(row as PurchaseInvoiceRecord).deductions.map((d) => (
              <span key={d.id} title={`${d.account_code} — ${d.account_name}`}>
                {d.name_snapshot} ({Number(d.rate).toLocaleString('fa-IR', { maximumFractionDigits: 3 })}٪ از {fa(Number(d.basis_amount))}) (−): {fa(Number(d.amount))}
              </span>
            ))}
            <span>قابل پرداخت به تأمین‌کننده: <strong>{fa(Number((row as PurchaseInvoiceRecord).payable_amount))}</strong></span>
          </>
        ) : (
          <span>قابل پرداخت: <strong>{fa(net + additions + duties + tax + rounding)}</strong></span>
        )}
        {!isSales && Number((row as PurchaseInvoiceRecord).settled_amount) > 0 && (
          <span>تسویه‌شده: {fa(Number((row as PurchaseInvoiceRecord).settled_amount))} — مانده: {fa(Number((row as PurchaseInvoiceRecord).remaining_amount))}</span>
        )}
        {!isSales && (row as PurchaseInvoiceRecord).journal_entry_number && (
          <span>
            سند حسابداری: {(row as PurchaseInvoiceRecord).journal_entry_number!.toLocaleString('fa-IR')}
            {(row as PurchaseInvoiceRecord).journal_entry_date && ` — ${formatJalali((row as PurchaseInvoiceRecord).journal_entry_date!)}`}
          </span>
        )}
        {isSales && <span>بهای تمام‌شده: {fa(cost)}</span>}
        {isSales && (
          <span className={profit >= 0 ? 'stock-ok' : 'stock-over'}>
            سود ناخالص: <strong>{fa(profit)}</strong> ({margin.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)
          </span>
        )}
      </div>
      {/* خدمت رسید انبار ندارد: فاکتوری که کالایی برای تحویل ندارد ویرایشگرِ رسید هم ندارد. */}
      {!isSales && !row.voided_at && (row as PurchaseInvoiceRecord).inventory_status !== 'not_applicable' && (
        <WarehouseReceiptEditor
          token={token}
          invoice={row as PurchaseInvoiceRecord}
          warehouses={warehouses}
          canVoid={canVoidWarehouseReceipt}
          onCreated={onChanged}
        />
      )}
      {isSales && !row.voided_at && (
        <WarehouseIssueEditor
          token={token}
          invoice={row as SalesInvoiceRecord}
          warehouses={warehouses}
          canCreate={canCreateWarehouseIssue}
          canVoid={canVoidWarehouseReceipt}
          onChanged={onChanged}
        />
      )}
    </div>
  )
}

function WarehouseIssueEditor({
  token,
  invoice,
  warehouses,
  canCreate,
  canVoid,
  onChanged,
}: {
  token: string
  invoice: SalesInvoiceRecord
  warehouses: WarehouseCache[]
  canCreate: boolean
  canVoid: boolean
  onChanged: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [warehouseId, setWarehouseId] = useState(invoice.warehouse_id ?? warehouses[0]?.id ?? '')
  const [issueDate, setIssueDate] = useState(todayIso())
  const [qty, setQty] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [issues, setIssues] = useState<WarehouseIssueRecord[] | null>(null)
  const requestKey = useRef(newIdempotencyKey())
  const pending = invoice.lines.filter((line) => Number(line.remaining_issueable_qty) > 0)

  const refreshIssues = useCallback(async () => {
    try {
      setIssues(await fetchWarehouseIssues(token, invoice.id))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'دریافت سابقه خروج‌های انبار ناموفق بود')
    }
  }, [token, invoice.id])

  useEffect(() => {
    void refreshIssues()
  }, [refreshIssues])

  async function submit() {
    const lines = pending
      .map((line) => ({ sales_invoice_line_id: line.id, qty: Number(qty[line.id] ?? line.remaining_issueable_qty) }))
      .filter((line) => line.qty > 0)
    if (!warehouseId || lines.length === 0) {
      setMessage('انبار و حداقل یک مقدار خروج لازم است.')
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      await createWarehouseIssueIdempotent(
        token,
        invoice.id,
        { issue_date: issueDate, warehouse_id: warehouseId, lines },
        requestKey.current,
      )
      requestKey.current = newIdempotencyKey()
      setMessage('خروج مستقل انبار ثبت و بهای تمام‌شده همان خروج صادر شد.')
      await refreshIssues()
      await onChanged()
      setOpen(false)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ثبت خروج انبار ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  async function handleVoid(issue: WarehouseIssueRecord) {
    const reason = window.prompt(`ابطال خروج انبار شماره ${issue.number.toLocaleString('fa-IR')}؟\nدلیل ابطال:`)
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMessage('دلیل ابطال باید نوشته شود.')
      return
    }
    setBusy(true)
    try {
      await voidWarehouseIssue(token, issue.id, reason)
      setMessage('خروج انبار با حرکت و سند جبرانی باطل شد.')
      await refreshIssues()
      await onChanged()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ابطال خروج انبار ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="invoice-adjustments">
      {canCreate && (
        <button type="button" onClick={() => setOpen((value) => !value)} disabled={pending.length === 0}>
          <PackageCheck size={14} /> {pending.length ? 'صدور خروج انبار' : 'خروج کامل شده'}
        </button>
      )}
      {open && (
        <div className="invoice-form">
          <p className="hint">فقط این سند، موجودی کالا و بهای تمام‌شده را تغییر می‌دهد؛ خدمات در این فهرست نمی‌آیند.</p>
          <label>انبار<select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}><option value="">— انتخاب کنید —</option>{warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}</select></label>
          <label>تاریخ خروج<JalaliDatePicker value={issueDate} onChange={setIssueDate} /></label>
          {pending.map((line) => (
            <label key={line.id}>
              {line.item_name_snapshot || itemNameFallback(line.item_id)} — مانده {Number(line.remaining_issueable_qty).toLocaleString('fa-IR')} {line.unit_snapshot}
              <NumberInput allowDecimal value={qty[line.id] ?? String(Number(line.remaining_issueable_qty))} onChange={(value) => setQty((old) => ({ ...old, [line.id]: value }))} />
            </label>
          ))}
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void submit()}>ثبت خروج</button>
        </div>
      )}
      {issues && issues.length > 0 && (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead><tr><th>شماره خروج</th><th>تاریخ</th><th>انبار</th><th>مقدار</th><th>وضعیت</th><th>عملیات</th></tr></thead>
            <tbody>{issues.map((issue) => (
              <tr key={issue.id} style={issue.voided_at ? { opacity: 0.55 } : undefined}>
                <td data-label="شماره خروج">{issue.number.toLocaleString('fa-IR')}</td>
                <td data-label="تاریخ">{formatJalali(issue.issue_date)}</td>
                <td data-label="انبار">{warehouses.find((warehouse) => warehouse.id === issue.warehouse_id)?.name ?? '—'}</td>
                <td data-label="مقدار">{issue.lines.reduce((sum, line) => sum + Number(line.qty), 0).toLocaleString('fa-IR')}</td>
                <td data-label="وضعیت">{issue.voided_at ? 'باطل‌شده' : 'معتبر'}</td>
                <td className="card-actions" data-label="عملیات">
                  {canVoid && !issue.voided_at ? <button type="button" className="icon-btn-danger" disabled={busy} onClick={() => void handleVoid(issue)}><Ban size={13} /> ابطال خروج</button> : '—'}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {message && <span className="hint">{message}</span>}
    </div>
  )
}

function WarehouseReceiptEditor({
  token,
  invoice,
  warehouses,
  canVoid,
  onCreated,
}: {
  token: string
  invoice: PurchaseInvoiceRecord
  warehouses: WarehouseCache[]
  canVoid: boolean
  onCreated: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id ?? '')
  const [receiptDate, setReceiptDate] = useState(todayIso())
  const [qty, setQty] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [receipts, setReceipts] = useState<WarehouseReceiptRecord[] | null>(null)
  const requestKey = useRef(newIdempotencyKey())
  const pending = invoice.lines.filter((line) => Number(line.remaining_qty) > 0)

  const refreshReceipts = useCallback(async () => {
    try {
      setReceipts(await fetchWarehouseReceipts(token, invoice.id))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'دریافت سابقه رسیدهای انبار ناموفق بود')
    }
  }, [token, invoice.id])

  useEffect(() => {
    void refreshReceipts()
  }, [refreshReceipts])

  async function submit() {
    const lines = pending
      .map((line) => ({ purchase_invoice_line_id: line.id, qty: Number(qty[line.id] ?? line.remaining_qty) }))
      .filter((line) => line.qty > 0)
    if (!warehouseId || lines.length === 0) {
      setMessage('انبار و حداقل یک مقدار تحویل لازم است.')
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      await createWarehouseReceiptIdempotent(
        token,
        invoice.id,
        { receipt_date: receiptDate, warehouse_id: warehouseId, lines },
        requestKey.current,
      )
      requestKey.current = newIdempotencyKey()
      setMessage('رسید انبار مستقل ثبت شد و موجودی به‌روز شد.')
      await refreshReceipts()
      await onCreated()
      setOpen(false)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ثبت رسید ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  async function handleVoid(receipt: WarehouseReceiptRecord) {
    const reason = window.prompt(
      `ابطال رسید انبار شماره ${receipt.number.toLocaleString('fa-IR')}؟\n\n` +
        'رسید پاک نمی‌شود؛ یک حرکت جبرانی در کاردکس ثبت می‌شود.\nدلیل ابطال:',
    )
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMessage('دلیل ابطال باید نوشته شود.')
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      await voidWarehouseReceipt(token, receipt.id, reason)
      setMessage(`رسید انبار شماره ${receipt.number.toLocaleString('fa-IR')} باطل شد.`)
      await refreshReceipts()
      await onCreated()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ابطال رسید انبار ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="invoice-adjustments">
      <button type="button" onClick={() => setOpen((value) => !value)} disabled={pending.length === 0}>
        <PackageCheck size={14} /> {pending.length ? 'صدور رسید انبار' : 'تحویل کامل شده'}
      </button>
      {open && (
        <div className="invoice-form">
          <p className="hint">ثبت فاکتور به‌تنهایی موجودی را تغییر نمی‌دهد؛ فقط این رسید ورود فیزیکی می‌سازد.</p>
          <label>انبار<select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>{warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
          <label>تاریخ رسید<JalaliDatePicker value={receiptDate} onChange={setReceiptDate} /></label>
          {pending.map((line) => (
            <label key={line.id}>
              {line.item_name_snapshot || itemNameFallback(line.item_id)} — مانده {Number(line.remaining_qty).toLocaleString('fa-IR')} {line.unit_snapshot}
              <NumberInput allowDecimal value={qty[line.id] ?? String(Number(line.remaining_qty))} onChange={(value) => setQty((old) => ({ ...old, [line.id]: value }))} />
            </label>
          ))}
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void submit()}>ثبت رسید</button>
        </div>
      )}
      {receipts && receipts.length > 0 && (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead><tr><th>شماره رسید</th><th>تاریخ</th><th>انبار</th><th>مقدار</th><th>وضعیت</th><th>عملیات</th></tr></thead>
            <tbody>
              {receipts.map((receipt) => (
                <tr key={receipt.id} style={receipt.voided_at ? { opacity: 0.55 } : undefined}>
                  <td data-label="شماره رسید">{receipt.number.toLocaleString('fa-IR')}</td>
                  <td data-label="تاریخ">{formatJalali(receipt.receipt_date)}</td>
                  <td data-label="انبار">{warehouses.find((warehouse) => warehouse.id === receipt.warehouse_id)?.name ?? '—'}</td>
                  <td data-label="مقدار">{receipt.lines.reduce((sum, line) => sum + Number(line.qty), 0).toLocaleString('fa-IR')}</td>
                  <td data-label="وضعیت">{receipt.voided_at ? 'باطل‌شده' : 'معتبر'}</td>
                  <td className="card-actions" data-label="عملیات">
                    {canVoid && !receipt.voided_at ? (
                      <button type="button" className="icon-btn-danger" disabled={busy} onClick={() => void handleVoid(receipt)}>
                        <Ban size={13} /> ابطال رسید
                      </button>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {message && <span className="hint">{message}</span>}
    </div>
  )
}

const itemNameFallback = (id: string) => id
