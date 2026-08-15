import { useState } from 'react'
import type { EmployeeRecord } from '../../api'
import type { SalaryContractDraft } from '../../lib/salaryContractDraft'
import { useSalaryContractDraft } from '../../lib/salaryContractDraft'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** ویزاردِ «ثبت حکم حقوقی» — کارمند و تاریخ ← حقوق و مزایا + پیش‌نمایشِ زنده. */
export function SalaryContractWizard({ token, employees }: { token: string; employees: EmployeeRecord[] }) {
  const d = useSalaryContractDraft({ token })
  const [resetTick, setResetTick] = useState(0)

  const steps: WizardStep[] = [
    {
      key: 'who',
      title: 'کارمند و تاریخ',
      subtitle: 'کارمند و تاریخِ اجرای حکم را مشخص کنید.',
      canAdvance: !!d.employeeId,
      blockHint: 'یک کارمند را انتخاب کنید.',
      body: (
        <div className="invoice-form">
          <label>
            کارمند
            <select value={d.employeeId} onChange={(e) => d.setEmployeeId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {employees.map((emp) => (<option key={emp.id} value={emp.id}>{emp.first_name} {emp.last_name}</option>))}
            </select>
          </label>
          <label>
            تاریخ اجرا
            <JalaliDatePicker value={d.effectiveFrom} onChange={d.setEffectiveFrom} />
          </label>
        </div>
      ),
    },
    {
      key: 'pay',
      title: 'حقوق و مزایا',
      subtitle: 'حقوق پایه و مزایا را وارد کنید، بعد ثبت را بزنید.',
      canAdvance: Number(d.baseSalary) > 0,
      blockHint: 'حقوق پایه (بزرگ‌تر از صفر) الزامی است.',
      body: (
        <div className="invoice-form">
          <label>حقوق پایه<NumberInput value={d.baseSalary} onChange={d.setBaseSalary} /></label>
          <label>حق مسکن<NumberInput value={d.housing} onChange={d.setHousing} /></label>
          <label>بن خواربار<NumberInput value={d.food} onChange={d.setFood} /></label>
          <label>سایر مزایا<NumberInput value={d.other} onChange={d.setOther} /></label>
        </div>
      ),
    },
  ]

  return (
    <TaskFlow
      title="ثبت حکم حقوقی"
      steps={steps}
      submitLabel="ثبت حکم"
      submitting={d.submitting}
      message={d.message}
      resetKey={resetTick}
      preview={<LivePreview d={d} employees={employees} />}
      onSubmit={() => {
        void d.submit().then((ok) => {
          if (ok) setResetTick((t) => t + 1)
        })
      }}
    />
  )
}

function LivePreview({ d, employees }: { d: SalaryContractDraft; employees: EmployeeRecord[] }) {
  const emp = employees.find((e) => e.id === d.employeeId)
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ حکم</p>
      <div className="live-preview-row"><span>کارمند</span><strong>{emp ? `${emp.first_name} ${emp.last_name}` : '—'}</strong></div>
      <div className="live-preview-row"><span>حقوق پایه</span><strong>{fa(Number(d.baseSalary) || 0)}</strong></div>
      <div className="live-preview-row"><span>مزایا</span><strong>{fa((Number(d.housing) || 0) + (Number(d.food) || 0) + (Number(d.other) || 0))}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>ناخالصِ حکم</span><strong>{fa(d.grossEstimate)}</strong></div>
    </div>
  )
}
