import { Clock3, History } from 'lucide-react'
import type { JournalEditEvent } from '../api'
import { toFaDigits } from '../lib/jalali'
import { journalEditChanges } from '../lib/journalEditChanges'

export function JournalEntryHistory({ events, loading, error }: {
  events: JournalEditEvent[]
  loading: boolean
  error: string | null
}) {
  return <section className="entry-history" aria-label="تاریخچه ویرایش سند">
    <header><History size={19} /><div><h3>تاریخچهٔ ویرایش</h3><p>آخرین اصلاح بالاست؛ هر نسخه و دلیل آن در دفتر حسابرسی نگه‌داری می‌شود.</p></div></header>
    {loading && <p role="status">در حال دریافت تاریخچه…</p>}
    {error && <p role="alert" className="entry-edit-error">تاریخچه دریافت نشد: {error}</p>}
    {!loading && !error && events.length === 0 && <p className="entry-history-empty">این سند هنوز ویرایش نشده است.</p>}
    {events.map((event, index) => {
      const changes = journalEditChanges(event)
      const reason = event.changes?.edit_reason?.to
      const editorName = event.changes?.editor_name?.to
      const when = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.at))
      return <article className="entry-history-event" key={event.id}>
        <div className="entry-history-event-head">
          <span className="entry-history-step">{toFaDigits(events.length - index)}</span>
          <div><strong>{editorName ? String(editorName) : event.actor_email}</strong><small><bdi>{event.actor_email}</bdi></small></div>
          <time dateTime={event.at}><Clock3 size={14} /> {when}</time>
        </div>
        {reason != null && reason !== '' && <p className="entry-history-reason">دلیل: {String(reason)}</p>}
        {changes.length > 0 ? <div className="entry-history-diff">{changes.map((change, i) => <div key={`${change.label}-${i}`}>
          <span>{change.label}</span><del>{change.before}</del><span aria-hidden="true">←</span><ins>{change.after}</ins>
        </div>)}</div> : <p className="muted">{event.summary}</p>}
      </article>
    })}
  </section>
}
