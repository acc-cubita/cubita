import { Globe, MonitorDown, Smartphone, Check } from 'lucide-react'

/** سه نسخه: وب (ابری)، دسکتاپ (ویندوز) و اپ اندروید. */
export function Platforms() {
  const appUrl = import.meta.env.VITE_APP_URL ?? 'https://acc.cubita.ir'
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'
  // APKِ اندروید از همان فیدی می‌آید که آپدیتِ درون‌برنامه‌ای از آن می‌خواند.
  const apkUrl = import.meta.env.VITE_ANDROID_APK_URL ?? 'https://acc.cubita.ir/updates/android/cubita-latest.apk'

  return (
    <section id="platforms">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">یک حساب، سه نسخه</span>
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

          <article className="platform-card">
            <span className="platform-icon platform-icon-3">
              <Smartphone size={26} />
            </span>
            <h3>اپ اندروید</h3>
            <p>نبضِ کسب‌وکار در جیبِ شما: داشبورد و گزارش‌ها، ثبتِ فاکتور و دریافت/پرداخت، و هشدارهای مهم به‌صورتِ اعلانِ زنده.</p>
            <ul className="platform-list">
              <li><Check size={16} /> ثبتِ فاکتور و دریافت/پرداخت در حرکت</li>
              <li><Check size={16} /> اعلانِ زنده‌ی هشدارها و پیام‌ها</li>
              <li><Check size={16} /> به‌روزرسانیِ خودکار از داخلِ برنامه</li>
            </ul>
            <div className="platform-actions">
              <a href={apkUrl} className="btn btn-primary">دانلودِ مستقیم (APK)</a>
              <a href="#features" className="btn btn-outline">امکانات</a>
            </div>
          </article>
        </div>
      </div>
    </section>
  )
}
