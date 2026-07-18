import { Inbox, Check, Clock } from 'lucide-react'
import type { OutboxEntry } from '../electron.d'
import { EmptyState } from './EmptyState'

export function OutboxList({ entries, emptyHint }: { entries: OutboxEntry[]; emptyHint: string }) {
  if (entries.length === 0) return <EmptyState icon={Inbox} text={emptyHint} />
  return (
    <ul className="outbox-list">
      {entries.map((o) => (
        <li key={o.local_id}>
          {o.synced ? (
            <span className="outbox-status outbox-status-ok">
              <Check size={13} /> همگام‌شده (شماره سرور: {o.server_number})
            </span>
          ) : (
            <span className="outbox-status outbox-status-pending">
              <Clock size={13} /> در انتظار ارسال
            </span>
          )}
          {o.sync_error && <span className="error"> — {o.sync_error}</span>}
        </li>
      ))}
    </ul>
  )
}
