import { Fragment, useEffect, useState } from 'react'
import { Ban, FileText, Printer, FileDown, ChevronDown, ChevronLeft, Copy } from 'lucide-react'
import {
  can,
  downloadPurchaseInvoicePdf,
  downloadSalesInvoicePdf,
  fetchContacts,
  fetchPurchaseInvoices,
  fetchSalesInvoices,
  printPurchaseInvoice,
  printSalesInvoice,
  voidPurchaseInvoice,
  voidSalesInvoice,
  type ContactRecord,
  type MeResponse,
  type PurchaseInvoiceRecord,
  type SalesInvoiceRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'

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
}: {
  token: string
  me: MeResponse
  kind: 'sales' | 'purchase'
  items: NamedItem[]
  /** رونوشتِ فاکتور — فرمِ فاکتور (فروش یا خرید) را با اقلامِ همین فاکتور پیش‌پر می‌کند. */
  onDuplicate?: (invoice: AnyInvoice) => void
}) {
  const isSales = kind === 'sales'
  const [rows, setRows] = useState<AnyInvoice[] | null>(null)
  const [contactNames, setContactNames] = useState<Map<string, string>>(new Map())
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  const canVoid = can(me, 'invoices', 'delete')
  const itemName = (id: string) => items.find((i) => i.id === id)?.name ?? id
  const columnCount = isSales ? 8 : 7
  // صفحه‌بندیِ فهرستِ فاکتورها (۱۰ در هر صفحه)؛ با تعویضِ نوع (فروش/خرید) به اولِ فهرست برمی‌گردد.
  const pg = usePagination(rows ?? [], 10, kind)

  async function refresh() {
    try {
      const data = isSales ? await fetchSalesInvoices(token) : await fetchPurchaseInvoices(token)
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
  }, [token, kind])

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

  async function handleVoid(row: AnyInvoice) {
    // دلیل اجباری است و سرور هم آن را الزام می‌کند؛ اینجا فقط زودتر پرسیده می‌شود
    // تا کاربر بعد از یک رفت‌وبرگشت شبکه پیام خطا نگیرد.
    const reason = window.prompt(
      `ابطال ${isSales ? 'فاکتور فروش' : 'فاکتور خرید'} شماره ${row.number}؟\n\n` +
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
      setMessage(`فاکتور باطل شد. سند معکوس شماره ${res.reversal_entry_number} ثبت شد.`)
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
      title={isSales ? 'فاکتورهای فروش' : 'فاکتورهای خرید'}
      description="روی هر ردیف بزنید تا اقلام و جزئیات باز شود. برای اصلاح اشتباه، فاکتور را باطل کنید — حذف نمی‌شود و سند معکوسش ثبت می‌گردد."
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
              <th>وضعیت</th>
              <th>عملیات</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((row) => {
              const isOpen = expanded === row.id
              const net = Number(row.total_amount)
              const rounding = isSales ? Number((row as SalesInvoiceRecord).rounding) : 0
              const grand = net + Number(row.tax_amount) + rounding
              const profit = isSales ? net - Number((row as SalesInvoiceRecord).total_cost) : 0
              const margin = isSales && net > 0 ? (profit / net) * 100 : 0
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
                <td data-label="وضعیت">
                  {row.voided_at ? <span title={row.void_reason}>باطل شده</span> : 'معتبر'}
                </td>
                <td className="card-actions" onClick={(e) => e.stopPropagation()} data-label="عملیات">
                  <div className="check-actions">
                    <button type="button" onClick={() => void handlePrint(row.id)}>
                      <Printer size={13} /> چاپ
                    </button>
                    <button type="button" onClick={() => void handlePdf(row)}>
                      <FileDown size={13} /> PDF
                    </button>
                    {onDuplicate && !row.voided_at && (
                      <button type="button" onClick={() => onDuplicate(row)}>
                        <Copy size={13} /> رونوشت
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
                    <InvoiceDetail row={row} isSales={isSales} itemName={itemName} />
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
    </SectionCard>
  )
}

function InvoiceDetail({
  row,
  isSales,
  itemName,
}: {
  row: AnyInvoice
  isSales: boolean
  itemName: (id: string) => string
}) {
  const net = Number(row.total_amount)
  const tax = Number(row.tax_amount)
  const discount = Number(row.total_discount)
  const headerDiscount = Number(row.invoice_discount) // هر دو نوع (فروش/خرید) این را دارند
  const rounding = isSales ? Number((row as SalesInvoiceRecord).rounding) : 0
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
      <div className="table-scroll">
        <table className="invoice-detail-table cards-on-mobile">
          <thead>
            <tr>
              <th>کالا</th>
              <th>تعداد</th>
              <th>{isSales ? 'قیمت واحد' : 'بهای واحد'}</th>
              <th>تخفیف</th>
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
              return (
                <tr key={line.id}>
                  <td className="entity-name" data-label="کالا">{itemName(line.item_id)}</td>
                  <td data-label="تعداد">{qty.toLocaleString('fa-IR')}</td>
                  <td data-label={isSales ? 'قیمت واحد' : 'بهای واحد'}>{fa(price)}</td>
                  <td data-label="تخفیف">{lineDiscount ? fa(lineDiscount) : '—'}</td>
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
        {tax > 0 && <span>مالیات: {fa(tax)}</span>}
        {rounding !== 0 && <span>گِرد کردن: {fa(rounding)}</span>}
        <span>قابل پرداخت: <strong>{fa(net + tax + rounding)}</strong></span>
        {isSales && <span>بهای تمام‌شده: {fa(cost)}</span>}
        {isSales && (
          <span className={profit >= 0 ? 'stock-ok' : 'stock-over'}>
            سود ناخالص: <strong>{fa(profit)}</strong> ({margin.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)
          </span>
        )}
      </div>
    </div>
  )
}
