import { useEffect, useMemo, useState } from 'react'
import { Banknote, HandCoins, Plus, Save, Undo2, UploadCloud } from 'lucide-react'
import {
  LOAN_STATUS_LABELS,
  cancelEmployeeLoan,
  createEmployeeLoan,
  createLoanType,
  createSettlement,
  fetchDeploymentInfo,
  fetchEmployeeLoans,
  fetchEmployees,
  fetchLoanTypes,
  fetchSettlements,
  saveDeploymentInfo,
  type DeploymentInfoRecord,
  type EmployeeLoanRecord,
  type EmployeeRecord,
  type LoanTypeRecord,
  type PayrollSettlementRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { SectionCard } from '../../components/SectionCard'
import { formatJalali } from '../../lib/jalali'
import { AsyncBlock, Note, OpsPage, type Msg } from '../accounting/kit'

/**
 * وامِ پرسنلی، تسویه‌حساب، و اطلاعاتِ استقرار.
 *
 * سه تصمیمِ این صفحه‌ها که در سرویس هم قفل شده‌اند:
 *
 * ۱. **اقساط این‌جا تایپ نمی‌شوند.** کاربر مبلغ و تعداد را می‌دهد و سرور اقساط را
 *    می‌سازد — با باقی‌مانده روی قسطِ آخر، تا جمعشان دقیقاً برابرِ وام بماند.
 * ۲. **مانده مشتق است**، جمعِ اقساطِ کسرنشده. هیچ ستونی نگهش نمی‌دارد، پس هیچ‌وقت با
 *    اقساط اختلاف پیدا نمی‌کند.
 * ۳. **بدهیِ وام در تسویه‌حساب تایپ نمی‌شود**؛ خالی که بماند از همان اقساط خوانده
 *    می‌شود. عددی که کاربر بنویسد می‌تواند با واقعیت نخواند.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const faAmount = (v: string | number) => (Number(v) === 0 ? '—' : Math.round(Number(v)).toLocaleString('fa-IR'))
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')
const empName = (e: EmployeeRecord) => `${e.first_name} ${e.last_name}`.trim()

// ── نوع وام ──────────────────────────────────────────────────────────────────

export function LoanTypePage({ token }: { token: string }) {
  const [rows, setRows] = useState<LoanTypeRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [name2, setName2] = useState('')
  const [installments, setInstallments] = useState('12')

  async function refresh() {
    try {
      setRows(await fetchLoanTypes(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createLoanType(token, {
        code: code.trim(),
        name: name.trim(),
        name2: name2.trim(),
        default_installments: Number(installments) || 12,
      })
      setMsg({ text: `نوعِ وام «${name.trim()}» ساخته شد.`, kind: 'ok' })
      setCode('')
      setName('')
      setName2('')
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Banknote}
      title="نوع وام جدید"
      description="دسته‌بندیِ وام‌هایی که به کارکنان می‌دهید: وامِ ضروری، وامِ مسکن، مساعده."
    >
      <SectionCard icon={Plus} title="ثبت نوع وام">
        <form className="cmp-form" onSubmit={submit}>
          <label>
            <span>کد *</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} required />
          </label>
          <label>
            <span>عنوان *</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} required />
          </label>
          <label>
            <span>عنوان (۲)</span>
            <input dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />
            <span className="field-hint">اختیاری — معمولاً همان عنوان به لاتین.</span>
          </label>
          <label>
            <span>تعداد قسط پیش‌فرض</span>
            <input type="number" min="1" max="240" value={installments}
                   onChange={(e) => setInstallments(e.target.value)} />
            <span className="field-hint">فقط پیش‌فرضِ فرم است؛ هر وام تعدادِ خودش را دارد.</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !code.trim() || !name.trim()}>
              <Save size={13} /> ثبت نوع وام
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={Banknote} title={rows ? `${fa(rows.length)} نوع وام` : 'در حال بارگذاری…'}>
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText="هنوز نوعِ وامی ثبت نشده — اولی را با فرمِ بالا بسازید."
        >
          {rows == null || rows.length === 0 ? (
            <EmptyState icon={Banknote} text="هنوز نوعِ وامی ثبت نشده — اولی را با فرمِ بالا بسازید." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr><th>کد</th><th>عنوان</th><th>عنوان (۲)</th><th>قسط پیش‌فرض</th><th>وضعیت</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="کد">{r.code}</td>
                      <td data-label="عنوان">{r.name}</td>
                      <td data-label="عنوان (۲)">{r.name2 || '—'}</td>
                      <td className="num" data-label="قسط پیش‌فرض">{fa(r.default_installments)}</td>
                      <td data-label="وضعیت">{r.is_active ? 'فعال' : 'غیرفعال'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ── وام پرسنلی ───────────────────────────────────────────────────────────────

export function EmployeeLoanPage({ token }: { token: string }) {
  const [rows, setRows] = useState<EmployeeLoanRecord[] | null>(null)
  const [types, setTypes] = useState<LoanTypeRecord[]>([])
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  const [employeeId, setEmployeeId] = useState('')
  const [typeId, setTypeId] = useState('')
  const [amount, setAmount] = useState('')
  const [loanDate, setLoanDate] = useState('')
  const [count, setCount] = useState('12')
  const [firstDue, setFirstDue] = useState('')
  const [note, setNote] = useState('')

  async function refresh() {
    try {
      setRows(await fetchEmployeeLoans(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
    void fetchLoanTypes(token).then((t) => setTypes(t.filter((x) => x.is_active))).catch(() => {})
    void fetchEmployees(token).then((e) => setEmployees(e.filter((x) => x.is_active))).catch(() => {})
  }, [token])

  //: انتخابِ نوعِ وام، تعدادِ قسط را پیشنهاد می‌دهد — ولی کاربر می‌تواند عوضش کند.
  function pickType(id: string) {
    setTypeId(id)
    const found = types.find((t) => t.id === id)
    if (found) setCount(String(found.default_installments))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createEmployeeLoan(token, {
        employee_id: employeeId,
        loan_type_id: typeId || null,
        amount: Number(amount) || 0,
        loan_date: loanDate,
        installment_count: Number(count) || 1,
        first_due_date: firstDue || null,
        note: note.trim(),
      })
      setMsg({ text: 'وام ثبت شد و اقساطش ساخته شدند.', kind: 'ok' })
      setAmount('')
      setNote('')
      setFirstDue('')
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function cancel(id: string) {
    setMsg(null)
    try {
      await cancelEmployeeLoan(token, id)
      setMsg({ text: 'وام لغو شد — اقساطِ کسرشده دست نخوردند.', kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  return (
    <OpsPage
      icon={HandCoins}
      title="تقسیط — وام‌های پرسنلی"
      description="وامِ کارکنان و اقساطش. هر قسط که سررسید شود، هنگام صدور فیش از خالصِ حقوق کسر می‌شود."
    >
      <SectionCard icon={Plus} title="ثبت وام">
        <form className="cmp-form" onSubmit={submit}>
          <p className="muted cmp-form-wide">
            اقساط را شما تایپ نمی‌کنید: مبلغ و تعداد را بدهید و سرور می‌سازدشان —
            باقی‌مانده‌ی تقسیم روی قسطِ آخر می‌نشیند تا جمعشان دقیقاً برابرِ وام بماند.
          </p>
          <label>
            <span>کارمند *</span>
            <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {employees.map((e) => <option key={e.id} value={e.id}>{empName(e)}</option>)}
            </select>
          </label>
          <label>
            <span>نوع وام</span>
            <select value={typeId} onChange={(e) => pickType(e.target.value)}>
              <option value="">— بدون نوع —</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <label>
            <span>مبلغ وام (ریال) *</span>
            <input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} required />
          </label>
          <label>
            <span>تاریخ وام *</span>
            <JalaliDatePicker value={loanDate} onChange={setLoanDate} />
          </label>
          <label>
            <span>تعداد قسط *</span>
            <input type="number" min="1" max="240" value={count} onChange={(e) => setCount(e.target.value)} required />
          </label>
          <label>
            <span>سررسید قسط اول</span>
            <JalaliDatePicker value={firstDue} onChange={setFirstDue} />
            <span className="field-hint">خالی = یک ماه بعد از تاریخِ وام.</span>
          </label>
          <label className="cmp-form-wide">
            <span>توضیح</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"
                    disabled={busy || !employeeId || !amount || !loanDate}>
              <Save size={13} /> ثبت وام
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={HandCoins} title={rows ? `${fa(rows.length)} وام` : 'در حال بارگذاری…'}>
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText="هنوز وامی ثبت نشده — اولی را با فرمِ بالا بسازید."
        >
          {rows == null || rows.length === 0 ? (
            <EmptyState icon={HandCoins} text="هنوز وامی ثبت نشده — اولی را با فرمِ بالا بسازید." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>کارمند</th><th>تاریخ</th><th>مبلغ</th><th>تعداد قسط</th>
                    <th>مانده</th><th>وضعیت</th><th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="کارمند">{r.employee_name || '—'}</td>
                      <td data-label="تاریخ">{formatJalali(r.loan_date)}</td>
                      <td className="num" data-label="مبلغ">{faAmount(r.amount)}</td>
                      <td className="num" data-label="تعداد قسط">{fa(r.installment_count)}</td>
                      <td className="num" data-label="مانده">{faAmount(r.balance)}</td>
                      <td data-label="وضعیت">{LOAN_STATUS_LABELS[r.status] ?? r.status}</td>
                      <td className="card-actions" data-label="">
                        <button type="button" onClick={() => setOpen(open === r.id ? null : r.id)}>
                          {open === r.id ? 'بستنِ اقساط' : 'اقساط'}
                        </button>
                        {r.status === 'active' && (
                          <button type="button" onClick={() => void cancel(r.id)}>
                            <Undo2 size={13} /> لغو
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncBlock>

        {open && rows && (
          <InstallmentTable rows={rows.find((r) => r.id === open)?.installments ?? []} />
        )}
      </SectionCard>
    </OpsPage>
  )
}

function InstallmentTable({ rows }: { rows: EmployeeLoanRecord['installments'] }) {
  if (rows.length === 0) return <EmptyState icon={HandCoins} text="این وام قسطی ندارد." />
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr><th>قسط</th><th>سررسید</th><th>مبلغ</th><th>وضعیت</th></tr>
        </thead>
        <tbody>
          {rows.map((i) => (
            <tr key={i.id}>
              <td className="card-title" data-label="قسط">{fa(i.seq)}</td>
              <td data-label="سررسید">{formatJalali(i.due_date)}</td>
              <td className="num" data-label="مبلغ">{faAmount(i.amount)}</td>
              <td data-label="وضعیت">{i.deducted_period_id ? 'کسر شده' : 'کسر نشده'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── تسویه حساب ───────────────────────────────────────────────────────────────

export function SettlementPage({ token }: { token: string }) {
  const [rows, setRows] = useState<PayrollSettlementRecord[] | null>(null)
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [loans, setLoans] = useState<EmployeeLoanRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  const [employeeId, setEmployeeId] = useState('')
  const [settleDate, setSettleDate] = useState('')
  const [severance, setSeverance] = useState('')
  const [leavePayout, setLeavePayout] = useState('')
  const [otherEarnings, setOtherEarnings] = useState('')
  const [otherDeductions, setOtherDeductions] = useState('')
  const [note, setNote] = useState('')

  async function refresh() {
    try {
      setRows(await fetchSettlements(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
    void fetchEmployees(token).then(setEmployees).catch(() => {})
    void fetchEmployeeLoans(token).then(setLoans).catch(() => {})
  }, [token])

  //: بدهیِ وام تایپ نمی‌شود — از اقساطِ واقعی خوانده می‌شود. این‌جا فقط *نشانش*
  //: می‌دهیم تا کاربر پیش از ثبت بداند چه عددی کسر خواهد شد.
  const loanBalance = useMemo(
    () =>
      loans
        .filter((l) => l.employee_id === employeeId && l.status === 'active')
        .reduce((sum, l) => sum + Number(l.balance || 0), 0),
    [loans, employeeId],
  )

  const net =
    (Number(severance) || 0) + (Number(leavePayout) || 0) + (Number(otherEarnings) || 0)
    - loanBalance - (Number(otherDeductions) || 0)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createSettlement(token, {
        employee_id: employeeId,
        settlement_date: settleDate,
        severance_amount: Number(severance) || 0,
        leave_payout_amount: Number(leavePayout) || 0,
        other_earnings: Number(otherEarnings) || 0,
        other_deductions: Number(otherDeductions) || 0,
        note: note.trim(),
      })
      setMsg({ text: 'تسویه‌حساب ثبت شد.', kind: 'ok' })
      setSeverance('')
      setLeavePayout('')
      setOtherEarnings('')
      setOtherDeductions('')
      setNote('')
      await refresh()
      setLoans(await fetchEmployeeLoans(token))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={UploadCloud}
      title="تسویه حساب"
      description="تسویه‌ی پایانِ کار: سنوات، بازخریدِ مرخصی و بدهیِ وام، همه در یک عددِ خالص."
    >
      <SectionCard icon={Plus} title="ثبت تسویه‌حساب">
        <form className="cmp-form" onSubmit={submit}>
          <p className="muted cmp-form-wide">
            برای هر کارمند یک تسویه‌ی نهایی ثبت می‌شود. بدهیِ وام را تایپ نمی‌کنید —
            از اقساطِ کسرنشده‌ی وام‌های فعالش خوانده می‌شود.
          </p>
          <label>
            <span>کارمند *</span>
            <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {employees.map((e) => <option key={e.id} value={e.id}>{empName(e)}</option>)}
            </select>
          </label>
          <label>
            <span>تاریخ تسویه *</span>
            <JalaliDatePicker value={settleDate} onChange={setSettleDate} />
          </label>
          <label>
            <span>سنوات (ریال)</span>
            <input type="number" min="0" value={severance} onChange={(e) => setSeverance(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>بازخرید مرخصی (ریال)</span>
            <input type="number" min="0" value={leavePayout} onChange={(e) => setLeavePayout(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>سایر مزایا (ریال)</span>
            <input type="number" min="0" value={otherEarnings} onChange={(e) => setOtherEarnings(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>سایر کسورات (ریال)</span>
            <input type="number" min="0" value={otherDeductions} onChange={(e) => setOtherDeductions(e.target.value)} placeholder="۰" />
          </label>

          {employeeId && (
            <section className="fy-status cmp-form-wide">
              <div>
                بدهیِ وامِ این کارمند: <strong>{faAmount(loanBalance)}</strong> ریال
                {' — '}
                خالصِ پرداختی: <strong>{faAmount(net)}</strong> ریال
                {net < 0 && ' (منفی: بدهیِ وام از مزایا بیشتر است)'}
              </div>
            </section>
          )}

          <label className="cmp-form-wide">
            <span>توضیح</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !employeeId || !settleDate}>
              <Save size={13} /> ثبت تسویه‌حساب
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={UploadCloud} title={rows ? `${fa(rows.length)} تسویه‌حساب` : 'در حال بارگذاری…'}>
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText="هنوز تسویه‌حسابی ثبت نشده."
        >
          {rows == null || rows.length === 0 ? (
            <EmptyState icon={UploadCloud} text="هنوز تسویه‌حسابی ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>کارمند</th><th>تاریخ</th><th>سنوات</th><th>بازخرید مرخصی</th>
                    <th>بدهی وام</th><th>خالص</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="کارمند">{r.employee_name || '—'}</td>
                      <td data-label="تاریخ">{formatJalali(r.settlement_date)}</td>
                      <td className="num" data-label="سنوات">{faAmount(r.severance_amount)}</td>
                      <td className="num" data-label="بازخرید مرخصی">{faAmount(r.leave_payout_amount)}</td>
                      <td className="num" data-label="بدهی وام">{faAmount(r.loan_balance)}</td>
                      <td className="num" data-label="خالص">{faAmount(r.net_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ── اطلاعات استقرار ──────────────────────────────────────────────────────────

export function DeploymentInfoPage({ token }: { token: string }) {
  const [rows, setRows] = useState<DeploymentInfoRecord[] | null>(null)
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  const [employeeId, setEmployeeId] = useState('')
  const [year, setYear] = useState('')
  const [gross, setGross] = useState('')
  const [tax, setTax] = useState('')
  const [insurance, setInsurance] = useState('')
  const [leaveDays, setLeaveDays] = useState('')
  const [priorDays, setPriorDays] = useState('')

  async function refresh() {
    try {
      setRows(await fetchDeploymentInfo(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
    void fetchEmployees(token).then(setEmployees).catch(() => {})
  }, [token])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await saveDeploymentInfo(token, {
        employee_id: employeeId,
        year: Number(year) || 0,
        cumulative_gross: Number(gross) || 0,
        cumulative_tax: Number(tax) || 0,
        cumulative_insurance: Number(insurance) || 0,
        leave_balance_days: Number(leaveDays) || 0,
        prior_service_days: Number(priorDays) || 0,
      })
      setMsg({ text: 'اطلاعاتِ استقرار ذخیره شد.', kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={UploadCloud}
      title="اطلاعات استقرار"
      description="آنچه پیش از آمدن به کوبیتا اتفاق افتاده: پرداختیِ تجمیعیِ سال، مانده‌ی مرخصی و سابقه."
    >
      <SectionCard icon={Plus} title="ثبت اطلاعات استقرار">
        <form className="cmp-form" onSubmit={submit}>
          {/* این هشدار تزئینی نیست: مالیاتِ حقوق پلکانی و سالانه است و بدونِ
              پرداختیِ ماه‌های گذشته، پلکان از صفر شروع می‌شود. */}
          <section className="fy-status cmp-form-wide">
            <div>
              اگر وسطِ سال به کوبیتا آمده‌اید، <strong>حتماً</strong> پرداختیِ تجمیعیِ
              ماه‌های گذشته را وارد کنید. مالیاتِ حقوق پلکانی و سالانه است؛ بدونِ این
              عدد پلکان از صفر شروع می‌شود و مالیاتِ ماه‌های باقی‌مانده کمتر از واقع
              محاسبه می‌شود.
            </div>
          </section>
          <label>
            <span>کارمند *</span>
            <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {employees.map((e) => <option key={e.id} value={e.id}>{empName(e)}</option>)}
            </select>
          </label>
          <label>
            <span>سال مالی (شمسی) *</span>
            <input type="number" min="1300" max="1500" value={year} onChange={(e) => setYear(e.target.value)} required />
          </label>
          <label>
            <span>پرداختی تجمیعی (ریال)</span>
            <input type="number" min="0" value={gross} onChange={(e) => setGross(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>مالیات کسرشده تجمیعی (ریال)</span>
            <input type="number" min="0" value={tax} onChange={(e) => setTax(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>بیمه کسرشده تجمیعی (ریال)</span>
            <input type="number" min="0" value={insurance} onChange={(e) => setInsurance(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>مانده مرخصی (روز)</span>
            <input type="number" min="0" step="0.5" value={leaveDays} onChange={(e) => setLeaveDays(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>سابقه قبلی (روز)</span>
            <input type="number" min="0" value={priorDays} onChange={(e) => setPriorDays(e.target.value)} placeholder="۰" />
            <span className="field-hint">مبنای سنوات — بدونش کارمندِ ده‌ساله تازه‌وارد دیده می‌شود.</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !employeeId || !year}>
              <Save size={13} /> ذخیره
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={UploadCloud} title={rows ? `${fa(rows.length)} ردیف` : 'در حال بارگذاری…'}>
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText="هنوز اطلاعاتِ استقراری ثبت نشده."
        >
          {rows == null || rows.length === 0 ? (
            <EmptyState icon={UploadCloud} text="هنوز اطلاعاتِ استقراری ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>کارمند</th><th>سال</th><th>پرداختی تجمیعی</th>
                    <th>مالیات</th><th>بیمه</th><th>مانده مرخصی</th><th>سابقه (روز)</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="کارمند">{r.employee_name || '—'}</td>
                      <td className="num" data-label="سال">{fa(r.year)}</td>
                      <td className="num" data-label="پرداختی تجمیعی">{faAmount(r.cumulative_gross)}</td>
                      <td className="num" data-label="مالیات">{faAmount(r.cumulative_tax)}</td>
                      <td className="num" data-label="بیمه">{faAmount(r.cumulative_insurance)}</td>
                      <td className="num" data-label="مانده مرخصی">{fa(Number(r.leave_balance_days))}</td>
                      <td className="num" data-label="سابقه (روز)">{fa(r.prior_service_days)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
