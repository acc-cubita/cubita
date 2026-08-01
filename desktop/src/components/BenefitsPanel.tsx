import { useCallback, useEffect, useState } from 'react'
import { Gift, Save, CalendarPlus, Coins, Wallet } from 'lucide-react'
import {
  fetchBenefits,
  fetchEmployees,
  issueEidi,
  issueLeavePayout,
  issueSeverance,
  recordLeave,
  setBenefitSettings,
  type BenefitsReport,
  type EmployeeRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { isoToJalali, todayIso } from '../lib/jalali'

const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
const faDays = (v: string | number) => Number(v).toLocaleString('fa-IR')

export function BenefitsPanel({ token }: { token: string }) {
  const [year, setYear] = useState(isoToJalali(todayIso()).jy)
  const [report, setReport] = useState<BenefitsReport | null>(null)
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // تنظیمِ سریعِ سقف عیدی و روز مرخصی
  const [minWage, setMinWage] = useState('')
  const [leaveDays, setLeaveDays] = useState('')

  // ثبت مرخصی
  const [leaveEmp, setLeaveEmp] = useState('')
  const [leaveDate, setLeaveDate] = useState(todayIso())
  const [leaveTaken, setLeaveTaken] = useState('')
  const [leaveNote, setLeaveNote] = useState('')

  const load = useCallback(async () => {
    setError(null)
    try {
      const r = await fetchBenefits(token, year)
      setReport(r)
      setMinWage(Number(r.min_base_wage) ? String(Number(r.min_base_wage)) : '')
      setLeaveDays(String(r.annual_leave_days))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token, year])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    fetchEmployees(token).then(setEmployees).catch(() => setEmployees([]))
  }, [token])

  async function saveSettings() {
    setMessage(null)
    try {
      await setBenefitSettings(token, {
        year,
        min_base_wage: Number(minWage) || 0,
        annual_leave_days: Number(leaveDays) || 26,
      })
      setMessage('تنظیمات مزایا ذخیره شد.')
      await load()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleIssueEidi() {
    setMessage(null)
    try {
      const r = await issueEidi(token, year)
      setMessage(`عیدی سال ${year} صادر شد — سند شماره ${r.journal_entry_number ?? '—'} به مبلغ ${fa(r.amount)}.`)
      await load()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleSeverance(empId: string) {
    setMessage(null)
    try {
      const r = await issueSeverance(token, empId)
      setMessage(`سنوات صادر شد — سند شماره ${r.journal_entry_number ?? '—'} به مبلغ ${fa(r.amount)}.`)
      await load()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleLeavePayout(empId: string) {
    setMessage(null)
    try {
      const r = await issueLeavePayout(token, empId, year)
      setMessage(`بازخرید مرخصی صادر شد — سند شماره ${r.journal_entry_number ?? '—'} به مبلغ ${fa(r.amount)}.`)
      await load()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleRecordLeave(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!leaveEmp || !(Number(leaveTaken) > 0)) {
      setMessage('کارمند و تعداد روز مرخصی الزامی است.')
      return
    }
    try {
      await recordLeave(token, {
        employee_id: leaveEmp,
        leave_date: leaveDate,
        days: Number(leaveTaken),
        note: leaveNote,
      })
      setLeaveTaken('')
      setLeaveNote('')
      setMessage('مرخصی ثبت شد.')
      await load()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard
      icon={Gift}
      title="مزایا — عیدی، سنوات و مرخصی"
      description="محاسبه‌ی عیدیِ پایان سال، سنوات پایان خدمت و ماندهٔ مرخصیِ هر کارمند، و صدور سند برای هرکدام."
    >
      <div className="benefit-toolbar">
        <label>
          سال (شمسی)
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value) || year)}
            style={{ width: 100 }}
          />
        </label>
        <label>
          حداقل حقوق ماهانه (سقف عیدی)
          <input type="number" min="0" value={minWage} onChange={(e) => setMinWage(e.target.value)} placeholder="۰ = بدون سقف" />
        </label>
        <label>
          روزهای مرخصی سالانه
          <input type="number" min="0" value={leaveDays} onChange={(e) => setLeaveDays(e.target.value)} />
        </label>
        <button type="button" onClick={() => void saveSettings()}>
          <Save size={13} /> ذخیره تنظیمات
        </button>
        <button type="button" className="btn-primary" onClick={() => void handleIssueEidi()}>
          <Gift size={13} /> صدور عیدی سال {year}
        </button>
      </div>

      {message && <div className="hint">{message}</div>}
      {error && <div className="error">{error}</div>}

      {!report ? (
        <p className="hint">در حال بارگذاری…</p>
      ) : report.rows.length === 0 ? (
        <EmptyState icon={Gift} text="برای این سال کارمندی با حکم حقوقی یافت نشد." />
      ) : (
        <div className="entity-table-wrap">
          <table className="entity-table benefits-table">
            <thead>
              <tr>
                <th>کارمند</th>
                <th>حقوق پایه</th>
                <th>عیدی</th>
                <th>سنوات تا امروز</th>
                <th>ماندهٔ مرخصی (روز)</th>
                <th>طلب مرخصی</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.employee_id}>
                  <td className="entity-name">{r.employee_name}</td>
                  <td data-label="حقوق پایه" className="money-cell">{fa(r.base_salary)}</td>
                  <td data-label="عیدی" className="money-cell">{fa(r.eidi)}</td>
                  <td data-label="سنوات تا امروز" className="money-cell">{fa(r.severance)}</td>
                  <td data-label="ماندهٔ مرخصی (روز)" className={Number(r.leave_remaining) < 0 ? 'text-danger' : ''}>{faDays(r.leave_remaining)}</td>
                  <td data-label="طلب مرخصی" className="money-cell">{fa(r.leave_value)}</td>
                  <td className="benefits-action">
                    <div className="row-actions">
                      <button type="button" onClick={() => void handleSeverance(r.employee_id)} title="صدور سنوات">
                        <Coins size={13} /> سنوات
                      </button>
                      <button type="button" onClick={() => void handleLeavePayout(r.employee_id)} title="بازخرید مرخصی">
                        <Wallet size={13} /> مرخصی
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td className="entity-name">جمع</td>
                <td data-label="حقوق پایه"></td>
                <td data-label="عیدی" className="money-cell">{fa(report.total_eidi)}</td>
                <td data-label="سنوات تا امروز" className="money-cell">{fa(report.total_severance)}</td>
                <td data-label="ماندهٔ مرخصی (روز)"></td>
                <td data-label="طلب مرخصی" className="money-cell">{fa(report.total_leave_value)}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <h3 className="panel-subhead"><CalendarPlus size={15} /> ثبت مرخصیِ استفاده‌شده</h3>
      <form className="benefit-toolbar" onSubmit={handleRecordLeave}>
        <label>
          کارمند
          <select value={leaveEmp} onChange={(e) => setLeaveEmp(e.target.value)}>
            <option value="">— انتخاب —</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.first_name} {e.last_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={leaveDate} onChange={setLeaveDate} />
        </label>
        <label>
          تعداد روز
          <input type="number" min="0" step="any" value={leaveTaken} onChange={(e) => setLeaveTaken(e.target.value)} style={{ width: 90 }} />
        </label>
        <label>
          توضیح
          <input type="text" value={leaveNote} onChange={(e) => setLeaveNote(e.target.value)} />
        </label>
        <button type="submit" className="btn-primary">
          <CalendarPlus size={13} /> ثبت مرخصی
        </button>
      </form>
    </SectionCard>
  )
}
