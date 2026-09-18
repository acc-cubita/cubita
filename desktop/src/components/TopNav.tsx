import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { TenantSwitcher } from './TenantSwitcher'
import {
  Menu,
  X,
  Search,
  ChevronDown,
  RefreshCw,
  LogOut,
  Building2,
  Download,
  User,
} from 'lucide-react'
import { buildNav, uniqueNavItems, type PageKey } from '../lib/navModel'
import { LIST_MENUS, OPS_MENUS, menuEntryActive } from './moduleLists'
import { MODULE_SECTIONS, listSections, opsSections } from './moduleSections'
import { useNavSection } from './navContext'
import { isElectron } from '../platform'

/** نامِ گروهِ آیتم‌های حسابِ کاربری در کشوی موبایل. */
const ACCOUNT_GROUP = 'حساب کاربری'

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
  token,
  currentTenantId,
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
  token?: string
  currentTenantId?: string
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
  //: سطحِ سومِ کشو: ماژولِ تب‌داری که بخش‌هایش باز است (فقط یکی هم‌زمان).
  const [openModule, setOpenModule] = useState<PageKey | null>(null)
  //: تبِ فعالِ صفحه — تا بخشِ انتخاب‌شده در کشو هایلایت شود.
  const navSection = useNavSection()
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

  function go(page: PageKey, section?: string) {
    onNavigate(page, section)
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
    if (!mobileOpen) return
    setOpenGroup(activeGroupHeading)
    //: ماژولِ فعالِ تب‌دار هم باز می‌شود تا بخشِ انتخاب‌شده بدونِ ضربه‌ی اضافه دیده شود.
    setOpenModule(MODULE_SECTIONS[active] ? active : null)
  }, [mobileOpen, activeGroupHeading, active])

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
                onClick={() => {
                  if (hasActive) return go(active)
                  //: گروهی با منوی کار‌به‌کار روی اولین کارش باز می‌شود، نه اولین صفحه.
                  const landing = OPS_MENUS[group.heading]?.[0]
                  go(landing?.key ?? first.key, landing?.section)
                }}
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

          {businessName && token && currentTenantId ? (
            <TenantSwitcher token={token} currentTenantId={currentTenantId} businessName={businessName} />
          ) : businessName ? (
            //: بدونِ توکن یا شناسه‌ی مستأجر، همان چیپِ خواندنیِ قبلی می‌ماند.
            <span className="topnav-org" title="کسب‌وکار">
              <Building2 size={15} />
              <span className="topnav-org-name">{businessName}</span>
            </span>
          ) : null}

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

      {/* کشوی موبایل — سه سطح: گروه ← ماژول ← بخش‌های ماژول */}
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
                const opsMenu = OPS_MENUS[group.heading]
                //: تبِ فعالِ صفحه‌ی جاری — ورودی‌های منو که به یک تب اشاره می‌کنند با آن فعال‌اند.
                const curSection = navSection?.section ?? MODULE_SECTIONS[active]?.[0]?.key ?? null
                const isOpen = openGroup === group.heading
                const hasActive =
                  group.items.some((i) => i.key === active) || lists.some((i) => i.key === active)
                return (
                  <div className={`topnav-mobile-group${isOpen ? ' open' : ''}`} key={group.heading}>
                    <MobileRow
                      level="group"
                      icon={group.icon}
                      label={group.heading}
                      expanded={isOpen}
                      marked={hasActive && !isOpen}
                      onClick={() => setOpenGroup((h) => (h === group.heading ? null : group.heading))}
                    />
                    <div className="topnav-mobile-panel">
                      <div className="mob-inner">
                        {/* تیترِ «عملیات»/«فهرست» فقط وقتی معنا دارد که گروه هر دو را داشته
                            باشد؛ گروهی که فقط عملیات دارد با یک تیترِ تنها شلوغ‌تر می‌شد. */}
                        {lists.length > 0 && <div className="mob-section-label">عملیات</div>}
                        {/* منوی کار‌به‌کار («تامین‌کنندگان و انبار»): هر ردیف یک کار است که
                            ممکن است تبی از صفحه‌ی «خرید» یا «انبار» باشد. */}
                        {opsMenu?.map((entry) => {
                          const Icon = entry.icon
                          return (
                            <MobileRow
                              key={`${entry.key}:${entry.section ?? ''}`}
                              level="item"
                              icon={<Icon size={18} />}
                              label={entry.label}
                              active={menuEntryActive(entry, active, curSection)}
                              onClick={() => go(entry.key, entry.section)}
                            />
                          )
                        })}
                        {!opsMenu && group.items.map((item) => {
                          const sections = MODULE_SECTIONS[item.key]
                          if (!sections) {
                            return (
                              <MobileRow
                                key={item.key}
                                level="item"
                                icon={item.icon}
                                label={item.label}
                                active={active === item.key}
                                trailing={navBadge(item.key)}
                                onClick={() => go(item.key)}
                              />
                            )
                          }
                          const current = active === item.key
                          const activeSection = current ? (navSection?.section ?? sections[0]?.key) : null
                          // بخش‌ها در دو دسته، همان دو ستونِ دسکتاپ: دفترها (فهرست دارایی‌ها، …)
                          // زیرِ تیترِ «فهرست» می‌آیند، نه لابه‌لای عملیات.
                          const parts = (level: 'item' | 'section') => {
                            const ledgers = listSections(sections)
                            return [opsSections(sections), ledgers].map((part, i) =>
                              part.length === 0 ? null : (
                                <Fragment key={i}>
                                  {ledgers.length > 0 && (
                                    <div className="mob-section-label">{i === 0 ? 'عملیات' : 'فهرست'}</div>
                                  )}
                                  {part.map((sec) => {
                                    const Icon = sec.icon
                                    return (
                                      <MobileRow
                                        key={sec.key}
                                        level={level}
                                        icon={<Icon size={level === 'item' ? 18 : 16} />}
                                        label={sec.label}
                                        active={activeSection === sec.key}
                                        onClick={() => go(item.key, sec.key)}
                                      />
                                    )
                                  })}
                                </Fragment>
                              ),
                            )
                          }
                          // گروهی که فقط همین یک ماژول است و هم‌نامِ آن («دارایی ثابت» ← «دارایی
                          // ثابت»): ردیفِ ماژول تکرارِ سرتیتر است، پس بخش‌ها مستقیم زیرِ گروه
                          // می‌نشینند — همان کاری که ستونِ «عملیات»ِ دسکتاپ می‌کند.
                          if (group.items.length === 1 && item.label === group.heading) {
                            return <Fragment key={item.key}>{parts('item')}</Fragment>
                          }
                          // ماژولِ تب‌دار: ضربه روی ردیف **باز/بسته** می‌کند، نه رفتن.
                          // پیش از این «تولید» فقط لینک بود و بخش‌هایش هیچ‌جای کشو نبودند —
                          // روی موبایل تنها راهِ رسیدن به «سفارش تولید» نوارِ تبِ داخلِ صفحه بود.
                          const modOpen = openModule === item.key
                          return (
                            <div className={`topnav-mobile-mod${modOpen ? ' open' : ''}`} key={item.key}>
                              <MobileRow
                                level="item"
                                icon={item.icon}
                                label={item.label}
                                expanded={modOpen}
                                parent={current}
                                marked={current && !modOpen}
                                trailing={navBadge(item.key)}
                                onClick={() => setOpenModule((m) => (m === item.key ? null : item.key))}
                              />
                              <div className="topnav-mobile-panel">
                                <div className="mob-inner mob-inner--sections">{parts('section')}</div>
                              </div>
                            </div>
                          )
                        })}
                        {/* منوی «فهرست»ِ همین گروه. کارتِ فهرست زیرِ ۱۰۲۴px پنهان است، پس
                            بدونِ این‌ها صفحه‌های فهرست روی موبایل از هیچ راهی باز نمی‌شدند. */}
                        {lists.length > 0 && <div className="mob-section-label">فهرست</div>}
                        {lists.map((item) => {
                          const Icon = item.icon
                          return (
                            <MobileRow
                              key={`${item.key}:${item.section ?? ''}`}
                              level="item"
                              icon={<Icon size={16} />}
                              label={item.label}
                              active={menuEntryActive(item, active, curSection)}
                              onClick={() => go(item.key, item.section)}
                            />
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )
              })}

              <div className={`topnav-mobile-group${openGroup === ACCOUNT_GROUP ? ' open' : ''}`}>
                <MobileRow
                  level="group"
                  icon={<User size={17} />}
                  label={ACCOUNT_GROUP}
                  expanded={openGroup === ACCOUNT_GROUP}
                  marked={secondary.some((i) => i.key === active) && openGroup !== ACCOUNT_GROUP}
                  onClick={() => setOpenGroup((h) => (h === ACCOUNT_GROUP ? null : ACCOUNT_GROUP))}
                />
                <div className="topnav-mobile-panel">
                  <div className="mob-inner">
                    {secondary.map((item) => (
                      <MobileRow
                        key={item.key}
                        level="item"
                        icon={item.icon}
                        label={item.label}
                        active={active === item.key}
                        onClick={() => go(item.key)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* «خروج» از آکاردئون بیرون کشیده شد: با آکاردئون، دو ضربه لازم داشت و
                کاری که همیشه باید یک ضربه باشد را پشتِ یک گروهِ بسته می‌برد. */}
            <div className="topnav-mobile-foot">
              <MobileRow level="item" icon={<LogOut size={17} />} label="خروج" danger onClick={onLogout} />
            </div>
          </div>
        </>
      )}
    </header>
  )
}

/**
 * یک ردیفِ کشوی موبایل — **همه‌ی سطح‌ها از همین می‌سازند**: گروه، ماژول، بخش، فهرست.
 *
 * پیش از این هر سطح markupِ خودش را داشت و هرکدام آیکون، فاصله و فلش را جور دیگری
 * می‌چید؛ نتیجه ستونی بود که آیکون‌هایش زیرِ هم نمی‌نشستند. حالا چیدمان یکی است:
 * آیکون و متن در سمتِ راست (`mob-row-main`)، فلش یا نشان در سمتِ چپ
 * (`mob-row-end`)، با `justify-content: space-between` میانشان. فرقِ سطح‌ها فقط در
 * اندازه، وزن و تورفتگی است — نه در ساختار.
 */
function MobileRow({
  level,
  icon,
  label,
  onClick,
  expanded,
  active = false,
  parent = false,
  marked = false,
  danger = false,
  trailing,
}: {
  level: 'group' | 'item' | 'section'
  icon?: ReactNode
  label: string
  onClick: () => void
  /** undefined یعنی ردیف آکاردئون نیست و فلش ندارد. */
  expanded?: boolean
  /** صفحه/بخشی که کاربر همین حالا رویش است. */
  active?: boolean
  /** ماژولِ جاری که بخش‌هایش زیرش است — برجسته، ولی نه مثلِ بخشِ فعال. */
  parent?: boolean
  /** نقطه‌ی «صفحه‌ی فعال داخلِ این شاخه‌ی بسته است». */
  marked?: boolean
  danger?: boolean
  trailing?: ReactNode
}) {
  const isAccordion = expanded !== undefined
  const cls = [
    'mob-row',
    `mob-row--${level}`,
    active && 'is-active',
    parent && 'is-parent',
    expanded && 'is-open',
    danger && 'is-danger',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button
      type="button"
      className={cls}
      onClick={onClick}
      aria-expanded={isAccordion ? expanded : undefined}
      aria-current={active ? 'page' : undefined}
    >
      <span className="mob-row-main">
        {/* ستونِ آیکون همیشه جا دارد، حتی خالی: گروهی بی‌آیکون (مثلِ «میزکار») وگرنه
            متنش را به جای آیکون می‌چسباند و از بقیه‌ی هم‌سطح‌ها بیرون می‌زد. */}
        <span className="mob-row-ico" aria-hidden="true">{icon}</span>
        <span className="mob-row-label">{label}</span>
      </span>
      {(trailing || marked || isAccordion) && (
        <span className="mob-row-end">
          {trailing}
          {marked && <span className="mob-dot" aria-hidden="true" />}
          {isAccordion && <ChevronDown className="mob-chev" size={16} aria-hidden="true" />}
        </span>
      )}
    </button>
  )
}
