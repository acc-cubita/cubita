import { useEffect, useRef, useState } from 'react'
import {
  createPurchaseReturn,
  fetchPurchaseReturnable,
  fetchPurchaseInvoices,
  fetchPurchaseReturns,
  newIdempotencyKey,
  printPurchaseReturn,
  type ReturnableLine,
  type PurchaseInvoiceRecord,
  type PurchaseReturnRecord,
} from '../api'
import { todayIso } from './jalali'
import { returnableKey } from './salesReturnDraft'

/** منطقِ مشترکِ «برگشت از خرید» — قرینه‌ی [useSalesReturnDraft] با api و شناسه‌ی خرید. */
export function usePurchaseReturnDraft({ token }: { token: string }) {
  const [invoices, setInvoices] = useState<PurchaseInvoiceRecord[]>([])
  const [returns, setReturns] = useState<PurchaseReturnRecord[]>([])
  const [invoiceId, setInvoiceId] = useState('')
  const [returnable, setReturnable] = useState<ReturnableLine[]>([])
  const [returnDate, setReturnDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [qtyByLine, setQtyByLine] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  //: یک کلید برای عمرِ این فرم — تلاشِ دوباره‌ی شبکه سندِ دوم نمی‌سازد.
  const idempotencyKey = useRef(newIdempotencyKey())

  const selectedInvoice = invoices.find((inv) => inv.id === invoiceId) ?? null
  const invoiceNumberById = new Map(invoices.map((inv) => [inv.id, inv.number]))

  async function refresh() {
    try {
      const [invoiceList, returnList] = await Promise.all([fetchPurchaseInvoices(token), fetchPurchaseReturns(token)])
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

  useEffect(() => {
    setQtyByLine({})
    if (!invoiceId) {
      setReturnable([])
      return
    }
    let cancelled = false
    fetchPurchaseReturnable(token, invoiceId)
      .then((rows) => !cancelled && setReturnable(rows))
      .catch(() => !cancelled && setReturnable([]))
    return () => {
      cancelled = true
    }
  }, [token, invoiceId])

  const anyReturnable = returnable.some((r) => Number(r.remaining) > 0)
  const rowByKey = new Map(returnable.map((r) => [returnableKey(r), r]))

  //: کلید ردیفِ فاکتور است نه کالا — قرینه‌ی برگشت از فروش، و به همان دلیل:
  //: یک کالا می‌تواند در یک فاکتور دو ردیف با دو بها داشته باشد.
  const enteredLines = Object.entries(qtyByLine)
    .filter(([, qty]) => Number(qty) > 0)
    .map(([key, qty]) => {
      const row = rowByKey.get(key)
      return {
        ...(row?.purchase_invoice_line_id
          ? { purchase_invoice_line_id: row.purchase_invoice_line_id }
          : { item_id: row?.item_id ?? key }),
        qty: Number(qty),
      }
    })
  const overRemaining = Object.entries(qtyByLine).some(([key, qty]) => {
    const row = rowByKey.get(key)
    return row !== undefined && Number(qty) > Number(row.remaining)
  })
  const returnLinesValid = enteredLines.length > 0 && !overRemaining

  //: نمای نمایشی — جدا از `enteredLines` که دقیقاً payloadِ API است.
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
      }
    })
  const enteredTotal = enteredRows.reduce((sum, row) => sum + row.qty * row.unitPrice, 0)

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!selectedInvoice) {
      setMessage('یک فاکتور خرید انتخاب کنید.')
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
      await createPurchaseReturn(
        token,
        {
          return_date: returnDate,
          purchase_invoice_id: selectedInvoice.id,
          description,
          lines: enteredLines,
        },
        idempotencyKey.current,
      )
      idempotencyKey.current = newIdempotencyKey()
      setQtyByLine({})
      setDescription('')
      setMessage('برگشت از خرید با موفقیت ثبت شد.')
      await refresh()
      const rows = await fetchPurchaseReturnable(token, selectedInvoice.id)
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
      await printPurchaseReturn(token, id)
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
    qtyByLine,
    setQtyByLine,
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
    refresh,
    handlePrint,
  }
}

export type PurchaseReturnDraft = ReturnType<typeof usePurchaseReturnDraft>
