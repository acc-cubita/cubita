import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, FileText } from 'lucide-react'
import { fetchJournalEntry, type JournalEntryRecord } from '../api'
import { EntryCard } from './EntryCard'

/**
 * آخرین پله‌ی drill-down: **خودِ سند با همه‌ی ردیف‌هایش**.
 *
 * تحلیل §۲۸ می‌گوید گزارش نباید بن‌بست باشد و §۱۱ می‌گوید هر عددِ مهم باید قابلِ
 * توضیح باشد. زنجیره این است:
 *
 *     تراز / مرور حساب  →  کارتِ حساب (دفتر)  →  همین سند  →  منشأش
 *
 * محتوایش را از `EntryCard`ِ مشترک می‌گیرد — همان چیزی که دفترِ روزنامه رندر
 * می‌کند. اگر این‌جا نسخه‌ی دومِ «یک سند با ردیف‌هایش» نوشته می‌شد، دو نمای یک
 * داده می‌شد و روزی از هم جدا می‌افتادند.
 */
export function JournalEntryDrawer({
  token,
  entryId,
  accountNames,
  onClose,
}: {
  token: string
  entryId: string
  accountNames?: Map<string, string>
  onClose: () => void
}) {
  const [entry, setEntry] = useState<JournalEntryRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchJournalEntry(token, entryId)
      .then((r) => { if (alive) setEntry(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
  }, [token, entryId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="drawer-head">
          <div className="drawer-title">
            <FileText size={17} />
            <div>
              <div className="drawer-title-main">سند حسابداری</div>
              <div className="drawer-title-sub">
                {entry?.number != null ? `شماره ${entry.number.toLocaleString('fa-IR')}` : '—'}
              </div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-body">
          {error && <div className="error">{error}</div>}
          {!entry && !error && <p className="muted">در حال بارگذاری…</p>}
          {entry && <EntryCard entry={entry} accountNames={accountNames} />}
        </div>
      </div>
    </div>,
    document.body,
  )
}
