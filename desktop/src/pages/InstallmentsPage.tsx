import { Fragment, useEffect, useMemo, useState } from 'react'
import { CalendarClock, CircleDollarSign, Plus, Save, Wallet, X, Ban, Printer } from 'lucide-react'
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
import { NumberInput } from '../components/NumberInput'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali, toFaDigits } from '../lib/jalali'

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

type PlanFilter = 'all' | 'active' | 'overdue' | 'completed' | 'cancelled'

// نوارِ پیشرفتِ وصول (پرداخت‌شده ÷ تسهیم‌شده)
function ProgressBar({ paid, scheduled }: { paid: number; scheduled: number }) {
  const pct = scheduled > 0 ? Math.min(100, Math.round((paid / scheduled) * 100)) : 0
  return (
    <div className="inst-progress" title={`${toFaDigits(pct)}٪ وصول‌شده`}>
      <div className="inst-progress-fill" style={{ width: `${pct}%` }} />
      <span className="inst-progress-label">{toFaDigits(pct)}٪</span>
    </div>
  )
}

export function InstallmentsPage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [plans, setPlans] = useState<InstallmentPlan[]>([])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<PlanFilter>('all')
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

  const filteredPlans = useMemo(() => {
    return plans.filter((p) => {
      if (filter === 'all') return true
      if (filter === 'overdue') return p.status === 'active' && p.overdue_count > 0
      return p.status === filter
    })
  }, [plans, filter])

  const filterCounts = useMemo(() => ({
    all: plans.length,
    active: plans.filter((p) => p.status === 'active').length,
    overdue: plans.filter((p) => p.status === 'active' && p.overdue_count > 0).length,
    completed: plans.filter((p) => p.status === 'completed').length,
    cancelled: plans.filter((p) => p.status === 'cancelled').length,
  }), [plans])

  // پیش‌نمایشِ تسهیم — همان منطقِ سرور: financed=کل−پیش، قسط=کف(financed÷n)، باقی‌مانده به آخری
  const amortization = useMemo(() => {
    const t = Number(total), d = Number(down) || 0, n = Number(count) || 0
    if (!(t > 0) || n < 1 || d < 0 || d >= t) return null
    const financed = t - d
    const base = Math.floor(financed / n)
    const last = base + (financed - base * n)
    return { financed, base, last, n }
  }, [total, down, count])

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

  function printSchedule(plan: InstallmentPlan) {
    const win = window.open('', '_blank', 'width=840,height=1000')
    if (!win) return
    const rows = plan.installments.map((i) =>
      `<tr><td>${toFaDigits(i.seq)}</td><td>${formatJalali(i.due_date)}</td><td class="num">${fa(i.amount)}</td><td class="num">${fa(i.paid_amount)}</td><td class="num">${fa(i.remaining)}</td><td>${INST_STATUS[i.status].label}</td></tr>`,
    ).join('')
    win.document.write(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>جدولِ اقساط ${plan.number ?? ''} — ${plan.contact_name}</title>
<style>
  *{box-sizing:border-box}
  body{font-family:Vazirmatn,Tahoma,sans-serif;margin:28px;color:#1f2937}
  h1{font-size:20px;margin:0 0 4px}
  .muted{color:#6b7280;font-size:13px}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #111827;padding-bottom:12px;margin-bottom:16px}
  .meta{text-align:left;font-size:13px;line-height:1.9}
  .summary{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px;font-size:13px}
  .summary div{border:1px solid #e5e7eb;border-radius:8px;padding:8px 14px}
  table{width:100%;border-collapse:collapse;margin-bottom:16px}
  th{text-align:right;background:#f3f4f6;font-size:13px;padding:8px 10px;border:1px solid #e5e7eb}
  td{padding:8px 10px;border:1px solid #e5e7eb;font-size:13.5px}
  td.num{text-align:left;font-variant-numeric:tabular-nums}
  .foot{margin-top:26px;color:#6b7280;font-size:11.5px;line-height:1.8}
</style></head><body>
  <div class="head">
    <div><h1>جدولِ اقساط</h1><div class="muted">${plan.title || 'فروش اقساطی'}</div></div>
    <div class="meta">
      <div>مشتری: <strong>${plan.contact_name}</strong></div>
      <div>قرارداد شماره: ${plan.number != null ? toFaDigits(plan.number) : '—'}</div>
      <div>تاریخِ شروع: ${formatJalali(plan.start_date)}</div>
    </div>
  </div>
  <div class="summary">
    <div>مبلغ کل: <strong>${fa(plan.total_amount)}</strong></div>
    <div>پیش‌پرداخت: <strong>${fa(plan.down_payment)}</strong></div>
    <div>تسهیم‌شده: <strong>${fa(plan.financed)}</strong></div>
    <div>پرداخت‌شده: <strong>${fa(plan.total_paid)}</strong></div>
    <div>مانده: <strong>${fa(plan.total_remaining)}</strong></div>
  </div>
  <table>
    <thead><tr><th>قسط</th><th>سررسید</th><th class="num">مبلغ</th><th class="num">پرداخت‌شده</th><th class="num">مانده</th><th>وضعیت</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <div class="foot">این جدول از سیستمِ حسابداری صادر شده است. هر پرداخت به‌صورتِ دریافت از مشتری در خزانه ثبت می‌شود.</div>
  <script>window.onload=function(){window.print()}</script>
</body></html>`)
    win.document.close()
  }

  const filters: { key: PlanFilter; label: string }[] = [
    { key: 'all', label: 'همه' },
    { key: 'active', label: 'فعال' },
    { key: 'overdue', label: 'دارای معوق' },
    { key: 'completed', label: 'تسویه‌شده' },
    { key: 'cancelled', label: 'لغوشده' },
  ]

  return (
    <div className="page panels">
      <PageHeader
        icon={CalendarClock}
        title="فروش اقساطی"
        description="قرارداد اقساط برای فروش نسیه بسازید، زمان‌بندی وصول را ببینید و هر قسط را با دریافتِ خودکارِ خزانه ثبت کنید."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<CalendarClock size={18} />} label="قراردادهای فعال" value={fa(kpis.active)} />
        <StatCard icon={<CircleDollarSign size={18} />} label="مانده‌ی قابل وصول" value={fa(kpis.remaining)} hint="ریال" />
        <StatCard icon={<Wallet size={18} />} label="اقساط معوق" value={fa(kpis.overdue)} tone={kpis.overdue > 0 ? 'danger' : 'success'} hint="ریال" />
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
                مبلغ کل (ریال)
                <NumberInput value={total} onChange={setTotal} required />
              </label>
              <label>
                پیش‌پرداخت
                <NumberInput value={down} onChange={setDown} placeholder="۰" />
              </label>
            </div>
            <div className="field-row">
              <label>
                تعداد اقساط
                <NumberInput value={count} onChange={setCount} required />
              </label>
              <label>
                فاصله (ماه)
                <NumberInput value={interval} onChange={setInterval} />
              </label>
            </div>
            <label>
              تاریخِ اولین قسط
              <JalaliDatePicker value={startDate} onChange={setStartDate} />
            </label>

            {amortization && (
              <div className="pos-summary" style={{ marginTop: 4 }}>
                <div className="pos-row"><span>مبلغِ تسهیم‌شده (کل − پیش‌پرداخت)</span><strong>{fa(amortization.financed)}</strong></div>
                <div className="pos-row"><span>هر قسط</span><strong>{fa(amortization.base)}</strong></div>
                {amortization.last !== amortization.base && (
                  <div className="pos-row"><span>قسط آخر (با گِردکردن)</span><strong>{fa(amortization.last)}</strong></div>
                )}
                <div className="pos-row pos-total"><span>{toFaDigits(amortization.n)} قسط، هر {toFaDigits(Number(interval) || 1)} ماه</span><strong>{fa(amortization.financed)}</strong></div>
              </div>
            )}

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> ثبت قرارداد</button>
            </div>
            {formMessage && <div className="hint">{formMessage}</div>}
          </form>
        </SectionCard>

        <SectionCard
          icon={CalendarClock}
          title="قراردادها"
          description={`${fa(filteredPlans.length)} از ${fa(plans.length)} قرارداد`}
        >
          <div className="inst-filters">
            {filters.map((f) => (
              <button
                key={f.key}
                type="button"
                className={filter === f.key ? 'chip-active' : ''}
                onClick={() => setFilter(f.key)}
              >
                {f.label} ({toFaDigits(filterCounts[f.key])})
              </button>
            ))}
          </div>
          {filteredPlans.length === 0 ? (
            <EmptyState icon={CalendarClock} text={plans.length === 0 ? 'هنوز قرارداد اقساطی ثبت نشده.' : 'قراردادی مطابق فیلتر نیست.'} />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table inst-plans-table">
                <thead>
                  <tr><th>#</th><th>مشتری</th><th>مبلغ کل</th><th>پیشرفت</th><th>مانده</th><th>وضعیت</th><th>اقدام</th></tr>
                </thead>
                <tbody>
                  {filteredPlans.map((p) => (
                    <tr key={p.id} className={selectedId === p.id ? 'row-selected' : undefined} style={{ cursor: 'pointer' }} onClick={() => setSelectedId(p.id)}>
                      <td data-label="#">{fa(p.number ?? 0)}</td>
                      <td className="entity-name">
                        <div className="entity-name">{p.contact_name}</div>
                        <div className="entity-sub">{p.title}</div>
                      </td>
                      <td data-label="مبلغ کل" className="money-cell">{fa(p.total_amount)}</td>
                      <td data-label="پیشرفت" className="inst-progress-cell">
                        <ProgressBar paid={Number(p.total_paid)} scheduled={Number(p.total_paid) + Number(p.total_remaining)} />
                      </td>
                      <td data-label="مانده" className="money-cell">
                        {fa(p.total_remaining)}
                        {p.overdue_count > 0 && <span className="status-badge tone-danger" style={{ marginRight: 4 }}>{fa(p.overdue_count)} معوق</span>}
                      </td>
                      <td data-label="وضعیت"><span className={`status-badge tone-${PLAN_STATUS[p.status].tone}`}>{PLAN_STATUS[p.status].label}</span></td>
                      <td className="inst-plan-action">
                        <div className="row-actions">
                          <button type="button" onClick={(e) => { e.stopPropagation(); printSchedule(p) }}><Printer size={13} /> چاپ</button>
                          {p.status === 'active' && (
                            <button type="button" className="icon-btn-danger" onClick={(e) => { e.stopPropagation(); void handleCancel(p) }} title="لغو قرارداد"><Ban size={13} /></button>
                          )}
                        </div>
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
          actions={
            <div className="row-actions">
              <button type="button" onClick={() => printSchedule(selected)}><Printer size={13} /> چاپ جدول</button>
              <button type="button" onClick={() => setSelectedId(null)}><X size={13} /> بستن</button>
            </div>
          }
        >
          <div className="inst-sched-progress">
            <ProgressBar paid={Number(selected.total_paid)} scheduled={Number(selected.total_paid) + Number(selected.total_remaining)} />
            <span className="inst-sched-progress-text">
              {fa(selected.total_paid)} از {fa(Number(selected.total_paid) + Number(selected.total_remaining))} ریال وصول شده
              {selected.next_due_date && ` · سررسید بعدی: ${formatJalali(selected.next_due_date)}`}
            </span>
          </div>
          <div className="entity-table-wrap">
            <table className="entity-table inst-sched-table">
              <thead>
                <tr><th>قسط</th><th>سررسید</th><th>مبلغ</th><th>پرداخت‌شده</th><th>مانده</th><th>وضعیت</th><th>اقدام</th></tr>
              </thead>
              <tbody>
                {selected.installments.map((inst) => (
                  <Fragment key={inst.id}>
                    <tr>
                      <td data-label="قسط">{fa(inst.seq)}</td>
                      <td data-label="سررسید">{formatJalali(inst.due_date)}</td>
                      <td data-label="مبلغ" className="money-cell">{fa(inst.amount)}</td>
                      <td data-label="پرداخت‌شده" className="money-cell">{fa(inst.paid_amount)}</td>
                      <td data-label="مانده" className="money-cell">{fa(inst.remaining)}</td>
                      <td data-label="وضعیت"><span className={`status-badge tone-${INST_STATUS[inst.status].tone}`}>{INST_STATUS[inst.status].label}</span></td>
                      <td className="inst-inst-action">
                        {selected.status === 'active' && inst.status !== 'paid' && (
                          <button type="button" onClick={() => startPay(inst)}><Wallet size={13} /> پرداخت</button>
                        )}
                      </td>
                    </tr>
                    {payingId === inst.id && (
                      <tr className="inst-pay-row">
                        <td colSpan={7}>
                          <div className="pay-inline">
                            <label>مبلغ<NumberInput value={payAmount} onChange={setPayAmount} /></label>
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
