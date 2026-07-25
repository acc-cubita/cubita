import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'

const NAV_LINKS = [
  { href: '#features', label: 'امکانات' },
  { href: '#pricing', label: 'پلن‌ها' },
  { href: '#demo', label: 'دمو' },
]

export function Header() {
  const appUrl = import.meta.env.VITE_APP_URL ?? 'https://acc.cubita.ir'
  const [open, setOpen] = useState(false)

  // با تغییر مسیر (کلیک روی یک لینک) پنل موبایل خودش بسته شود؛ وگرنه کاربر
  // به بخش بعدی صفحه می‌رود ولی پنل باز روی محتوا می‌ماند.
  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    window.addEventListener('hashchange', close)
    return () => window.removeEventListener('hashchange', close)
  }, [open])

  return (
    <header className="site-header">
      <div className="container">
        <a href="/" className="brand">
          <span className="brand-mark">C</span>
          کوبیتا
        </a>

        <nav className="site-nav" aria-label="منوی اصلی">
          {NAV_LINKS.map((l) => (
            <a href={l.href} key={l.href}>
              {l.label}
            </a>
          ))}
        </nav>

        <a href={appUrl} target="_blank" rel="noreferrer" className="btn btn-primary desktop-only">
          ورود به برنامه
        </a>

        <button
          type="button"
          className="mobile-nav-toggle"
          aria-label={open ? 'بستن منو' : 'باز کردن منو'}
          aria-expanded={open}
          aria-controls="mobile-nav-panel"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <nav id="mobile-nav-panel" className="mobile-nav-panel" aria-label="منوی موبایل">
          {NAV_LINKS.map((l) => (
            <a href={l.href} key={l.href} onClick={() => setOpen(false)}>
              {l.label}
            </a>
          ))}
          <a href={appUrl} target="_blank" rel="noreferrer" className="btn btn-primary">
            ورود به برنامه
          </a>
        </nav>
      )}
    </header>
  )
}
