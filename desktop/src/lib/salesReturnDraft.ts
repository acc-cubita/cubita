import { useEffect, useState } from 'react'
import {
  createSalesReturn,
  fetchReturnable,
  fetchSalesInvoices,
  fetchSalesReturns,
  printSalesReturn,
  type ReturnableLine,
  type SalesInvoiceRecord,
  type SalesReturnRecord,
} from '../api'
import { todayIso } from './jalali'

/**
 * منطقِ مشترکِ «برگشت از فروش» — انتخابِ فاکتور، باقی‌ماندهٔ قابلِ برگشت، مقادیر و submit،
 * به‌علاوه‌ی فهرستِ برگشت‌های گذشته. هم فرمِ کلاسیک ([SalesReturnForm]) و هم ویزارد
 * ([SalesReturnWizard]) از این می‌خوانند.
 */
export function useSalesReturnDraft({ token }: { token: string }) {
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  const [returns, setReturns] = useState<SalesReturnRecord[]>([])
  const [invoiceId, setInvoiceId] = useState('')
  const [returnable, setReturnable] = useState<ReturnableLine[]>([])
  const [returnDate, setReturnDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [qtyByItem, setQtyByItem] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const selectedInvoice = invoices.find((inv) => inv.id === invoiceId) ?? null
  const invoiceNumberById = new Map(invoices.map((inv) => [inv.id, inv.number]))

  async function refresh() {
    try {
      const [invoiceList, returnList] = await Promise.all([fetchSalesInvoices(token), fetchSalesReturns(token)])
      setInvoices(invoiceList)
      setReturns(returnList)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // با انتخابِ فاکتور، باقی‌ماندهٔ قابلِ برگشتِ هر کالا زنده خوانده می‌شود.
  useEffect(() => {
    setQtyByItem({})
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
  const enteredLines = Object.entries(qtyByItem)
    .filter(([, qty]) => Number(qty) > 0)
    .map(([itemId, qty]) => ({ item_id: itemId, qty: Number(qty) }))
  const overRemaining = enteredLines.some((l) => {
    const r = returnable.find((x) => x.item_id === l.item_id)
    return r && l.qty > Number(r.remaining)
  })
  const returnLinesValid = enteredLines.length > 0 && !overRemaining

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
      await createSalesReturn(token, {
        return_date: returnDate,
        sales_invoice_id: selectedInvoice.id,
        description,
        lines: enteredLines,
      })
      setQtyByItem({})
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
    invoiceId,
    setInvoiceId,
    returnable,
    returnDate,
    setReturnDate,
    description,
    setDescription,
    qtyByItem,
    setQtyByItem,
    message,
    setMessage,
    busy,
    selectedInvoice,
    invoiceNumberById,
    anyReturnable,
    enteredLines,
    returnLinesValid,
    submit,
    refresh,
    handlePrint,
  }
}

export type SalesReturnDraft = ReturnType<typeof useSalesReturnDraft>
