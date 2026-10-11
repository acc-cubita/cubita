import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { FEATURES } from '../content/features'
import { ANDROID_APK_URL, APP_URL, DOWNLOAD_URL, ENTERPRISE_DOWNLOAD_URL, TRIAL_URL } from '../content/links'
import { BRAND_CELLS } from './brand'

/**
 * سرصفحه و پاصفحه‌ی مشترکِ سایت — همه‌ی صفحه‌ها همین را دارند، تا کاربری که از پاصفحه به
 * «حریمِ خصوصی» می‌رود به سایتِ دیگری نرسد. پاصفحه پیوندِ همه‌ی صفحه‌های محتوایی را دارد: برای
 * خزنده همان «نقشهٔ داخلی» است که هر صفحه را از هر صفحه‌ی دیگر در دو کلیک می‌رساند.
 */

//: نشانی‌ها در `content/links.ts` زندگی می‌کنند (فرادادهٔ سئو هم از همان‌جا می‌خواند)؛ این‌جا برای
//: واردکننده‌های قدیمی دوباره صادر می‌شوند.
export { ANDROID_APK_URL, APP_URL, DOWNLOAD_URL, ENTERPRISE_DOWNLOAD_URL, TRIAL_URL }

//: صفحه‌های محتوایی مسیرِ خودشان را دارند (برای جست‌وجو)؛ پرسش‌ها و فرمِ خرید بخشِ صفحه‌ی
//: اصلی‌اند و با `/` شروع می‌شوند تا از هر صفحه‌ای به همان‌جا برسند.
const NAV = [
  { href: '/features', label: 'امکانات' },
  { href: '/enterprise', label: 'سازمانیِ رایگان' },
  { href: '/download', label: 'دانلود' },
  { href: '/#cc-faq', label: 'سوالات متداول' },
  //: پلن‌های قیمت‌دار برداشته شدند (۱۴۰۵/۰۷/۰۳) — خرید از راهِ گفت‌وگو با کارشناس است.
  { href: '/#cc-contact', label: 'خرید و مشاوره' },
]

//: پیوندِ صفحه‌ی جاری `aria-current` می‌گیرد؛ زیرصفحه‌های امکانات هم «امکانات» را روشن می‌کنند.
const isCurrent = (pathname: string, href: string) =>
  !href.includes('#') && (pathname === href || pathname.startsWith(`${href}/`))

export function BrandMark({ onDark = false }: { onDark?: boolean }) {
  return (
    <svg
      className={`cc-brand-svg${onDark ? ' cc-brand-svg-ring' : ''}`}
      width="34"
      height="34"
      viewBox="0 0 120 120"
      aria-hidden="true"
    >
      <rect width="120" height="120" rx="28" fill="#17130C" />
      {BRAND_CELLS.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="20" height="20" rx="5" fill="#FFC72C" />
      ))}
      <rect x="76" y="24" width="20" height="20" rx="5" fill="#A592E9" />
    </svg>
  )
}

export function SiteHeader() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className={`cc-header${scrolled ? ' cc-header-raised' : ''}`}>
      <div className="cc-header-in">
        <a href="/" className="cc-brand">
          <BrandMark /> کوبیتا
        </a>
        <nav className="cc-nav" aria-label="منوی اصلی">
          {NAV.map((l) => (
            <a href={l.href} key={l.href} aria-current={isCurrent(pathname, l.href) ? 'page' : undefined}>
              {l.label}
            </a>
          ))}
        </nav>
        <div className="cc-header-actions">
          <a href={APP_URL} target="_blank" rel="noreferrer" className="cc-btn cc-btn-outline cc-btn-sm">
            ورود به برنامه
          </a>
          <a href={TRIAL_URL} className="cc-btn cc-btn-primary cc-btn-sm">
            ۱۴ روز رایگان
          </a>
        </div>
        <button
          type="button"
          className="cc-nav-toggle"
          aria-label={open ? 'بستن منو' : 'باز کردن منو'}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      {open && (
        <nav className="cc-nav-mobile" aria-label="منوی موبایل" onClick={() => setOpen(false)}>
          {NAV.map((l) => (
            <a href={l.href} key={l.href} aria-current={isCurrent(pathname, l.href) ? 'page' : undefined}>
              {l.label}
            </a>
          ))}
          <div className="cc-nav-mobile-actions">
            <a href={APP_URL} target="_blank" rel="noreferrer" className="cc-btn cc-btn-outline">
              ورود به برنامه
            </a>
            <a href={TRIAL_URL} className="cc-btn cc-btn-primary">
              شروعِ ۱۴ روز رایگان
            </a>
          </div>
        </nav>
      )}
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="cc-site-footer">
      <div className="cc-footer-grid">
        <div className="cc-footer-brand">
          <a href="/" className="cc-brand">
            <BrandMark onDark /> کوبیتا
          </a>
          <p>نرم‌افزارِ حسابداریِ ابری و آفلاین برای کسب‌وکارهای ایرانی؛ روی وب، ویندوز و اندروید، و نسخه‌ی سازمانیِ رایگان روی سرورِ خودِ شرکت.</p>
          <a
            className="cc-enamad"
            referrerPolicy="origin"
            target="_blank"
            rel="noopener"
            href="https://trustseal.enamad.ir/?id=623640&Code=tfCgeyzE0htaTRGDcOopEIvMsEIdYuOR"
          >
            <img
              referrerPolicy="origin"
              src="https://trustseal.enamad.ir/logo.aspx?id=623640&Code=tfCgeyzE0htaTRGDcOopEIvMsEIdYuOR"
              alt="نماد اعتماد الکترونیکی"
              {...({ code: 'tfCgeyzE0htaTRGDcOopEIvMsEIdYuOR' } as Record<string, string>)}
            />
          </a>
        </div>
        <div className="cc-footer-col">
          <h4>محصول</h4>
          <a href="/features">امکانات</a>
          <a href="/enterprise">کوبیتا سازمانیِ رایگان</a>
          <a href="/download">دانلود</a>
          <a href="/#cc-contact">خرید و مشاوره</a>
          <a href={TRIAL_URL}>شروعِ رایگان</a>
        </div>
        <div className="cc-footer-col">
          <h4>امکانات</h4>
          {FEATURES.map((f) => (
            <a key={f.slug} href={`/features/${f.slug}`}>
              {f.name}
            </a>
          ))}
        </div>
        <div className="cc-footer-col">
          <h4>دانلود</h4>
          <a href={DOWNLOAD_URL} download>
            نسخه‌ی ویندوز
          </a>
          <a href={ANDROID_APK_URL}>اپ اندروید</a>
          <a href={ENTERPRISE_DOWNLOAD_URL} download>
            کوبیتا سازمانی (رایگان)
          </a>
          <a href={APP_URL} target="_blank" rel="noreferrer">
            نسخه‌ی وب
          </a>
        </div>
        <div className="cc-footer-col">
          <h4>پشتیبانی</h4>
          <a href="/#cc-faq">سوالاتِ متداول</a>
          <a href="mailto:acc.cubita@gmail.com">acc.cubita@gmail.com</a>
        </div>
        <div className="cc-footer-col">
          <h4>قوانین</h4>
          <a href="/terms">شرایطِ استفاده از خدمات</a>
          <a href="/privacy">حریمِ خصوصی</a>
        </div>
      </div>
      {/* سالِ شمسی در پیش‌رندر و دوباره در مرورگر حساب می‌شود؛ شبِ تحویلِ سال نباید خطای هیدریشن بدهد. */}
      <div className="cc-footer-bottom" suppressHydrationWarning>
        © {new Intl.DateTimeFormat('fa-IR', { year: 'numeric' }).format(new Date())} کوبیتا — تمامِ حقوق محفوظ است.
      </div>
    </footer>
  )
}
