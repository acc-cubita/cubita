import { useState } from 'react'
import { createEmployee } from '../api'
import { todayIso } from './jalali'

/** منطقِ مشترکِ «افزودن پرسنل» — مصرف‌شده در فرمِ کلاسیک و ویزارد. */
export function useEmployeeDraft({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [nationalId, setNationalId] = useState('')
  const [hireDate, setHireDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const valid = !!firstName && !!lastName && !!nationalId

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!valid) {
      setMessage('نام، نام‌خانوادگی و کد ملی الزامی است.')
      return false
    }
    setSubmitting(true)
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
      setMessage('کارمند ثبت شد.')
      onCreated()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    firstName,
    setFirstName,
    lastName,
    setLastName,
    nationalId,
    setNationalId,
    hireDate,
    setHireDate,
    message,
    submitting,
    valid,
    submit,
  }
}

export type EmployeeDraft = ReturnType<typeof useEmployeeDraft>
