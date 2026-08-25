import { Fragment, useEffect, useState } from 'react'
import { ChevronRight, ListChecks, Loader2, Play, Inbox } from 'lucide-react'
import { MODULE_SECTIONS, type SectionDef } from './moduleSections'
import { MODULE_LISTS, listDefFor, type ListRow } from './moduleLists'
import type { NavGroup } from '../lib/navModel'
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
 */

const COLLAPSE_KEY = 'cubita.modulePanels.collapsed'

/** گروهِ ناوبری‌ای که این صفحه داخلش است (صفحه‌های حسابِ کاربری در هیچ گروهی نیستند). */
const groupOf = (groups: NavGroup[], page: PageKey) =>
  groups.find((g) => g.items.some((i) => i.key === page)) ?? null

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
  // صفحه‌های هم‌گروه فقط وقتی فهرست می‌شوند که بیش از یکی باشند؛ گروهِ تک‌صفحه‌ای
  // در نوارِ بالا هم با نامِ خودش دیده می‌شود، پس تکرارش در کارت بی‌فایده است.
  const group = groupOf(groups, page)
  const siblings = group?.items ?? []
  const pages = siblings.length > 1 ? siblings : []

  // ماژولی که نه عملیاتِ چندگانه دارد و نه فهرست (داشبورد، راهنما، …) این ستون‌ها را
  // اصلاً نمی‌گیرد تا فضای محتوا هدر نرود.
  if (!hasModulePanels(page, groups)) return null

  return (
    <div className="mod-panels">
      {(sections.length > 0 || pages.length > 0) && (
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
            {/* صفحه‌های هم‌گروه، و زیرِ صفحه‌ی فعال بخش‌های خودش — همان چیزی که
                پیش‌تر دراپ‌داونِ نوارِ بالا نشان می‌داد، حالا این‌جا. */}
            {pages.map((it) => {
              // صفحه‌ای که هم‌نامِ خودِ ماژول است یک سطحِ تکراری می‌سازد
              // («حسابداری ← حسابداری ← ثبت سند»). به‌جای ردیفِ بی‌فایده، بخش‌هایش
              // مستقیم در سطحِ اول می‌نشینند.
              const redundant = it.label === group?.heading
              const own = MODULE_SECTIONS[it.key] ?? []
              if (redundant && own.length > 0) {
                return (
                  <Fragment key={it.key}>
                    {own.map((s) => {
                      const Icon = s.icon
                      const on = it.key === page && activeSection === s.key
                      return (
                        <button
                          key={s.key}
                          type="button"
                          className={`mod-op${on ? ' active' : ''}`}
                          onClick={() =>
                            it.key === page ? onSelectSection(s.key) : onNavigate(it.key, s.key)
                          }
                        >
                          <Icon size={16} />
                          <span>{s.label}</span>
                        </button>
                      )
                    })}
                  </Fragment>
                )
              }
              return (
                <Fragment key={it.key}>
                  <button
                    type="button"
                    className={`mod-op${it.key === page ? ' active' : ''}`}
                    onClick={() => onNavigate(it.key)}
                  >
                    {it.icon}
                    <span>{it.label}</span>
                  </button>
                  {it.key === page && own.length > 0 && (
                    <div className="mod-sub">{sectionButtons(own, activeSection, onSelectSection)}</div>
                  )}
                </Fragment>
              )
            })}
            {pages.length === 0 && sectionButtons(sections, activeSection, onSelectSection)}
          </div>
        </section>
      )}

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
          <ListPanel token={token} page={page} section={activeSection} />
        </div>
      </section>
    </div>
  )
}

/** دکمه‌های بخشِ صفحه‌ی فعال — چه تنها باشند چه تودرتو زیرِ نامِ صفحه. */
function sectionButtons(
  sections: SectionDef[],
  activeSection: string | null,
  onSelectSection: (key: string) => void,
) {
  return sections.map((s) => {
    const Icon = s.icon
    return (
      <button
        key={s.key}
        type="button"
        className={`mod-op${activeSection === s.key ? ' active' : ''}`}
        onClick={() => onSelectSection(s.key)}
      >
        <Icon size={16} />
        <span>{s.label}</span>
      </button>
    )
  })
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
