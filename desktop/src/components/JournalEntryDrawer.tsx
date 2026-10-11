import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, FileText, AlertTriangle, RotateCcw, Pencil } from 'lucide-react'
import { fetchJournalEntry, fetchJournalEditHistory, type JournalEntryRecord, type JournalEditEvent } from '../api'
import { toFaDigits } from '../lib/jalali'
import { entryErrorText } from '../lib/entryPresentation'
import { EntryCard } from './EntryCard'
import { JournalEntryEditForm } from './JournalEntryEditForm'
import { JournalEntryHistory } from './JournalEntryHistory'

/** آخرین پلهٔ drill-down؛ محتوا فقط از EntryCard مشترک می‌آید. */
export function JournalEntryDrawer({ token, entryId, accountNames, onClose }: {
  token: string
  entryId: string
  accountNames?: Map<string, string>
  onClose: () => void
}) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  const [attempt, setAttempt] = useState(0)
  const [historyAttempt, setHistoryAttempt] = useState(0)
  const [editing, setEditing] = useState(false)
  const requestKey = JSON.stringify([token, entryId, attempt])
  const [result, setResult] = useState<{ key: string; entry?: JournalEntryRecord; error?: string } | null>(null)
  // تعویض سند/حساب یا تلاش مجدد نباید حتی یک فریم سند قبلی را نشان دهد.
  const current = result?.key === requestKey ? result : null
  const historyKey = JSON.stringify([token, entryId, historyAttempt])
  const [historyResult, setHistoryResult] = useState<{ key: string; events?: JournalEditEvent[]; error?: string } | null>(null)
  const history = historyResult?.key === historyKey ? historyResult : null
  const close = () => {
    if (editing && !window.confirm('اصلاحات ذخیره‌نشده کنار گذاشته شوند؟')) return
    onCloseRef.current()
  }
  const closeAction = useRef(close)
  closeAction.current = close

  useEffect(() => {
    let alive = true
    fetchJournalEntry(token, entryId)
      .then((entry) => { if (alive) setResult({ key: requestKey, entry }) })
      .catch((error) => {
        if (alive) setResult({ key: requestKey, error: entryErrorText(error) })
      })
    return () => { alive = false }
  }, [token, entryId, requestKey])

  useEffect(() => {
    let alive = true
    fetchJournalEditHistory(token, entryId)
      .then((events) => { if (alive) setHistoryResult({ key: historyKey, events }) })
      .catch((error) => { if (alive) setHistoryResult({ key: historyKey, error: entryErrorText(error) }) })
    return () => { alive = false }
  }, [token, entryId, historyKey])

  useEffect(() => { setEditing(false) }, [entryId])

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopImmediatePropagation() // فقط این کشو بسته شود، نه دفترِ پشت آن.
        closeAction.current()
      } else if (event.key === 'Tab' && panelRef.current) {
        const controls = [...panelRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex="0"]')]
          .filter((node) => node.getClientRects().length > 0 || node === closeRef.current)
        const first = controls[0]
        const last = controls[controls.length - 1]
        if (event.shiftKey && (document.activeElement === first || !panelRef.current.contains(document.activeElement))) {
          event.preventDefault(); last?.focus()
        } else if (!event.shiftKey && (document.activeElement === last || !panelRef.current.contains(document.activeElement))) {
          event.preventDefault(); first?.focus()
        }
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [])

  return createPortal(
    <div className="drawer-overlay journal-entry-overlay" onClick={() => closeAction.current()}>
      <div ref={panelRef} className="drawer-panel journal-entry-panel" onClick={(event) => event.stopPropagation()}
        role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="drawer-head">
          <div className="drawer-title">
            <span className="entry-drawer-icon"><FileText size={21} aria-hidden="true" /></span>
            <div>
              <div id={titleId} className="drawer-title-main">جزئیات سند حسابداری</div>
              <div className="drawer-title-sub">{current?.entry ? `${toFaDigits(current.entry.lines.length)} ردیف · نمایش سند ثبت‌شده` : 'نمایش سند ثبت‌شده'}</div>
            </div>
          </div>
          <button ref={closeRef} type="button" className="drawer-close" onClick={() => closeAction.current()} aria-label="بستن جزئیات سند"><X size={18} /></button>
        </div>
        <div className="drawer-body" aria-busy={!current}>
          {current?.error && <div className="entry-load-state entry-load-error" role="alert">
            <AlertTriangle size={28} aria-hidden="true" />
            <h3>سند دریافت نشد</h3>
            <p>{current.error}</p>
            <p className="muted">اتصال به سرور را بررسی کنید و دوباره تلاش کنید. سند ثبت‌شده تغییر نکرده است.</p>
            <button type="button" className="btn" onClick={() => {
              closeRef.current?.focus() // دکمهٔ تلاش پس از کلیک حذف می‌شود؛ فوکوس در کشو بماند.
              setAttempt((value) => value + 1)
            }}><RotateCcw size={15} />تلاش دوباره</button>
          </div>}
          {!current && <div className="entry-load-state" role="status">
            <FileText size={28} aria-hidden="true" />
            <h3>در حال دریافت سند…</h3>
            <p className="muted">مشخصات و ردیف‌های سند از سرور خوانده می‌شوند.</p>
          </div>}
          {current?.entry && <>
            {!editing && current.entry.source_type === 'manual' && !current.entry.voided_at && !current.entry.reverses_entry_id &&
              <div className="entry-drawer-actions"><button type="button" className="btn" onClick={() => setEditing(true)}>
                <Pencil size={15} /> ویرایش سند
              </button><span>سند موقت یا دائم، فقط در دورهٔ مالی باز و با دلیل قابل اصلاح است.</span></div>}
            {editing ? <JournalEntryEditForm key={`${entryId}-${current.entry.updated_at}`} token={token} entry={current.entry}
              onCancel={() => { if (window.confirm('اصلاحات ذخیره‌نشده کنار گذاشته شوند؟')) setEditing(false) }}
              onSaved={(updated) => {
                setResult({ key: requestKey, entry: updated })
                setEditing(false)
                setHistoryAttempt((value) => value + 1)
              }} /> : <EntryCard entry={current.entry} accountNames={accountNames} />}
            <JournalEntryHistory events={history?.events ?? []} loading={!history} error={history?.error ?? null} />
          </>}
        </div>
      </div>
    </div>, document.body,
  )
}
