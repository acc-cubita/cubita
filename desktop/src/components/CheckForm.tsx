import { Receipt, Save } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { useCheckDraft } from '../lib/checkDraft'

/** فرمِ کلاسیکِ «ثبت چک» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ [useCheckDraft]. */
export function CheckForm({ token, onQueued }: { token: string; onQueued: () => void }) {
  const d = useCheckDraft({ token, onQueued })

  return (
    <SectionCard icon={Receipt} title="ثبت چک دریافتنی/پرداختنی">
      <form
        className="invoice-form"
        onSubmit={(e) => {
          e.preventDefault()
          void d.submit()
        }}
      >
        <label>
          نوع چک
          <select value={d.type} onChange={(e) => d.changeType(e.target.value as 'receivable' | 'payable')}>
            <option value="receivable">دریافتنی (از مشتری)</option>
            <option value="payable">پرداختنی (به تأمین‌کننده)</option>
          </select>
        </label>
        <label>
          {d.type === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}
          <select value={d.contactId} onChange={(e) => d.setContactId(e.target.value)}>
            <option value="">— بدون طرف‌حساب —</option>
            {d.contactOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          شماره چک
          <input type="text" value={d.number} onChange={(e) => d.setNumber(e.target.value)} required />
        </label>
        <label>
          نام بانک
          <input type="text" value={d.bankName} onChange={(e) => d.setBankName(e.target.value)} />
        </label>
        <label>
          مبلغ
          <NumberInput value={d.amount} onChange={d.setAmount} required />
        </label>
        <label>
          تاریخ صدور
          <JalaliDatePicker value={d.issueDate} onChange={d.setIssueDate} />
        </label>
        <label>
          تاریخ سررسید
          <JalaliDatePicker value={d.dueDate} onChange={d.setDueDate} />
        </label>
        <label>
          توضیحات
          <input type="text" value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={d.submitting}>
            <Save size={14} /> ثبت چک
          </button>
        </div>
        {d.message && <div className="hint">{d.message}</div>}
      </form>
    </SectionCard>
  )
}
