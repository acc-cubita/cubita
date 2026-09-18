import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'

/**
 * سرصفحه و پاصفحه‌ی مشترکِ سایت — صفحه‌ی اصلی، شرایطِ استفاده، حریمِ خصوصی و نتیجه‌ی
 * پرداخت همه همین را دارند، تا کاربری که از پاصفحه به «حریمِ خصوصی» می‌رود به سایتِ
 * دیگری نرسد.
 */

// ورودِ ترایال روی prod متمرکز است: acc.cubita.ir با ?signup مستقیم روی صفحه‌ی ثبت‌نام
// باز می‌شود. (قبلاً به demo.cubita.ir می‌رفت که دیتابیسِ جدا داشت و ورود را خراب می‌کرد.)
export const TRIAL_URL = 'https://acc.cubita.ir/?signup'
export const APP_URL = 'https://acc.cubita.ir'
// لینکِ پایدارِ دانلودِ نسخه‌ی دسکتاپِ ویندوز (فایلِ سرور روی هر انتشار به‌روز می‌شود).
export const DOWNLOAD_URL = 'https://acc.cubita.ir/updates/Cubita-Setup.exe'
// همان الگو برای اپ اندروید: cubita-latest.apk روی هر انتشار به آخرین نسخه اشاره می‌کند.
export const ANDROID_APK_URL = 'https://acc.cubita.ir/updates/android/cubita-latest.apk'

//: با `/` شروع می‌شوند تا از صفحه‌های حقوقی هم به بخشِ درستِ صفحه‌ی اصلی برسند؛ روی
//: خودِ صفحه‌ی اصلی فقط هش عوض می‌شود و صفحه دوباره بار نمی‌شود.
const NAV = [
  { href: '/#cc-features', label: 'امکانات' },
  { href: '/#cc-platforms', label: 'نسخه‌ها' },
  { href: '/#cc-industries', label: 'صنایع' },
  { href: '/#cc-pricing', label: 'پلن‌ها و قیمت' },
  { href: '/#cc-faq', label: 'سوالات متداول' },
]

export function BrandMark({ id = 'm' }: { id?: string }) {
  const g = `cc-brandgrad-${id}`
  return (
    <svg className="cc-brand-svg" width="34" height="34" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill={`url(#${g})`} />
      <rect x="7.5" y="17" width="4" height="7.5" rx="2" fill="#fff" fillOpacity="0.8" />
      <rect x="14" y="13" width="4" height="11.5" rx="2" fill="#fff" fillOpacity="0.9" />
      <rect x="20.5" y="9.5" width="4" height="15" rx="2" fill="#fff" />
      <circle cx="22.5" cy="6.4" r="2.4" fill="#fff" fillOpacity="0.9" />
      <defs>
        <linearGradient id={g} x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1FC274" />
          <stop offset="1" stopColor="#00874B" />
        </linearGradient>
      </defs>
    </svg>
  )
}

export function SiteHeader() {
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
          <BrandMark id="hdr" /> کوبیتا
        </a>
        <nav className="cc-nav" aria-label="منوی اصلی">
          {NAV.map((l) => (
            <a href={l.href} key={l.href}>
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
            <a href={l.href} key={l.href}>
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
            <BrandMark id="ftr" /> کوبیتا
          </a>
          <p>نرم‌افزارِ حسابداریِ ابری و آفلاین برای کسب‌وکارهای ایرانی؛ روی وب، ویندوز و اندروید.</p>
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
          <a href="/#cc-features">امکانات</a>
          <a href="/#cc-platforms">نسخه‌ها</a>
          <a href="/#cc-pricing">پلن‌ها و قیمت‌ها</a>
          <a href={TRIAL_URL}>شروعِ رایگان</a>
        </div>
        <div className="cc-footer-col">
          <h4>دانلود</h4>
          <a href={DOWNLOAD_URL} download>
            نسخه‌ی ویندوز
          </a>
          <a href={ANDROID_APK_URL}>اپ اندروید</a>
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
      <div className="cc-footer-bottom">
        © {new Intl.DateTimeFormat('fa-IR', { year: 'numeric' }).format(new Date())} کوبیتا — تمامِ حقوق محفوظ است.
      </div>
    </footer>
  )
}
