import { useMemo, useState } from 'react'
import { CalendarDays, Check, Hash, MapPin, RotateCcw, Tags } from 'lucide-react'
import {
  fetchCalendarEvents,
  setCalendarEventDone,
  fetchContactGroups,
  fetchGeoLocations,
  fetchNumbering,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { CountBadge, ListToolbar, SearchField } from '../../components/form/FormKit'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, toFaDigits } from '../../lib/jalali'
import { AsyncBlock, Metric, OpsPage, faInt, useAsync } from '../accounting/kit'

/**
 * دفترهای نظیرِ عملیاتِ رکوردسازِ ماژول‌های «شرکت» و «تنظیمات».
 *
 * قاعده‌ی نظیر (اسکیلِ `cubita-page`، بخشِ ۱): هر عملیاتی که رکورد ثبت می‌کند، در
 * کارتِ «فهرست»ِ همان ماژول یک دفترِ خواندنی دارد. صفحه‌ی عملیات جای ثبت است و
 * این‌جا جای گشتن — با جمع‌ها و فیلتر، بدونِ فرم.
 */

// ═══════════════════ شرکت: محل‌های جغرافیایی ═══════════════════

export function GeoListPage({ token }: { token: string }) {
  const [q, setQ] = useState('')
  const data = useAsync(() => fetchGeoLocations(token), [token])

  const rows = useMemo(() => {
    const term = q.trim()
    return (data.data ?? []).filter((g) => !term || g.name.includes(term) || g.path.includes(term) || g.code.includes(term))
  }, [data.data, q])
  const pg = usePagination(rows, 20, q)
  const tagged = (data.data ?? []).reduce((s, g) => s + g.contact_count, 0)

  return (
    <OpsPage
      canvas
      icon={MapPin}
      title="محل‌های جغرافیایی"
      description="درختِ کشور ← استان ← شهر ← منطقه و اینکه هر محل به چند طرف‌حساب خورده است."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<MapPin size={14} />} label="محل‌ها" value={faInt((data.data ?? []).length)} />
            <Metric icon={<MapPin size={14} />} label="طرف‌حسابِ برچسب‌خورده" value={faInt(tagged)} tone="in" />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={MapPin}
        title="محل‌ها"
        badge={data.data ? <CountBadge accent>{faInt(rows.length)} ردیف</CountBadge> : undefined}
      >
        <ListToolbar>
          <SearchField value={q} onChange={setQ} placeholder="نام، مسیر یا کد" label="جست‌وجو" />
        </ListToolbar>
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="محلی با این شرایط نیست. از عملیاتِ «محل‌های جغرافیایی» بسازید."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>نوع</th>
                  <th>کد</th>
                  <th>مسیر</th>
                  <th>طرف حساب</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((g) => (
                  <tr key={g.id} className={g.is_active ? '' : 'acc-row--void'}>
                    <td className="card-title" data-label="نام">{g.name}</td>
                    <td data-label="نوع">{g.kind}</td>
                    <td data-label="کد"><span dir="ltr">{g.code || '—'}</span></td>
                    <td className="card-wide" data-label="مسیر">{g.path}</td>
                    <td className="num" data-label="طرف حساب">{faInt(g.contact_count)}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${g.is_active ? 'tone-success' : 'tone-muted'}`}>
                        {g.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ شرکت: گروه‌های طرف حساب ═══════════════════

export function ContactGroupListPage({ token }: { token: string }) {
  const data = useAsync(() => fetchContactGroups(token), [token])
  const rows = data.data ?? []
  const pg = usePagination(rows, 20)
  const tagged = rows.reduce((s, g) => s + g.contact_count, 0)

  return (
    <OpsPage
      canvas
      icon={Tags}
      title="گروه‌های طرف حساب"
      description="گروه‌بندیِ مشتریان و تأمین‌کنندگان و شمارِ اعضای هر گروه."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Tags size={14} />} label="گروه‌ها" value={faInt(rows.length)} />
            <Metric icon={<Tags size={14} />} label="عضوِ گروه‌دار" value={faInt(tagged)} tone="in" />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Tags}
        title="گروه‌ها"
        badge={data.data ? <CountBadge accent>{faInt(rows.length)} گروه</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="گروهی ثبت نشده. از عملیاتِ «گروه جدید» بسازید."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>کد</th>
                  <th>یادداشت</th>
                  <th>اعضا</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((g) => (
                  <tr key={g.id} className={g.is_active ? '' : 'acc-row--void'}>
                    <td className="card-title" data-label="نام">{g.name}</td>
                    <td data-label="کد"><span dir="ltr">{g.code || '—'}</span></td>
                    <td className="card-wide" data-label="یادداشت">{g.notes || '—'}</td>
                    <td className="num" data-label="اعضا">{faInt(g.contact_count)}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${g.is_active ? 'tone-success' : 'tone-muted'}`}>
                        {g.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ شرکت: رویدادهای تقویم ═══════════════════

const CATEGORY_LABEL: Record<string, string> = {
  general: 'عمومی',
  check: 'چک',
  installment: 'قسط',
  receivable: 'مطالبات',
  inventory: 'انبار',
  recurring: 'سند تکرارشونده',
  credit: 'اعتبار',
}

export function CalendarListPage({ token }: { token: string }) {
  const [only, setOnly] = useState<'all' | 'open' | 'done'>('all')
  //: بدونِ این کلید، فهرست بعد از «انجام شد» تازه نمی‌شود و کاربر فکر می‌کند
  //: دکمه کار نکرده. تبِ قبلیِ تقویم همین را داشت و با جابه‌جایی گم شده بود.
  const [reloadKey, setReloadKey] = useState(0)
  const [busyId, setBusyId] = useState<string | null>(null)
  const data = useAsync(() => fetchCalendarEvents(token), [token, reloadKey])

  async function toggleDone(id: string, next: boolean) {
    setBusyId(id)
    try {
      await setCalendarEventDone(token, id, next)
      setReloadKey((k) => k + 1)
    } finally {
      setBusyId(null)
    }
  }

  const rows = useMemo(() => {
    return (data.data ?? [])
      .filter((e) => (only === 'open' ? !e.is_done : only === 'done' ? e.is_done : true))
      .sort((a, b) => b.event_date.localeCompare(a.event_date))
  }, [data.data, only])
  const pg = usePagination(rows, 20, only)
  const open = (data.data ?? []).filter((e) => !e.is_done).length

  return (
    <OpsPage
      canvas
      icon={CalendarDays}
      title="رویدادهای تقویم"
      description="همه‌ی یادآوری‌ها و رویدادهای ثبت‌شده — انجام‌شده و باز."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <div className="cc-presets">
              {(
                [
                  ['all', 'همه'],
                  ['open', 'باز'],
                  ['done', 'انجام‌شده'],
                ] as const
              ).map(([key, label]) => (
                <button key={key} type="button" className={only === key ? 'is-active' : ''} onClick={() => setOnly(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-summary">
            <Metric icon={<CalendarDays size={14} />} label="رویدادها" value={faInt((data.data ?? []).length)} />
            <Metric icon={<CalendarDays size={14} />} label="باز" value={faInt(open)} tone={open > 0 ? 'out' : 'in'} />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={CalendarDays}
        title="رویدادها"
        badge={data.data ? <CountBadge accent>{faInt(rows.length)} ردیف</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="رویدادی با این فیلتر نیست. از عملیاتِ «تقویم و یادآوری» بسازید."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>عنوان</th>
                  <th>دسته</th>
                  <th>ساعت</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((e) => (
                  <tr key={e.id} className={e.is_done ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(e.event_date)}</td>
                    <td className="card-wide" data-label="عنوان">{e.title}</td>
                    <td data-label="دسته">{CATEGORY_LABEL[e.category] ?? e.category}</td>
                    <td data-label="ساعت">
                      {e.start_time ? <span dir="ltr">{e.start_time}</span> : '—'}
                    </td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${e.is_done ? 'tone-success' : 'tone-warning'}`}>
                        {e.is_done ? 'انجام شد' : 'باز'}
                      </span>
                    </td>
                    <td className="card-actions">
                      <button
                        type="button"
                        disabled={busyId === e.id}
                        onClick={() => void toggleDone(e.id, !e.is_done)}
                      >
                        {e.is_done ? (
                          <>
                            <RotateCcw size={13} /> بازگشایی
                          </>
                        ) : (
                          <>
                            <Check size={13} /> انجام شد
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ تنظیمات: روش‌های شماره‌گذاری ═══════════════════

export function NumberingListPage({ token }: { token: string }) {
  const data = useAsync(() => fetchNumbering(token), [token])
  const rows = data.data ?? []
  const pg = usePagination(rows, 20)

  return (
    <OpsPage
      canvas
      icon={Hash}
      title="روش‌های شماره‌گذاری"
      description="شماره‌ی بعدیِ هر نوع سند — همان چیزی که هنگامِ ثبت روی مدرک می‌نشیند."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Hash size={14} />} label="انواعِ سند" value={faInt(rows.length)} />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Hash}
        title="شماره‌گذاری"
        badge={data.data ? <CountBadge accent>{faInt(rows.length)} نوع سند</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="هنوز شماره‌گذاری‌ای تعریف نشده."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th>نوع سند</th>
                  <th>آخرین شماره</th>
                  <th>شماره‌ی بعدی</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.doc_type}>
                    <td className="card-title" data-label="نوع سند">{r.label}</td>
                    <td className="num" data-label="آخرین شماره">{toFaDigits(r.last_number)}</td>
                    <td className="num" data-label="شماره‌ی بعدی">{toFaDigits(r.next_number)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
