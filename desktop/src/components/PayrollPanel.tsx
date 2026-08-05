import { useEffect, useMemo, useState } from 'react'
import { Users, Save, CalendarPlus, Download, FileText, Gift, Settings } from 'lucide-react'
import { Tabs } from './Tabs'
import { BenefitsPanel } from './BenefitsPanel'
import { Pager, usePagination } from './Pager'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { PayrollSettingsPanel } from './PayrollSettingsPanel'
import { PayslipDrawer } from './PayslipDrawer'
import { formatJalali, isoToJalali, todayIso, JALALI_MONTH_NAMES } from '../lib/jalali'
import {
  createEmployee,
  createPayrollPeriod,
  createSalaryContract,
  downloadInsuranceListCsv,
  fetchAttendance,
  fetchEmployees,
  fetchPayrollPeriods,
  fetchPayslips,
  generatePayslips,
  upsertAttendance,
  type EmployeeRecord,
  type PayrollPeriodRecord,
  type PayslipRecord,
} from '../api'

// دوره‌ی حقوق شمسی است: ماه‌ها فروردین..اسفند (JALALI_MONTH_NAMES)

export function PayrollPanel({ token }: { token: string }) {
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [periods, setPeriods] = useState<PayrollPeriodRecord[]>([])
  const [selectedPeriodId, setSelectedPeriodId] = useState<string>('')
  const [message, setMessage] = useState<string | null>(null)

  async function refresh() {
    setEmployees(await fetchEmployees(token))
    setPeriods(await fetchPayrollPeriods(token))
  }

  useEffect(() => {
    void refresh()
  }, [])

  const selectedPeriod = periods.find((p) => p.id === selectedPeriodId)

  // بخش‌ها به‌جای چیده‌شدنِ زیرِ هم، تب‌بندی می‌شوند (مثلِ بقیه‌ی ماژول‌ها). حالتِ مشترک
  // (پرسنل/دوره‌ها) در همین کامپوننت می‌ماند، پس جابه‌جایی بین تب‌ها داده را از دست نمی‌دهد.
  return (
    <Tabs
      syncPage="payroll"
      tabs={[
        {
          key: 'staff',
          label: 'پرسنل و احکام',
          icon: Users,
          content: (
            <>
              {message && <div className="hint">{message}</div>}
              <EmployeeForm
                token={token}
                onCreated={() => {
                  void refresh()
                  setMessage('کارمند ثبت شد.')
                }}
              />
              <EmployeeList employees={employees} />
              <SalaryContractForm
                token={token}
                employees={employees}
                onCreated={() => setMessage('حکم حقوقی ثبت شد.')}
              />
            </>
          ),
        },
        {
          key: 'run',
          label: 'کارکرد و صدور فیش',
          icon: CalendarPlus,
          content: (
            <>
              <PeriodSection
                token={token}
                periods={periods}
                selectedPeriodId={selectedPeriodId}
                onSelect={setSelectedPeriodId}
                onPeriodCreated={() => void refresh()}
              />
              {selectedPeriodId ? (
                <PayrollRunPanel token={token} employees={employees} period={selectedPeriod} periodId={selectedPeriodId} />
              ) : (
                <p className="hint">یک دوره را انتخاب یا ایجاد کنید تا جدولِ کارکرد و صدورِ فیش نمایش داده شود.</p>
              )}
            </>
          ),
        },
        {
          key: 'benefits',
          label: 'مزایا',
          icon: Gift,
          content: <BenefitsPanel token={token} />,
        },
        {
          key: 'settings',
          label: 'تنظیماتِ حقوق',
          icon: Settings,
          content: <PayrollSettingsPanel token={token} onSaved={() => void refresh()} />,
        },
      ]}
    />
  )
}

function EmployeeForm({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [nationalId, setNationalId] = useState('')
  const [hireDate, setHireDate] = useState(new Date().toISOString().slice(0, 10))
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!firstName || !lastName || !nationalId) {
      setError('نام، نام‌خانوادگی و کد ملی الزامی است.')
      return
    }
    try {
      await createEmployee(token, {
        first_name: firstName,
        last_name: lastName,
        national_id: nationalId,
        phone: '',
        email: '',
        bank_account_number: '',
        hire_date: hireDate,
      })
      setFirstName('')
      setLastName('')
      setNationalId('')
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <form className="invoice-form" onSubmit={handleSubmit}>
      <h3>افزودن پرسنل</h3>
      <label>
        نام
        <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
      </label>
      <label>
        نام‌خانوادگی
        <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} />
      </label>
      <label>
        کد ملی
        <input type="text" value={nationalId} onChange={(e) => setNationalId(e.target.value)} />
      </label>
      <label>
        تاریخ استخدام
        <JalaliDatePicker value={hireDate} onChange={setHireDate} />
      </label>
      <div className="invoice-form-footer">
        <button type="submit" className="btn-primary"><Save size={14} /> ثبت پرسنل</button>
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}

function EmployeeList({ employees }: { employees: EmployeeRecord[] }) {
  const pg = usePagination(employees, 10)
  if (employees.length === 0) return <EmptyState icon={Users} text="پرسنلی ثبت نشده." />
  return (
    <div className="entity-table-wrap">
      <table className="entity-table payroll-emp-table">
        <thead>
          <tr>
            <th>نام</th>
            <th>کد ملی</th>
            <th>تاریخ استخدام</th>
            <th>وضعیت</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((e) => (
            <tr key={e.id}>
              <td className="entity-name">
                {e.first_name} {e.last_name}
              </td>
              <td data-label="کد ملی">{e.national_id}</td>
              <td data-label="تاریخ استخدام">{formatJalali(e.hire_date)}</td>
              <td data-label="وضعیت">
                <span className={`status-badge ${e.is_active ? 'tone-success' : 'tone-muted'}`}>
                  {e.is_active ? 'فعال' : 'غیرفعال'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

function SalaryContractForm({
  token,
  employees,
  onCreated,
}: {
  token: string
  employees: EmployeeRecord[]
  onCreated: () => void
}) {
  const [employeeId, setEmployeeId] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10))
  const [baseSalary, setBaseSalary] = useState('')
  const [housing, setHousing] = useState('0')
  const [food, setFood] = useState('0')
  const [other, setOther] = useState('0')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!employeeId || Number(baseSalary) <= 0) {
      setError('کارمند و حقوق پایه (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      await createSalaryContract(token, {
        employee_id: employeeId,
        effective_from: effectiveFrom,
        base_salary: Number(baseSalary),
        housing_allowance: Number(housing) || 0,
        food_allowance: Number(food) || 0,
        other_allowance: Number(other) || 0,
      })
      setBaseSalary('')
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <form className="invoice-form" onSubmit={handleSubmit}>
      <h3>ثبت حکم حقوقی</h3>
      <label>
        کارمند
        <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
          <option value="">— انتخاب —</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.first_name} {emp.last_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        تاریخ اجرا
        <JalaliDatePicker value={effectiveFrom} onChange={setEffectiveFrom} />
      </label>
      <label>
        حقوق پایه
        <NumberInput value={baseSalary} onChange={setBaseSalary} />
      </label>
      <label>
        حق مسکن
        <NumberInput value={housing} onChange={setHousing} />
      </label>
      <label>
        بن خواربار
        <NumberInput value={food} onChange={setFood} />
      </label>
      <label>
        سایر مزایا
        <NumberInput value={other} onChange={setOther} />
      </label>
      <div className="invoice-form-footer">
        <button type="submit" className="btn-primary"><Save size={14} /> ثبت حکم</button>
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}

function PeriodSection({
  token,
  periods,
  selectedPeriodId,
  onSelect,
  onPeriodCreated,
}: {
  token: string
  periods: PayrollPeriodRecord[]
  selectedPeriodId: string
  onSelect: (id: string) => void
  onPeriodCreated: () => void
}) {
  const today = isoToJalali(todayIso())
  const [year, setYear] = useState(today.jy)
  const [month, setMonth] = useState(today.jm)
  const [error, setError] = useState<string | null>(null)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const period = await createPayrollPeriod(token, { year, month })
      onPeriodCreated()
      onSelect(period.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="invoice-form">
      <h3>دوره‌های حقوقی</h3>
      <form onSubmit={handleCreate} className="check-actions">
        <NumberInput group={false} value={year} onChange={(v) => setYear(Number(v))} style={{ width: 90 }} />
        <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
          {JALALI_MONTH_NAMES.map((name, idx) => (
            <option key={idx} value={idx + 1}>
              {name}
            </option>
          ))}
        </select>
        <button type="submit"><CalendarPlus size={14} /> ایجاد دوره جدید</button>
      </form>
      {error && <div className="error">{error}</div>}
      <div className="check-actions" style={{ marginTop: 8, flexWrap: 'wrap' }}>
        {periods.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onSelect(p.id)}
            style={{ fontWeight: p.id === selectedPeriodId ? 700 : 400 }}
          >
            {p.year}/{String(p.month).padStart(2, '0')} ({p.status === 'finalized' ? 'نهایی‌شده' : 'پیش‌نویس'})
          </button>
        ))}
      </div>
    </div>
  )
}

function PayrollRunPanel({
  token,
  employees,
  period,
  periodId,
}: {
  token: string
  employees: EmployeeRecord[]
  period: PayrollPeriodRecord | undefined
  periodId: string
}) {
  const [attendance, setAttendance] = useState<Record<string, { worked: string; overtime: string }>>({})
  const [payslips, setPayslips] = useState<PayslipRecord[]>([])
  const payslipsPg = usePagination(payslips, 10)
  const [message, setMessage] = useState<string | null>(null)
  const [openPayslip, setOpenPayslip] = useState<PayslipRecord | null>(null)

  const empById = useMemo(() => new Map(employees.map((e) => [e.id, e])), [employees])

  async function refresh() {
    const existing = await fetchAttendance(token, periodId)
    const map: Record<string, { worked: string; overtime: string }> = {}
    for (const a of existing) {
      map[a.employee_id] = { worked: a.worked_days, overtime: a.overtime_hours }
    }
    setAttendance(map)
    setPayslips(await fetchPayslips(token, periodId))
  }

  useEffect(() => {
    void refresh()
  }, [periodId])

  async function saveAttendance(employeeId: string) {
    const entry = attendance[employeeId] ?? { worked: '30', overtime: '0' }
    await upsertAttendance(token, {
      employee_id: employeeId,
      period_id: periodId,
      worked_days: Number(entry.worked) || 0,
      absent_days: 30 - (Number(entry.worked) || 0),
      overtime_hours: Number(entry.overtime) || 0,
    })
    setMessage(`کارکرد ذخیره شد.`)
  }

  async function handleGenerate() {
    setMessage(null)
    try {
      const result = await generatePayslips(token, periodId)
      setPayslips(result)
      setMessage(`${result.length} فیش حقوقی صادر شد.`)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDownloadInsuranceList() {
    setMessage(null)
    try {
      const { filename, blob } = await downloadInsuranceListCsv(token, periodId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="invoice-form">
      <h3>کارکرد و صدور فیش برای دوره‌ی انتخاب‌شده</h3>
      <div className="entity-table-wrap">
        <table className="entity-table payroll-attend-table">
          <thead>
            <tr>
              <th>کارمند</th>
              <th>روز کارکرد</th>
              <th>ساعت اضافه‌کار</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {employees.map((emp) => (
              <tr key={emp.id}>
                <td className="entity-name">
                  {emp.first_name} {emp.last_name}
                </td>
                <td data-label="روز کارکرد">
                  <NumberInput
                    value={attendance[emp.id]?.worked ?? '30'}
                    onChange={(v) =>
                      setAttendance((prev) => ({
                        ...prev,
                        [emp.id]: { worked: v, overtime: prev[emp.id]?.overtime ?? '0' },
                      }))
                    }
                  />
                </td>
                <td data-label="ساعت اضافه‌کار">
                  <NumberInput
                    value={attendance[emp.id]?.overtime ?? '0'}
                    onChange={(v) =>
                      setAttendance((prev) => ({
                        ...prev,
                        [emp.id]: { worked: prev[emp.id]?.worked ?? '30', overtime: v },
                      }))
                    }
                  />
                </td>
                <td className="attend-action">
                  <button type="button" onClick={() => void saveAttendance(emp.id)}>
                    <Save size={13} /> ذخیره کارکرد
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="invoice-form-footer">
        <button type="button" className="btn-primary" onClick={() => void handleGenerate()}>
          صدور فیش‌های حقوقی این دوره
        </button>
        {payslips.length > 0 && (
          <button type="button" onClick={() => void handleDownloadInsuranceList()}>
            <Download size={13} /> دانلود لیست بیمه (CSV)
          </button>
        )}
      </div>
      {payslips.length > 0 && (
        <p className="hint">
          فرمت این فایل عمومی است؛ قبل از ارسال رسمی به سازمان تأمین اجتماعی، آن را با آخرین مشخصات سامانه‌ی لیست بیمه تطبیق دهید.
        </p>
      )}
      {message && <div className="hint">{message}</div>}

      {payslips.length > 0 && (
        <div className="entity-table-wrap">
          <table className="entity-table payslip-table">
            <thead>
              <tr>
                <th>شماره</th>
                <th>کارمند</th>
                <th>ناخالص</th>
                <th>بیمه</th>
                <th>مالیات</th>
                <th>خالص پرداختی</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {payslipsPg.pageItems.map((p) => {
                const emp = empById.get(p.employee_id)
                return (
                  <tr key={p.id}>
                    <td data-label="شماره">{p.number}</td>
                    <td className="entity-name">{emp ? `${emp.first_name} ${emp.last_name}` : '—'}</td>
                    <td data-label="ناخالص" className="money-cell">{Number(p.gross_pay).toLocaleString('fa-IR')}</td>
                    <td data-label="بیمه" className="money-cell">{Number(p.insurance_employee_share).toLocaleString('fa-IR')}</td>
                    <td data-label="مالیات" className="money-cell">{Number(p.tax_amount).toLocaleString('fa-IR')}</td>
                    <td data-label="خالص پرداختی" className="money-cell"><strong>{Number(p.net_pay).toLocaleString('fa-IR')}</strong></td>
                    <td className="payslip-action">
                      <button type="button" onClick={() => setOpenPayslip(p)}>
                        <FileText size={13} /> فیش / چاپ
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <Pager page={payslipsPg.page} pageCount={payslipsPg.pageCount} onChange={payslipsPg.setPage} />
        </div>
      )}

      {openPayslip && (
        <PayslipDrawer
          payslip={openPayslip}
          employee={empById.get(openPayslip.employee_id)}
          period={period}
          onClose={() => setOpenPayslip(null)}
        />
      )}
    </div>
  )
}
