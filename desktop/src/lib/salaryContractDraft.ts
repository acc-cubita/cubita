import { useState } from 'react'
import { createSalaryContract } from '../api'
import { todayIso } from './jalali'

/** منطقِ مشترکِ «ثبت حکم حقوقی» — مصرف‌شده در فرمِ کلاسیک و ویزارد. */
export function useSalaryContractDraft({ token, onCreated }: { token: string; onCreated?: () => void }) {
  const [employeeId, setEmployeeId] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState(todayIso())
  const [baseSalary, setBaseSalary] = useState('')
  const [housing, setHousing] = useState('0')
  const [food, setFood] = useState('0')
  const [other, setOther] = useState('0')
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const valid = !!employeeId && Number(baseSalary) > 0

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!valid) {
      setMessage('کارمند و حقوق پایه (بزرگ‌تر از صفر) الزامی است.')
      return false
    }
    setSubmitting(true)
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
      setMessage('حکم حقوقی ثبت شد.')
      onCreated?.()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  // مجموعِ حقوق و مزایا برای پیش‌نمایش
  const grossEstimate =
    (Number(baseSalary) || 0) + (Number(housing) || 0) + (Number(food) || 0) + (Number(other) || 0)

  return {
    employeeId,
    setEmployeeId,
    effectiveFrom,
    setEffectiveFrom,
    baseSalary,
    setBaseSalary,
    housing,
    setHousing,
    food,
    setFood,
    other,
    setOther,
    message,
    submitting,
    valid,
    grossEstimate,
    submit,
  }
}

export type SalaryContractDraft = ReturnType<typeof useSalaryContractDraft>
