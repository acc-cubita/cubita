import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { requestPurchase, type Plan } from '../api'

export function PurchaseModal({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [business, setBusiness] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // با Escape هم باید بشود بست — رفتار استاندارد هر دیالوگ، و کاربری که با
  // صفحه‌کلید کار می‌کند راه دیگری برای خروج بدون موس ندارد.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!name.trim() || !email.trim()) {
      setError('نام و ایمیل الزامی است.')
      return
    }
    setLoading(true)
    try {
      const { payment_url } = await requestPurchase({
        plan_key: plan.key,
        customer_name: name,
        customer_email: email,
        customer_phone: phone,
        business_name: business,
        billing_period: 'yearly',
      })
      window.location.href = payment_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در ارتباط با درگاه پرداخت. لطفاً بعداً دوباره تلاش کنید.')
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-box"
        role="dialog"
        aria-modal="true"
        aria-labelledby="purchase-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h3 id="purchase-modal-title">خرید پلن {plan.name}</h3>
            <div className="modal-sub">
              {Number(plan.price_toman).toLocaleString('fa-IR')} تومان / {plan.billing_period === 'yearly' ? 'سالانه' : 'ماهانه'}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="modal-close"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <div className="form-field">
            <label htmlFor="pm-name">نام و نام خانوادگی</label>
            <input id="pm-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="form-field">
            <label htmlFor="pm-email">ایمیل</label>
            <input
              id="pm-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="pm-phone">شماره تماس</label>
            <input id="pm-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="pm-business">نام کسب‌وکار (اختیاری)</label>
            <input id="pm-business" value={business} onChange={(e) => setBusiness(e.target.value)} />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              انصراف
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'در حال اتصال به درگاه...' : 'پرداخت با زرین‌پال'}
            </button>
          </div>
          <p className="modal-legal-note">
            با ادامه‌ی پرداخت، <a href="/terms" target="_blank" rel="noreferrer">شرایط استفاده از خدمات</a> و{' '}
            <a href="/privacy" target="_blank" rel="noreferrer">حریم خصوصی</a> کوبیتا را می‌پذیرید.
          </p>
        </form>
      </div>
    </div>
  )
}
