import { useEffect, useMemo, useState } from 'react'
import { Banknote, HandCoins, Plus, Save, Undo2, UploadCloud, X } from 'lucide-react'
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
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import {
  ActionBar,
  FormField,
  FormGrid,
  FormStatus,
  InlineCreate,
  SelectWithAdd,
  TabHead,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { formatJalali } from '../../lib/jalali'
import { ActiveChip, AsyncBlock, Note, OpsPage, type Msg } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'

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
 *
 * چیدمان با اجزای فرمِ سازمانی است (`components/form/FormKit`) — همان «قرارداد جدید».
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const faAmount = (v: string | number) => (Number(v) === 0 ? '—' : Math.round(Number(v)).toLocaleString('fa-IR'))
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')
const empName = (e: EmployeeRecord) => `${e.first_name} ${e.last_name}`.trim()

const LOAN_STATUS_TONES: Record<string, string> = {
  active: 'tone-success',
  settled: 'tone-muted',
  cancelled: 'tone-muted',
}

function SubmitButton({ busy, label }: { busy: boolean; label: string }) {
  return (
    <button type="submit" className="btn-primary" disabled={busy}>
      <Save size={15} /> {busy ? 'در حال ثبت…' : label}
    </button>
  )
}

/**
 * انتخابِ کارمند. پیامِ «پرسنلی ثبت نشده» فقط وقتی دیده می‌شود که فهرست واقعاً خالی
 * برگشته باشد — نه در لحظه‌ی بارگذاری.
 */
function EmployeeSelect({
  id,
  employees,
  value,
  onChange,
}: {
  id: string
  employees: EmployeeRecord[] | null
  value: string
  onChange: (v: string) => void
}) {
  return (
    <FormField
      id={id}
      label="کارمند"
      required
      message={
        employees?.length === 0 ? (
          <span className="ef-message--warn">هنوز پرسنلی ثبت نشده — از «پرسنل و احکام» اضافه کنید.</span>
        ) : undefined
      }
    >
      {(fid) => (
        <SearchSelect id={fid} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {(employees ?? []).map((e) => (
            <option key={e.id} value={e.id}>
              {empName(e)}
            </option>
          ))}
        </SearchSelect>
      )}
    </FormField>
  )
}

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
    const missing = firstMissing([
      [code, 'lt-code', 'کد را وارد کنید.'],
      [name, 'lt-name', 'عنوان را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard icon={Plus} title="ثبت نوع وام">
            <FormGrid>
              <FormField id="lt-code" label="کد" required>
                {(id) => <input id={id} value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} />}
              </FormField>
              <FormField id="lt-name" label="عنوان" required>
                {(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="عنوان (۲)" tip="اختیاری — معمولاً همان عنوان به لاتین.">
                {(id) => <input id={id} dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="تعداد قسط پیش‌فرض" tip="فقط پیش‌فرضِ فرمِ وام است؛ هر وام تعدادِ خودش را دارد.">
                {(id) => <NumberInput id={id} group={false} value={installments} onChange={setInstallments} />}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            <SubmitButton busy={busy} label="ثبت نوع وام" />
          </ActionBar>
        </form>

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
                    <tr>
                      <th>کد</th>
                      <th>عنوان</th>
                      <th>عنوان (۲)</th>
                      <th>قسط پیش‌فرض</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        <td className="card-title" data-label="کد">
                          {r.code}
                        </td>
                        <td data-label="عنوان">{r.name}</td>
                        <td data-label="عنوان (۲)">{r.name2 || '—'}</td>
                        <td className="num" data-label="قسط پیش‌فرض">
                          {fa(r.default_installments)}
                        </td>
                        <td data-label="وضعیت">
                          <ActiveChip active={r.is_active} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

// ── وام پرسنلی ───────────────────────────────────────────────────────────────

export function EmployeeLoanPage({ token }: { token: string }) {
  const [rows, setRows] = useState<EmployeeLoanRecord[] | null>(null)
  const [types, setTypes] = useState<LoanTypeRecord[]>([])
  const [employees, setEmployees] = useState<EmployeeRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [listMsg, setListMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const [addType, setAddType] = useState(false)

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
    void fetchEmployees(token)
      .then((e) => setEmployees(e.filter((x) => x.is_active)))
      .catch(() => setEmployees([]))
  }, [token])

  //: انتخابِ نوعِ وام، تعدادِ قسط را پیشنهاد می‌دهد — ولی کاربر می‌تواند عوضش کند.
  function pickType(id: string, list: LoanTypeRecord[] = types) {
    setTypeId(id)
    const found = list.find((t) => t.id === id)
    if (found) setCount(String(found.default_installments))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const missing = firstMissing([
      [employeeId, 'el-employee', 'کارمند را انتخاب کنید.'],
      [Number(amount) > 0, 'el-amount', 'مبلغِ وام را وارد کنید.'],
      [loanDate, 'el-date', 'تاریخِ وام را انتخاب کنید.'],
      [Number(count) > 0, 'el-count', 'تعدادِ قسط را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
    setListMsg(null)
    try {
      await cancelEmployeeLoan(token, id)
      setListMsg({ text: 'وام لغو شد — اقساطِ کسرشده دست نخوردند.', kind: 'ok' })
      await refresh()
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
    }
  }

  //: پیش‌نمایشِ قسط — سرور باقی‌مانده‌ی تقسیم را روی قسطِ آخر می‌گذارد، پس «≈».
  const perInstallment = Number(amount) > 0 && Number(count) > 0 ? Math.floor(Number(amount) / Number(count)) : 0
  const openLoan = open ? rows?.find((r) => r.id === open) : undefined

  return (
    <OpsPage
      icon={HandCoins}
      title="تقسیط — وام‌های پرسنلی"
      description="وامِ کارکنان و اقساطش. هر قسط که سررسید شود، هنگام صدور فیش از خالصِ حقوق کسر می‌شود."
    >
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard
            icon={Plus}
            title="ثبت وام"
            tip="اقساط را شما تایپ نمی‌کنید: مبلغ و تعداد را بدهید و سرور می‌سازدشان — باقی‌مانده‌ی تقسیم روی قسطِ آخر می‌نشیند تا جمعشان دقیقاً برابرِ وام بماند."
          >
            <FormGrid>
              <EmployeeSelect id="el-employee" employees={employees} value={employeeId} onChange={setEmployeeId} />
              <FormField label="نوع وام">
                {(id) => (
                  <SelectWithAdd
                    id={id}
                    value={typeId}
                    onChange={(v) => pickType(v)}
                    options={types.map((t) => ({ value: t.id, label: t.name }))}
                    addLabel="افزودن نوع وام تازه"
                    adding={addType}
                    onToggleAdd={() => setAddType((v) => !v)}
                  />
                )}
              </FormField>
              <FormField id="el-amount" label="مبلغ وام (ریال)" required>
                {(id) => <NumberInput id={id} value={amount} onChange={setAmount} placeholder="۰" />}
              </FormField>

              {addType && (
                <InlineCreate
                  label="نوع وام تازه"
                  onClose={() => setAddType(false)}
                  fields={[
                    { key: 'code', label: 'کد', required: true },
                    { key: 'name', label: 'عنوان', required: true },
                  ]}
                  onCreate={async (values) => {
                    const row = await createLoanType(token, {
                      code: values.code.trim(),
                      name: values.name.trim(),
                      default_installments: Number(count) || 12,
                    })
                    const next = [...types, row]
                    setTypes(next)
                    pickType(row.id, next)
                    setAddType(false)
                  }}
                />
              )}

              <FormField id="el-date" label="تاریخ وام" required>
                {(id) => <JalaliDatePicker id={id} value={loanDate} onChange={setLoanDate} />}
              </FormField>
              <FormField id="el-count" label="تعداد قسط" required>
                {(id) => <NumberInput id={id} group={false} value={count} onChange={setCount} />}
              </FormField>
              <FormField label="سررسید قسط اول" tip="خالی = یک ماه بعد از تاریخِ وام.">
                {(id) => <JalaliDatePicker id={id} value={firstDue} onChange={setFirstDue} />}
              </FormField>
              <FormField label="توضیح" span="full">
                {(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar
            status={
              <FormStatus
                msg={msg}
                idle={
                  perInstallment > 0 && (
                    <>
                      قسطِ ماهانه ≈ <b>{fa(perInstallment)}</b> ریال در {fa(Number(count))} قسط
                    </>
                  )
                }
              />
            }
          >
            <SubmitButton busy={busy} label="ثبت وام" />
          </ActionBar>
        </form>

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
                      <th>کارمند</th>
                      <th>تاریخ</th>
                      <th>مبلغ</th>
                      <th>تعداد قسط</th>
                      <th>مانده</th>
                      <th>وضعیت</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        <td className="card-title" data-label="کارمند">
                          {r.employee_name || '—'}
                        </td>
                        <td data-label="تاریخ">{formatJalali(r.loan_date)}</td>
                        <td className="num" data-label="مبلغ">
                          {faAmount(r.amount)}
                        </td>
                        <td className="num" data-label="تعداد قسط">
                          {fa(r.installment_count)}
                        </td>
                        <td className="num" data-label="مانده">
                          {faAmount(r.balance)}
                        </td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${LOAN_STATUS_TONES[r.status] ?? ''}`}>
                            {LOAN_STATUS_LABELS[r.status] ?? r.status}
                          </span>
                        </td>
                        <td className="card-actions">
                          <button type="button" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>
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
          <Note msg={listMsg} />

          {openLoan && (
            <div className="ef-block">
              <TabHead
                title={`اقساطِ وامِ ${openLoan.employee_name || ''}`.trim()}
                actions={
                  <button type="button" onClick={() => setOpen(null)}>
                    <X size={14} /> بستن
                  </button>
                }
              />
              <InstallmentTable rows={openLoan.installments} />
            </div>
          )}
        </SectionCard>
      </div>
    </OpsPage>
  )
}

function InstallmentTable({ rows }: { rows: EmployeeLoanRecord['installments'] }) {
  if (rows.length === 0) return <EmptyState icon={HandCoins} text="این وام قسطی ندارد." />
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr>
            <th>قسط</th>
            <th>سررسید</th>
            <th>مبلغ</th>
            <th>وضعیت</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((i) => (
            <tr key={i.id}>
              <td className="card-title" data-label="قسط">
                {fa(i.seq)}
              </td>
              <td data-label="سررسید">{formatJalali(i.due_date)}</td>
              <td className="num" data-label="مبلغ">
                {faAmount(i.amount)}
              </td>
              <td data-label="وضعیت">
                <span className={`status-badge ${i.deducted_period_id ? 'tone-success' : ''}`}>
                  {i.deducted_period_id ? 'کسر شده' : 'کسر نشده'}
                </span>
              </td>
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
  const [employees, setEmployees] = useState<EmployeeRecord[] | null>(null)
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
    void fetchEmployees(token).then(setEmployees).catch(() => setEmployees([]))
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
    const missing = firstMissing([
      [employeeId, 'st-employee', 'کارمند را انتخاب کنید.'],
      [settleDate, 'st-date', 'تاریخِ تسویه را انتخاب کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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

  const amountField = (label: string, value: string, set: (v: string) => void) => (
    <FormField label={label}>{(id) => <NumberInput id={id} value={value} onChange={set} placeholder="۰" />}</FormField>
  )

  return (
    <OpsPage
      icon={UploadCloud}
      title="تسویه حساب"
      description="تسویه‌ی پایانِ کار: سنوات، بازخریدِ مرخصی و بدهیِ وام، همه در یک عددِ خالص."
    >
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard
            icon={Plus}
            title="ثبت تسویه‌حساب"
            tip="برای هر کارمند یک تسویه‌ی نهایی ثبت می‌شود. بدهیِ وام را تایپ نمی‌کنید — از اقساطِ کسرنشده‌ی وام‌های فعالش خوانده می‌شود."
          >
            <FormGrid>
              <EmployeeSelect id="st-employee" employees={employees} value={employeeId} onChange={setEmployeeId} />
              <FormField id="st-date" label="تاریخ تسویه" required>
                {(id) => <JalaliDatePicker id={id} value={settleDate} onChange={setSettleDate} />}
              </FormField>
              {amountField('سنوات (ریال)', severance, setSeverance)}
              {amountField('بازخرید مرخصی (ریال)', leavePayout, setLeavePayout)}
              {amountField('سایر مزایا (ریال)', otherEarnings, setOtherEarnings)}
              {amountField('سایر کسورات (ریال)', otherDeductions, setOtherDeductions)}
              <FormField label="توضیح" span="full">
                {(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar
            status={
              <FormStatus
                msg={msg}
                idle={
                  employeeId && (
                    <>
                      بدهیِ وام: <b>{faAmount(loanBalance)}</b> ریال · خالصِ پرداختی: <b>{faAmount(net)}</b> ریال
                      {net < 0 && <span className="ef-message--warn"> (منفی: بدهیِ وام از مزایا بیشتر است)</span>}
                    </>
                  )
                }
              />
            }
          >
            <SubmitButton busy={busy} label="ثبت تسویه‌حساب" />
          </ActionBar>
        </form>

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
                      <th>کارمند</th>
                      <th>تاریخ</th>
                      <th>سنوات</th>
                      <th>بازخرید مرخصی</th>
                      <th>بدهی وام</th>
                      <th>خالص</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        <td className="card-title" data-label="کارمند">
                          {r.employee_name || '—'}
                        </td>
                        <td data-label="تاریخ">{formatJalali(r.settlement_date)}</td>
                        <td className="num" data-label="سنوات">
                          {faAmount(r.severance_amount)}
                        </td>
                        <td className="num" data-label="بازخرید مرخصی">
                          {faAmount(r.leave_payout_amount)}
                        </td>
                        <td className="num" data-label="بدهی وام">
                          {faAmount(r.loan_balance)}
                        </td>
                        <td className="num" data-label="خالص">
                          {faAmount(r.net_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

// ── اطلاعات استقرار ──────────────────────────────────────────────────────────

export function DeploymentInfoPage({ token }: { token: string }) {
  const [rows, setRows] = useState<DeploymentInfoRecord[] | null>(null)
  const [employees, setEmployees] = useState<EmployeeRecord[] | null>(null)
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
    void fetchEmployees(token).then(setEmployees).catch(() => setEmployees([]))
  }, [token])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const missing = firstMissing([
      [employeeId, 'di-employee', 'کارمند را انتخاب کنید.'],
      [year, 'di-year', 'سالِ مالی را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          {/* جمله‌ی سرِ کارت تزئینی نیست: مالیاتِ حقوق پلکانی و سالانه است و بدونِ
              پرداختیِ ماه‌های گذشته، پلکان از صفر شروع می‌شود. */}
          <SectionCard
            icon={Plus}
            title="ثبت اطلاعات استقرار"
            description="اگر وسطِ سال به کوبیتا آمده‌اید، پرداختیِ تجمیعیِ ماه‌های گذشته را حتماً وارد کنید."
            tip="مالیاتِ حقوق پلکانی و سالانه است؛ بدونِ این عدد پلکان از صفر شروع می‌شود و مالیاتِ ماه‌های باقی‌مانده کمتر از واقع محاسبه می‌شود."
          >
            <FormGrid>
              <EmployeeSelect id="di-employee" employees={employees} value={employeeId} onChange={setEmployeeId} />
              <FormField id="di-year" label="سال مالی (شمسی)" required>
                {(id) => <NumberInput id={id} group={false} value={year} onChange={setYear} placeholder="۱۴۰۵" />}
              </FormField>
              <FormField label="پرداختی تجمیعی (ریال)">
                {(id) => <NumberInput id={id} value={gross} onChange={setGross} placeholder="۰" />}
              </FormField>
              <FormField label="مالیات کسرشده تجمیعی (ریال)">
                {(id) => <NumberInput id={id} value={tax} onChange={setTax} placeholder="۰" />}
              </FormField>
              <FormField label="بیمه کسرشده تجمیعی (ریال)">
                {(id) => <NumberInput id={id} value={insurance} onChange={setInsurance} placeholder="۰" />}
              </FormField>
              <FormField label="مانده مرخصی (روز)">
                {(id) => <NumberInput id={id} allowDecimal value={leaveDays} onChange={setLeaveDays} placeholder="۰" />}
              </FormField>
              <FormField label="سابقه قبلی (روز)" tip="مبنای سنوات — بدونش کارمندِ ده‌ساله تازه‌وارد دیده می‌شود.">
                {(id) => <NumberInput id={id} group={false} value={priorDays} onChange={setPriorDays} placeholder="۰" />}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            <button type="submit" className="btn-primary" disabled={busy}>
              <Save size={15} /> {busy ? 'در حال ذخیره…' : 'ذخیره'}
            </button>
          </ActionBar>
        </form>

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
                      <th>کارمند</th>
                      <th>سال</th>
                      <th>پرداختی تجمیعی</th>
                      <th>مالیات</th>
                      <th>بیمه</th>
                      <th>مانده مرخصی</th>
                      <th>سابقه (روز)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        <td className="card-title" data-label="کارمند">
                          {r.employee_name || '—'}
                        </td>
                        <td className="num" data-label="سال">
                          {r.year.toLocaleString('fa-IR', { useGrouping: false })}
                        </td>
                        <td className="num" data-label="پرداختی تجمیعی">
                          {faAmount(r.cumulative_gross)}
                        </td>
                        <td className="num" data-label="مالیات">
                          {faAmount(r.cumulative_tax)}
                        </td>
                        <td className="num" data-label="بیمه">
                          {faAmount(r.cumulative_insurance)}
                        </td>
                        <td className="num" data-label="مانده مرخصی">
                          {fa(Number(r.leave_balance_days))}
                        </td>
                        <td className="num" data-label="سابقه (روز)">
                          {fa(r.prior_service_days)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}
