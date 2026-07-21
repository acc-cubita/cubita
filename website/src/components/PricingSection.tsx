import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { fetchPlans, type Plan } from '../api'
import { PurchaseModal } from './PurchaseModal'

export function PricingSection() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null)

  useEffect(() => {
    fetchPlans()
      .then(setPlans)
      .catch(() => setLoadError('در حال حاضر امکان دریافت لیست پلن‌ها نیست. لطفاً بعداً دوباره تلاش کنید.'))
  }, [])

  return (
    <section id="pricing">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">قیمت‌گذاری</span>
          <h2>یک پلن مناسب اندازه‌ی کسب‌وکار شما</h2>
          <p>قیمت‌ها سالانه و به تومان است. هر زمان می‌توانید پلن خود را ارتقا دهید.</p>
        </div>

        {loadError && (
          <p role="alert" className="form-error centered">
            {loadError}
          </p>
        )}

        <div className="pricing-grid">
          {plans.map((plan) => (
            <div className={`plan-card${plan.highlighted ? ' highlighted' : ''}`} key={plan.key}>
              {plan.highlighted && <span className="plan-badge">پیشنهادی</span>}
              <div className="plan-name">{plan.name}</div>
              <div className="plan-desc">{plan.description}</div>
              <div className="plan-price">
                <span className="amount">{Number(plan.price_toman).toLocaleString('fa-IR')}</span>
                <span className="unit">تومان</span>
              </div>
              <div className="plan-period">
                {plan.billing_period === 'yearly' ? 'سالانه' : 'ماهانه'}
                {plan.max_users ? ` — تا ${plan.max_users} کاربر` : ' — کاربر نامحدود'}
              </div>
              <ul className="plan-features">
                {plan.features.map((f) => (
                  <li key={f}>
                    <Check size={16} />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={`btn ${plan.highlighted ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setSelectedPlan(plan)}
              >
                خرید این پلن
              </button>
            </div>
          ))}
        </div>
      </div>

      {selectedPlan && <PurchaseModal plan={selectedPlan} onClose={() => setSelectedPlan(null)} />}
    </section>
  )
}
