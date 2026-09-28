import { Inbox, Check, Clock, Pencil } from 'lucide-react'
import type { OutboxEntry } from '../electron.d'
import { EmptyState } from './EmptyState'
import { outboxErrorText } from '../lib/outboxError'
import { formatJalali } from '../lib/jalali'

function journalSummary(entry: OutboxEntry): string {
  try {
    const data = JSON.parse(entry.payload)
    return `${formatJalali(data.entry_date)} — ${data.description || 'بدون شرح'}`
  } catch { return 'اطلاعات سند خوانده نشد' }
}

export function OutboxList({ entries, emptyHint, onEdit, editingId, editBusy = false }: {
  entries: OutboxEntry[]; emptyHint: string; onEdit?: (entry: OutboxEntry) => void; editingId?: string; editBusy?: boolean
}) {
  if (entries.length === 0) return <EmptyState icon={Inbox} text={emptyHint} />
  return (
    <ul className="outbox-list">
      {entries.map((o) => (
        <li key={o.local_id}>
          {onEdit && <div className="muted">{journalSummary(o)}</div>}
          {o.synced ? (
            <span className="outbox-status outbox-status-ok">
              <Check size={13} /> همگام‌شده (شماره سرور: {o.server_number?.toLocaleString('fa-IR') ?? '—'})
            </span>
          ) : (
            <span className="outbox-status outbox-status-pending">
              <Clock size={13} /> در انتظار ارسال
            </span>
          )}
          {o.sync_error && <span className="error"> — {outboxErrorText(o.sync_error)}</span>}
          {!o.synced && onEdit && <button type="button" className="btn-secondary" disabled={editBusy || Boolean(editingId)} onClick={() => onEdit(o)}>
            <Pencil size={13} />{editingId === o.local_id ? 'در حال ویرایش' : 'ویرایش سند'}
          </button>}
        </li>
      ))}
    </ul>
  )
}
