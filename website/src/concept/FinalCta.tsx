import { Download, PhoneCall } from 'lucide-react'
import { ENTERPRISE_DOWNLOAD_URL, TRIAL_URL } from '../content/links'

/**
 * نوارِ پایانیِ تیره — دو راهِ شروع کنارِ هم: نسخه‌ی ابری (۱۴ روز رایگان) و سازمانیِ رایگان.
 * صفحه‌ی اصلی متنِ خودش را می‌دهد؛ بقیه‌ی صفحه‌ها همین پیش‌فرض را دارند.
 */
export function FinalCta({
  title = 'همین امروز، رایگان شروع کنید',
  text = 'نسخه‌ی ابری را ۱۴ روز رایگان امتحان کنید، یا کوبیتا سازمانی را روی سرورِ شرکت نصب کنید — تا سه کاربر برای همیشه رایگان.',
  contactHref = '/#cc-contact',
}: {
  title?: string
  text?: string
  contactHref?: string
}) {
  return (
    <section className="cc-final-cta">
      <div className="cc-final-cta-in">
        <div>
          <h2>{title}</h2>
          <p>{text}</p>
        </div>
        <div className="cc-final-cta-btns">
          <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
            شروعِ ۱۴ روز رایگان
          </a>
          <a className="cc-btn cc-btn-on-dark" href={ENTERPRISE_DOWNLOAD_URL} download>
            <Download size={16} /> دانلودِ سازمانیِ رایگان
          </a>
          <a className="cc-btn cc-btn-on-dark" href={contactHref}>
            <PhoneCall size={16} /> خرید و مشاوره
          </a>
        </div>
      </div>
    </section>
  )
}
