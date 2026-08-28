import { useEffect, useState } from 'react'
import { FileCheck, RefreshCw, ArrowLeftCircle, Printer, FileDown, Pencil } from 'lucide-react'
import {
  fetchSalesQuotations,
  fetchContacts,
  updateQuotationStatus,
  convertQuotationToInvoice,
  printSalesQuotation,
  downloadSalesQuotationPdf,
  type SalesQuotationRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'

const STATUS_LABELS: Record<string, string> = {
  draft: 'پیش‌نویس',
  sent: 'ارسال‌شده',
  accepted: 'تأییدشده',
  rejected: 'ردشده',
  converted: 'تبدیل به فاکتور',
}

const STATUS_TONE: Record<string, string> = {
  draft: 'default',
  sent: 'warning',
  accepted: 'success',
  rejected: 'danger',
  converted: 'success',
}

export function QuotationsList({
  token,
  onConverted,
  onEdit,
}: {
  token: string
  onConverted: () => void
  onEdit: (quotation: SalesQuotationRecord) => void
}) {
  const [quotations, setQuotations] = useState<SalesQuotationRecord[]>([])
  const [contactNames, setContactNames] = useState<Map<string, string>>(new Map())
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  // صفحه‌بندیِ جدولِ پیش‌فاکتورها (۱۰ ردیف).
  const pg = usePagination(quotations, 10)

  async function refresh() {
    setError(null)
    try {
      setQuotations(await fetchSalesQuotations(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    fetchContacts(token)
      .then((rows) => setContactNames(new Map(rows.map((c) => [c.id, c.name]))))
      .catch(() => setContactNames(new Map()))
  }, [])

  function customerLabel(q: SalesQuotationRecord): string {
    if (q.contact_id) return contactNames.get(q.contact_id) ?? '—'
    return q.customer_name || '—'
  }

  async function handleStatusChange(id: string, status: string) {
    setError(null)
    setBusyId(id)
    try {
      await updateQuotationStatus(token, id, status)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusyId(null)
    }
  }

  async function handlePrint(id: string) {
    setError(null)
    try {
      await printSalesQuotation(token, id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handlePdf(q: SalesQuotationRecord) {
    setError(null)
    try {
      await downloadSalesQuotationPdf(token, q.id, q.number)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleConvert(id: string) {
    setError(null)
    setBusyId(id)
    try {
      await convertQuotationToInvoice(token, id)
      await refresh()
      onConverted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <SectionCard
      icon={FileCheck}
      title="لیست پیش‌فاکتورها"
      actions={
        <button onClick={() => void refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {error && <div className="error">{error}</div>}
      {quotations.length === 0 ? (
        <EmptyState icon={FileCheck} text="پیش‌فاکتوری ثبت نشده." />
      ) : (
        <div className="table-scroll">
        <table className="cards-on-mobile">
          <thead>
            <tr>
              <th>شماره</th>
              <th>مشتری</th>
              <th>تاریخ</th>
              <th>اعتبار تا</th>
              <th>مبلغ</th>
              <th>وضعیت</th>
              <th>اقدام</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((q) => (
              <tr key={q.id}>
                <td data-label="شماره">{q.number != null ? q.number.toLocaleString('fa-IR') : '—'}</td>
                <td className="entity-name card-title" data-label="مشتری">{customerLabel(q)}</td>
                <td data-label="تاریخ">{formatJalali(q.quotation_date)}</td>
                <td data-label="اعتبار تا">{formatJalali(q.valid_until)}</td>
                <td data-label="مبلغ">{Number(q.total_amount).toLocaleString('fa-IR')}</td>
                <td data-label="وضعیت">
                  <span className={`status-badge tone-${STATUS_TONE[q.status] ?? 'default'}`}>
                    {STATUS_LABELS[q.status] ?? q.status}
                  </span>
                </td>
                <td className="card-actions" data-label="اقدام">
                  <div className="check-actions">
                    <button type="button" onClick={() => void handlePrint(q.id)}>
                      <Printer size={13} /> چاپ
                    </button>
                    <button type="button" onClick={() => void handlePdf(q)}>
                      <FileDown size={13} /> PDF
                    </button>
                    {q.status !== 'converted' && (
                      <button type="button" onClick={() => onEdit(q)}>
                        <Pencil size={13} /> ویرایش
                      </button>
                    )}
                    {q.status === 'draft' && (
                      <>
                        <button type="button" disabled={busyId === q.id} onClick={() => void handleStatusChange(q.id, 'sent')}>
                          ارسال شد
                        </button>
                        <button type="button" disabled={busyId === q.id} onClick={() => void handleStatusChange(q.id, 'accepted')}>
                          تأیید شد
                        </button>
                        <button type="button" disabled={busyId === q.id} onClick={() => void handleStatusChange(q.id, 'rejected')}>
                          رد شد
                        </button>
                      </>
                    )}
                    {q.status === 'sent' && (
                      <>
                        <button type="button" disabled={busyId === q.id} onClick={() => void handleStatusChange(q.id, 'accepted')}>
                          تأیید شد
                        </button>
                        <button type="button" disabled={busyId === q.id} onClick={() => void handleStatusChange(q.id, 'rejected')}>
                          رد شد
                        </button>
                      </>
                    )}
                    {(q.status === 'draft' || q.status === 'sent' || q.status === 'accepted') && (
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={busyId === q.id}
                        onClick={() => void handleConvert(q.id)}
                      >
                        <ArrowLeftCircle size={13} /> تبدیل به فاکتور
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
  )
}
