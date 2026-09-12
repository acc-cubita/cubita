import { useEffect, useRef, useState } from 'react'
import {
  createSalesReturn,
  fetchReturnable,
  fetchSalesInvoices,
  fetchSalesReturnReasons,
  fetchSalesReturns,
  newIdempotencyKey,
  printSalesReturn,
  voidSalesReturn,
  type ReturnableLine,
  type SalesInvoiceRecord,
  type SalesReturnReasonRecord,
  type SalesReturnRecord,
} from '../api'
import { todayIso } from './jalali'

/** کلیدِ یک ردیفِ قابلِ برگشت.
 *
 * **ردیفِ فاکتور است، نه کالا.** یک کالا می‌تواند در یک فاکتور دو ردیف با دو
 * قیمت داشته باشد؛ اگر مقدارها با `item_id` کلید می‌خوردند، هر دو ردیف یک خانه
 * می‌شدند و کاربر نمی‌توانست بگوید از کدام قیمت برمی‌گرداند.
 */
export const returnableKey = (row: ReturnableLine) =>
  row.sales_invoice_line_id ?? row.purchase_invoice_line_id ?? row.item_id

/**
 * منطقِ مشترکِ «برگشت از فروش» — انتخابِ فاکتور، باقی‌ماندهٔ قابلِ برگشتِ هر ردیف،
 * مقادیر، علتِ برگشت و submit، به‌علاوه‌ی فهرستِ برگشت‌های گذشته و ابطالشان.
 * هم فرمِ کلاسیک ([SalesReturnForm]) و هم ویزارد ([SalesReturnWizard]) از این می‌خوانند.
 */
export function useSalesReturnDraft({ token }: { token: string }) {
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  const [returns, setReturns] = useState<SalesReturnRecord[]>([])
  const [reasons, setReasons] = useState<SalesReturnReasonRecord[]>([])
  const [invoiceId, setInvoiceId] = useState('')
  const [returnable, setReturnable] = useState<ReturnableLine[]>([])
  const [returnDate, setReturnDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [qtyByLine, setQtyByLine] = useState<Record<string, string>>({})
  const [reasonByLine, setReasonByLine] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  //: یک کلید برای عمرِ این فرم. تلاشِ دوباره‌ی شبکه نباید سندِ دوم بسازد؛ پس از
  //: هر ثبتِ موفق کلید تازه می‌شود تا برگشتِ *بعدی* بتواند ثبت شود.
  const idempotencyKey = useRef(newIdempotencyKey())

  const selectedInvoice = invoices.find((inv) => inv.id === invoiceId) ?? null
  const invoiceNumberById = new Map(invoices.map((inv) => [inv.id, inv.number]))
  const reasonTitleById = new Map(reasons.map((r) => [r.id, r.title]))

  async function refresh() {
    try {
      const [invoiceList, returnList, reasonList] = await Promise.all([
        fetchSalesInvoices(token),
        fetchSalesReturns(token),
        //: فهرستِ **کامل** — سندِ تاریخی می‌تواند علتی داشته باشد که امروز
        //: غیرفعال شده، و آن علت باید هنوز نامش را نشان دهد.
        fetchSalesReturnReasons(token),
      ])
      setInvoices(invoiceList)
      setReturns(returnList)
      setReasons(reasonList)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // با انتخابِ فاکتور، باقی‌ماندهٔ قابلِ برگشتِ هر ردیف زنده خوانده می‌شود.
  useEffect(() => {
    setQtyByLine({})
    setReasonByLine({})
    if (!invoiceId) {
      setReturnable([])
      return
    }
    let cancelled = false
    fetchReturnable(token, invoiceId)
      .then((rows) => !cancelled && setReturnable(rows))
      .catch(() => !cancelled && setReturnable([]))
    return () => {
      cancelled = true
    }
  }, [token, invoiceId])

  const anyReturnable = returnable.some((r) => Number(r.remaining) > 0)
  const rowByKey = new Map(returnable.map((r) => [returnableKey(r), r]))

  const enteredLines = Object.entries(qtyByLine)
    .filter(([, qty]) => Number(qty) > 0)
    .map(([key, qty]) => {
      const row = rowByKey.get(key)
      const reasonId = reasonByLine[key]
      return {
        //: شناسه‌ی ردیف را می‌فرستیم تا سرور مجبور به حدس نشود. اگر ردیفی
        //: هویتِ مبدأ نداشت (داده‌ی پیش از مهاجرتِ ۰۱۲۱)، کالا جایگزینش می‌شود.
        ...(row?.sales_invoice_line_id
          ? { sales_invoice_line_id: row.sales_invoice_line_id }
          : { item_id: row?.item_id ?? key }),
        qty: Number(qty),
        ...(reasonId ? { return_reason_id: reasonId } : {}),
      }
    })

  const overRemaining = Object.entries(qtyByLine).some(([key, qty]) => {
    const row = rowByKey.get(key)
    return row !== undefined && Number(qty) > Number(row.remaining)
  })
  const returnLinesValid = enteredLines.length > 0 && !overRemaining

  /** نمای نمایشیِ ردیف‌های واردشده — برای خلاصه‌ی ویزارد.
   *
   * از `enteredLines` جداست چون آن دقیقاً چیزی است که به API می‌رود؛ چسباندنِ
   * نام و واحد به آن یعنی فرستادنِ فیلدهای بی‌مصرف روی سیم.
   */
  const enteredRows = Object.entries(qtyByLine)
    .filter(([, qty]) => Number(qty) > 0)
    .map(([key, qty]) => {
      const row = rowByKey.get(key)
      return {
        key,
        name: row?.item_name ?? '—',
        unit: row?.unit ?? '',
        qty: Number(qty),
        unitPrice: Number(row?.unit_price ?? 0),
        reason: reasonTitleById.get(reasonByLine[key] ?? '') ?? '',
      }
    })

  /** جمعِ مبلغِ برگشتی — با قیمتِ **همان ردیف**، نه میانگینِ کالا. */
  const enteredTotal = enteredRows.reduce((sum, row) => sum + row.qty * row.unitPrice, 0)

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!selectedInvoice) {
      setMessage('یک فاکتور فروش انتخاب کنید.')
      return false
    }
    if (enteredLines.length === 0) {
      setMessage('حداقل مقدار برگشتی یک ردیف را وارد کنید.')
      return false
    }
    if (overRemaining) {
      setMessage('مقدار برگشتی نمی‌تواند از باقی‌ماندهٔ قابلِ برگشت بیشتر باشد.')
      return false
    }
    setBusy(true)
    try {
      await createSalesReturn(
        token,
        {
          return_date: returnDate,
          sales_invoice_id: selectedInvoice.id,
          description,
          lines: enteredLines,
        },
        idempotencyKey.current,
      )
      idempotencyKey.current = newIdempotencyKey()
      setQtyByLine({})
      setReasonByLine({})
      setDescription('')
      setMessage('برگشت از فروش با موفقیت ثبت شد.')
      await refresh()
      const rows = await fetchReturnable(token, selectedInvoice.id)
      setReturnable(rows)
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setBusy(false)
    }
  }

  /** ابطالِ یک برگشتِ ثبت‌شده — سندِ معکوس، نه حذف.
   *
   * تا پیش از این هیچ راهی نبود، و گاردِ ابطالِ فاکتور کاربر را به کاری ارجاع
   * می‌داد که وجود نداشت: یک برگشتِ اشتباهی، فاکتورش را برای همیشه قفل می‌کرد.
   */
  async function voidReturn(id: string, reason: string): Promise<boolean> {
    setMessage(null)
    setBusy(true)
    try {
      await voidSalesReturn(token, id, reason)
      setMessage('سندِ برگشت باطل شد و ماندهٔ قابلِ برگشتِ فاکتور برگشت.')
      await refresh()
      if (invoiceId) setReturnable(await fetchReturnable(token, invoiceId))
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function handlePrint(id: string) {
    setMessage(null)
    try {
      await printSalesReturn(token, id)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return {
    invoices,
    returns,
    reasons,
    reasonTitleById,
    invoiceId,
    setInvoiceId,
    returnable,
    returnDate,
    setReturnDate,
    description,
    setDescription,
    qtyByLine,
    setQtyByLine,
    reasonByLine,
    setReasonByLine,
    message,
    setMessage,
    busy,
    selectedInvoice,
    invoiceNumberById,
    anyReturnable,
    enteredLines,
    enteredRows,
    enteredTotal,
    returnLinesValid,
    submit,
    voidReturn,
    refresh,
    handlePrint,
  }
}

export type SalesReturnDraft = ReturnType<typeof useSalesReturnDraft>
