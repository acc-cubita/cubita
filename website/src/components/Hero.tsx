import { ArrowLeft, Check, Sparkles } from 'lucide-react'
import { ProductMockup } from './ProductMockup'

const TRUST = ['بدون نیاز به نصب برای شروع', 'پرداخت امن با زرین‌پال', 'نسخه‌ی دسکتاپ و وب', 'پشتیبانی فارسی']

export function Hero() {
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'

  return (
    <section className="hero">
      <div className="container hero-grid">
        <div className="hero-copy">
          <span className="hero-badge">
            <Sparkles size={14} />
            حسابداری دوطرفه کامل، آماده‌ی کسب‌وکار ایرانی
          </span>
          <h1>
            حسابداری کسب‌وکارتان را
            <br />
            <span className="text-gradient">ساده و شفاف</span> کنید
          </h1>
          <p className="lead">
            فاکتور فروش و خرید، انبارداری، حسابداری دوطرفه، چک و بانک، حقوق و دستمزد — در یک اپ دسکتاپ که حتی
            بدون اینترنت هم کار می‌کند، یا مستقیم از مرورگر.
          </p>
          <div className="hero-actions">
            <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-primary btn-lg">
              مشاهده دموی رایگان
              <ArrowLeft size={16} />
            </a>
            <a href="#pricing" className="btn btn-outline btn-lg">
              مشاهده پلن‌ها و قیمت‌ها
            </a>
          </div>
          <ul className="hero-trust">
            {TRUST.map((t) => (
              <li key={t}>
                <Check size={15} />
                {t}
              </li>
            ))}
          </ul>
        </div>

        <div className="hero-visual">
          <ProductMockup />
        </div>
      </div>
    </section>
  )
}
