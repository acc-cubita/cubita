import { useState } from 'react'
import { BookOpen, Plus, Trash2, Save } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import { createJournalEntryDirect } from '../api'
import { isElectron } from '../platform'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

interface DraftLine {
  accountId: string
  debit: string
  credit: string
}

const emptyLine = (): DraftLine => ({ accountId: '', debit: '', credit: '' })

export function JournalEntryForm({
  token,
  accounts,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  onQueued: () => void
}) {
  const [description, setDescription] = useState('')
  const [entryDate, setEntryDate] = useState(todayIso())
  const [lines, setLines] = useState<DraftLine[]>([emptyLine(), emptyLine()])
  const [message, setMessage] = useState<string | null>(null)

  const postableAccounts = accounts.filter((a) => !a.is_group)

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  function addLine() {
    setLines((prev) => [...prev, emptyLine()])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 2 ? prev.filter((_, i) => i !== index) : prev))
  }

  const totalDebit = lines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0)
  const totalCredit = lines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0)
  const isBalanced = totalDebit === totalCredit && totalDebit > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    const validLines = lines.filter((l) => l.accountId && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0))
    if (validLines.length < 2) {
      setMessage('سند باید حداقل دو ردیف معتبر (حساب + بدهکار یا بستانکار) داشته باشد.')
      return
    }
    const debitSum = validLines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0)
    const creditSum = validLines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0)
    if (debitSum !== creditSum || debitSum === 0) {
      setMessage(`سند متوازن نیست: بدهکار=${debitSum.toLocaleString('fa-IR')} بستانکار=${creditSum.toLocaleString('fa-IR')}`)
      return
    }

    const payload = {
      entry_date: entryDate,
      description,
      lines: validLines.map((l) => ({
        account_id: l.accountId,
        debit: Number(l.debit) || 0,
        credit: Number(l.credit) || 0,
      })),
    }

    try {
      if (isElectron) {
        await window.cubita.queueJournalEntry(payload)
        setMessage('سند در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createJournalEntryDirect(token, payload)
        setMessage('سند با موفقیت ثبت شد.')
      }
      setDescription('')
      setLines([emptyLine(), emptyLine()])
      onQueued()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={BookOpen} title="ثبت سند حسابداری دستی">
      {postableAccounts.length === 0 ? (
        <p className="hint">قبل از ثبت سند، یک‌بار «هم‌گام‌سازی» کنید تا چارت حساب در دسترس باشد.</p>
      ) : (
        <form className="invoice-form" onSubmit={handleSubmit}>
          <label>
            شرح سند
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <label>
            تاریخ سند
            <JalaliDatePicker value={entryDate} onChange={setEntryDate} />
          </label>

          <table className="invoice-lines">
            <thead>
              <tr>
                <th>حساب</th>
                <th>بدهکار</th>
                <th>بستانکار</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i}>
                  <td>
                    <select value={line.accountId} onChange={(e) => updateLine(i, { accountId: e.target.value })}>
                      <option value="">— انتخاب حساب —</option>
                      {postableAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      value={line.debit}
                      onChange={(e) => updateLine(i, { debit: e.target.value, credit: '' })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      value={line.credit}
                      onChange={(e) => updateLine(i, { credit: e.target.value, debit: '' })}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn-danger"
                      onClick={() => removeLine(i)}
                      disabled={lines.length === 2}
                      aria-label="حذف ردیف"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <span className={isBalanced ? 'invoice-total' : 'invoice-total error'}>
              بدهکار: {totalDebit.toLocaleString('fa-IR')} / بستانکار: {totalCredit.toLocaleString('fa-IR')}
            </span>
            <button type="submit" className="btn-primary">
              <Save size={14} /> ثبت سند
            </button>
          </div>

          {message && <div className="hint">{message}</div>}
        </form>
      )}
    </SectionCard>
  )
}
