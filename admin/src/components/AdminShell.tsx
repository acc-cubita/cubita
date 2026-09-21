/**
 * پوسته‌ی اپِ ستاد: نوارِ کناری + نوارِ بالا.
 *
 * زیرِ ۹۰۰px نوارِ کناری به کشویی از بالا تبدیل می‌شود. مالک از گوشی هم این پنل
 * را باز می‌کند، پس نمای موبایل بخشی از «تمام‌شده» است نه یک افزوده.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { LogOut, Menu, Moon, Sun, X } from 'lucide-react'

import type { StaffMe } from '../api'
import { visibleNav, type PageKey } from '../nav'

export default function AdminShell({
  me,
  page,
  onNavigate,
  onLogout,
  diagnostics,
  children,
}: {
  me: StaffMe
  page: PageKey
  onNavigate: (page: PageKey) => void
  onLogout: () => void
  diagnostics: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const [dark, setDark] = useState(
    () => document.documentElement.getAttribute('data-theme') === 'dark',
  )

  //: تغییرِ صفحه کشوی موبایل را می‌بندد، وگرنه کاربر روی منوی باز می‌ماند و
  //: فکر می‌کند کلیکش کار نکرده.
  useEffect(() => setOpen(false), [page])

  //: زدنِ **همان** صفحه‌ی فعلی هم باید کشو را ببندد. با تکیه بر `useEffect`
  //: بالا این حالت جا می‌ماند (صفحه عوض نمی‌شود، پس افکت شلیک نمی‌کند) و کشو
  //: باز می‌ماند — کاربر فکر می‌کند لمسش نگرفته.
  const go = (next: PageKey) => {
    setOpen(false)
    onNavigate(next)
  }

  function toggleTheme() {
    const next = !dark
    setDark(next)
    document.documentElement.setAttribute('data-theme', next ? 'dark' : 'light')
    try {
      localStorage.setItem('cubita.admin.theme', next ? 'dark' : 'light')
    } catch {
      /* ذخیره‌سازیِ مسدود: تمِ این نشست کار می‌کند، فقط یادش نمی‌ماند. */
    }
  }

  const items = visibleNav(me)

  return (
    <div className={`ad-shell${open ? ' drawer-open' : ''}`}>
      <aside className="ad-side">
        <div className="ad-side-brand">
          <span className="ad-logo">ستادِ کوبیتا</span>
          <button
            type="button"
            className="ad-x ad-side-close"
            onClick={() => setOpen(false)}
            aria-label="بستن منو"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="ad-nav">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`ad-nav-item${page === item.key ? ' active' : ''}`}
              onClick={() => go(item.key)}
              aria-current={page === item.key ? 'page' : undefined}
            >
              <item.icon size={17} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="ad-side-foot">{diagnostics}</div>
      </aside>

      <div className="ad-main">
        <header className="ad-topbar">
          <button
            type="button"
            className="ad-burger"
            onClick={() => setOpen((v) => !v)}
            aria-label="منو"
          >
            <Menu size={18} />
          </button>

          <div className="ad-who">
            <strong>{me.name}</strong>
            <span className="ad-role">{me.role_label}</span>
          </div>

          <div className="ad-topbar-actions">
            <button
              type="button"
              className="ad-icon-btn"
              onClick={toggleTheme}
              aria-label={dark ? 'روشن' : 'تیره'}
              title={dark ? 'حالتِ روشن' : 'حالتِ تیره'}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button type="button" className="ad-icon-btn" onClick={onLogout} aria-label="خروج" title="خروج">
              <LogOut size={17} />
            </button>
          </div>
        </header>

        {me.via === 'legacy' ? (
          <p className="ad-note tone-warn ad-legacy">
            با توکنِ قدیمیِ اپِ مشتری وارد شده‌اید. کوچ هنوز کامل نیست — پس از
            ساختِ کاربرِ ستادی، پرچمِ سازگاری را خاموش کنید.
          </p>
        ) : null}

        <main className="ad-page">{children}</main>
      </div>

      {open ? <div className="ad-scrim" onClick={() => setOpen(false)} /> : null}
    </div>
  )
}
