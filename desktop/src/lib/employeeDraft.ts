import { useState } from 'react'
import { createEmployee } from '../api'
import { todayIso } from './jalali'

/** منطقِ «افزودن پرسنل» (تبِ «پرسنل و احکام»). */
export function useEmployeeDraft({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [nationalId, setNationalId] = useState('')
  const [hireDate, setHireDate] = useState(todayIso())
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const valid = !!firstName && !!lastName && !!nationalId

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!valid) {
      setMessage({ text: 'نام، نام‌خانوادگی و کد ملی الزامی است.', kind: 'err' })
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
      setMessage({ text: `«${firstName} ${lastName}» ثبت شد.`, kind: 'ok' })
      onCreated()
      return true
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
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
    setMessage,
    submitting,
    valid,
    submit,
  }
}

export type EmployeeDraft = ReturnType<typeof useEmployeeDraft>
