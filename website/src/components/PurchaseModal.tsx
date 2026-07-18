import { useState } from 'react'
import { X } from 'lucide-react'
import { requestPurchase, type Plan } from '../api'

export function PurchaseModal({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [business, setBusiness] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
      })
      window.location.href = payment_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در ارتباط با درگاه پرداخت. لطفاً بعداً دوباره تلاش کنید.')
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3>خرید پلن {plan.name}</h3>
            <div className="modal-sub">
              {Number(plan.price_toman).toLocaleString('fa-IR')} تومان / {plan.billing_period === 'yearly' ? 'سالانه' : 'ماهانه'}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)' }}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {error && <div className="form-error">{error}</div>}
          <div className="form-field">
            <label>نام و نام خانوادگی</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="form-field">
            <label>ایمیل</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="form-field">
            <label>شماره تماس</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div className="form-field">
            <label>نام کسب‌وکار (اختیاری)</label>
            <input value={business} onChange={(e) => setBusiness(e.target.value)} />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              انصراف
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'در حال اتصال به درگاه...' : 'پرداخت با زرین‌پال'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
