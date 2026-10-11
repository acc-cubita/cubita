import { Building2, Check, Download, Globe, MonitorSmartphone, Smartphone } from 'lucide-react'
import { FaqList } from '../concept/FaqList'
import { FinalCta } from '../concept/FinalCta'
import { PageLayout } from '../concept/PageLayout'
import { DOWNLOAD_FAQS } from '../content/download'
import { ANDROID_APK_URL, APP_URL, DOWNLOAD_URL, ENTERPRISE_DOWNLOAD_URL, TRIAL_URL } from '../content/links'
import { DOWNLOAD_META } from '../seo/pages'

//: چهار نسخه به ترتیبِ پرسشِ «کدام را بگیرم؟»: سازمانیِ رایگان (بی‌حسابِ ابری کار می‌کند) اول،
//: بعد سه نسخه‌ی یک حسابِ ابری.
const PRODUCTS = [
  {
    icon: Building2,
    title: 'کوبیتا سازمانی',
    badge: 'رایگان تا ۳ کاربر',
    desc: 'برای شرکت‌ها: سرور در خودِ شرکت و حسابدارها روی شبکه‌ی داخلی. حسابِ ابری لازم ندارد.',
    points: ['ویندوز ۱۰ و ۱۱ (۶۴ بیتی)', 'یک نصاب برای سرور و کلاینت', 'داده‌ی کاملاً درون‌سازمانی'],
    primary: { href: ENTERPRISE_DOWNLOAD_URL, label: 'دانلودِ نصاب', download: true },
    more: { href: '/enterprise', label: 'معرفی و مقایسه' },
  },
  {
    icon: MonitorSmartphone,
    title: 'کوبیتا برای ویندوز',
    badge: 'نسخه‌ی ابری',
    desc: 'اینترنت قطع شد؟ آفلاین کار کنید؛ با اتصالِ دوباره خودکار با حسابِ ابری هم‌گام می‌شود.',
    points: ['ویندوز ۱۰ و ۱۱ (۶۴ بیتی)', 'کارِ کاملاً آفلاین', 'به‌روزرسانیِ خودکار'],
    primary: { href: DOWNLOAD_URL, label: 'دانلود برای ویندوز', download: true },
    more: { href: TRIAL_URL, label: 'ساختِ حساب (۱۴ روز رایگان)' },
  },
  {
    icon: Smartphone,
    title: 'اپ اندروید',
    badge: 'نسخه‌ی ابری',
    desc: 'داشبورد و گزارش، ثبتِ فاکتور و دریافت و پرداخت، و هشدارها به‌صورتِ اعلانِ زنده.',
    points: ['فایلِ APK مستقیم', 'به‌روزرسانیِ خودکار', 'همان حسابِ وب و ویندوز'],
    primary: { href: ANDROID_APK_URL, label: 'دانلودِ اپ اندروید', download: false },
    more: { href: TRIAL_URL, label: 'ساختِ حساب (۱۴ روز رایگان)' },
  },
  {
    icon: Globe,
    title: 'نسخه‌ی وب',
    badge: 'بدونِ نصب',
    desc: 'از هر مرورگری وارد شوید؛ همه‌چیز روی ابر و همیشه به‌روز است.',
    points: ['بدونِ نصب و نگهداری', 'دسترسی از هر دستگاه', 'پشتیبان‌گیریِ خودکار'],
    primary: { href: APP_URL, label: 'ورود به نسخه‌ی وب', download: false },
    more: { href: TRIAL_URL, label: 'ساختِ حساب (۱۴ روز رایگان)' },
  },
]

export function DownloadPage() {
  return (
    <PageLayout meta={DOWNLOAD_META}>
      <section className="cc-page-hero">
        <div className="cc-page-hero-in">
          <span className="cc-eyebrow">ویندوز، اندروید، وب و سازمانی</span>
          <h1>دانلود نرم‌افزار حسابداری کوبیتا</h1>
          <p className="cc-lead">
            کوبیتا سازمانی را برای شبکه‌ی داخلیِ شرکت رایگان نصب کنید، یا با یک حسابِ ابری روی ویندوز، اندروید و مرورگر کار
            کنید. همه‌ی نسخه‌ها فارسی‌اند و همه‌ی امکاناتِ حسابداری را دارند.
          </p>
        </div>
      </section>

      <section className="cc-section">
        <ul className="cc-grid cc-grid-4 cc-platform-grid">
          {PRODUCTS.map((p) => (
            <li key={p.title} className="cc-card cc-platform">
              <span className="cc-icon cc-icon-lg">
                <p.icon size={24} />
              </span>
              <h2 className="cc-card-title">{p.title}</h2>
              <span className="cc-badge">{p.badge}</span>
              <p>{p.desc}</p>
              <ul className="cc-checklist">
                {p.points.map((pt) => (
                  <li key={pt}>
                    <Check size={15} /> {pt}
                  </li>
                ))}
              </ul>
              <div className="cc-card-action cc-card-actions">
                <a
                  className="cc-btn cc-btn-primary"
                  href={p.primary.href}
                  {...(p.primary.download ? { download: true } : {})}
                  {...(p.primary.href === APP_URL ? { target: '_blank', rel: 'noreferrer' } : {})}
                >
                  {p.primary.download && <Download size={16} />} {p.primary.label}
                </a>
                <a className="cc-btn cc-btn-outline" href={p.more.href}>
                  {p.more.label}
                </a>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="cc-section cc-section-alt" id="faq">
        <div className="cc-section-head">
          <span className="cc-eyebrow">نصب</span>
          <h2>پرسش‌های رایج درباره‌ی دانلود و نصب</h2>
        </div>
        <FaqList items={DOWNLOAD_FAQS} idPrefix="dl-faq" />
      </section>

      <FinalCta />
    </PageLayout>
  )
}
