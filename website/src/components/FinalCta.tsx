import { ArrowLeft } from 'lucide-react'

export function FinalCta() {
  const appUrl = import.meta.env.VITE_APP_URL ?? 'https://acc.cubita.ir'

  return (
    <section className="final-cta">
      <div className="container final-cta-inner">
        <div className="final-cta-card">
          <h2>همین امروز حسابداری کسب‌وکارتان را متحول کنید</h2>
          <p>پلن مناسب کسب‌وکارتان را انتخاب کنید و تنها در چند دقیقه کار را شروع کنید.</p>
          <div className="hero-actions justify-center">
            <a href="#pricing" className="btn btn-primary btn-lg">
              مشاهده پلن‌ها و شروع
              <ArrowLeft size={16} />
            </a>
            <a href={appUrl} target="_blank" rel="noreferrer" className="btn btn-outline-light btn-lg">
              ورود به برنامه
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
