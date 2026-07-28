import { PlayCircle } from 'lucide-react'

/** بندِ «اول امتحان کنید، بعد انتخاب کنید» — قرینه‌ی CTAی امتحانِ رقیب. */
export function TrialCta() {
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'
  return (
    <section className="trial-cta-section">
      <div className="container">
        <div className="trial-cta">
          <div className="trial-cta-text">
            <span className="trial-cta-badge">
              <PlayCircle size={16} /> بدونِ ثبت‌نام
            </span>
            <h2>اول امتحان کنید، بعد انتخاب کنید</h2>
            <p>دموی زنده با داده‌ی یک فروشگاهِ واقعی آماده است — بدونِ نصب و بدونِ کارتِ بانکی، همین حالا داخلِ برنامه بگردید.</p>
          </div>
          <div className="trial-cta-actions">
            <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-primary btn-lg">مشاهده‌ی دموی زنده</a>
            <a href="#pricing" className="btn btn-outline-light btn-lg">مشاهده‌ی پلن‌ها</a>
          </div>
        </div>
      </div>
    </section>
  )
}
