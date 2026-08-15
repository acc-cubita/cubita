import { useState } from 'react'
import type { CheckDraft } from '../../lib/checkDraft'
import { useCheckDraft } from '../../lib/checkDraft'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { formatJalali } from '../../lib/jalali'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** ویزاردِ «ثبت چک» — دو مرحله + پیش‌نمایشِ زنده. */
export function CheckWizard({ token, onQueued }: { token: string; onQueued: () => void }) {
  const d = useCheckDraft({ token, onQueued })
  const [resetTick, setResetTick] = useState(0)

  const steps: WizardStep[] = [
    {
      key: 'party',
      title: 'نوع و طرف‌حساب',
      subtitle: 'چک دریافتنی است یا پرداختنی، و مربوط به کدام شخص.',
      body: (
        <div className="invoice-form">
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
              {d.contactOptions.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
            </select>
          </label>
        </div>
      ),
    },
    {
      key: 'details',
      title: 'مشخصاتِ چک',
      subtitle: 'شماره، مبلغ و سررسید را وارد کنید، بعد ثبت را بزنید.',
      canAdvance: d.valid,
      blockHint: 'شماره چک، مبلغ (بزرگ‌تر از صفر) و تاریخ سررسید الزامی است.',
      body: (
        <div className="invoice-form">
          <label>
            شماره چک
            <input type="text" value={d.number} onChange={(e) => d.setNumber(e.target.value)} />
          </label>
          <label>
            نام بانک
            <input type="text" value={d.bankName} onChange={(e) => d.setBankName(e.target.value)} />
          </label>
          <label>
            مبلغ
            <NumberInput value={d.amount} onChange={d.setAmount} />
          </label>
          <label>
            تاریخ صدور
            <JalaliDatePicker value={d.issueDate} onChange={d.setIssueDate} />
          </label>
          <label>
            تاریخ سررسید
            <JalaliDatePicker value={d.dueDate} onChange={d.setDueDate} />
          </label>
          <label className="field-full">
            توضیحات
            <input type="text" value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
          </label>
        </div>
      ),
    },
  ]

  return (
    <TaskFlow
      title="ثبت چک دریافتنی/پرداختنی"
      steps={steps}
      submitLabel="ثبت چک"
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

function LivePreview({ d }: { d: CheckDraft }) {
  const contact = d.contactOptions.find((c) => c.id === d.contactId)
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ چک</p>
      <div className="live-preview-row"><span>نوع</span><strong>{d.type === 'receivable' ? 'دریافتنی' : 'پرداختنی'}</strong></div>
      <div className="live-preview-row"><span>{d.type === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}</span><strong>{contact?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>شماره</span><strong>{d.number || '—'}</strong></div>
      <div className="live-preview-row"><span>بانک</span><strong>{d.bankName || '—'}</strong></div>
      <div className="live-preview-row"><span>سررسید</span><strong>{d.dueDate ? formatJalali(d.dueDate) : '—'}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>مبلغ</span><strong>{fa(Number(d.amount) || 0)}</strong></div>
    </div>
  )
}
