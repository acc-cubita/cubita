import { useEffect, type ReactNode } from 'react'
import { ChevronLeft } from 'lucide-react'
import { SITE_NAME, applyMeta, type PageMeta } from '../seo/meta'
import { SiteFooter, SiteHeader } from './SiteChrome'
import './concept.css'

/**
 * پوسته‌ی هر صفحه: سرصفحه، مسیرِ صفحه (breadcrumb)، محتوا و پاصفحه.
 *
 * فرادادهٔ همان صفحه را هم روی سند می‌گذارد — پیش‌رندر آن را از پیش در `<head>` نوشته، و این برای
 * اجرای توسعه (بی پیش‌رندر) و ناوبریِ درون‌برنامه‌ای است.
 */
export function PageLayout({ meta, children }: { meta: PageMeta; children: ReactNode }) {
  useEffect(() => applyMeta(meta), [meta])
  return (
    <div className="cc-root" dir="rtl">
      <SiteHeader />
      <main>
        {meta.breadcrumb?.length ? <Breadcrumbs meta={meta} /> : null}
        {children}
      </main>
      <SiteFooter />
    </div>
  )
}

function Breadcrumbs({ meta }: { meta: PageMeta }) {
  const crumbs = [{ name: SITE_NAME, path: '/' }, ...(meta.breadcrumb ?? [])]
  return (
    <nav className="cc-crumbs" aria-label="مسیر صفحه">
      <ol>
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1
          return (
            <li key={c.path}>
              {last ? <span aria-current="page">{c.name}</span> : <a href={c.path}>{c.name}</a>}
              {!last && <ChevronLeft size={14} aria-hidden="true" />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
