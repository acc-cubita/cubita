import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createPayrollPeriod,
  downloadInsuranceListCsv,
  fetchAttendance,
  fetchPayrollPeriods,
  fetchPayslips,
  generatePayslips,
  upsertAttendance,
  type EmployeeRecord,
  type PayrollPeriodRecord,
  type PayslipRecord,
} from '../api'
import { isoToJalali, todayIso } from './jalali'

interface AttendanceEntry {
  worked: string
  overtime: string
}

/**
 * منطقِ مشترکِ فرایندِ «کارکرد و صدور فیش» — دوره (انتخاب/ساخت) + جدولِ کارکردِ همه‌ی
 * پرسنل + صدور فیش + لیستِ بیمه. مصرف‌شده در پنلِ کلاسیک و ویزاردِ سه‌مرحله‌ای.
 */
export function usePayrollRunDraft({ token, employees }: { token: string; employees: EmployeeRecord[] }) {
  const [periods, setPeriods] = useState<PayrollPeriodRecord[]>([])
  const [selectedPeriodId, setSelectedPeriodId] = useState('')

  const today = isoToJalali(todayIso())
  const [year, setYear] = useState(today.jy)
  const [month, setMonth] = useState(today.jm)
  const [periodError, setPeriodError] = useState<string | null>(null)

  const [attendance, setAttendance] = useState<Record<string, AttendanceEntry>>({})
  const [payslips, setPayslips] = useState<PayslipRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [openPayslip, setOpenPayslip] = useState<PayslipRecord | null>(null)

  const empById = useMemo(() => new Map(employees.map((e) => [e.id, e])), [employees])
  const selectedPeriod = periods.find((p) => p.id === selectedPeriodId)

  const refreshPeriods = useCallback(async () => {
    try {
      setPeriods(await fetchPayrollPeriods(token))
    } catch {
      // فهرستِ دوره‌ها نمایشی است؛ خطایش نباید مانعِ کار شود.
    }
  }, [token])

  useEffect(() => {
    void refreshPeriods()
  }, [refreshPeriods])

  // با تغییرِ دوره‌ی انتخابی، کارکرد و فیش‌های همان دوره خوانده می‌شوند.
  useEffect(() => {
    if (!selectedPeriodId) {
      setAttendance({})
      setPayslips([])
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const existing = await fetchAttendance(token, selectedPeriodId)
        if (cancelled) return
        const map: Record<string, AttendanceEntry> = {}
        for (const a of existing) map[a.employee_id] = { worked: a.worked_days, overtime: a.overtime_hours }
        setAttendance(map)
        setPayslips(await fetchPayslips(token, selectedPeriodId))
      } catch {
        /* خطای بارگذاری نادیده — دوره‌ی خالی */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, selectedPeriodId])

  async function createPeriod(): Promise<boolean> {
    setPeriodError(null)
    try {
      const period = await createPayrollPeriod(token, { year, month })
      await refreshPeriods()
      setSelectedPeriodId(period.id)
      return true
    } catch (err) {
      setPeriodError(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    }
  }

  function setAttendanceField(empId: string, patch: Partial<AttendanceEntry>) {
    setAttendance((prev) => ({
      ...prev,
      [empId]: { worked: prev[empId]?.worked ?? '30', overtime: prev[empId]?.overtime ?? '0', ...patch },
    }))
  }

  async function saveAttendance(empId: string) {
    const entry = attendance[empId] ?? { worked: '30', overtime: '0' }
    await upsertAttendance(token, {
      employee_id: empId,
      period_id: selectedPeriodId,
      worked_days: Number(entry.worked) || 0,
      absent_days: 30 - (Number(entry.worked) || 0),
      overtime_hours: Number(entry.overtime) || 0,
    })
    setMessage('کارکرد ذخیره شد.')
  }

  async function generate(): Promise<boolean> {
    setMessage(null)
    try {
      const result = await generatePayslips(token, selectedPeriodId)
      setPayslips(result)
      setMessage(`${result.length} فیش حقوقی صادر شد.`)
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    }
  }

  async function downloadInsurance() {
    setMessage(null)
    try {
      const { filename, blob } = await downloadInsuranceListCsv(token, selectedPeriodId)
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

  return {
    periods,
    selectedPeriodId,
    setSelectedPeriodId,
    selectedPeriod,
    year,
    setYear,
    month,
    setMonth,
    periodError,
    createPeriod,
    attendance,
    setAttendanceField,
    saveAttendance,
    payslips,
    generate,
    downloadInsurance,
    message,
    openPayslip,
    setOpenPayslip,
    empById,
  }
}

export type PayrollRunDraft = ReturnType<typeof usePayrollRunDraft>
