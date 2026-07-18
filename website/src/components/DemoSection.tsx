import { MonitorPlay } from 'lucide-react'

export function DemoSection() {
  // رمز دمو عمداً fallback ندارد: باید از build-time env بیاید تا چرخشش نیازی به تغییر کد نداشته باشد.
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'
  const demoEmail = import.meta.env.VITE_DEMO_EMAIL ?? ''
  const demoPassword = import.meta.env.VITE_DEMO_PASSWORD ?? ''
  const hasCreds = Boolean(demoEmail && demoPassword)

  return (
    <section id="demo" className="demo-section">
      <div className="container">
        <div className="demo-panel">
          <div className="demo-panel-text">
            <h2>
              <MonitorPlay size={22} style={{ verticalAlign: 'text-bottom', marginLeft: 8 }} />
              نرم‌افزار واقعی را همین حالا امتحان کنید
            </h2>
            <p>
              این یک نسخه‌ی دموی زنده از خود نرم‌افزار کوبیتاست، با داده‌ی نمونه‌ی از پیش پرشده — فقط برای
              مشاهده (بدون امکان ثبت یا تغییر). نیازی به ثبت‌نام نیست.
            </p>
            <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-primary">
              ورود به نسخه‌ی دمو
            </a>
          </div>
          {hasCreds && (
            <div className="demo-creds">
              <div>
                <span>ایمیل ورود</span>
                <b>{demoEmail}</b>
              </div>
              <div>
                <span>رمز عبور</span>
                <b>{demoPassword}</b>
              </div>
              <div className="demo-warning">این حساب فقط‌خواندنی است؛ همه‌ی داده‌ها نمونه‌اند، نه اطلاعات واقعی مشتریان.</div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
