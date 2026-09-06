import { useCallback, useEffect, useState } from 'react'
import { Users, Save, CalendarPlus, Download, FileSignature, FileText, Gift, Settings } from 'lucide-react'
import { Tabs } from './Tabs'
import { BenefitsPanel } from './BenefitsPanel'
import { Pager, usePagination } from './Pager'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { PayrollSettingsPanel } from './PayrollSettingsPanel'
import { PayslipDrawer } from './PayslipDrawer'
import { formatJalali, JALALI_MONTH_NAMES } from '../lib/jalali'
import type { PageKey } from '../lib/navModel'
import { fetchEmployees, type EmployeeRecord } from '../api'
import { useTheme } from '../lib/theme'
import { useEmployeeDraft } from '../lib/employeeDraft'
import { usePayrollRunDraft, type PayrollRunDraft } from '../lib/payrollRunDraft'
import { EmployeeWizard } from './wizard/EmployeeWizard'
import { PayrollRunWizard } from './wizard/PayrollRunWizard'

// دوره‌ی حقوق شمسی است: ماه‌ها فروردین..اسفند (JALALI_MONTH_NAMES)

export function PayrollPanel({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey) => void
}) {
  const guided = useTheme().theme.content === 'guided'
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const refreshEmployees = useCallback(async () => {
    setEmployees(await fetchEmployees(token))
  }, [token])
  useEffect(() => {
    void refreshEmployees()
  }, [refreshEmployees])

  // فرایندِ کارکرد/فیش (دوره‌ها/کارکرد/فیش) — در سطحِ پنل نگه داشته می‌شود تا با جابه‌جایی
  // بین تب‌ها داده از دست نرود؛ هم پنلِ کلاسیک و هم ویزارد همین یک منبع را مصرف می‌کنند.
  const run = usePayrollRunDraft({ token, employees })

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
              {guided ? (
                <EmployeeWizard token={token} onCreated={refreshEmployees} />
              ) : (
                <EmployeeFormClassic token={token} onCreated={refreshEmployees} />
              )}
              <EmployeeList employees={employees} />
              <ContractPointer onNavigate={onNavigate} />
            </>
          ),
        },
        {
          key: 'run',
          label: 'کارکرد و صدور فیش',
          icon: CalendarPlus,
          content: guided ? (
            <PayrollRunWizard d={run} employees={employees} />
          ) : (
            <ClassicRun d={run} employees={employees} />
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
          content: <PayrollSettingsPanel token={token} onSaved={() => void refreshEmployees()} />,
        },
      ]}
    />
  )
}

/* ───────────────────────── پرسنل و احکام (کلاسیک) ───────────────────────── */

function EmployeeFormClassic({ token, onCreated }: { token: string; onCreated: () => void }) {
  const d = useEmployeeDraft({ token, onCreated })
  return (
    <form
      className="invoice-form"
      onSubmit={(e) => {
        e.preventDefault()
        void d.submit()
      }}
    >
      <h3>افزودن پرسنل</h3>
      <label>
        نام
        <input type="text" value={d.firstName} onChange={(e) => d.setFirstName(e.target.value)} />
      </label>
      <label>
        نام‌خانوادگی
        <input type="text" value={d.lastName} onChange={(e) => d.setLastName(e.target.value)} />
      </label>
      <label>
        کد ملی
        <input type="text" value={d.nationalId} onChange={(e) => d.setNationalId(e.target.value)} />
      </label>
      <label>
        تاریخ استخدام
        <JalaliDatePicker value={d.hireDate} onChange={d.setHireDate} />
      </label>
      <div className="invoice-form-footer">
        <button type="submit" className="btn-primary" disabled={d.submitting}><Save size={14} /> ثبت پرسنل</button>
      </div>
      {d.message && <div className="hint">{d.message}</div>}
    </form>
  )
}

export function EmployeeList({ employees }: { employees: EmployeeRecord[] }) {
  const pg = usePagination(employees, 10)
  if (employees.length === 0) return <EmptyState icon={Users} text="پرسنلی ثبت نشده." />
  return (
    <div className="entity-table-wrap">
      <div className="table-scroll">
        <table className="entity-table payroll-emp-table cards-on-mobile">
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
                <td className="entity-name" data-label="نام">
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
      </div>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

/**
 * جای حکمِ حقوقی این‌جا نیست — «قرارداد جدید» است.
 *
 * تا امروز یک فرمِ کوتاهِ «ثبت حکم حقوقی» همین‌جا بود که فقط کارمند، تاریخ اجرا و
 * چهار مبلغ می‌گرفت و به همان `/api/salary-contracts` می‌فرستاد که فرمِ کاملِ
 * قرارداد می‌فرستد. دو نمای یک داده بود، و بدتر: چون نوعِ قرارداد پیش‌فرض
 * «استخدام» است، حکمی که از این‌جا ثبت می‌شد **جای استخدامِ واقعی را می‌گرفت** و
 * فرمِ کامل بعد از آن فقط «اصلاح قرارداد» می‌توانست بزند — بی‌آنکه شماره، نوع
 * استخدام، محل خدمت، شغل و اطلاعات بیمه و مالیات هیچ‌وقت پر شده باشند.
 */
function ContractPointer({ onNavigate }: { onNavigate?: (page: PageKey) => void }) {
  return (
    <section className="fy-note">
      <FileSignature size={16} />
      <div>
        قرارداد و حکمِ حقوقی در «قرارداد جدید» ثبت می‌شود — آن‌جا نوعِ قرارداد، سه
        تاریخ، اطلاعات استخدامی، عوامل حقوق و مزایا و اطلاعات بیمه و مالیات هم پرسیده
        می‌شوند.
        {onNavigate && (
          <>
            {' '}
            <button type="button" onClick={() => onNavigate('contractnew')}>قرارداد جدید</button>
          </>
        )}
      </div>
    </section>
  )
}

/* ───────────────────────── کارکرد و صدور فیش (مشترک) ───────────────────────── */

/** انتخاب/ساختِ دوره‌ی حقوقی — مشترکِ پنلِ کلاسیک و مرحله‌ی اولِ ویزارد. */
export function PeriodPicker({ d }: { d: PayrollRunDraft }) {
  return (
    <div className="invoice-form">
      <h3>دوره‌های حقوقی</h3>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void d.createPeriod()
        }}
        className="check-actions"
      >
        <NumberInput group={false} value={d.year} onChange={(v) => d.setYear(Number(v))} style={{ width: 90 }} />
        <select value={d.month} onChange={(e) => d.setMonth(Number(e.target.value))}>
          {JALALI_MONTH_NAMES.map((name, idx) => (
            <option key={idx} value={idx + 1}>{name}</option>
          ))}
        </select>
        <button type="submit"><CalendarPlus size={14} /> ایجاد دوره جدید</button>
      </form>
      {d.periodError && <div className="error">{d.periodError}</div>}
      <div className="check-actions" style={{ marginTop: 8, flexWrap: 'wrap' }}>
        {d.periods.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => d.setSelectedPeriodId(p.id)}
            style={{ fontWeight: p.id === d.selectedPeriodId ? 700 : 400 }}
          >
            {p.year}/{String(p.month).padStart(2, '0')} ({p.status === 'finalized' ? 'نهایی‌شده' : 'پیش‌نویس'})
          </button>
        ))}
      </div>
    </div>
  )
}

/** جدولِ کارکردِ همه‌ی پرسنل (روز کارکرد + اضافه‌کار) — مشترکِ پنلِ کلاسیک و مرحله‌ی دومِ ویزارد. */
export function AttendanceTable({ d, employees }: { d: PayrollRunDraft; employees: EmployeeRecord[] }) {
  return (
    <div className="entity-table-wrap">
      <div className="table-scroll">
        <table className="entity-table payroll-attend-table cards-on-mobile">
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
                <td className="entity-name" data-label="کارمند">{emp.first_name} {emp.last_name}</td>
                <td data-label="روز کارکرد">
                  <NumberInput value={d.attendance[emp.id]?.worked ?? '30'} onChange={(v) => d.setAttendanceField(emp.id, { worked: v })} />
                </td>
                <td data-label="ساعت اضافه‌کار">
                  <NumberInput value={d.attendance[emp.id]?.overtime ?? '0'} onChange={(v) => d.setAttendanceField(emp.id, { overtime: v })} />
                </td>
                <td className="attend-action card-actions">
                  <button type="button" onClick={() => void d.saveAttendance(emp.id)}><Save size={13} /> ذخیره کارکرد</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** نتیجه‌ی صدور فیش (دکمه‌ی صدور اختیاری + لیستِ بیمه + جدولِ فیش‌ها + کشوی چاپ) — مشترک. */
export function PayslipResults({ d, showGenerate = true }: { d: PayrollRunDraft; showGenerate?: boolean }) {
  const pg = usePagination(d.payslips, 10)
  return (
    <>
      {(showGenerate || d.payslips.length > 0) && (
        <div className="invoice-form-footer">
          {showGenerate && (
            <button type="button" className="btn-primary" onClick={() => void d.generate()}>
              صدور فیش‌های حقوقی این دوره
            </button>
          )}
          {/* سه خروجیِ همان دوره: بیمه برای تأمین اجتماعی، مالیات برای سازمان
              مالیاتی، و پرداخت برای بانک. هر سه از عددِ *همان فیش* می‌خوانند، نه
              محاسبه‌ی دوباره — وگرنه فایلِ اداره و فیشِ کارمند دو تا می‌شوند. */}
          {d.payslips.length > 0 && (
            <>
              <button type="button" onClick={() => void d.downloadCsv('insurance-list')}>
                <Download size={13} /> لیست بیمه (CSV)
              </button>
              <button type="button" onClick={() => void d.downloadCsv('tax-list')}>
                <Download size={13} /> فایل مالیات (CSV)
              </button>
              <button type="button" onClick={() => void d.downloadCsv('payment-list')}>
                <Download size={13} /> دیسکت پرداخت (CSV)
              </button>
            </>
          )}
        </div>
      )}
      {d.payslips.length > 0 && (
        <p className="hint">
          قالبِ ستون‌های فایلِ بیمه و مالیات عمومی است؛ پیش از ارسالِ رسمی، با آخرین
          مشخصاتِ سامانه‌ی مربوطه تطبیقش دهید. دیسکتِ پرداخت شماره‌حسابِ کارمند را از
          پرونده‌اش می‌خواند — کارمندِ بی‌شماره‌حساب حذف نمی‌شود، ستونش خالی می‌آید تا
          ببینیدش.
        </p>
      )}
      {d.message && <div className="hint">{d.message}</div>}

      {d.payslips.length > 0 && (
        <div className="entity-table-wrap">
          <div className="table-scroll">
            <table className="entity-table payslip-table cards-on-mobile">
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
                {pg.pageItems.map((p) => {
                  const emp = d.empById.get(p.employee_id)
                  return (
                    <tr key={p.id}>
                      <td data-label="شماره">{p.number}</td>
                      <td className="entity-name" data-label="کارمند">{emp ? `${emp.first_name} ${emp.last_name}` : '—'}</td>
                      <td data-label="ناخالص" className="money-cell">{Number(p.gross_pay).toLocaleString('fa-IR')}</td>
                      <td data-label="بیمه" className="money-cell">{Number(p.insurance_employee_share).toLocaleString('fa-IR')}</td>
                      <td data-label="مالیات" className="money-cell">{Number(p.tax_amount).toLocaleString('fa-IR')}</td>
                      <td data-label="خالص پرداختی" className="money-cell"><strong>{Number(p.net_pay).toLocaleString('fa-IR')}</strong></td>
                      <td className="payslip-action card-actions">
                        <button type="button" onClick={() => d.setOpenPayslip(p)}><FileText size={13} /> فیش / چاپ</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}

      {d.openPayslip && (
        <PayslipDrawer
          payslip={d.openPayslip}
          employee={d.empById.get(d.openPayslip.employee_id)}
          period={d.selectedPeriod}
          onClose={() => d.setOpenPayslip(null)}
        />
      )}
    </>
  )
}

function ClassicRun({ d, employees }: { d: PayrollRunDraft; employees: EmployeeRecord[] }) {
  return (
    <>
      <PeriodPicker d={d} />
      {d.selectedPeriodId ? (
        <div className="invoice-form">
          <h3>کارکرد و صدور فیش برای دوره‌ی انتخاب‌شده</h3>
          <AttendanceTable d={d} employees={employees} />
          <PayslipResults d={d} />
        </div>
      ) : (
        <p className="hint">یک دوره را انتخاب یا ایجاد کنید تا جدولِ کارکرد و صدورِ فیش نمایش داده شود.</p>
      )}
    </>
  )
}
