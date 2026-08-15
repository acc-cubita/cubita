import { useState } from 'react'
import { Plus } from 'lucide-react'
import type { AccountCache } from '../../electron.d'
import { useJournalEntryDraft, type JournalEntryDraft } from '../../lib/journalEntryDraft'
import { JournalLinesTable } from '../JournalEntryForm'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** ویزاردِ «ثبت سند حسابداری» — سربرگ ← ردیف‌ها و موازنه + پیش‌نمایشِ زنده. */
export function JournalEntryWizard({
  token,
  accounts,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  onQueued: () => void
}) {
  const d = useJournalEntryDraft({ token, accounts, onQueued })
  const [resetTick, setResetTick] = useState(0)

  if (d.postableAccounts.length === 0) {
    return (
      <section className="taskflow">
        <h2 className="taskflow-title">ثبت سند حسابداری</h2>
        <p className="hint">قبل از ثبت سند، یک‌بار «هم‌گام‌سازی» کنید تا چارت حساب در دسترس باشد.</p>
      </section>
    )
  }

  const steps: WizardStep[] = [
    {
      key: 'head',
      title: 'سربرگِ سند',
      subtitle: 'شرح، تاریخ و (در صورت نیاز) مرکز هزینه را مشخص کنید.',
      body: (
        <div className="invoice-form">
          <label>
            شرح سند
            <input type="text" value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
          </label>
          <label>
            تاریخ سند
            <JalaliDatePicker value={d.entryDate} onChange={d.setEntryDate} />
          </label>
          {d.costCenters.length > 0 && (
            <label>
              مرکز هزینه/پروژه (اختیاری)
              <select value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {d.costCenters.map((c) => (
                  <option key={c.id} value={c.id}>{c.code ? `${c.code} — ${c.name}` : c.name}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      ),
    },
    {
      key: 'lines',
      title: 'ردیف‌ها و موازنه',
      subtitle: 'حساب‌ها را با بدهکار/بستانکار وارد کنید؛ سند باید متوازن شود.',
      canAdvance: d.isBalanced && d.validLineCount >= 2,
      blockHint: 'حداقل دو ردیفِ معتبر و موازنه‌ی بدهکار با بستانکار لازم است.',
      body: (
        <>
          <JournalLinesTable d={d} />
          <div className="invoice-form-footer">
            <button type="button" onClick={d.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <span className={d.isBalanced ? 'invoice-total' : 'invoice-total error'}>
              بدهکار: {fa(d.totalDebit)} / بستانکار: {fa(d.totalCredit)}
            </span>
          </div>
        </>
      ),
    },
  ]

  return (
    <TaskFlow
      title="ثبت سند حسابداری"
      steps={steps}
      submitLabel="ثبت سند"
      submitting={d.submitting}
      message={d.message}
      resetKey={resetTick}
      preview={<LivePreview d={d} />}
      onSubmit={() => {
        void d.submit().then((ok) => {
          if (ok) setResetTick((t) => t + 1)
        })
      }}
    />
  )
}

function LivePreview({ d }: { d: JournalEntryDraft }) {
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ سند</p>
      <div className="live-preview-row"><span>شرح</span><strong>{d.description || '—'}</strong></div>
      <div className="live-preview-row"><span>تاریخ</span><strong>{d.entryDate}</strong></div>
      <div className="live-preview-row"><span>ردیفِ معتبر</span><strong>{fa(d.validLineCount)}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row"><span>جمع بدهکار</span><strong>{fa(d.totalDebit)}</strong></div>
      <div className="live-preview-row"><span>جمع بستانکار</span><strong>{fa(d.totalCredit)}</strong></div>
      <div className="live-preview-row live-preview-total">
        <span>وضعیت</span>
        <strong style={{ color: d.isBalanced ? 'var(--success)' : 'var(--danger)' }}>
          {d.isBalanced ? 'متوازن' : 'نامتوازن'}
        </strong>
      </div>
    </div>
  )
}
