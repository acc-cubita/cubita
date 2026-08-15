import { useState } from 'react'
import type { EmployeeDraft } from '../../lib/employeeDraft'
import { useEmployeeDraft } from '../../lib/employeeDraft'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { formatJalali } from '../../lib/jalali'
import { TaskFlow, type WizardStep } from './TaskFlow'

/** ویزاردِ «افزودن پرسنل» — هویت ← استخدام + پیش‌نمایشِ زنده. */
export function EmployeeWizard({ token, onCreated }: { token: string; onCreated: () => void }) {
  const d = useEmployeeDraft({ token, onCreated })
  const [resetTick, setResetTick] = useState(0)

  const steps: WizardStep[] = [
    {
      key: 'identity',
      title: 'هویت',
      subtitle: 'نام، نام‌خانوادگی و کد ملیِ کارمند را وارد کنید.',
      canAdvance: d.valid,
      blockHint: 'نام، نام‌خانوادگی و کد ملی الزامی است.',
      body: (
        <div className="invoice-form">
          <label>نام<input type="text" value={d.firstName} onChange={(e) => d.setFirstName(e.target.value)} /></label>
          <label>نام‌خانوادگی<input type="text" value={d.lastName} onChange={(e) => d.setLastName(e.target.value)} /></label>
          <label>کد ملی<input type="text" value={d.nationalId} onChange={(e) => d.setNationalId(e.target.value)} /></label>
        </div>
      ),
    },
    {
      key: 'hire',
      title: 'استخدام',
      subtitle: 'تاریخِ استخدام را مشخص کنید، بعد ثبت را بزنید.',
      body: (
        <div className="invoice-form">
          <label>تاریخ استخدام<JalaliDatePicker value={d.hireDate} onChange={d.setHireDate} /></label>
        </div>
      ),
    },
  ]

  return (
    <TaskFlow
      title="افزودن پرسنل"
      steps={steps}
      submitLabel="ثبت پرسنل"
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

function LivePreview({ d }: { d: EmployeeDraft }) {
  const name = `${d.firstName} ${d.lastName}`.trim()
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ پرسنل</p>
      <div className="live-preview-row"><span>نام</span><strong>{name || '—'}</strong></div>
      <div className="live-preview-row"><span>کد ملی</span><strong>{d.nationalId || '—'}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>تاریخ استخدام</span><strong>{d.hireDate ? formatJalali(d.hireDate) : '—'}</strong></div>
    </div>
  )
}
