import { LogOut, ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { MODULE_SECTIONS } from './moduleSections'
import { buildNav, type NavGroup, type NavItem, type PageKey } from '../lib/navModel'

// PageKey از navModel می‌آید؛ برای سازگاریِ importهای موجود (Dashboard/Tabs/…) از این‌جا هم صادر می‌شود.
export type { PageKey } from '../lib/navModel'

export function Sidebar({
  active,
  activeSection,
  onNavigate,
  userName,
  roleName,
  isPlatformAdmin,
  isSuperAdmin,
  tenantKind,
  onLogout,
  open = false,
  onClose,
}: {
  active: PageKey
  /** تبِ فعالِ صفحه (زیرمنوی سطح‌سوم)؛ null یعنی تبِ پیش‌فرض (اولین). */
  activeSection: string | null
  onNavigate: (page: PageKey, section?: string) => void
  userName: string
  roleName: string
  isPlatformAdmin: boolean
  isSuperAdmin: boolean
  /** نوعِ حساب در بازار: standard | distributor | retailer — گیتِ ماژول‌های بازار. */
  tenantKind: string
  onLogout: () => void
  /** فقط در وبِ باریک (موبایل) معنا دارد: نوار کناری کشوی روی‌هم می‌شود. */
  open?: boolean
  onClose?: () => void
}) {
  // ناوبری (گروه‌ها + آیتم‌های ثانویه) از منبعِ مشترکِ navModel با گیتِ نقش/نوعِ حساب.
  const { groups, secondary } = buildNav({ isPlatformAdmin, isSuperAdmin, tenantKind })

  // آکاردئون: فقط یک گروه هم‌زمان باز است تا نوار کوتاه بماند. به‌صورتِ پیش‌فرض،
  // گروهی که صفحه‌ی فعال در آن است باز می‌شود؛ و با تغییرِ صفحه‌ی فعال هم‌گام می‌ماند.
  const activeGroup = groups.find((g) => g.items.some((i) => i.key === active))?.heading ?? null
  const [openGroup, setOpenGroup] = useState<string | null>(activeGroup)
  useEffect(() => {
    if (activeGroup) setOpenGroup(activeGroup)
  }, [activeGroup])

  // سطح‌سوم: کدام ماژول زیرمنوی تب‌هایش باز است. فقط یکی هم‌زمان، و ماژولِ فعال
  // (اگر تب‌دار باشد) خودکار باز می‌شود.
  const [openModule, setOpenModule] = useState<PageKey | null>(
    MODULE_SECTIONS[active] ? active : null,
  )
  useEffect(() => {
    // ماژولِ فعالِ تب‌دار باز می‌شود؛ رفتن به یک صفحه‌ی بدونِ تب، زیرمنوی بازِ قبلی را می‌بندد.
    setOpenModule(MODULE_SECTIONS[active] ? active : null)
  }, [active])

  // برگِ ساده (بدونِ زیرمنو): داشبورد، صندوق، گزارش‌ها، آیتم‌های ثانویه و مدیریتی.
  const renderLeaf = (item: NavItem) => (
    <button
      key={item.key}
      type="button"
      className={`sidebar-nav-item${active === item.key ? ' active' : ''}`}
      onClick={() => {
        onNavigate(item.key)
        onClose?.()
      }}
    >
      {item.icon}
      <span>{item.label}</span>
    </button>
  )

  // ماژول: اگر تب‌دار باشد، یک آکاردئونِ سطح‌دوم با زیرمنوی تب‌ها (سطح‌سوم)؛ وگرنه برگِ ساده.
  const renderModule = (item: NavItem) => {
    const sections = MODULE_SECTIONS[item.key]
    if (!sections) return renderLeaf(item)
    const isCurrent = active === item.key
    const isOpen = openModule === item.key
    // تبِ فعال: صریح، وگرنه (وقتی هنوز تبی انتخاب نشده) اولین تب.
    const activeSecKey = isCurrent ? activeSection ?? sections[0]?.key : null
    return (
      <div className={`sidebar-mod${isOpen ? ' open' : ''}`} key={item.key}>
        {/* سرتیترِ ماژول دو ناحیه‌ی کلیک دارد: نامِ ماژول → رفتن به تبِ اول + بازکردن؛
            فلش → فقط باز/بستنِ زیرمنو (بدونِ جابه‌جایی). دو دکمه‌ی مجزا چون دکمه در
            دکمه HTML معتبر نیست. درِ کشوی موبایل باز می‌ماند تا کاربر تب را انتخاب کند. */}
        <div className={`sidebar-mod-header${isCurrent ? ' current' : ''}`}>
          <button
            type="button"
            className="sidebar-mod-main"
            onClick={() => {
              onNavigate(item.key)
              setOpenModule(item.key)
            }}
          >
            {item.icon}
            <span className="mod-label">{item.label}</span>
            {isCurrent && !isOpen && <span className="acc-dot" aria-hidden="true" />}
          </button>
          <button
            type="button"
            className="sidebar-mod-toggle"
            aria-label={isOpen ? 'بستنِ زیرمنو' : 'بازکردنِ زیرمنو'}
            aria-expanded={isOpen}
            onClick={() => setOpenModule((m) => (m === item.key ? null : item.key))}
          >
            <ChevronDown className="mod-chev" size={15} />
          </button>
        </div>
        <div className="sidebar-mod-panel">
          <div className="mod-inner">
            {sections.map((s) => (
              <button
                key={s.key}
                type="button"
                className={`sidebar-subitem${activeSecKey === s.key ? ' active' : ''}`}
                onClick={() => {
                  onNavigate(item.key, s.key)
                  onClose?.()
                }}
              >
                <span>{s.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const renderGroup = (group: NavGroup) => {
    // گروهِ تک‌آیتم (مثلِ داشبورد) نیازی به آکاردئون ندارد؛ مستقیم دیده می‌شود.
    if (group.items.length === 1) {
      return (
        <div className="sidebar-nav-solo" key={group.heading}>
          {renderModule(group.items[0])}
        </div>
      )
    }
    const isOpen = openGroup === group.heading
    const hasActive = group.items.some((i) => i.key === active)
    return (
      <div className={`sidebar-acc${isOpen ? ' open' : ''}`} key={group.heading}>
        <button
          type="button"
          className={`sidebar-acc-header${hasActive ? ' has-active' : ''}`}
          aria-expanded={isOpen}
          onClick={() => setOpenGroup((h) => (h === group.heading ? null : group.heading))}
        >
          <span className="acc-ico">{group.icon}</span>
          <span className="acc-label">{group.heading}</span>
          {hasActive && !isOpen && <span className="acc-dot" aria-hidden="true" />}
          <ChevronDown className="acc-chev" size={16} />
        </button>
        <div className="sidebar-acc-panel">
          <div className="acc-inner">{group.items.map(renderModule)}</div>
        </div>
      </div>
    )
  }

  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">C</span>
        <span className="sidebar-brand-name">کوبیتا</span>
      </div>

      <nav className="sidebar-nav">
        {groups.map(renderGroup)}
        <div className="sidebar-nav-divider" />
        <div className="sidebar-nav-group">{secondary.map(renderLeaf)}</div>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">{userName.charAt(0)}</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">{userName}</div>
            <div className="sidebar-user-role">{roleName}</div>
          </div>
        </div>
        <button type="button" className="sidebar-logout" onClick={onLogout} title="خروج">
          <LogOut size={17} />
        </button>
      </div>
      </aside>
    </>
  )
}
