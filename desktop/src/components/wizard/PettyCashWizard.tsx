import { useState } from 'react'
import type { AccountCache } from '../../electron.d'
import { usePettyCashDraft, type PettyCashDraft } from '../../lib/pettyCashDraft'
import { PettyCashLedger } from '../PettyCashPanel'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
type Mode = 'charge' | 'expense'

/** ویزاردِ «تنخواه‌گردان» — انتخابِ نوعِ گردش ← جزئیات + پیش‌نمایشِ زنده؛ دفترچه زیرِ ویزارد. */
export function PettyCashWizard({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const d = usePettyCashDraft({ token, accounts })
  const [mode, setMode] = useState<Mode>('charge')
  const [resetTick, setResetTick] = useState(0)

  const steps: WizardStep[] = [
    {
      key: 'kind',
      title: 'نوعِ گردش',
      subtitle: 'شارژِ تنخواه از صندوق/بانک، یا ثبتِ هزینه‌ی پرداخت‌شده از تنخواه.',
      body: (
        <div className="invoice-form">
          <label>
            نوعِ عملیات
            <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              <option value="charge">شارژ تنخواه‌گردان</option>
              <option value="expense">هزینه‌کرد از تنخواه‌گردان</option>
            </select>
          </label>
        </div>
      ),
    },
    mode === 'charge'
      ? {
          key: 'charge',
          title: 'جزئیاتِ شارژ',
          subtitle: 'حساب منبع، مبلغ و تاریخ را وارد کنید، بعد ثبت را بزنید.',
          canAdvance: d.chargeValid,
          blockHint: 'حساب منبع و مبلغ (بزرگ‌تر از صفر) الزامی است.',
          body: (
            <div className="invoice-form">
              <label>از حساب
                <select value={d.chargeSourceId} onChange={(e) => d.setChargeSourceId(e.target.value)}>
                  <option value="">— انتخاب —</option>
                  {d.postable.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                </select>
              </label>
              <label>مبلغ<NumberInput value={d.chargeAmount} onChange={d.setChargeAmount} /></label>
              <label>تاریخ<JalaliDatePicker value={d.chargeDate} onChange={d.setChargeDate} /></label>
            </div>
          ),
        }
      : {
          key: 'expense',
          title: 'جزئیاتِ هزینه',
          subtitle: 'حساب هزینه، مبلغ و توضیحات را وارد کنید، بعد ثبت را بزنید.',
          canAdvance: d.expenseValid,
          blockHint: 'حساب هزینه و مبلغ (بزرگ‌تر از صفر) الزامی است.',
          body: (
            <div className="invoice-form">
              <label>بابت حساب هزینه
                <select value={d.expenseAccountId} onChange={(e) => d.setExpenseAccountId(e.target.value)}>
                  <option value="">— انتخاب —</option>
                  {d.expenseAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                </select>
              </label>
              <label>مبلغ<NumberInput value={d.expenseAmount} onChange={d.setExpenseAmount} /></label>
              <label className="field-full">توضیحات<input type="text" value={d.expenseDescription} onChange={(e) => d.setExpenseDescription(e.target.value)} /></label>
              <label>تاریخ<JalaliDatePicker value={d.expenseDate} onChange={d.setExpenseDate} /></label>
            </div>
          ),
        },
  ]

  return (
    <>
      <TaskFlow
        title="تنخواه‌گردان"
        steps={steps}
        submitLabel={mode === 'charge' ? 'ثبت شارژ' : 'ثبت هزینه'}
        submitting={d.submitting}
        message={d.message}
        resetKey={resetTick}
        preview={<LivePreview d={d} mode={mode} />}
        onSubmit={() => {
          const op = mode === 'charge' ? d.submitCharge() : d.submitExpense()
          void op.then((ok) => {
            if (ok) setResetTick((t) => t + 1)
          })
        }}
      />
      <PettyCashLedger d={d} />
    </>
  )
}

function LivePreview({ d, mode }: { d: PettyCashDraft; mode: Mode }) {
  const amount = Number(mode === 'charge' ? d.chargeAmount : d.expenseAmount) || 0
  const after = d.balance == null ? null : d.balance + (mode === 'charge' ? amount : -amount)
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ گردش</p>
      <div className="live-preview-row"><span>نوع</span><strong>{mode === 'charge' ? 'شارژ' : 'هزینه'}</strong></div>
      <div className="live-preview-row"><span>موجودیِ فعلی</span><strong>{d.balance == null ? '—' : fa(d.balance)}</strong></div>
      <div className="live-preview-row"><span>{mode === 'charge' ? 'شارژ' : 'هزینه'}</span><strong>{mode === 'charge' ? '+' : '−'}{fa(amount)}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>موجودیِ بعد</span><strong>{after == null ? '—' : fa(after)}</strong></div>
    </div>
  )
}
