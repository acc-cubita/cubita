import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BellRing,
  CalendarCheck2,
  CalendarDays,
  CalendarPlus,
  ChevronLeft,
  ChevronRight,
  Check,
  Clock,
  ListChecks,
  Pencil,
  RotateCcw,
  Save,
  Trash2,
  X,
} from 'lucide-react'
import {
  createCalendarEvent,
  deleteCalendarEvent,
  fetchCalendarEvents,
  setCalendarEventDone,
  updateCalendarEvent,
  type CalendarCategory,
  type CalendarEventIn,
  type CalendarEventRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { ReminderCenterPanel } from '../components/ReminderCenterPanel'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { Pager, usePagination } from '../components/Pager'
import {
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAY_SHORT,
  buildJalaliMonthCells,
  formatJalali,
  isoToJalali,
  jalaliToIso,
  toFaDigits,
  todayIso,
} from '../lib/jalali'

const CATEGORY_META: Record<CalendarCategory, { label: string; cls: string }> = {
  reminder: { label: 'یادآوری', cls: 'cat-reminder' },
  meeting: { label: 'جلسه', cls: 'cat-meeting' },
  payment: { label: 'پرداخت / چک', cls: 'cat-payment' },
  tax: { label: 'مالیات', cls: 'cat-tax' },
  task: { label: 'کار', cls: 'cat-task' },
  other: { label: 'سایر', cls: 'cat-other' },
}

const CATEGORY_ORDER: CalendarCategory[] = ['reminder', 'meeting', 'payment', 'tax', 'task', 'other']

interface FormState {
  title: string
  category: CalendarCategory
  event_date: string
  start_time: string
  end_time: string
  description: string
  is_done: boolean
}

const emptyForm = (): FormState => ({
  title: '',
  category: 'reminder',
  event_date: todayIso(),
  start_time: '',
  end_time: '',
  description: '',
  is_done: false,
})

function timeRange(ev: CalendarEventRecord): string {
  if (!ev.start_time) return 'تمام‌روز'
  return ev.end_time ? toFaDigits(`${ev.start_time} - ${ev.end_time}`) : toFaDigits(ev.start_time)
}

export function CalendarPage({ token }: { token: string }) {
  const [events, setEvents] = useState<CalendarEventRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formMessage, setFormMessage] = useState<string | null>(null)

  // نمای ماه (شمسی)
  const initial = isoToJalali(todayIso())
  const [viewYear, setViewYear] = useState(initial.jy)
  const [viewMonth, setViewMonth] = useState(initial.jm)

  // فیلترهای تب فهرست
  const [filterCategory, setFilterCategory] = useState<'all' | CalendarCategory>('all')
  const [showDone, setShowDone] = useState(true)
  const [search, setSearch] = useState('')

  async function refresh() {
    setError(null)
    try {
      setEvents(await fetchCalendarEvents(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  // نگاشت تاریخِ ISO → رویدادها، برای پرکردنِ سریعِ خانه‌های ماه
  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEventRecord[]>()
    for (const ev of events) {
      const list = map.get(ev.event_date) ?? []
      list.push(ev)
      map.set(ev.event_date, list)
    }
    return map
  }, [events])

  // شاخص‌های بالای صفحه
  const kpis = useMemo(() => {
    const todayStr = todayIso()
    const done = events.filter((e) => e.is_done).length
    const pending = events.filter((e) => !e.is_done)
    const overdue = pending.filter((e) => e.event_date < todayStr).length
    return { total: events.length, done, pending: pending.length, overdue }
  }, [events])

  const cells = buildJalaliMonthCells(viewYear, viewMonth)
  const today = isoToJalali(todayIso())
  const selected = form.event_date ? isoToJalali(form.event_date) : null

  function resetForm() {
    setForm(emptyForm())
    setEditingId(null)
    setFormMessage(null)
  }

  function startEdit(ev: CalendarEventRecord) {
    setEditingId(ev.id)
    setForm({
      title: ev.title,
      category: ev.category,
      event_date: ev.event_date,
      start_time: ev.start_time ?? '',
      end_time: ev.end_time ?? '',
      description: ev.description,
      is_done: ev.is_done,
    })
    setFormMessage(null)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setFormMessage(null)
    if (!form.title.trim()) {
      setFormMessage('عنوان رویداد الزامی است.')
      return
    }
    if (form.end_time && form.start_time && form.end_time < form.start_time) {
      setFormMessage('ساعت پایان نمی‌تواند قبل از ساعت شروع باشد.')
      return
    }
    const payload: CalendarEventIn = {
      title: form.title.trim(),
      description: form.description,
      event_date: form.event_date,
      start_time: form.start_time || null,
      end_time: form.end_time || null,
      category: form.category,
      is_done: form.is_done,
    }
    try {
      if (editingId) {
        await updateCalendarEvent(token, editingId, payload)
        setFormMessage('رویداد ویرایش شد.')
      } else {
        await createCalendarEvent(token, payload)
        setFormMessage('رویداد جدید ثبت شد.')
      }
      setForm({ ...emptyForm(), event_date: form.event_date })
      setEditingId(null)
      await refresh()
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(ev: CalendarEventRecord) {
    if (!window.confirm(`رویداد «${ev.title}» حذف شود؟`)) return
    try {
      await deleteCalendarEvent(token, ev.id)
      if (editingId === ev.id) resetForm()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function toggleDone(ev: CalendarEventRecord) {
    try {
      await setCalendarEventDone(token, ev.id, !ev.is_done)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  function selectDay(iso: string) {
    setForm((f) => ({ ...f, event_date: iso }))
    if (editingId) setEditingId(null) // انتخاب یک روزِ تازه یعنی «رویداد جدید»، نه ادامه‌ی ویرایش
  }

  function prevMonth() {
    if (viewMonth === 1) {
      setViewYear((y) => y - 1)
      setViewMonth(12)
    } else setViewMonth((m) => m - 1)
  }

  function nextMonth() {
    if (viewMonth === 12) {
      setViewYear((y) => y + 1)
      setViewMonth(1)
    } else setViewMonth((m) => m + 1)
  }

  function goToday() {
    const t = isoToJalali(todayIso())
    setViewYear(t.jy)
    setViewMonth(t.jm)
  }

  const filteredList = useMemo(() => {
    return events
      .filter((ev) => {
        if (filterCategory !== 'all' && ev.category !== filterCategory) return false
        if (!showDone && ev.is_done) return false
        if (search && !ev.title.includes(search) && !ev.description.includes(search)) return false
        return true
      })
      .sort((a, b) => {
        if (a.event_date !== b.event_date) return a.event_date < b.event_date ? 1 : -1 // تازه‌ترین بالا
        return (a.start_time ?? '') < (b.start_time ?? '') ? -1 : 1
      })
  }, [events, filterCategory, showDone, search])
  // صفحه‌بندیِ فهرستِ رویدادها (۱۰ ردیف)؛ با تغییرِ فیلتر/جست‌وجو به صفحه‌ی اول برمی‌گردد.
  const evPg = usePagination(filteredList, 10, `${filterCategory}|${showDone}|${search}`)

  const eventForm = (
    <SectionCard
      icon={editingId ? Pencil : CalendarPlus}
      title={editingId ? 'ویرایش رویداد' : 'رویداد / یادآوری جدید'}
      actions={
        editingId ? (
          <button onClick={resetForm}>
            <X size={13} /> انصراف
          </button>
        ) : undefined
      }
    >
      <form className="invoice-form" onSubmit={handleSave}>
        <label>
          عنوان
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="مثلاً: سررسید چک شماره ۱۲۳"
            required
          />
        </label>
        <label>
          دسته‌بندی
          <select
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value as CalendarCategory })}
          >
            {CATEGORY_ORDER.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_META[c].label}
              </option>
            ))}
          </select>
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={form.event_date} onChange={(iso) => setForm({ ...form, event_date: iso })} />
        </label>
        <div className="cal-time-row">
          <label>
            ساعت شروع (اختیاری)
            <input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
          </label>
          <label>
            ساعت پایان (اختیاری)
            <input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
          </label>
        </div>
        <label>
          توضیحات
          <input
            type="text"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </label>
        <label className="cal-check-inline">
          <input type="checkbox" checked={form.is_done} onChange={(e) => setForm({ ...form, is_done: e.target.checked })} />
          انجام‌شده / رسیدگی‌شده
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary">
            <Save size={14} /> {editingId ? 'ذخیره تغییرات' : 'ثبت رویداد'}
          </button>
          {editingId && (
            <button
              type="button"
              className="icon-btn-danger"
              onClick={() => {
                const ev = events.find((x) => x.id === editingId)
                if (ev) void handleDelete(ev)
              }}
            >
              <Trash2 size={14} /> حذف
            </button>
          )}
        </div>
        {formMessage && <div className="hint">{formMessage}</div>}
      </form>
    </SectionCard>
  )

  const monthView = (
    <SectionCard
      icon={CalendarDays}
      title={`${JALALI_MONTH_NAMES[viewMonth - 1]} ${toFaDigits(viewYear)}`}
      actions={
        <div className="cal-nav">
          <button type="button" onClick={goToday}>
            امروز
          </button>
          <button type="button" onClick={prevMonth} title="ماه قبل" aria-label="ماه قبل">
            <ChevronRight size={16} />
          </button>
          <button type="button" onClick={nextMonth} title="ماه بعد" aria-label="ماه بعد">
            <ChevronLeft size={16} />
          </button>
        </div>
      }
    >
      <div className="cal-grid">
        {JALALI_WEEKDAY_SHORT.map((w) => (
          <div key={w} className="cal-weekday">
            {w}
          </div>
        ))}
        {cells.map((d, idx) => {
          if (d === null) return <div key={idx} className="cal-cell empty" />
          const iso = jalaliToIso(viewYear, viewMonth, d)
          const dayEvents = eventsByDate.get(iso) ?? []
          const isToday = today.jy === viewYear && today.jm === viewMonth && today.jd === d
          const isSelected = !!selected && selected.jy === viewYear && selected.jm === viewMonth && selected.jd === d
          return (
            <div
              key={idx}
              className={`cal-cell${isToday ? ' today' : ''}${isSelected ? ' selected' : ''}`}
              onClick={() => selectDay(iso)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  selectDay(iso)
                }
              }}
            >
              <span className="cal-cell-num">{toFaDigits(d)}</span>
              <div className="cal-cell-events">
                {dayEvents.slice(0, 3).map((ev) => (
                  <button
                    key={ev.id}
                    type="button"
                    className={`cal-chip ${CATEGORY_META[ev.category].cls}${ev.is_done ? ' done' : ''}`}
                    title={`${ev.title}${ev.start_time ? ` — ${ev.start_time}` : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      startEdit(ev)
                    }}
                  >
                    {ev.title}
                  </button>
                ))}
                {dayEvents.length > 3 && <span className="cal-more">+{toFaDigits(dayEvents.length - 3)} بیشتر</span>}
              </div>
            </div>
          )
        })}
      </div>
    </SectionCard>
  )

  const listView = (
    <SectionCard
      icon={ListChecks}
      title="همه‌ی رویدادها و یادآوری‌ها"
      actions={
        <div className="check-actions">
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value as typeof filterCategory)}>
            <option value="all">همه‌ی دسته‌ها</option>
            {CATEGORY_ORDER.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_META[c].label}
              </option>
            ))}
          </select>
          <label className="cal-check-inline">
            <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />
            نمایش انجام‌شده‌ها
          </label>
          <input type="text" placeholder="جستجو..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      }
    >
      {filteredList.length === 0 ? (
        <EmptyState icon={CalendarDays} text="رویدادی مطابق فیلتر پیدا نشد." />
      ) : (
        <div className="entity-table-wrap">
        <table className="entity-table cal-list-table">
          <thead>
            <tr>
              <th>وضعیت</th>
              <th>تاریخ</th>
              <th>ساعت</th>
              <th>عنوان</th>
              <th>دسته</th>
              <th>اقدام</th>
            </tr>
          </thead>
          <tbody>
            {evPg.pageItems.map((ev) => (
              <tr key={ev.id} className={ev.is_done ? 'cal-row-done' : ''}>
                <td className="cal-status-cell" data-label="وضعیت">
                  <button
                    type="button"
                    className={`cal-done-toggle${ev.is_done ? ' on' : ''}`}
                    onClick={() => toggleDone(ev)}
                    title={ev.is_done ? 'برگرداندن به انجام‌نشده' : 'علامت انجام‌شده'}
                  >
                    {ev.is_done ? <Check size={14} /> : <RotateCcw size={14} />}
                  </button>
                </td>
                <td data-label="تاریخ">{formatJalali(ev.event_date)}</td>
                <td data-label="ساعت">{timeRange(ev)}</td>
                <td className="entity-name">
                  <div className="cal-list-title">{ev.title}</div>
                  {ev.description && <div className="cal-list-desc">{ev.description}</div>}
                </td>
                <td data-label="دسته">
                  <span className={`status-badge cal-badge ${CATEGORY_META[ev.category].cls}`}>
                    {CATEGORY_META[ev.category].label}
                  </span>
                </td>
                <td className="cal-action-cell">
                  <div className="cal-row-actions">
                    <button type="button" onClick={() => startEdit(ev)}>
                      <Pencil size={13} /> ویرایش
                    </button>
                    <button type="button" className="icon-btn-danger" onClick={() => handleDelete(ev)} title="حذف">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={evPg.page} pageCount={evPg.pageCount} onChange={evPg.setPage} />
        </div>
      )}
    </SectionCard>
  )

  return (
    <div className="page">
      <PageHeader
        icon={CalendarDays}
        title="تقویم و یادآوری"
        description="رویدادها، جلسات، سررسید چک‌ها و یادآوری‌های کسب‌وکار را ثبت کنید؛ در نمای ماهانه‌ی شمسی ببینید و مدیریت کنید."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<CalendarDays size={18} />} label="کل رویدادها" value={kpis.total.toLocaleString('fa-IR')} />
        <StatCard icon={<CalendarCheck2 size={18} />} label="انجام‌شده" value={kpis.done.toLocaleString('fa-IR')} tone="success" />
        <StatCard icon={<Clock size={18} />} label="در انتظار" value={kpis.pending.toLocaleString('fa-IR')} />
        <StatCard
          icon={<AlertTriangle size={18} />}
          label="عقب‌افتاده"
          value={kpis.overdue.toLocaleString('fa-IR')}
          tone={kpis.overdue > 0 ? 'danger' : 'default'}
        />
      </div>

      <Tabs
        syncPage="calendar"
        tabs={[
          {
            key: 'reminders',
            label: 'کارهای امروز',
            icon: BellRing,
            content: <ReminderCenterPanel token={token} />,
          },
          {
            key: 'calendar',
            label: 'تقویم ماهانه',
            icon: CalendarDays,
            content: (
              <div className="cal-layout">
                {monthView}
                {eventForm}
              </div>
            ),
          },
          {
            key: 'list',
            label: 'فهرست رویدادها',
            icon: ListChecks,
            content: (
              <>
                {eventForm}
                {listView}
              </>
            ),
          },
        ]}
      />
    </div>
  )
}
