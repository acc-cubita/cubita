import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
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
import { buildNav, uniqueNavItems, type PageKey } from '../lib/navModel'
import { LIST_MENUS } from './moduleLists'
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
  //: آکاردئونِ کشوی موبایل — فقط یک گروه هم‌زمان باز است.
  //:
  //: **چرا لازم شد:** کشو همه‌ی گروه‌ها را باز و تخت نشان می‌داد. با احتسابِ منوهای
  //: «فهرست»ِ هر گروه، این یعنی نزدیکِ صد ردیف روی یک صفحه‌ی ۳۹۰px — کاربر باید
  //: چند صفحه اسکرول می‌کرد تا ماژولی را پیدا کند. حالا فقط سرتیترها دیده می‌شوند
  //: و کلِ منو در یک نگاه جا می‌شود.
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const barRef = useRef<HTMLElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLElement>(null)

  /* ── جمع‌شدنِ سنجیده‌ی نوار ────────────────────────────────────────────────
     تعدادِ ماژول‌های نوار از حسابی به حسابِ دیگر فرق دارد: گرنتِ ماژول‌های محدود،
     گروهِ «بازارِ عمده‌فروشی» برای پخش‌کننده/فروشگاه، «مدیریت سامانه» برای سوپرادمین.
     پس هیچ بریک‌پوینتِ ثابتی درست نیست — با یک ترکیب جا می‌شود و با ترکیبِ بعدی نوار
     از لبه بیرون می‌زند. این‌جا خودِ جا‌شدن سنجیده می‌شود و اگر جا نشد همان کشوی
     همبرگریِ موبایل می‌آید.

     `neededRef` عرضِ طبیعیِ نوارِ *باز* را نگه می‌دارد؛ چون منو نمی‌شکند، این عدد به
     عرضِ پنجره وابسته نیست. باز‌شدنِ دوباره با همان عدد سنجیده می‌شود، پس نوسانِ
     باز/بسته رخ نمی‌دهد (همبرگر از منو باریک‌تر است، پس هر بار که باز می‌شود جا دارد). */
  //: دو مرحله‌ی کوچک‌شدنِ نوار، به همین ترتیب: اول جست‌وجوی ماژول کنار می‌رود
  //: (`tight`)، و تنها اگر باز هم جا نشد کلِ منو به کشوی همبرگری می‌رود (`collapsed`).
  const [tight, setTight] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  // امضای *محتوایی* گروه‌ها، نه هویتِ آرایه: `groups` هر رندر تازه ساخته می‌شود و
  // وابستگی به خودش این افکت را در هر رندر می‌دواند (باز↔بسته، حلقه‌ی بی‌پایان).
  const navKey = useMemo(
    () => groups.map((g) => `${g.heading}:${g.items.length}`).join('|'),
    [groups],
  )

  useLayoutEffect(() => {
    const inner = innerRef.current
    const menu = menuRef.current
    if (!inner || !menu) return

    const px = (v: string) => parseFloat(v) || 0

    function fit() {
      if (!inner || !menu) return
      const items = Array.from(menu.children) as HTMLElement[]
      if (items.length === 0) return

      // عرضِ *طبیعیِ* منو. آیتم‌ها `flex: 0 0 auto` دارند و منوی جمع‌شده هم از جریان
      // بیرون است ولی اندازه‌پذیر — پس این عدد به عرضِ پنجره و به حالتِ فعلی وابسته
      // نیست، و همین است که بازشدنِ دوباره را ممکن می‌کند.
      const ms = getComputedStyle(menu)
      const menuWidth =
        items.reduce((sum, el) => sum + el.offsetWidth, 0) +
        px(ms.columnGap) * (items.length - 1) +
        px(ms.marginInlineStart)

      // بقیه‌ی نوار — عمداً **بی‌احتسابِ همبرگر**، که فقط در حالتِ جمع‌شده وجود دارد.
      // اگر آن را می‌شمردیم، هر بار که نوار باز می‌شد عرضِ لازم عوض می‌شد و تصمیم بین
      // باز و بسته نوسان می‌کرد.
      const others = (Array.from(inner.children) as HTMLElement[]).filter(
        (el) => el !== menu && !el.classList.contains('topnav-hamburger') && el.offsetWidth > 0,
      )
      const cs = getComputedStyle(inner)
      const base =
        menuWidth +
        others.reduce((sum, el) => sum + el.offsetWidth, 0) +
        px(cs.paddingInlineStart) +
        px(cs.paddingInlineEnd) +
        px(cs.columnGap) * others.length

      // هزینه‌ی جست‌وجو جدا حساب می‌شود تا هر دو مرحله در *یک* سنجش تصمیم‌گیری شوند.
      // اگر مرحله‌به‌مرحله سنجیده می‌شد، هر تغییرِ حالت یک سنجشِ تازه می‌خواست و
      // نوار می‌توانست بین دو حالت بلرزد.
      const search = inner.querySelector('.topnav-search') as HTMLElement | null
      const actions = inner.querySelector('.topnav-actions') as HTMLElement | null
      const searchCost =
        search && search.offsetWidth > 0
          ? search.offsetWidth + (actions ? px(getComputedStyle(actions).columnGap) : 0)
          : 0
      // `base` وقتی نوار tight است جست‌وجو را نمی‌شمارد (از جریان بیرون رفته).
      const withSearch = tight ? base + searchCost : base
      const withoutSearch = tight ? base : base - searchCost

      const avail = inner.clientWidth
      setTight(withSearch > avail)
      setCollapsed(withoutSearch > avail)
    }

    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(inner)
    return () => ro.disconnect()
  }, [collapsed, tight, navKey])

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

  //: با هر بار باز شدنِ کشو، گروهی که صفحه‌ی فعال در آن است باز می‌شود. بدونِ این،
  //: آکاردئونِ تماماً بسته کاربر را گم می‌کند: «الان کجای منو هستم؟» جوابی ندارد.
  const activeGroupHeading =
    groups.find(
      (g) =>
        g.items.some((i) => i.key === active) ||
        (LIST_MENUS[g.heading] ?? []).some((i) => i.key === active),
    )?.heading ?? null
  useEffect(() => {
    if (mobileOpen) setOpenGroup(activeGroupHeading)
  }, [mobileOpen, activeGroupHeading])

  // جست‌وجوی سریعِ ماژول‌ها: همه‌ی آیتم‌ها را تخت می‌کند و با متنِ ورودی فیلتر می‌کند.
  const allItems = useMemo(
    () => uniqueNavItems(groups, secondary),
    [groups, secondary],
  )
  const results = query.trim()
    ? allItems.filter((i) => i.label.includes(query.trim())).slice(0, 8)
    : []

  return (
    <header
      className={`topnav${tight ? ' topnav--tight' : ''}${collapsed ? ' topnav--collapsed' : ''}`}
      ref={barRef}
    >
      <div className="topnav-inner" ref={innerRef}>
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

        <nav className="topnav-menu" ref={menuRef}>
          {/* دراپ‌داونِ زیرمنو حذف شد: کلیک روی ماژول مستقیم واردش می‌شود و زیرمنوها
              در کارتِ «عملیات» باز می‌شوند — یک جا، نه دو جا. */}
          {groups.map((group) => {
            const hasActive = group.items.some((i) => i.key === active)
            const first = group.items[0]
            // گروهِ تک‌آیتم نامِ خودِ آیتم را می‌گیرد؛ بقیه نامِ ماژول را.
            const label = group.items.length === 1 ? first.label : group.heading
            // نشانِ خوانده‌نشده روی نامِ ماژول می‌نشیند، چون آیتمِ بازار دیگر
            // در نوار دیده نمی‌شود.
            const badgeKey = group.items.find(
              (i) => i.key === 'marketplace' || i.key === 'distributor',
            )?.key
            return (
              <button
                key={group.heading}
                type="button"
                className={`topnav-item${hasActive ? ' active' : ''}`}
                // اگر همین حالا داخلِ این ماژول هستیم، کلیک نباید از صفحه‌ی فعلی بپراند.
                onClick={() => go(hasActive ? active : first.key)}
              >
                {label}
                {badgeKey ? navBadge(badgeKey) : null}
              </button>
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
          <div className="topnav-mobile" role="dialog" aria-modal="true" aria-label="منوی اصلی">
            {/* سربرگ از بدنه جداست و `flex-shrink: 0` دارد: پیش از این کلِ کشو یک
                ظرفِ اسکرول‌دار بود و سربرگ با فهرستِ بلند فشرده می‌شد، تا جایی که
                دکمه‌ی بستن روی نامِ برند می‌نشست. حالا بدنه می‌لغزد و سربرگ سرِ جا می‌ماند. */}
            <div className="topnav-mobile-head">
              <span className="topnav-mobile-title">کوبیتا</span>
              <button
                type="button"
                className="topnav-mobile-close"
                onClick={() => setMobileOpen(false)}
                aria-label="بستنِ منو"
              >
                <X size={20} />
              </button>
            </div>

            <div className="topnav-mobile-body">
              {groups.map((group) => {
                const lists = LIST_MENUS[group.heading] ?? []
                const isOpen = openGroup === group.heading
                const hasActive =
                  group.items.some((i) => i.key === active) || lists.some((i) => i.key === active)
                return (
                  <div className={`topnav-mobile-group${isOpen ? ' open' : ''}`} key={group.heading}>
                    <button
                      type="button"
                      className={`topnav-mobile-heading${hasActive ? ' has-active' : ''}`}
                      aria-expanded={isOpen}
                      onClick={() => setOpenGroup((h) => (h === group.heading ? null : group.heading))}
                    >
                      <span className="mob-heading-label">{group.heading}</span>
                      {/* گروهِ بسته‌ای که صفحه‌ی فعال را در خود دارد نشانه می‌گیرد،
                          وگرنه با بسته‌بودن هیچ ردی از «کجا هستم» نمی‌ماند. */}
                      {hasActive && !isOpen && <span className="mob-dot" aria-hidden="true" />}
                      <ChevronDown className="mob-chev" size={16} />
                    </button>

                    <div className="topnav-mobile-panel">
                      <div className="mob-inner">
                        {group.items.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            className={`topnav-mobile-item${active === item.key ? ' active' : ''}`}
                            onClick={() => go(item.key)}
                          >
                            <span className="topnav-dd-ico">{item.icon}</span>
                            <span className="mob-item-label">{item.label}</span>
                            {navBadge(item.key)}
                          </button>
                        ))}
                        {/* منوی «فهرست»ِ همین گروه. کارتِ فهرست زیرِ ۱۰۲۴px پنهان است، پس
                            بدونِ این‌ها صفحه‌های فهرست روی موبایل از هیچ راهی باز نمی‌شدند. */}
                        {lists.map((item) => {
                          const Icon = item.icon
                          return (
                            <button
                              key={item.key}
                              type="button"
                              className={`topnav-mobile-item topnav-mobile-item--list${active === item.key ? ' active' : ''}`}
                              onClick={() => go(item.key)}
                            >
                              <span className="topnav-dd-ico"><Icon size={16} /></span>
                              <span className="mob-item-label">{item.label}</span>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )
              })}

              <div className={`topnav-mobile-group${openGroup === 'حساب کاربری' ? ' open' : ''}`}>
                <button
                  type="button"
                  className={`topnav-mobile-heading${secondary.some((i) => i.key === active) ? ' has-active' : ''}`}
                  aria-expanded={openGroup === 'حساب کاربری'}
                  onClick={() => setOpenGroup((h) => (h === 'حساب کاربری' ? null : 'حساب کاربری'))}
                >
                  <span className="mob-heading-label">حساب کاربری</span>
                  {secondary.some((i) => i.key === active) && openGroup !== 'حساب کاربری' && (
                    <span className="mob-dot" aria-hidden="true" />
                  )}
                  <ChevronDown className="mob-chev" size={16} />
                </button>
                <div className="topnav-mobile-panel">
                  <div className="mob-inner">
                    {secondary.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        className={`topnav-mobile-item${active === item.key ? ' active' : ''}`}
                        onClick={() => go(item.key)}
                      >
                        <span className="topnav-dd-ico">{item.icon}</span>
                        <span className="mob-item-label">{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* «خروج» از آکاردئون بیرون کشیده شد: با آکاردئون، دو ضربه لازم داشت و
                کاری که همیشه باید یک ضربه باشد را پشتِ یک گروهِ بسته می‌برد. */}
            <div className="topnav-mobile-foot">
              <button type="button" className="topnav-mobile-item topnav-dd-danger" onClick={onLogout}>
                <span className="topnav-dd-ico"><LogOut size={16} /></span>
                <span className="mob-item-label">خروج</span>
              </button>
            </div>
          </div>
        </>
      )}
    </header>
  )
}
