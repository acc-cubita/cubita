import { Sparkles, Check } from 'lucide-react'

/**
 * خوشه‌ی شناورِ رابطِ محصول در هیرو — چند کارتِ شیشه‌ایِ تیره که رابطِ خودِ کوبیتا
 * را نشان می‌دهند (روشِ پرداخت، حلقه‌ی آماری، گردشِ کار، پرداخت‌ها، خریدها) دورِ یک
 * نشانِ برندِ مرکزی. کاملاً تزئینی (aria-hidden) و برندِ خودِ ماست، نه هیچ محصولِ دیگر.
 */
export function HeroCluster() {
  const bars = [42, 66, 50, 80, 58, 92, 72]
  return (
    <div className="hero-cluster" aria-hidden="true">
      <div className="hc-ring" />

      <div className="hc-card hc-pay">
        <div className="hc-mini-title">روش پرداخت</div>
        <div className="hc-pay-opt is-on"><span className="hc-radio" /> انتقال بانکی</div>
        <div className="hc-pay-opt"><span className="hc-radio" /> کارت به کارت</div>
        <div className="hc-pay-opt"><span className="hc-radio" /> زرین‌پال</div>
      </div>

      <div className="hc-card hc-donut">
        <div className="hc-donut-ring"><div className="hc-donut-hole">۹۱٬۲۵۰</div></div>
        <ul className="hc-legend">
          <li><i className="d-a" /> فاکتورها</li>
          <li><i className="d-b" /> سفارش‌ها</li>
          <li><i className="d-c" /> پرداخت‌ها</li>
        </ul>
      </div>

      <div className="hc-card hc-flow">
        <div className="hc-flow-row">
          <span className="hc-av" />
          <div><b>خرید</b><small>فاکتور ثبت شد</small></div>
          <span className="hc-badge ok"><Check size={10} /></span>
        </div>
        <div className="hc-flow-row">
          <span className="hc-av" />
          <div><b>حسابداری</b><small>در انتظار بررسی</small></div>
          <span className="hc-badge wait" />
        </div>
        <div className="hc-flow-row">
          <span className="hc-av" />
          <div><b>مدیریت</b><small>در انتظار تأیید</small></div>
          <span className="hc-badge wait" />
        </div>
      </div>

      <div className="hc-card hc-amount">
        <div className="hc-mini-title">پرداخت‌ها</div>
        <div className="hc-amount-val">۸٬۵۰۰٬۰۰۰ <small>تومان</small></div>
        <div className="hc-bar"><span style={{ width: '72%' }} /></div>
      </div>

      <div className="hc-card hc-bars">
        <div className="hc-mini-title">خریدها</div>
        <div className="hc-bars-row">
          {bars.map((h, i) => <i key={i} style={{ height: `${h}%` }} />)}
        </div>
      </div>

      <div className="hc-brand"><Sparkles size={20} /> کوبیتا</div>
    </div>
  )
}
