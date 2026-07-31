import { Fragment, useEffect, useMemo, useState } from 'react'
import { CalendarClock, CircleDollarSign, Plus, Save, Wallet, X, Ban } from 'lucide-react'
import {
  cancelInstallmentPlan,
  createInstallmentPlan,
  fetchContacts,
  fetchInstallmentPlans,
  payInstallment,
  type ContactRecord,
  type Installment,
  type InstallmentPlan,
} from '../api'
import type { BankAccountCache } from '../electron.d'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali } from '../lib/jalali'

const fa = (n: string | number) => Number(n).toLocaleString('fa-IR')

const PLAN_STATUS: Record<InstallmentPlan['status'], { label: string; tone: string }> = {
  active: { label: 'فعال', tone: 'warning' },
  completed: { label: 'تسویه‌شده', tone: 'success' },
  cancelled: { label: 'لغوشده', tone: 'muted' },
}
const INST_STATUS: Record<Installment['status'], { label: string; tone: string }> = {
  pending: { label: 'در انتظار', tone: 'muted' },
  partial: { label: 'پرداخت جزئی', tone: 'warning' },
  paid: { label: 'پرداخت‌شده', tone: 'success' },
  overdue: { label: 'معوق', tone: 'danger' },
}

export function InstallmentsPage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [plans, setPlans] = useState<InstallmentPlan[]>([])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // فرم قرارداد
  const [contactId, setContactId] = useState('')
  const [title, setTitle] = useState('')
  const [total, setTotal] = useState('')
  const [down, setDown] = useState('')
  const [count, setCount] = useState('6')
  const [interval, setInterval] = useState('1')
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10))
  const [formMessage, setFormMessage] = useState<string | null>(null)

  // پرداخت قسط
  const [payingId, setPayingId] = useState<string | null>(null)
  const [payAmount, setPayAmount] = useState('')
  const [payMethod, setPayMethod] = useState<'cash' | 'bank'>('cash')
  const [payBankId, setPayBankId] = useState('')
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10))
  const [payMessage, setPayMessage] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [ps, cs] = await Promise.all([fetchInstallmentPlans(token), fetchContacts(token)])
      setPlans(ps)
      setContacts(cs.filter((c) => c.type !== 'supplier'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }
  useEffect(() => { void refresh() }, [])

  const selected = useMemo(() => plans.find((p) => p.id === selectedId) ?? null, [plans, selectedId])

  const kpis = useMemo(() => {
    const active = plans.filter((p) => p.status === 'active')
    const remaining = active.reduce((s, p) => s + Number(p.total_remaining), 0)
    const overdue = active.reduce((s, p) => s + Number(p.overdue_amount), 0)
    return { active: active.length, remaining, overdue }
  }, [plans])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setFormMessage(null)
    if (!contactId || Number(total) <= 0 || Number(count) < 1) {
      setFormMessage('مشتری، مبلغ کل و تعداد اقساط الزامی‌اند.')
      return
    }
    try {
      const plan = await createInstallmentPlan(token, {
        contact_id: contactId,
        title: title || undefined,
        total_amount: Number(total),
        down_payment: Number(down) || 0,
        num_installments: Number(count),
        interval_months: Number(interval) || 1,
        start_date: startDate,
      })
      setFormMessage('قرارداد اقساط ثبت شد.')
      setContactId(''); setTitle(''); setTotal(''); setDown(''); setCount('6')
      await refresh()
      setSelectedId(plan.id)
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  function startPay(inst: Installment) {
    setPayingId(inst.id)
    setPayAmount(String(Number(inst.remaining)))
    setPayMethod('cash')
    setPayBankId('')
    setPayDate(new Date().toISOString().slice(0, 10))
    setPayMessage(null)
  }

  async function handlePay(inst: Installment) {
    if (!selected) return
    setPayMessage(null)
    if (Number(payAmount) <= 0) { setPayMessage('مبلغ باید بزرگ‌تر از صفر باشد.'); return }
    if (payMethod === 'bank' && !payBankId) { setPayMessage('حساب بانکی را انتخاب کنید.'); return }
    try {
      await payInstallment(token, selected.id, inst.id, {
        amount: Number(payAmount),
        transaction_date: payDate,
        method: payMethod,
        bank_account_id: payMethod === 'bank' ? payBankId : null,
      })
      setPayingId(null)
      await refresh()
    } catch (err) {
      setPayMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleCancel(plan: InstallmentPlan) {
    if (!window.confirm(`قرارداد ${plan.title} لغو شود؟ پرداخت‌های انجام‌شده باقی می‌مانند.`)) return
    try {
      await cancelInstallmentPlan(token, plan.id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="page">
      <PageHeader
        icon={CalendarClock}
        title="فروش اقساطی"
        description="قرارداد اقساط برای فروش نسیه بسازید، زمان‌بندی وصول را ببینید و هر قسط را با دریافتِ خودکارِ خزانه ثبت کنید."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<CalendarClock size={18} />} label="قراردادهای فعال" value={fa(kpis.active)} />
        <StatCard icon={<CircleDollarSign size={18} />} label="مانده‌ی قابل وصول" value={fa(kpis.remaining)} hint="تومان" />
        <StatCard icon={<Wallet size={18} />} label="اقساط معوق" value={fa(kpis.overdue)} tone={kpis.overdue > 0 ? 'danger' : 'success'} hint="تومان" />
      </div>

      <div className="workspace-split">
        <SectionCard icon={Plus} title="قرارداد اقساط جدید" description="فروش نسیه را به اقساط ماهانه تقسیم کنید.">
          <form className="invoice-form form-full" onSubmit={handleCreate}>
            <label>
              مشتری
              <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
                <option value="">— انتخاب مشتری —</option>
                {contacts.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            </label>
            <label>
              عنوان قرارداد
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="مثلاً خرید یخچال" />
            </label>
            <div className="field-row">
              <label>
                مبلغ کل (تومان)
                <input type="number" min="0" value={total} onChange={(e) => setTotal(e.target.value)} required />
              </label>
              <label>
                پیش‌پرداخت
                <input type="number" min="0" value={down} onChange={(e) => setDown(e.target.value)} placeholder="۰" />
              </label>
            </div>
            <div className="field-row">
              <label>
                تعداد اقساط
                <input type="number" min="1" value={count} onChange={(e) => setCount(e.target.value)} required />
              </label>
              <label>
                فاصله (ماه)
                <input type="number" min="1" value={interval} onChange={(e) => setInterval(e.target.value)} />
              </label>
            </div>
            <label>
              تاریخِ اولین قسط
              <JalaliDatePicker value={startDate} onChange={setStartDate} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> ثبت قرارداد</button>
            </div>
            {formMessage && <div className="hint">{formMessage}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={CalendarClock} title="قراردادها" description={`${fa(plans.length)} قرارداد`}>
          {plans.length === 0 ? (
            <EmptyState icon={CalendarClock} text="هنوز قرارداد اقساطی ثبت نشده." />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table">
                <thead>
                  <tr><th>#</th><th>مشتری</th><th>مبلغ کل</th><th>مانده</th><th>وضعیت</th><th></th></tr>
                </thead>
                <tbody>
                  {plans.map((p) => (
                    <tr key={p.id} className={selectedId === p.id ? 'row-selected' : undefined} style={{ cursor: 'pointer' }} onClick={() => setSelectedId(p.id)}>
                      <td>{fa(p.number ?? 0)}</td>
                      <td>
                        <div className="entity-name">{p.contact_name}</div>
                        <div className="entity-sub">{p.title}</div>
                      </td>
                      <td className="money-cell">{fa(p.total_amount)}</td>
                      <td className="money-cell">
                        {fa(p.total_remaining)}
                        {p.overdue_count > 0 && <span className="status-badge tone-danger" style={{ marginRight: 4 }}>{fa(p.overdue_count)} معوق</span>}
                      </td>
                      <td><span className={`status-badge tone-${PLAN_STATUS[p.status].tone}`}>{PLAN_STATUS[p.status].label}</span></td>
                      <td>
                        {p.status === 'active' && (
                          <button type="button" onClick={(e) => { e.stopPropagation(); void handleCancel(p) }}><Ban size={13} /> لغو</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>

      {selected && (
        <SectionCard
          icon={CalendarClock}
          title={`زمان‌بندی اقساط — ${selected.contact_name}`}
          description={`قرارداد ${fa(selected.number ?? 0)} · کل ${fa(selected.total_amount)} · پیش‌پرداخت ${fa(selected.down_payment)} · پرداخت‌شده ${fa(selected.total_paid)}`}
          actions={<button type="button" onClick={() => setSelectedId(null)}><X size={13} /> بستن</button>}
        >
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr><th>قسط</th><th>سررسید</th><th>مبلغ</th><th>پرداخت‌شده</th><th>مانده</th><th>وضعیت</th><th></th></tr>
              </thead>
              <tbody>
                {selected.installments.map((inst) => (
                  <Fragment key={inst.id}>
                    <tr>
                      <td>{fa(inst.seq)}</td>
                      <td>{formatJalali(inst.due_date)}</td>
                      <td className="money-cell">{fa(inst.amount)}</td>
                      <td className="money-cell">{fa(inst.paid_amount)}</td>
                      <td className="money-cell">{fa(inst.remaining)}</td>
                      <td><span className={`status-badge tone-${INST_STATUS[inst.status].tone}`}>{INST_STATUS[inst.status].label}</span></td>
                      <td>
                        {selected.status === 'active' && inst.status !== 'paid' && (
                          <button type="button" onClick={() => startPay(inst)}><Wallet size={13} /> پرداخت</button>
                        )}
                      </td>
                    </tr>
                    {payingId === inst.id && (
                      <tr>
                        <td colSpan={7}>
                          <div className="pay-inline">
                            <label>مبلغ<input type="number" min="0" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} /></label>
                            <label>تاریخ<JalaliDatePicker value={payDate} onChange={setPayDate} /></label>
                            <label>روش
                              <select value={payMethod} onChange={(e) => setPayMethod(e.target.value as 'cash' | 'bank')}>
                                <option value="cash">نقدی (صندوق)</option>
                                <option value="bank">بانکی</option>
                              </select>
                            </label>
                            {payMethod === 'bank' && (
                              <label>حساب بانکی
                                <select value={payBankId} onChange={(e) => setPayBankId(e.target.value)}>
                                  <option value="">— انتخاب —</option>
                                  {bankAccounts.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                                </select>
                              </label>
                            )}
                            <button type="button" className="btn-primary" onClick={() => void handlePay(inst)}><Save size={13} /> ثبت دریافت</button>
                            <button type="button" onClick={() => setPayingId(null)}><X size={13} /></button>
                          </div>
                          {payMessage && <div className="error">{payMessage}</div>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint">هر پرداخت خودکار به‌صورتِ «دریافت از مشتری» در خزانه ثبت می‌شود و مانده‌ی حساب‌های دریافتنی را کم می‌کند.</p>
        </SectionCard>
      )}
    </div>
  )
}
