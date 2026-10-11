import { PageLayout } from '../concept/PageLayout'
import { NOT_FOUND_META } from '../seo/pages'

/** هر نشانیِ ناشناخته. nginx همین را با کدِ ۴۰۴ می‌دهد (`404.html`)، نه صفحه‌ی اصلی با ۲۰۰. */
export function NotFoundPage() {
  return (
    <PageLayout meta={NOT_FOUND_META}>
      <section className="cc-result">
        <div className="cc-result-card">
          <h1 className="cc-result-title">این صفحه پیدا نشد</h1>
          <p>نشانی را درست وارد کرده‌اید؟ شاید صفحه جابه‌جا شده باشد. از این‌جا ادامه دهید:</p>
          <div className="cc-card-actions cc-center">
            <a href="/" className="cc-btn cc-btn-primary">
              صفحه‌ی اصلی
            </a>
            <a href="/features" className="cc-btn cc-btn-outline">
              امکانات
            </a>
            <a href="/download" className="cc-btn cc-btn-outline">
              دانلود
            </a>
          </div>
        </div>
      </section>
    </PageLayout>
  )
}
