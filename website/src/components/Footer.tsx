const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div className="footer-brand">
          <a href="/" className="brand">
            <span className="brand-mark">C</span>
            کوبیتا
          </a>
          <p>نرم‌افزار حسابداری ابری و آفلاین برای کسب‌وکارهای ایرانی.</p>
        </div>

        <div className="footer-col">
          <h4>محصول</h4>
          <a href="#features">امکانات</a>
          <a href="#how-it-works">شروع کار</a>
          <a href="#pricing">پلن‌ها و قیمت‌ها</a>
          <a href={demoUrl} target="_blank" rel="noreferrer">
            دموی رایگان
          </a>
        </div>

        <div className="footer-col">
          <h4>پشتیبانی</h4>
          <a href="#faq">سوالات متداول</a>
          <a href="mailto:ipnetcity@gmail.com">ipnetcity@gmail.com</a>
        </div>

        <div className="footer-col">
          <h4>قانونی</h4>
          <a href="/terms">شرایط استفاده از خدمات</a>
          <a href="/privacy">حریم خصوصی</a>
        </div>
      </div>
      <div className="container footer-bottom">© {new Date().getFullYear()} کوبیتا — تمام حقوق محفوظ است.</div>
    </footer>
  )
}
