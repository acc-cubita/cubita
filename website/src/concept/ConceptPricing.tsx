import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Check, X, Sparkles } from 'lucide-react'
import { fetchPlans, requestPurchase, type Plan } from '../api'

const TRIAL_URL = 'https://demo.cubita.ir'

function PurchaseModal({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [business, setBusiness] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
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
      })
      window.location.href = payment_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در ارتباط با درگاه پرداخت. لطفاً بعداً دوباره تلاش کنید.')
      setLoading(false)
    }
  }

  return (
    <div className="cc-modal-backdrop" onClick={onClose}>
      <motion.div
        className="cc-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cc-pm-title"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
      >
        <div className="cc-modal-head">
          <div>
            <h3 id="cc-pm-title">خرید پلن {plan.name}</h3>
            <div className="cc-modal-sub">
              {Number(plan.price_toman).toLocaleString('fa-IR')} تومان / {plan.billing_period === 'yearly' ? 'سالانه' : 'ماهانه'}
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="بستن" className="cc-modal-close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="cc-form-error" role="alert">
              {error}
            </div>
          )}
          <div className="cc-field">
            <label htmlFor="cc-pm-name">نام و نام خانوادگی</label>
            <input id="cc-pm-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="cc-field">
            <label htmlFor="cc-pm-email">ایمیل</label>
            <input id="cc-pm-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="cc-field">
            <label htmlFor="cc-pm-phone">شماره تماس</label>
            <input id="cc-pm-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div className="cc-field">
            <label htmlFor="cc-pm-business">نام کسب‌وکار (اختیاری)</label>
            <input id="cc-pm-business" value={business} onChange={(e) => setBusiness(e.target.value)} />
          </div>
          <div className="cc-modal-actions">
            <button type="button" className="cc-btn cc-btn-ghost" onClick={onClose}>
              انصراف
            </button>
            <button type="submit" className="cc-btn cc-btn-primary" disabled={loading}>
              {loading ? 'در حال اتصال به درگاه...' : 'پرداخت با زرین‌پال'}
            </button>
          </div>
          <p className="cc-modal-legal">
            با ادامه‌ی پرداخت، <a href="/terms" target="_blank" rel="noreferrer">شرایط استفاده</a> و{' '}
            <a href="/privacy" target="_blank" rel="noreferrer">حریم خصوصی</a> کوبیتا را می‌پذیرید.
          </p>
        </form>
      </motion.div>
    </div>
  )
}

export function ConceptPricing() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Plan | null>(null)

  useEffect(() => {
    fetchPlans()
      .then(setPlans)
      .catch(() => setLoadError('در حال حاضر امکان دریافت لیست پلن‌ها نیست. لطفاً بعداً دوباره تلاش کنید.'))
  }, [])

  return (
    <section className="cc-section" id="cc-pricing">
      <motion.div
        className="cc-section-head"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
      >
        <span className="cc-eyebrow cc-eyebrow-center">قیمت‌گذاری</span>
        <h2>یک پلن به اندازه‌ی کسب‌وکارت</h2>
        <p>هر پلن با ۱۴ روز آزمایشِ رایگان شروع می‌شود؛ قیمت‌ها سالانه و به تومان است و هر زمان می‌توانی ارتقا دهی.</p>
      </motion.div>

      {loadError && <p className="cc-form-error cc-center">{loadError}</p>}

      <div className="cc-pricing-grid">
        {plans.map((plan, i) => (
          <motion.div
            key={plan.key}
            className={`cc-plan${plan.highlighted ? ' cc-plan-hot' : ''}`}
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
          >
            {plan.highlighted && (
              <span className="cc-plan-badge">
                <Sparkles size={13} /> پیشنهادی
              </span>
            )}
            <div className="cc-plan-name">{plan.name}</div>
            <div className="cc-plan-desc">{plan.description}</div>
            <div className="cc-plan-price">
              <span className="cc-plan-amount">{Number(plan.price_toman).toLocaleString('fa-IR')}</span>
              <span className="cc-plan-unit">تومان</span>
            </div>
            <div className="cc-plan-period">
              {plan.billing_period === 'yearly' ? 'سالانه' : 'ماهانه'}
              {plan.max_users ? ` — تا ${plan.max_users} کاربر` : ' — کاربر نامحدود'}
            </div>
            <ul className="cc-plan-feats">
              {plan.features.map((f) => (
                <li key={f}>
                  <Check size={16} /> {f}
                </li>
              ))}
            </ul>
            <button
              type="button"
              className={`cc-btn ${plan.highlighted ? 'cc-btn-primary' : 'cc-btn-ghost'} cc-plan-btn`}
              onClick={() => setSelected(plan)}
            >
              خرید این پلن
            </button>
          </motion.div>
        ))}
      </div>

      <p className="cc-pricing-note">
        مطمئن نیستی؟ اول <a href={TRIAL_URL}>۱۴ روز رایگان</a> امتحان کن — بدونِ کارتِ بانکی.
      </p>

      {selected && <PurchaseModal plan={selected} onClose={() => setSelected(null)} />}
    </section>
  )
}
