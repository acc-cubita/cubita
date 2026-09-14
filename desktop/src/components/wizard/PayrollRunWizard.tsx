import type { EmployeeRecord } from '../../api'
import type { PayrollRunDraft } from '../../lib/payrollRunDraft'
import { PeriodPicker, AttendanceTable, FactorInputsTable, PayslipResults } from '../PayrollPanel'
import { TaskFlow, type WizardStep } from './TaskFlow'

/**
 * ویزاردِ «کارکرد و صدور فیش» — سه مرحله: دوره ← کارکرد ← صدور فیش.
 * منبعِ داده (draft) از پنل می‌آید تا با جابه‌جایی بین تب‌ها حفظ شود. بدونِ پنلِ کناری
 * چون جدول‌های کارکرد/فیش پهن‌اند و تمامِ عرض را لازم دارند.
 */
export function PayrollRunWizard({ d, employees }: { d: PayrollRunDraft; employees: EmployeeRecord[] }) {
  const steps: WizardStep[] = [
    {
      key: 'period',
      title: 'دوره',
      subtitle: 'یک دوره‌ی حقوقی را انتخاب یا ایجاد کنید.',
      canAdvance: !!d.selectedPeriodId,
      blockHint: 'برای ادامه یک دوره را انتخاب یا ایجاد کنید.',
      body: <PeriodPicker d={d} />,
    },
    {
      key: 'attendance',
      title: 'کارکرد',
      subtitle: 'روزِ کارکرد، اضافه‌کار، و مبلغِ عواملِ متغیرِ همین دوره را وارد و ذخیره کنید.',
      body:
        employees.length === 0 ? (
          <p className="hint">پرسنلی ثبت نشده — ابتدا از تبِ «پرسنل و احکام» کارمند اضافه کنید.</p>
        ) : (
          <>
            <AttendanceTable d={d} employees={employees} />
            <h3 style={{ marginTop: 16 }}>ورودیِ عوامل این دوره</h3>
            <FactorInputsTable d={d} employees={employees} />
          </>
        ),
    },
    {
      key: 'payslips',
      title: 'صدور فیش',
      subtitle: 'با «صدور فیش‌های حقوقی» فیش‌ها ساخته می‌شوند؛ سپس می‌توانید لیستِ بیمه را بگیرید یا هر فیش را چاپ کنید.',
      body: <PayslipResults d={d} showGenerate={false} />,
    },
  ]

  return (
    <TaskFlow
      title="کارکرد و صدور فیش"
      steps={steps}
      submitLabel="صدور فیش‌های حقوقی این دوره"
      onSubmit={() => void d.generate()}
    />
  )
}
