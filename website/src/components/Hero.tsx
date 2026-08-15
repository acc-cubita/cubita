import { ArrowLeft, Sparkles, Layers, Store } from 'lucide-react'
import { HeroCluster } from './HeroCluster'

export function Hero() {
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'

  return (
    <section className="hero">
      <div className="hero-grid-bg" aria-hidden="true" />
      <div className="container hero-grid">
        <div className="hero-copy">
          <span className="hero-badge">
            <Sparkles size={14} />
            سامانه‌ی یکپارچه‌ی مالی و بازار عمده‌فروشی
          </span>
          <h1>
            <span className="text-gradient">حسابداریِ ساخته‌شده برای کسب‌وکار،</span>
            <br />
            بدونِ پیچیدگی
          </h1>
          <p className="lead">
            کوبیتا عملیاتِ مالیِ شما را به یک مزیتِ رقابتی تبدیل می‌کند — فروش، خرید و انبار،
            حسابداریِ دوطرفه، چک و خزانه و بازارِ عمده‌فروشی، همه در یک سامانه‌ی متصل؛ روی
            دسکتاپ و وب، حتی بدونِ اینترنت.
          </p>
          <div className="hero-actions">
            <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-primary btn-lg">
              مشاهده‌ی دموی رایگان
              <ArrowLeft size={16} />
            </a>
            <a href="#pricing" className="btn btn-outline btn-lg">
              پلن‌ها و قیمت‌ها
            </a>
          </div>
          <div className="hero-feature-cards">
            <a href="#features" className="feature-chip feature-chip--emerald">
              <div className="feature-chip-head">
                <Layers size={17} /> اتوماسیونِ فروش و انبار
                <ArrowLeft size={15} className="chip-arrow" />
              </div>
              <p>فاکتور، موجودی و خزانه را در یک گردشِ خودکار و یکپارچه به هم وصل کنید.</p>
            </a>
            <a href="#solutions" className="feature-chip feature-chip--violet">
              <div className="feature-chip-head">
                <Store size={17} /> بازارِ عمده‌فروشی B2B
                <ArrowLeft size={15} className="chip-arrow" />
              </div>
              <p>خرید و فروشِ عمده بین کسب‌وکارها، با تسویه و کمیسیونِ خودکار.</p>
            </a>
          </div>
        </div>

        <div className="hero-visual">
          <HeroCluster />
        </div>
      </div>
    </section>
  )
}
