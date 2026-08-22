import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Menu,
  X,
  Search,
  ChevronDown,
  RefreshCw,
  LogOut,
  Building2,
  Download,
} from 'lucide-react'
import { buildNav, type PageKey } from '../lib/navModel'
import { isElectron } from '../platform'

/** لینکِ پایدارِ دانلودِ نسخه‌ی دسکتاپ (روی هر انتشار همین می‌ماند؛ فایلِ سرور به‌روز می‌شود). */
export const DESKTOP_DOWNLOAD_URL = 'https://acc.cubita.ir/updates/Cubita-Setup.exe'

/** نوارِ ناوبریِ افقیِ بالا (چیدمانِ Xero) — جایگزینِ نوارِ کناری وقتی تمِ فعال
 *  `shell === 'topnav'` باشد. از همان مدلِ ناوبریِ مشترک (buildNav) می‌خواند. */
export function TopNav({
  active,
  onNavigate,
  userName,
  roleName,
  businessName,
  isPlatformAdmin,
  isSuperAdmin,
  tenantKind,
  enabledModules,
  allowedModules,
  isOwner,
  mpUnread = 0,
  onLogout,
  onSync,
  syncing,
  syncStatus,
}: {
  active: PageKey
  onNavigate: (page: PageKey, section?: string) => void
  userName: string
  roleName: string
  businessName: string
  isPlatformAdmin: boolean
  isSuperAdmin: boolean
  tenantKind: string
  /** شخصی‌سازیِ پنل — کلیدِ ماژول‌های روشن/مجاز و اینکه کاربر مالک است. */
  enabledModules?: string[]
  allowedModules?: string[]
  isOwner?: boolean
  /** پیامِ خوانده‌نشده‌ی گفتگوی بازار — نشان روی منوی «بازارِ خرید»/«پخشِ من». */
  mpUnread?: number
  onLogout: () => void
  onSync?: () => void
  syncing?: boolean
  syncStatus?: string
}) {
  const { groups, secondary } = buildNav({
    isPlatformAdmin,
    isSuperAdmin,
    tenantKind,
    enabledModules,
    allowedModules,
    isOwner,
  })

  // نشانِ خوانده‌نشده فقط روی ماژول‌های بازار (پخش‌کننده/فروشگاه) و وقتی عدد > ۰ است.
  const navBadge = (key: PageKey) =>
    mpUnread > 0 && (key === 'marketplace' || key === 'distributor') ? (
      <span className="nav-badge">{mpUnread > 99 ? '۹۹+' : mpUnread.toLocaleString('fa-IR')}</span>
    ) : null

  // یک منوی بازِ هم‌زمان: نامِ گروه، یا '__user__'، یا null. + کشوی موبایل جدا.
  const [open, setOpen] = useState<string | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [query, setQuery] = useState('')
  const barRef = useRef<HTMLElement>(null)

  // کلیک بیرون از نوار → بستنِ منوها. (پنل‌ها stopPropagation ندارند؛ ناوبری خودش می‌بندد.)
  useEffect(() => {
    function onDown(e: PointerEvent) {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setOpen(null)
        setQuery('')
      }
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [])

  // Escape همه‌چیز را می‌بندد.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(null)
        setMobileOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  function go(page: PageKey) {
    onNavigate(page)
    setOpen(null)
    setMobileOpen(false)
    setQuery('')
  }

  // جست‌وجوی سریعِ ماژول‌ها: همه‌ی آیتم‌ها را تخت می‌کند و با متنِ ورودی فیلتر می‌کند.
  const allItems = useMemo(
    () => [...groups.flatMap((g) => g.items), ...secondary],
    [groups, secondary],
  )
  const results = query.trim()
    ? allItems.filter((i) => i.label.includes(query.trim())).slice(0, 8)
    : []

  return (
    <header className="topnav" ref={barRef}>
      <div className="topnav-inner">
        <button
          type="button"
          className="topnav-hamburger"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="منو"
        >
          <Menu size={24} />
        </button>

        <button type="button" className="topnav-brand" onClick={() => go('overview')}>
          <span className="topnav-mark">C</span>
          <span className="topnav-brand-name">کوبیتا</span>
        </button>

        <nav className="topnav-menu">
          {groups.map((group) => {
            const hasActive = group.items.some((i) => i.key === active)
            // گروهِ تک‌آیتم (داشبورد) دکمه‌ی مستقیم است، نه دراپ‌داون.
            if (group.items.length === 1) {
              const only = group.items[0]
              return (
                <button
                  key={group.heading}
                  type="button"
                  className={`topnav-item${active === only.key ? ' active' : ''}`}
                  onClick={() => go(only.key)}
                >
                  {only.label}
                  {navBadge(only.key)}
                </button>
              )
            }
            const isOpen = open === group.heading
            return (
              <div className="topnav-dd" key={group.heading}>
                <button
                  type="button"
                  className={`topnav-item${hasActive ? ' active' : ''}${isOpen ? ' open' : ''}`}
                  aria-expanded={isOpen}
                  onClick={() => setOpen((o) => (o === group.heading ? null : group.heading))}
                >
                  {group.heading}
                  <ChevronDown size={15} className="topnav-item-chev" />
                </button>
                {isOpen && (
                  <div className="topnav-dd-panel">
                    {group.items.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        className={`topnav-dd-item${active === item.key ? ' active' : ''}`}
                        onClick={() => go(item.key)}
                      >
                        <span className="topnav-dd-ico">{item.icon}</span>
                        <span>{item.label}</span>
                        {navBadge(item.key)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        <div className="topnav-actions">
          <div className="topnav-search">
            <Search size={15} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جست‌وجوی ماژول…"
              aria-label="جست‌وجوی ماژول"
            />
            {results.length > 0 && (
              <div className="topnav-search-results">
                {results.map((r) => (
                  <button key={r.key} type="button" className="topnav-dd-item" onClick={() => go(r.key)}>
                    <span className="topnav-dd-ico">{r.icon}</span>
                    <span>{r.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {businessName && (
            <span className="topnav-org" title="کسب‌وکار">
              <Building2 size={15} />
              <span className="topnav-org-name">{businessName}</span>
            </span>
          )}

          {!isElectron && (
            <a
              href={DESKTOP_DOWNLOAD_URL}
              className="topnav-download"
              title="دانلودِ نسخه‌ی دسکتاپِ کوبیتا (ویندوز) — کار با برنامه حتی بدونِ مرورگر"
              download
            >
              <Download size={16} />
              <span className="topnav-download-txt">دانلودِ دسکتاپ</span>
            </a>
          )}

          {isElectron && onSync && (
            <button type="button" className="topnav-sync" onClick={onSync} disabled={syncing} title={syncStatus || 'هم‌گام‌سازی'}>
              <RefreshCw size={16} className={syncing ? 'spin' : ''} />
            </button>
          )}

          <div className="topnav-dd topnav-user-wrap">
            <button
              type="button"
              className={`topnav-user${open === '__user__' ? ' open' : ''}`}
              aria-expanded={open === '__user__'}
              onClick={() => setOpen((o) => (o === '__user__' ? null : '__user__'))}
            >
              <span className="topnav-avatar">{userName.charAt(0)}</span>
              <ChevronDown size={15} className="topnav-item-chev" />
            </button>
            {open === '__user__' && (
              <div className="topnav-dd-panel topnav-user-panel">
                <div className="topnav-user-head">
                  <div className="topnav-user-name">{userName}</div>
                  <div className="topnav-user-role">{roleName}</div>
                </div>
                {secondary.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`topnav-dd-item${active === item.key ? ' active' : ''}`}
                    onClick={() => go(item.key)}
                  >
                    <span className="topnav-dd-ico">{item.icon}</span>
                    <span>{item.label}</span>
                  </button>
                ))}
                <div className="topnav-dd-divider" />
                <button type="button" className="topnav-dd-item topnav-dd-danger" onClick={onLogout}>
                  <span className="topnav-dd-ico"><LogOut size={16} /></span>
                  <span>خروج</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* کشوی موبایل — فهرستِ عمودیِ همه‌ی ماژول‌ها */}
      {mobileOpen && (
        <>
          <div className="topnav-mobile-overlay" onClick={() => setMobileOpen(false)} aria-hidden="true" />
          <div className="topnav-mobile">
            <div className="topnav-mobile-head">
              <span className="topnav-brand-name">کوبیتا</span>
              <button type="button" onClick={() => setMobileOpen(false)} aria-label="بستن"><X size={18} /></button>
            </div>
            <div className="topnav-mobile-body">
              {groups.map((group) => (
                <div className="topnav-mobile-group" key={group.heading}>
                  <div className="topnav-mobile-heading">{group.heading}</div>
                  {group.items.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      className={`topnav-mobile-item${active === item.key ? ' active' : ''}`}
                      onClick={() => go(item.key)}
                    >
                      <span className="topnav-dd-ico">{item.icon}</span>
                      <span>{item.label}</span>
                      {navBadge(item.key)}
                    </button>
                  ))}
                </div>
              ))}
              <div className="topnav-mobile-group">
                <div className="topnav-mobile-heading">حساب کاربری</div>
                {secondary.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`topnav-mobile-item${active === item.key ? ' active' : ''}`}
                    onClick={() => go(item.key)}
                  >
                    <span className="topnav-dd-ico">{item.icon}</span>
                    <span>{item.label}</span>
                  </button>
                ))}
                <button type="button" className="topnav-mobile-item topnav-dd-danger" onClick={onLogout}>
                  <span className="topnav-dd-ico"><LogOut size={16} /></span>
                  <span>خروج</span>
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </header>
  )
}
