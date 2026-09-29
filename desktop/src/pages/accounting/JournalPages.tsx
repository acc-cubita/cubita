import { BookOpen, Inbox } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { AccountCache, OutboxEntry, JournalOutboxEdit, JournalOutboxSaveResult } from '../../electron.d'
import { JournalEntryForm } from '../../components/JournalEntryForm'
import { OutboxList } from '../../components/OutboxList'
import { SectionCard } from '../../components/SectionCard'
import { isElectron } from '../../platform'
import { OpsPage } from './kit'
import { outboxErrorText } from '../../lib/outboxError'
import { parseQueuedJournalDraft } from '../../lib/journalOutboxDraft'

/**
 * چهار عملیاتی که مستقیماً روی *سند* کار می‌کنند.
 *
 * تقسیم‌بندی عمدی است و از خودِ کارِ دفترداری می‌آید:
 *  - **سند حسابداری** جایی است که سند *ساخته* می‌شود.
 *  - **کارتابل اسناد موقت** جایی است که سند *بازبینی* و دائم می‌شود — تکی، دسته‌ای به منشأ، یا کلِ
 *    یک بازه برای پایانِ ماه. منوی جدای «تبدیل اسناد موقت به دائم» همین کارِ آخر را روی همین داده
 *    می‌کرد و در بازچینیِ ۱۴۰۵/۰۷/۰۳ در کارتابل ادغام شد.
 *  - **شماره‌گذاری مجدد** و **ادغام** دو ابزارِ مرتب‌کردنِ دفترِ به‌هم‌ریخته‌اند و
 *    هر دو عمداً فقط روی اسنادِ موقت کار می‌کنند.
 */

// ═══════════════════════ ۱) سند حسابداری ═══════════════════════

export function JournalEntryPage({
  token,
  accounts,
  outbox,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
}) {
  const [editing, setEditing] = useState<JournalOutboxEdit | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const editingRef = useRef<JournalOutboxEdit | null>(null)
  const opening = useRef(false)
  const mounted = useRef(true)
  const editorRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (editing) {
      editorRef.current?.scrollIntoView?.({ block: 'start' })
      editorRef.current?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true })
    }
  }, [editing])
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      const current = editingRef.current
      if (current) void window.cubita?.cancelJournalEdit?.(current.local_id, current.lease).catch(() => {})
    }
  }, [])
  async function openEdit(entry: OutboxEntry) {
    if (opening.current || editingRef.current) return
    opening.current = true
    setBusy(true)
    setNotice(null)
    try {
      if (!window.cubita.beginJournalEdit) throw new Error('این برنامه هنوز ویرایش صف را پشتیبانی نمی‌کند؛ ابتدا برنامه را به‌روز کنید.')
      const result = await window.cubita.beginJournalEdit(entry.local_id)
      if (result.state === 'editing') {
        if (!mounted.current) { await window.cubita.cancelJournalEdit?.(result.edit.local_id, result.edit.lease); return }
        try { parseQueuedJournalDraft(result.edit.payload) }
        catch (error) { await window.cubita.cancelJournalEdit?.(result.edit.local_id, result.edit.lease); throw error }
        editingRef.current = result.edit
        setEditing(result.edit)
      } else {
        if (!mounted.current) return
        setNotice({ kind: 'ok', text: result.message })
        onQueued()
      }
    } catch (error) {
      if (mounted.current) setNotice({ kind: 'err', text: outboxErrorText(error instanceof Error ? error.message : String(error)) })
    } finally { opening.current = false; if (mounted.current) setBusy(false) }
  }
  function closeEdit(result?: JournalOutboxSaveResult) {
    const current = editingRef.current
    if (current) void window.cubita.cancelJournalEdit?.(current.local_id, current.lease).catch(() => {})
    editingRef.current = null
    setEditing(null)
    setNotice(result ? { kind: result.state === 'synced' ? 'ok' : 'err', text: result.message } : null)
  }
  return (
    <OpsPage
      canvas
      icon={BookOpen}
      title="سند حسابداری"
      description="ثبتِ سندِ دستی. سندِ تازه «موقت» ثبت می‌شود تا در کارتابل بازبینی شود؛ فاکتور و فیش و چک خودشان خودکار سند می‌خورند. دفترِ کاملِ اسناد زیرِ کارتِ «فهرست» است."
    >
      {notice && <div className={notice.kind === 'err' ? 'error' : 'success-text'} role="status">{notice.text}</div>}
      {/* فرم تازه پنهان می‌ماند، نه unmount؛ انصراف پیش‌نویس قبلی را برمی‌گرداند. */}
      <div hidden={Boolean(editing)}><JournalEntryForm token={token} accounts={accounts} onQueued={onQueued} /></div>
      {editing && <section ref={editorRef} className="journal-outbox-editor" aria-label="ویرایش همان سند صف‌شده">
        <p className="muted">در حال اصلاح همان سند داخل صف هستید؛ ارسال آن تا پایان ویرایش متوقف است. ذخیره، سند جدیدی نمی‌سازد.</p>
        <JournalEntryForm key={editing.lease} token={token} accounts={accounts} editing={editing} onQueued={onQueued}
          onEdited={closeEdit} onCancel={() => closeEdit()} />
      </section>}

      {isElectron && (
        <SectionCard
          icon={Inbox}
          title="صف اسناد ارسال‌نشده"
          description="سندهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
        >
          <OutboxList entries={outbox} emptyHint="سندی در صف نیست." onEdit={(entry) => { void openEdit(entry) }}
            editingId={editing?.local_id} editBusy={busy} />
        </SectionCard>
      )}
    </OpsPage>
  )
}

// ═══════════════════ ۲) کارتابل اسناد موقت ═══════════════════
//: برگه‌ی اکسلیِ کارتابل فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { EntryCartablePage } from './EntryCartablePage'

// ═══════════════ ۳) شماره‌گذاری مجدد اسناد ═══════════════
//: برگه‌ی اکسلیِ نقشه‌ی شماره‌ها فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { RenumberEntriesPage } from './RenumberEntriesPage'

// ═══════════════════════ ۴) ادغام اسناد ═══════════════════════
//: برگه‌ی اکسلیِ ادغام فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { MergeEntriesPage } from './MergeEntriesPage'

// ═══════════════════════ فهرستِ «اسناد حسابداری» ═══════════════════════
//: برگه‌ی اکسلیِ دفترِ اسناد فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { EntryListPage } from './EntryListPage'
