import { useEffect, useState } from 'react'
import { CreditCard, CheckCircle2 } from 'lucide-react'
import { fetchAdminPurchases, fulfillPurchase, type PurchaseRecord } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'

const STATUS_LABELS: Record<string, string> = {
  pending_payment: 'در انتظار پرداخت',
  paid: 'پرداخت‌شده — منتظر تحویل',
  cancelled: 'ناموفق/لغوشده',
  fulfilled: 'تحویل داده شده',
}

export function PurchasesAdminPanel({ token }: { token: string }) {
  const [purchases, setPurchases] = useState<PurchaseRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({})

  async function refresh() {
    setLoading(true)
    try {
      setPurchases(await fetchAdminPurchases(token))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function handleFulfill(purchaseId: string) {
    setMessage(null)
    try {
      await fulfillPurchase(token, purchaseId, noteDrafts[purchaseId] ?? '')
      await refresh()
      setMessage('خرید به‌عنوان «تحویل‌شده» علامت خورد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const paidCount = purchases.filter((p) => p.status === 'paid').length
  // صفحه‌بندیِ خریدها (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(purchases, 10)

  return (
    <SectionCard
      icon={CreditCard}
      title="خریدهای سایت تجاری"
      description="خریدهایی که مشتریان از صفحه‌ی قیمت‌گذاری cubita.ir ثبت کرده‌اند. بعد از تحویل دستی نسخه‌ی اختصاصی، خرید را «تحویل‌شده» علامت بزنید."
    >
      {message && <div className="hint">{message}</div>}
      {paidCount > 0 && (
        <div className="hint" style={{ color: 'var(--warning)' }}>
          {paidCount} خرید پرداخت‌شده منتظر تحویل دستی است.
        </div>
      )}

      {loading ? (
        <p className="hint">در حال بارگذاری...</p>
      ) : purchases.length === 0 ? (
        <EmptyState icon={CreditCard} text="هنوز هیچ خریدی ثبت نشده است." />
      ) : (
        <div className="table-scroll">
        <table className="cards-on-mobile">
          <thead>
            <tr>
              <th>تاریخ</th>
              <th>مشتری</th>
              <th>پلن</th>
              <th>مبلغ (تومان)</th>
              <th>وضعیت</th>
              <th>یادداشت</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((p) => (
              <tr key={p.id}>
                <td data-label="تاریخ">{formatJalali(p.created_at.slice(0, 10))}</td>
                <td className="card-title" data-label="مشتری">
                  {p.customer_name}
                  <br />
                  <span className="hint">{p.customer_email}{p.customer_phone ? ` — ${p.customer_phone}` : ''}</span>
                  {p.business_name && (
                    <>
                      <br />
                      <span className="hint">{p.business_name}</span>
                    </>
                  )}
                </td>
                <td data-label="پلن">{p.plan_name}</td>
                <td data-label="مبلغ (تومان)">{Number(p.amount_toman).toLocaleString('fa-IR')}</td>
                <td data-label="وضعیت">{STATUS_LABELS[p.status] ?? p.status}</td>
                <td data-label="یادداشت">
                  {p.status === 'paid' ? (
                    <input
                      type="text"
                      placeholder="یادداشت (اختیاری)"
                      value={noteDrafts[p.id] ?? ''}
                      onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [p.id]: e.target.value }))}
                      style={{ width: 160 }}
                    />
                  ) : (
                    p.admin_notes || '—'
                  )}
                </td>
                <td className="card-actions">
                  {p.status === 'paid' && (
                    <button type="button" onClick={() => void handleFulfill(p.id)}>
                      <CheckCircle2 size={13} /> تحویل داده شد
                    </button>
                  )}
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
