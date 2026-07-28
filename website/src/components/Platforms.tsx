import { Globe, MonitorDown, Check } from 'lucide-react'

/** «دو نسخه از نظر تکنولوژی» — قرینه‌ی بخشِ ابری/ویندوزِ رقیب، ولی برای کوبیتا: وب و دسکتاپ. */
export function Platforms() {
  const appUrl = import.meta.env.VITE_APP_URL ?? 'https://acc.cubita.ir'
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'

  return (
    <section id="platforms">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">یک حساب، دو نسخه</span>
          <h2>هرجا که هستید، به کسب‌وکارتان وصل باشید</h2>
          <p>یک بار ثبت‌نام کنید و از هر دستگاهی وارد شوید؛ داده‌ها همیشه یکی هستند و هم‌گام می‌مانند.</p>
        </div>

        <div className="platforms-grid">
          <article className="platform-card">
            <span className="platform-icon">
              <Globe size={26} />
            </span>
            <h3>نسخه‌ی وب (ابری)</h3>
            <p>از هر مرورگری، بدون نصب و بدون دردسرِ به‌روزرسانی. داده‌ها امن روی سرورِ ابری و همیشه در دسترس.</p>
            <ul className="platform-list">
              <li><Check size={16} /> بدون نصب — فقط یک مرورگر</li>
              <li><Check size={16} /> همیشه آخرین نسخه، خودکار</li>
              <li><Check size={16} /> دسترسی از موبایل، تبلت و لپ‌تاپ</li>
            </ul>
            <div className="platform-actions">
              <a href={appUrl} target="_blank" rel="noreferrer" className="btn btn-primary">ورود به برنامه</a>
              <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-outline">دموی زنده</a>
            </div>
          </article>

          <article className="platform-card">
            <span className="platform-icon platform-icon-2">
              <MonitorDown size={26} />
            </span>
            <h3>نسخه‌ی دسکتاپ (ویندوز)</h3>
            <p>نرم‌افزارِ نصبی که حتی بدونِ اینترنت هم کار می‌کند؛ اسناد در صف می‌مانند و با اتصالِ بعدی خودکار هم‌گام می‌شوند.</p>
            <ul className="platform-list">
              <li><Check size={16} /> کارِ کاملاً آفلاین</li>
              <li><Check size={16} /> هم‌گام‌سازیِ خودکار با سرور</li>
              <li><Check size={16} /> سرعتِ بالای بومی روی ویندوز</li>
            </ul>
            <div className="platform-actions">
              <a href="#pricing" className="btn btn-primary">شروع رایگان</a>
              <a href="#features" className="btn btn-outline">امکانات</a>
            </div>
          </article>
        </div>
      </div>
    </section>
  )
}
