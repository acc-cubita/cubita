import { ArrowLeft } from 'lucide-react'

export function FinalCta() {
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'

  return (
    <section className="final-cta">
      <div className="container final-cta-inner">
        <div className="final-cta-card">
          <h2>همین امروز حسابداری کسب‌وکارتان را متحول کنید</h2>
          <p>بدون نیاز به کارت اعتباری، نسخه‌ی دموی کوبیتا را همین حالا در مرورگر امتحان کنید.</p>
          <div className="hero-actions" style={{ justifyContent: 'center' }}>
            <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-primary btn-lg">
              مشاهده دموی رایگان
              <ArrowLeft size={16} />
            </a>
            <a href="#pricing" className="btn btn-outline-light btn-lg">
              مشاهده پلن‌ها
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
