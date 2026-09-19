import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createPayrollPeriod,
  downloadPayrollCsv,
  type PayrollExportKind,
  fetchAttendance,
  fetchFactorInputs,
  fetchPayrollFactors,
  fetchPayrollPeriods,
  fetchPayslips,
  generatePayslips,
  saveFactorInputs,
  upsertAttendance,
  type EmployeeRecord,
  type PayrollFactorRecord,
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
 * پرسنل + صدور فیش + لیستِ بیمه. مصرف‌شده در تبِ «کارکرد و صدور فیش».
 */
export function usePayrollRunDraft({ token, employees }: { token: string; employees: EmployeeRecord[] }) {
  const [periods, setPeriods] = useState<PayrollPeriodRecord[]>([])
  const [selectedPeriodId, setSelectedPeriodId] = useState('')

  const today = isoToJalali(todayIso())
  const [year, setYear] = useState(today.jy)
  const [month, setMonth] = useState(today.jm)
  const [periodError, setPeriodError] = useState<string | null>(null)

  const [attendance, setAttendance] = useState<Record<string, AttendanceEntry>>({})
  //: `${employee_id}|${factor_id}` → مبلغِ تایپ‌شده. کلیدِ مرکب چون یک کارمند
  //: می‌تواند چند عاملِ متغیر داشته باشد و یک عامل چند کارمند.
  const [factorInputs, setFactorInputs] = useState<Record<string, string>>({})
  const [variableFactors, setVariableFactors] = useState<PayrollFactorRecord[]>([])
  const [inputError, setInputError] = useState<string | null>(null)
  const [payslips, setPayslips] = useState<PayslipRecord[]>([])
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
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

  //: فقط عاملِ **متغیرِ فعال** ورودیِ دوره می‌گیرد. عاملِ قراردادی مبلغش روی
  //: حکم است و سرور هم همین را گارد می‌کند؛ نشان‌دادنش این‌جا فقط کاربر را به
  //: خطای ۴۰۰ می‌رساند.
  useEffect(() => {
    fetchPayrollFactors(token)
      .then((rows) => setVariableFactors(rows.filter((f) => f.kind === 'variable' && f.is_active)))
      .catch(() => setVariableFactors([]))
  }, [token])

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
        const rows = await fetchFactorInputs(token, selectedPeriodId)
        if (cancelled) return
        const inputMap: Record<string, string> = {}
        for (const r of rows) inputMap[`${r.employee_id}|${r.factor_id}`] = r.amount
        setFactorInputs(inputMap)
        setPayslips(await fetchPayslips(token, selectedPeriodId))
      } catch {
        /* خطای بارگذاری نادیده — دوره‌ی خالی */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, selectedPeriodId])

  function setFactorInput(employeeId: string, factorId: string, value: string) {
    setFactorInputs((prev) => ({ ...prev, [`${employeeId}|${factorId}`]: value }))
  }

  /** مبلغِ یک کارمند را ذخیره می‌کند. **فقط همان ردیف** می‌رود، نه کلِ جدول —
   *  وگرنه دو کاربر که هم‌زمان دو نفر را وارد می‌کنند کارِ هم را پاک می‌کردند. */
  async function saveFactorInput(employeeId: string): Promise<boolean> {
    if (!selectedPeriodId) return false
    setInputError(null)
    const rows = variableFactors.map((f) => ({
      employee_id: employeeId,
      factor_id: f.id,
      amount: Number(factorInputs[`${employeeId}|${f.id}`] || 0) || 0,
    }))
    try {
      await saveFactorInputs(token, selectedPeriodId, rows)
      setMessage({ text: 'ورودیِ عوامل ذخیره شد.', kind: 'ok' })
      return true
    } catch (e) {
      setInputError(e instanceof Error ? e.message : 'خطای ناشناخته')
      return false
    }
  }

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
    //: پیش‌تر خطای سرور این‌جا گرفته نمی‌شد و دکمه بی‌صدا هیچ کاری نمی‌کرد.
    try {
      await upsertAttendance(token, {
        employee_id: empId,
        period_id: selectedPeriodId,
        worked_days: Number(entry.worked) || 0,
        absent_days: 30 - (Number(entry.worked) || 0),
        overtime_hours: Number(entry.overtime) || 0,
      })
      setMessage({ text: 'کارکرد ذخیره شد.', kind: 'ok' })
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function generate(): Promise<boolean> {
    setMessage(null)
    try {
      const result = await generatePayslips(token, selectedPeriodId)
      setPayslips(result)
      setMessage({ text: `${result.length.toLocaleString('fa-IR')} فیش حقوقی صادر شد.`, kind: 'ok' })
      return true
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
      return false
    }
  }

  async function downloadCsv(kind: PayrollExportKind) {
    setMessage(null)
    try {
      const { filename, blob } = await downloadPayrollCsv(token, selectedPeriodId, kind)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
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
    variableFactors,
    factorInputs,
    inputError,
    setFactorInput,
    saveFactorInput,
    payslips,
    generate,
    downloadCsv,
    message,
    openPayslip,
    setOpenPayslip,
    empById,
  }
}

export type PayrollRunDraft = ReturnType<typeof usePayrollRunDraft>
