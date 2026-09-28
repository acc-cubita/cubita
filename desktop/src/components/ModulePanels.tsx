import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight, ChevronUp, ListChecks, Loader2, Play, Inbox, RotateCcw } from 'lucide-react'
import { MODULE_SECTIONS, listSections, opsSections, type SectionDef } from './moduleSections'
import {
  LIST_MENUS,
  LIST_PAGE_GROUP,
  MODULE_LISTS,
  OPS_MENUS,
  listDefFor,
  menuEntryActive,
  type ListMenuItem,
  type ListRow,
} from './moduleLists'
import { menuCategories, menuEntryVisible, navSections, type NavGroup } from '../lib/navModel'
import { DEFAULT_COLLAPSED_SECTIONS } from '../lib/menuSections'
import { useMenuOrder, type MenuOrderApi } from '../lib/menuOrder'
import type { PageKey } from './Sidebar'

/**
 * دو کارتِ کنارِ سایدبار: «عملیات» و «فهرست».
 *
 * با انتخابِ یک ماژول، این دو ستون بینِ سایدبار و ناحیه‌ی محتوا باز می‌شوند:
 *  - **عملیات:** زیرمنوهای همان ماژول. انتخابِ هرکدام دقیقاً همان تبی را باز می‌کند
 *    که نوارِ تبِ صفحه باز می‌کرد (همان `setSection`)، پس هیچ صفحه‌ای بازنویسی نشد.
 *  - **فهرست:** کارِ ذخیره‌شده‌ی همان عملیات (فاکتورهای ثبت‌شده، اسناد، چک‌ها، …).
 *
 * هر کارت جداگانه جمع‌شدنی است؛ روی نمایشگرِ کوچک، فضای فرم و جدول مهم‌تر از دیدنِ
 * همیشگیِ این دو ستون است. وضعیتِ جمع‌بودن در localStorage می‌ماند تا هر بار تکرار نشود.
 *
 * **ترتیبِ منوها دستِ کاربر است** (`MenuItem`): فلشِ بالا/پایین روی هر ردیف (با hover یا فوکوس)
 * یا Alt+↑/↓ روی خودِ منو. هر فهرست دامنه‌ی خودش را دارد و جابه‌جایی فقط داخلِ همان فهرست است؛
 * ترتیب روی همین دستگاه می‌ماند (`lib/menuOrder`) و «ترتیبِ پیش‌فرض» ته کارت برش می‌گرداند.
 */

const COLLAPSE_KEY = 'cubita.modulePanels.collapsed'
//: بازوبسته‌ی هر دسته، جدا از دو کارت. فقط انتخابِ صریحِ کاربر ذخیره می‌شود؛ نبودنِ کلید یعنی پیش‌فرض
//: (`DEFAULT_COLLAPSED_SECTIONS`).
const CATEGORY_KEY = 'cubita.modulePanels.categories'

type CategoryState = Record<string, boolean>

function loadCategories(): CategoryState {
  try {
    const raw = localStorage.getItem(CATEGORY_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return Object.fromEntries(Object.entries(parsed).filter(([, v]) => typeof v === 'boolean')) as CategoryState
    }
  } catch {
    // ترجیحِ خراب نباید منو را بشکند — همان پیش‌فرض.
  }
  return {}
}

/** آیا این صفحه جایی از منوهای این گروه هست — صفحه‌ی گروه، فهرستش، یا ورودیِ عملیاتش؟ */
const groupHas = (g: NavGroup, page: PageKey) =>
  g.items.some((i) => i.key === page) ||
  (LIST_MENUS[g.heading] ?? []).some((i) => i.key === page) ||
  (OPS_MENUS[g.heading] ?? []).some((i) => i.key === page)

/** گروهِ ناوبری‌ای که این صفحه داخلش است (صفحه‌های حسابِ کاربری در هیچ گروهی نیستند).
 *
 *  `preferred` گروهی است که کاربر همین حالا در آن بود. صفحه‌ی مشترکِ دو گروه
 *  («اعلامیه بدهکار بستانکار» در فروش و در انبار) با آن در همان گروه می‌ماند؛ بدونِ
 *  این، کلیک رویش از منوی انبار ستون‌ها را یک‌باره به منوی فروش عوض می‌کرد. */
const groupOf = (groups: NavGroup[], page: PageKey, preferred: string | null = null) =>
  groups.find((g) => g.heading === preferred && groupHas(g, page)) ??
  groups.find((g) => g.items.some((i) => i.key === page)) ??
  // صفحه‌ی فهرست خودش در منو نیست؛ گروهش را از نگاشتِ صریح می‌گیرد.
  groups.find((g) => g.heading === LIST_PAGE_GROUP[page]) ??
  null

/**
 * آیا این ماژول اصلاً دو کارت دارد؟
 *
 * پوسته با همین تصمیم کلاسِ `app-shell--panels` را می‌گذارد و CSS فقط آن‌وقت نوارِ تب
 * را پنهان می‌کند. اگر این‌جا false باشد ولی نوارِ تب پنهان شده بود، صفحه بدونِ هیچ
 * راهِ جابه‌جایی بینِ بخش‌ها می‌ماند — پس تصمیم باید یک‌جا و مشترک باشد.
 *
 * گروهِ چندصفحه‌ای هم کارت می‌گیرد حتی اگر صفحه‌ی فعلی نه بخش داشته باشد نه فهرست:
 * با حذفِ دراپ‌داونِ نوارِ بالا، کارتِ «عملیات» تنها راهِ رسیدن به صفحه‌های هم‌گروه است.
 */
export function hasModulePanels(page: PageKey, groups: NavGroup[]): boolean {
  return (
    LIST_PAGE_GROUP[page] !== undefined ||
    (groupOf(groups, page)?.items.length ?? 0) > 1 ||
    (MODULE_SECTIONS[page]?.length ?? 0) > 0 ||
    MODULE_LISTS[page] !== undefined
  )
}

type Collapsed = { ops: boolean; list: boolean }

function loadCollapsed(): Collapsed {
  try {
    const raw = localStorage.getItem(COLLAPSE_KEY)
    if (raw) return { ops: false, list: false, ...(JSON.parse(raw) as Partial<Collapsed>) }
  } catch {
    // خواندنِ ناموفق نباید چیدمان را بشکند — پیش‌فرضِ باز.
  }
  return { ops: false, list: false }
}

export function ModulePanels({
  page,
  section,
  onSelectSection,
  onNavigate,
  groups,
  token,
}: {
  page: PageKey
  section: string | null
  onSelectSection: (key: string) => void
  onNavigate: (page: PageKey, section?: string | null) => void
  groups: NavGroup[]
  token: string
}) {
  const [collapsed, setCollapsed] = useState<Collapsed>(loadCollapsed)
  const [categories, setCategories] = useState<CategoryState>(loadCategories)
  const mo = useMenuOrder()
  const toggle = (which: keyof Collapsed) =>
    setCollapsed((c) => {
      const next = { ...c, [which]: !c[which] }
      try {
        localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next))
      } catch {
        // ذخیره‌نشدنِ ترجیح مهم نیست؛ چیدمان باید کار کند.
      }
      return next
    })

  const sections = MODULE_SECTIONS[page] ?? []
  const activeSection = section ?? sections[0]?.key ?? null
  //: بخش‌های دفتری (فهرست دارایی‌ها، گزارش اسناد استهلاک، …) تبِ همین صفحه‌اند ولی
  //: جایشان ستونِ «فهرست» است — کنارِ کارهایی که کاربر *انجام می‌دهد* نمی‌نشینند.
  const ops = opsSections(sections)
  // صفحه‌های هم‌گروه فقط وقتی فهرست می‌شوند که بیش از یکی باشند؛ گروهِ تک‌صفحه‌ای
  // در نوارِ بالا هم با نامِ خودش دیده می‌شود، پس تکرارش در کارت بی‌فایده است.
  //
  // استثنا: صفحه‌ی *فهرستِ* یک گروهِ تک‌صفحه‌ای. آن‌جا نه بخشِ خودی هست و نه هم‌گروهی،
  // پس کارتِ «عملیات» اصلاً ساخته نمی‌شد و کاربر بدونِ راهِ برگشت به ماژول می‌ماند.
  const lastGroup = useRef<string | null>(null)
  const group = groupOf(groups, page, lastGroup.current)
  lastGroup.current = group?.heading ?? null
  const siblings = group?.items ?? []
  const pages = siblings.length > 1 || LIST_PAGE_GROUP[page] ? siblings : []
  //: ورودی‌ای که صفحه‌اش برای این کسب‌وکار نیست (ماژولِ خاموش، نوعِ دیگرِ کسب‌وکار) نمی‌آید.
  const reachable = <T extends { key: PageKey }>(menu: T[]) => menu.filter((e) => menuEntryVisible(e.key, groups))
  //: گروهی که منوی «عملیات»ش کار‌به‌کار است نه صفحه‌به‌صفحه («تامین‌کنندگان و انبار»).
  const opsMenu = group && OPS_MENUS[group.heading] ? reachable(OPS_MENUS[group.heading]) : undefined
  //: کارتِ «فهرست» منوی کاملِ فهرستِ همان ماژول است — همان ردیف‌هایی که کاربر برای هر
  //: ماژول تعریف کرد (دارایی ثابت پنج‌تا، تولید پنج‌تا، تامین‌کنندگان و انبار دوازده‌تا).
  //: #۱۲۴ آن را به یکی‌دوتا ردیفِ «مالِ همین عملیات» محدود کرده بود؛ کاربر گفت
  //: «تمام زیرمنوهای فهرست که تعریف کرده بودیم حذف شده» و برگشت.
  const listMenu = group && LIST_MENUS[group.heading] ? reachable(LIST_MENUS[group.heading]) : undefined
  //: ماژولِ تب‌داری که منوی گروهی ندارد: دفترهایش خودشان تب‌اند (`kind: 'list'`).
  const sectionLists = listSections(sections)
  //: کارتِ همیشه‌خالی فقط عرض می‌گیرد و چیزی نمی‌گوید؛ فقط وقتی نه منو هست، نه تبِ
  //: دفتری، نه رکوردِ زنده، کارت نمی‌آید.
  const hasList = Boolean(listMenu?.length) || sectionLists.length > 0 || listDefFor(page, activeSection) !== null

  //: دامنه‌های ترتیب — هر فهرستی که روی کارت می‌آید یکی. نامِ گروه و نه صفحه، چون همان منوی
  //: گروه از هر صفحه‌ی آن دیده می‌شود و باید یک ترتیب داشته باشد.
  const gk = group?.heading ?? page

  /**
   * دسته‌ی بازوبسته. بسته‌بودن ترجیح است نه قفل: انتخابِ صریحِ کاربر همیشه می‌برد، و بی آن
   * «تعریف‌ها» بسته است **مگر** صفحه‌ی فعال داخلش باشد — کسی که از جست‌وجو به «کالاها» رسیده
   * نباید ردیفِ خودش را زیرِ یک دسته‌ی بسته گم کند. دسته‌ی بسته‌ای که صفحه‌ی فعال را دارد نشان
   * می‌گیرد (`has-current`)، همان کارِ نقطه‌ی آکاردئونِ کشو.
   */
  const category = (card: 'ops' | 'list', title: string | null, count: number, hasCurrent: boolean) => {
    if (!title) return { collapsed: false, head: null }
    const id = `${card}:${gk}:${title}`
    const isCollapsed = categories[id] ?? (DEFAULT_COLLAPSED_SECTIONS.has(title) && !hasCurrent)
    const head = (
      <CategoryHead
        key={`h:${title}`}
        title={title}
        count={count}
        collapsed={isCollapsed}
        marked={isCollapsed && hasCurrent}
        onToggle={() =>
          setCategories((c) => {
            const next = { ...c, [id]: !isCollapsed }
            try {
              localStorage.setItem(CATEGORY_KEY, JSON.stringify(next))
            } catch {
              // ذخیره‌نشدنِ ترجیح مهم نیست؛ منو کار می‌کند.
            }
            return next
          })
        }
      />
    )
    return { collapsed: isCollapsed, head }
  }

  /** منوی گروه (`OPS_MENUS`/`LIST_MENUS`) دسته‌به‌دسته. منوی بی‌دسته همان فهرستِ یک‌دستِ قبلی است. */
  const categorizedMenu = (card: 'ops' | 'list', entries: ListMenuItem[], scope: string) => {
    const cats = menuCategories(entries)
    return cats.map((cat) => {
      const hasCurrent = cat.items.some((e) => menuEntryActive(e, page, activeSection))
      const { collapsed: shut, head } = cats.length > 1 ? category(card, cat.title, cat.items.length, hasCurrent) : { collapsed: false, head: null }
      return (
        <Fragment key={cat.title ?? ''}>
          {head}
          {!shut && menuButtons(cat.items, page, activeSection, onSelectSection, onNavigate, mo, scope)}
        </Fragment>
      )
    })
  }
  const secOps = (p: PageKey) => `sec-ops:${p}`
  const opsScopes = opsMenu
    ? [`ops:${gk}`]
    : pages.length > 0
      ? [`pages:${gk}`, ...pages.map((p) => secOps(p.key))]
      : [secOps(page)]
  const listScopes = listMenu?.length ? [`list:${gk}`] : sectionLists.length > 0 ? [`sec-list:${page}`] : []
  //: دسته‌های گروه («ساختار و تعریف‌ها»، «ثبت سند»، …) ترتیبِ ثابتِ `NAV_GROUPS` را دارند؛ ترتیبِ
  //: دلخواهِ کاربر فقط *درونِ* هر دسته است — وگرنه جابه‌جاییِ یک منو دسته‌ای را دو تکه می‌کرد.
  const pageSections = navSections(pages).map((sec) => ({
    ...sec,
    items: mo.sort(`pages:${gk}`, sec.items, (p) => p.key),
  }))

  // ماژولی که نه عملیاتِ چندگانه دارد و نه فهرست (داشبورد، راهنما، …) این ستون‌ها را
  // اصلاً نمی‌گیرد تا فضای محتوا هدر نرود.
  if (!hasModulePanels(page, groups)) return null

  return (
    <div className="mod-panels">
      {(opsMenu || ops.length > 0 || pages.length > 0) && (
        <section className={`mod-panel${collapsed.ops ? ' collapsed' : ''}`}>
          <button
            type="button"
            className="mod-panel-head"
            onClick={() => toggle('ops')}
            aria-expanded={!collapsed.ops}
            title={collapsed.ops ? 'بازکردنِ عملیات' : 'جمع‌کردنِ عملیات'}
          >
            <Play size={15} />
            <span className="mod-panel-title">عملیات</span>
            <ChevronRight size={15} className="mod-panel-chev" />
          </button>
          <div className="mod-panel-body">
            {opsMenu && categorizedMenu('ops', opsMenu, `ops:${gk}`)}
            {/* صفحه‌های هم‌گروه، و زیرِ صفحه‌ی فعال بخش‌های خودش — همان چیزی که
                پیش‌تر دراپ‌داونِ نوارِ بالا نشان می‌داد، حالا این‌جا. */}
            {!opsMenu &&
              pageSections.map((sec) => {
                const pageKeys = sec.items.filter((p) => !p.guide).map((p) => p.key)
                //: تیترِ دسته فقط وقتی گروه چند دسته دارد؛ گروهِ یک‌دست همان فهرستِ قبلی است.
                const titled = sec.title !== null && pageSections.filter((s) => s.title !== null).length > 1
                const { collapsed: shut, head } = titled
                  ? category('ops', sec.title, sec.items.length, sec.items.some((p) => p.key === page))
                  : { collapsed: false, head: null }
                return (
                  <Fragment key={sec.title ?? ''}>
                    {head}
                    {!shut && sec.items.map((it) => {
                      //: «مسیرِ کار» ردیفِ هم‌وزنِ کارها نیست؛ پیوندِ کم‌رنگِ بالای کارت است.
                      if (it.guide) {
                        const on = it.key === page
                        return (
                          <button
                            key={it.key}
                            type="button"
                            className={`mod-guide${on ? ' active' : ''}`}
                            aria-current={on ? 'page' : undefined}
                            onClick={() => onNavigate(it.key)}
                          >
                            {it.icon}
                            <span>{it.label}</span>
                          </button>
                        )
                      }
                      // صفحه‌ای که هم‌نامِ خودِ ماژول است یک سطحِ تکراری می‌سازد
                      // («حسابداری ← حسابداری ← ثبت سند»). به‌جای ردیفِ بی‌فایده، بخش‌هایش
                      // مستقیم در سطحِ اول می‌نشینند.
                      const redundant = it.label === group?.heading
                      const own = mo.sort(secOps(it.key), opsSections(MODULE_SECTIONS[it.key] ?? []), (x) => x.key)
                      if (redundant && own.length > 0) {
                        const ownKeys = own.map((x) => x.key)
                        return (
                          <Fragment key={it.key}>
                            {own.map((s) => {
                              const Icon = s.icon
                              const on = it.key === page && activeSection === s.key
                              return (
                                <MenuItem
                                  key={s.key}
                                  mo={mo}
                                  scope={secOps(it.key)}
                                  keys={ownKeys}
                                  itemKey={s.key}
                                  label={s.label}
                                  icon={<Icon size={16} />}
                                  className={`mod-op${on ? ' active' : ''}`}
                                  current={on}
                                  onClick={() => (it.key === page ? onSelectSection(s.key) : onNavigate(it.key, s.key))}
                                />
                              )
                            })}
                          </Fragment>
                        )
                      }
                      const current = it.key === page
                      const expanded = current && own.length > 0
                      return (
                        <Fragment key={it.key}>
                          <MenuItem
                            mo={mo}
                            scope={`pages:${gk}`}
                            keys={pageKeys}
                            itemKey={it.key}
                            label={it.label}
                            icon={it.icon}
                            //: صفحه‌ای که بخش‌هایش زیرش باز است «والد» است نه «فعال»: هایلایت
                            //: مالِ بخشِ انتخاب‌شده است. اگر هر دو یک‌جور برجسته شوند، دیگر
                            //: پیدا نیست کاربر دقیقاً روی کدام زیرمنو ایستاده.
                            className={`mod-op${expanded ? ' mod-op--parent' : current ? ' active' : ''}`}
                            current={current && !expanded}
                            onClick={() => onNavigate(it.key)}
                          />
                          {expanded && (
                            <div className="mod-sub">
                              {sectionButtons(own, activeSection, onSelectSection, mo, secOps(it.key))}
                            </div>
                          )}
                        </Fragment>
                      )
                    })}
                  </Fragment>
                )
              })}
            {/* ماژولِ تک‌صفحه‌ای (تولید، دارایی ثابت، …) ردیفی با نامِ خودش نمی‌گیرد: نامش
                همین حالا در نوارِ بالا هست و تکرارش در «عملیات» یک زیرمنوی بی‌معناست. */}
            {!opsMenu && pages.length === 0 && sectionButtons(ops, activeSection, onSelectSection, mo, secOps(page))}
          </div>
          {/* بیرون از بدنه‌ی اسکرول‌خور تا همیشه دیده شود و روی منوی آخر ننشیند. */}
          {mo.customized(opsScopes) && <ResetOrder onReset={() => mo.reset(opsScopes)} />}
        </section>
      )}

      {hasList && (
      <section className={`mod-panel mod-panel--list${collapsed.list ? ' collapsed' : ''}`}>
        <button
          type="button"
          className="mod-panel-head"
          onClick={() => toggle('list')}
          aria-expanded={!collapsed.list}
          title={collapsed.list ? 'بازکردنِ فهرست' : 'جمع‌کردنِ فهرست'}
        >
          <ListChecks size={15} />
          <span className="mod-panel-title">فهرست</span>
          <ChevronRight size={15} className="mod-panel-chev" />
        </button>
        <div className="mod-panel-body">
          {listMenu?.length ? (
            // هر ورودی صفحه‌ی همان فهرست را باز می‌کند (یا تبِ آن، اگر `section` دارد).
            categorizedMenu('list', listMenu, `list:${gk}`)
          ) : sectionLists.length > 0 ? (
            sectionButtons(sectionLists, activeSection, onSelectSection, mo, `sec-list:${page}`)
          ) : (
            // دفترِ جدا ندارد: چند رکوردِ آخرِ همین عملیات، زنده.
            <ListPanel token={token} page={page} section={activeSection} />
          )}
        </div>
        {mo.customized(listScopes) && <ResetOrder onReset={() => mo.reset(listScopes)} />}
      </section>
      )}
    </div>
  )
}

/** ورودی‌های منوی گروه — صفحه یا تبی از یک صفحه. تبِ همین صفحه فقط تب را عوض
 *  می‌کند؛ بقیه به صفحه‌ی خودشان (و تبشان) می‌روند. */
function menuButtons(
  entries: ListMenuItem[],
  page: PageKey,
  activeSection: string | null,
  onSelectSection: (key: string) => void,
  onNavigate: (page: PageKey, section?: string | null) => void,
  mo: MenuOrderApi,
  scope: string,
) {
  const keyOf = (e: ListMenuItem) => `${e.key}:${e.section ?? ''}`
  const sorted = mo.sort(scope, entries, keyOf)
  const keys = sorted.map(keyOf)
  return sorted.map((e) => {
    const Icon = e.icon
    const on = menuEntryActive(e, page, activeSection)
    return (
      <MenuItem
        key={keyOf(e)}
        mo={mo}
        scope={scope}
        keys={keys}
        itemKey={keyOf(e)}
        label={e.label}
        icon={<Icon size={16} />}
        className={`mod-op${on ? ' active' : ''}`}
        current={on}
        onClick={() => (e.key === page && e.section ? onSelectSection(e.section) : onNavigate(e.key, e.section ?? null))}
      />
    )
  })
}

/** دکمه‌های بخشِ صفحه‌ی فعال — چه تنها باشند چه تودرتو زیرِ نامِ صفحه. */
function sectionButtons(
  sections: SectionDef[],
  activeSection: string | null,
  onSelectSection: (key: string) => void,
  mo: MenuOrderApi,
  scope: string,
) {
  const sorted = mo.sort(scope, sections, (s) => s.key)
  const keys = sorted.map((s) => s.key)
  return sorted.map((s) => {
    const Icon = s.icon
    return (
      <MenuItem
        key={s.key}
        mo={mo}
        scope={scope}
        keys={keys}
        itemKey={s.key}
        label={s.label}
        icon={<Icon size={16} />}
        className={`mod-op${activeSection === s.key ? ' active' : ''}`}
        current={activeSection === s.key}
        onClick={() => onSelectSection(s.key)}
      />
    )
  })
}

/**
 * یک ردیفِ منو، جابه‌جاشدنی.
 *
 * فلش‌ها کنارِ خودِ منو‌اند نه داخلش (دکمه در دکمه مجاز نیست) و فقط با hover یا فوکوسِ همان
 * ردیف پیدا می‌شوند تا کارت شلوغ نشود؛ دستگاهِ بی‌hover همیشه می‌بیندشان. `tabIndex={-1}`:
 * کاربرِ صفحه‌کلید با Alt+↑/↓ روی خودِ منو جابه‌جا می‌کند، و سه ایستگاهِ Tab برای هر منو پیمایشِ
 * کارت را سه برابر می‌کرد. بعد از جابه‌جایی با صفحه‌کلید، فوکوس روی همان منو می‌ماند.
 */
function MenuItem({
  mo,
  scope,
  keys,
  itemKey,
  label,
  icon,
  className,
  current,
  onClick,
}: {
  mo: MenuOrderApi
  scope: string
  keys: string[]
  itemKey: string
  label: string
  icon: ReactNode
  className: string
  current: boolean
  onClick: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const i = keys.indexOf(itemKey)
  const move = (dir: -1 | 1, refocus: boolean) => {
    if (!mo.move(scope, keys, itemKey, dir)) return
    //: جابه‌جاییِ گره در DOM فوکوس را می‌اندازد — برمی‌گردد روی همان منو.
    if (refocus) requestAnimationFrame(() => ref.current?.focus())
  }
  return (
    <div className="mod-op-row">
      <button
        ref={ref}
        type="button"
        className={className}
        aria-current={current ? 'page' : undefined}
        aria-keyshortcuts={keys.length > 1 ? 'Alt+ArrowUp Alt+ArrowDown' : undefined}
        onClick={onClick}
        onKeyDown={(e) => {
          if (!e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return
          e.preventDefault()
          move(e.key === 'ArrowUp' ? -1 : 1, true)
        }}
      >
        {icon}
        <span>{label}</span>
      </button>
      {keys.length > 1 && (
        <span className="mod-op-move">
          <button
            type="button"
            tabIndex={-1}
            className="mod-op-arrow"
            aria-label={`بالا بردنِ «${label}»`}
            title="بالا (Alt+↑)"
            disabled={i <= 0}
            onClick={() => move(-1, false)}
          >
            <ChevronUp size={14} aria-hidden="true" />
          </button>
          <button
            type="button"
            tabIndex={-1}
            className="mod-op-arrow"
            aria-label={`پایین بردنِ «${label}»`}
            title="پایین (Alt+↓)"
            disabled={i >= keys.length - 1}
            onClick={() => move(1, false)}
          >
            <ChevronDown size={14} aria-hidden="true" />
          </button>
        </span>
      )}
    </div>
  )
}

/**
 * تیترِ دسته — دکمه‌ی بازوبسته. بسته که باشد تعدادِ ردیف‌هایش را می‌گوید، تا کاربر بداند زیرش چیزی هست
 * و چقدر؛ `marked` یعنی صفحه‌ی فعال همین زیر است.
 */
function CategoryHead({
  title,
  count,
  collapsed,
  marked,
  onToggle,
}: {
  title: string
  count: number
  collapsed: boolean
  marked: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      className={`mod-section-label${collapsed ? ' collapsed' : ''}${marked ? ' has-current' : ''}`}
      aria-expanded={!collapsed}
      title={collapsed ? `بازکردنِ «${title}»` : `جمع‌کردنِ «${title}»`}
      onClick={onToggle}
    >
      <ChevronDown size={13} className="mod-section-chev" aria-hidden="true" />
      <span className="mod-section-title">{title}</span>
      {collapsed && <span className="mod-section-count">{count.toLocaleString('fa-IR')}</span>}
    </button>
  )
}

/** ته کارت، فقط وقتی کاربر ترتیب را عوض کرده. */
function ResetOrder({ onReset }: { onReset: () => void }) {
  return (
    <button type="button" className="mod-order-reset" onClick={onReset}>
      <RotateCcw size={13} aria-hidden="true" /> ترتیبِ پیش‌فرض
    </button>
  )
}

function ListPanel({ token, page, section }: { token: string; page: PageKey; section: string | null }) {
  const def = listDefFor(page, section)
  const [rows, setRows] = useState<ListRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!def) {
      setRows(null)
      return
    }
    let cancelled = false
    setRows(null)
    setError(null)
    def
      .fetch(token)
      .then((data) => {
        if (cancelled) return
        // تازه‌ترین‌ها بالا؛ فهرست فقط یک نمای سریع است، نه جدولِ کامل.
        setRows((data as never[]).slice(0, 60).map(def.row))
      })
      .catch(() => {
        if (!cancelled) setError('فهرست بارگذاری نشد.')
      })
    return () => {
      cancelled = true
    }
    // fetcher با جفتِ (ماژول، عملیات) مشخص می‌شود.
  }, [token, page, section, def])

  if (!def) {
    return <p className="mod-list-empty">برای این عملیات فهرستی وجود ندارد.</p>
  }
  if (error) return <p className="mod-list-empty">{error}</p>
  if (rows === null) {
    return (
      <p className="mod-list-empty">
        <Loader2 size={16} className="spin" /> در حال بارگذاری…
      </p>
    )
  }
  if (rows.length === 0) {
    return (
      <p className="mod-list-empty">
        <Inbox size={16} /> هنوز چیزی ثبت نشده.
      </p>
    )
  }

  return (
    <>
      <div className="mod-list-label">{def.label}</div>
      <div className="mod-list">
        {rows.map((r) => (
          <div className="mod-list-row" key={r.id}>
            <div className="mod-list-main">
              <span className="mod-list-title">{r.title}</span>
              {r.subtitle && <span className="mod-list-sub">{r.subtitle}</span>}
            </div>
            {r.meta && <span className="mod-list-meta">{r.meta}</span>}
          </div>
        ))}
      </div>
    </>
  )
}
