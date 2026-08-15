import { useCallback, useEffect, useMemo, useState } from 'react'
import { BookOpenCheck, RefreshCw, ChevronDown, ChevronUp, Ban } from 'lucide-react'
import { fetchJournalEntries, voidJournalEntry, type JournalEntryRecord } from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

const SOURCE_LABELS: Record<string, string> = {
  manual: 'دستی', sales_invoice: 'فاکتور فروش', purchase_invoice: 'فاکتور خرید',
  sales_return: 'برگشت فروش', purchase_return: 'برگشت خرید', payroll: 'حقوق و دستمزد',
  stock_adjustment: 'تعدیل انبار', opening: 'افتتاحیه', depreciation: 'استهلاک',
  transfer_out: 'انتقال انبار', transfer_in: 'انتقال انبار', installment: 'اقساط', check: 'چک',
}

/**
 * دفترِ روزنامه — همه‌ی اسنادِ حسابداری با جزئیات و ابطالِ سندِ دستی. تا پیش از این
 * اسناد فقط از راهِ فرمِ ثبت دیده می‌شدند؛ حالا مرورِ کامل + ابطال ممکن است.
 */
export function JournalDaybookPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const [entries, setEntries] = useState<JournalEntryRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const accMap = useMemo(() => {
    const m = new Map<string, AccountCache>()
    for (const a of accounts) m.set(a.id, a)
    return m
  }, [accounts])

  // صفحه‌بندیِ اسناد (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(entries ?? [], 10)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const rows = await fetchJournalEntries(token)
      // تازه‌ترین اول (بر اساس تاریخ سپس شماره)
      rows.sort((a, b) => (a.entry_date === b.entry_date ? (b.number ?? 0) - (a.number ?? 0) : a.entry_date < b.entry_date ? 1 : -1))
      setEntries(rows)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  function accountLabel(id: string): string {
    const a = accMap.get(id)
    return a ? `${a.code} · ${a.name}` : '—'
  }
  const entryTotal = (e: JournalEntryRecord) => e.lines.reduce((s, l) => s + Number(l.debit), 0)

  async function doVoid(e: JournalEntryRecord) {
    const reason = window.prompt(`ابطالِ سندِ شماره ${e.number ?? '—'}\nدلیلِ ابطال (حداقل ۳ نویسه):`)
    if (reason === null) return
    if (reason.trim().length < 3) { setError('دلیلِ ابطال باید نوشته شود.'); return }
    setBusyId(e.id); setError(null); setMessage(null)
    try {
      const res = await voidJournalEntry(token, e.id, reason.trim())
      setMessage(`سند باطل شد؛ سندِ معکوس شماره ${res.reversal_entry_number ?? '—'} ثبت شد.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <SectionCard
      icon={BookOpenCheck}
      title="دفترِ روزنامه"
      description="همه‌ی اسنادِ حسابداری، تازه‌ترین اول. سندِ دستی را می‌توان باطل کرد (سندِ معکوس ثبت می‌شود)."
      actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
    >
      {error && <div className="error">{error}</div>}
      {message && <div className="hint">{message}</div>}

      {entries == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : entries.length === 0 ? (
        <EmptyState icon={BookOpenCheck} text="هنوز سندی ثبت نشده." />
      ) : (
        <div className="journal-list">
          {pg.pageItems.map((e) => {
            const open = openId === e.id
            const voided = e.voided_at != null
            const isReversal = e.reverses_entry_id != null
            const canVoid = e.source_type === 'manual' && !voided && !isReversal
            return (
              <div key={e.id} className={`journal-card${voided ? ' journal-card--voided' : ''}`}>
                <button type="button" className="journal-head" onClick={() => setOpenId(open ? null : e.id)}>
                  <div className="journal-head-main">
                    <div className="journal-title">
                      <span className="journal-num">#{e.number != null ? e.number.toLocaleString('fa-IR') : '—'}</span>
                      <span className="journal-date">{formatJalali(e.entry_date)}</span>
                      <span className="status-badge tone-default journal-source">{SOURCE_LABELS[e.source_type] ?? e.source_type}</span>
                      {voided && <span className="status-badge tone-danger">باطل‌شده</span>}
                      {isReversal && <span className="status-badge tone-warning">سندِ برگشتی</span>}
                    </div>
                    <div className="journal-desc">{e.description || '—'}</div>
                  </div>
                  <div className="journal-head-side">
                    <span className="journal-amount">{fa(entryTotal(e))}</span>
                    {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </div>
                </button>

                {open && (
                  <div className="journal-detail">
                    <table className="journal-lines-table">
                      <thead>
                        <tr><th>حساب</th><th>شرح</th><th>بدهکار</th><th>بستانکار</th></tr>
                      </thead>
                      <tbody>
                        {e.lines.map((l) => (
                          <tr key={l.id}>
                            <td data-label="حساب" className="entity-name">{accountLabel(l.account_id)}</td>
                            <td data-label="شرح">{l.description || '—'}</td>
                            <td data-label="بدهکار" className="money-cell">{Number(l.debit) > 0 ? fa(Number(l.debit)) : '—'}</td>
                            <td data-label="بستانکار" className="money-cell">{Number(l.credit) > 0 ? fa(Number(l.credit)) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {canVoid && (
                      <div className="journal-actions">
                        <button type="button" className="icon-btn-danger" disabled={busyId === e.id} onClick={() => void doVoid(e)}>
                          <Ban size={13} /> ابطالِ سند
                        </button>
                      </div>
                    )}
                    {!canVoid && e.source_type !== 'manual' && (
                      <p className="hint">این سند را ماژولِ «{SOURCE_LABELS[e.source_type] ?? e.source_type}» ساخته؛ برای برگشت، همان سندِ منبع را باطل کنید.</p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
  )
}
