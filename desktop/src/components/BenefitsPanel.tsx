import { useCallback, useEffect, useState } from 'react'
import { CalendarPlus, Coins, Gift, Save, SlidersHorizontal, Wallet } from 'lucide-react'
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
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ActionBar, FormField, FormGrid, FormStatus } from './form/FormKit'
import { firstMissing } from './form/firstMissing'
import { isoToJalali, todayIso } from '../lib/jalali'
import type { Msg } from '../pages/accounting/kit'

const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
const faDays = (v: string | number) => Number(v).toLocaleString('fa-IR')
const faYear = (y: number) => y.toLocaleString('fa-IR', { useGrouping: false })
const faDoc = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('fa-IR'))
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

/**
 * «مزایا» — عیدیِ پایان سال، سنوات و مرخصی.
 *
 * سه کارت: تنظیمِ سال (سقفِ عیدی و روزهای مرخصی)، جدولِ مزایای هر کارمند با صدورِ سندِ
 * سنوات/مرخصی در همان ردیف، و ثبتِ مرخصیِ استفاده‌شده. کارِ اصلیِ صفحه — صدورِ عیدیِ
 * سال — در نوارِ چسبیده‌ی پایین است، کنارِ ذخیره‌ی تنظیمات.
 */
export function BenefitsPanel({ token }: { token: string }) {
  const [year, setYear] = useState(isoToJalali(todayIso()).jy)
  const [report, setReport] = useState<BenefitsReport | null>(null)
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [msg, setMsg] = useState<Msg>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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
      setError(errText(err))
    }
  }, [token, year])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    fetchEmployees(token).then(setEmployees).catch(() => setEmployees([]))
  }, [token])

  /** هر کنشِ این صفحه یک شکل دارد: پیام پاک، کار، پیامِ نتیجه، بارگذاریِ دوباره. */
  async function act(run: () => Promise<string>) {
    setMsg(null)
    setBusy(true)
    try {
      setMsg({ text: await run(), kind: 'ok' })
      await load()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const saveSettings = () =>
    act(async () => {
      await setBenefitSettings(token, {
        year,
        min_base_wage: Number(minWage) || 0,
        annual_leave_days: Number(leaveDays) || 26,
      })
      return `تنظیماتِ مزایای سال ${faYear(year)} ذخیره شد.`
    })

  const handleIssueEidi = () =>
    act(async () => {
      const r = await issueEidi(token, year)
      return `عیدی سال ${faYear(year)} صادر شد — سند شماره ${faDoc(r.journal_entry_number)} به مبلغ ${fa(r.amount)} ریال.`
    })

  const handleSeverance = (empId: string) =>
    act(async () => {
      const r = await issueSeverance(token, empId)
      return `سنوات صادر شد — سند شماره ${faDoc(r.journal_entry_number)} به مبلغ ${fa(r.amount)} ریال.`
    })

  const handleLeavePayout = (empId: string) =>
    act(async () => {
      const r = await issueLeavePayout(token, empId, year)
      return `بازخرید مرخصی صادر شد — سند شماره ${faDoc(r.journal_entry_number)} به مبلغ ${fa(r.amount)} ریال.`
    })

  function handleRecordLeave(e: React.FormEvent) {
    e.preventDefault()
    const missing = firstMissing([
      [leaveEmp, 'lv-employee', 'کارمند را انتخاب کنید.'],
      [Number(leaveTaken) > 0, 'lv-days', 'تعدادِ روزِ مرخصی را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
    void act(async () => {
      await recordLeave(token, {
        employee_id: leaveEmp,
        leave_date: leaveDate,
        days: Number(leaveTaken),
        note: leaveNote,
      })
      setLeaveTaken('')
      setLeaveNote('')
      return 'مرخصی ثبت شد.'
    })
  }

  return (
    <div className="ef-form">
      <SectionCard icon={SlidersHorizontal} title="تنظیمِ مزایای سال">
        <FormGrid>
          <FormField label="سال (شمسی)">
            {(id) => <NumberInput id={id} group={false} value={year} onChange={(v) => setYear(Number(v) || year)} />}
          </FormField>
          <FormField label="حداقل حقوق ماهانه (ریال)" tip="سقفِ عیدی از همین عدد ساخته می‌شود. خالی یا ۰ یعنی عیدی سقف ندارد.">
            {(id) => <NumberInput id={id} value={minWage} onChange={setMinWage} placeholder="۰" />}
          </FormField>
          <FormField label="روزهای مرخصی سالانه">
            {(id) => <NumberInput id={id} value={leaveDays} onChange={setLeaveDays} />}
          </FormField>
        </FormGrid>
      </SectionCard>

      <SectionCard
        icon={Gift}
        title="عیدی، سنوات و مرخصی"
        tip="محاسبه‌ی عیدیِ پایان سال، سنوات پایان خدمت و ماندهٔ مرخصیِ هر کارمند. سند را از همان ردیف صادر کنید."
      >
        {error ? (
          <p className="ef-message ef-message--warn" role="alert">{error}</p>
        ) : !report ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : report.rows.length === 0 ? (
          <EmptyState icon={Gift} text="برای این سال کارمندی با حکم حقوقی یافت نشد." />
        ) : (
          <div className="table-scroll">
            <table className="entity-table benefits-table cards-on-mobile">
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
                    <td className="entity-name" data-label="کارمند">{r.employee_name}</td>
                    <td data-label="حقوق پایه" className="money-cell">{fa(r.base_salary)}</td>
                    <td data-label="عیدی" className="money-cell">{fa(r.eidi)}</td>
                    <td data-label="سنوات تا امروز" className="money-cell">{fa(r.severance)}</td>
                    <td data-label="ماندهٔ مرخصی (روز)" className={Number(r.leave_remaining) < 0 ? 'text-danger' : ''}>
                      {faDays(r.leave_remaining)}
                    </td>
                    <td data-label="طلب مرخصی" className="money-cell">{fa(r.leave_value)}</td>
                    <td className="benefits-action" data-label="عملیات">
                      <div className="row-actions">
                        <button type="button" onClick={() => void handleSeverance(r.employee_id)} disabled={busy} title="صدور سند سنوات">
                          <Coins size={13} /> سنوات
                        </button>
                        <button type="button" onClick={() => void handleLeavePayout(r.employee_id)} disabled={busy} title="صدور سند بازخرید مرخصی">
                          <Wallet size={13} /> مرخصی
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td className="entity-name" data-label="کارمند">جمع</td>
                  <td data-label="حقوق پایه"></td>
                  <td data-label="عیدی" className="money-cell">{fa(report.total_eidi)}</td>
                  <td data-label="سنوات تا امروز" className="money-cell">{fa(report.total_severance)}</td>
                  <td data-label="ماندهٔ مرخصی (روز)"></td>
                  <td data-label="طلب مرخصی" className="money-cell">{fa(report.total_leave_value)}</td>
                  <td data-label="عملیات"></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </SectionCard>

      <form onSubmit={handleRecordLeave} noValidate>
        <SectionCard icon={CalendarPlus} title="ثبت مرخصیِ استفاده‌شده">
          <FormGrid>
            <FormField id="lv-employee" label="کارمند" required>
              {(id) => (
                <select id={id} value={leaveEmp} onChange={(e) => setLeaveEmp(e.target.value)}>
                  <option value="">— انتخاب کنید —</option>
                  {employees.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.first_name} {e.last_name}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
            <FormField label="تاریخ">
              {(id) => <JalaliDatePicker id={id} value={leaveDate} onChange={setLeaveDate} />}
            </FormField>
            <FormField id="lv-days" label="تعداد روز" required>
              {(id) => <NumberInput id={id} allowDecimal value={leaveTaken} onChange={setLeaveTaken} />}
            </FormField>
            <FormField label="توضیح" span="full">
              {(id) => <input id={id} type="text" value={leaveNote} onChange={(e) => setLeaveNote(e.target.value)} />}
            </FormField>
          </FormGrid>
          <div className="ef-card-foot">
            <button type="submit" className="ef-btn-secondary" disabled={busy}>
              <CalendarPlus size={15} /> ثبت مرخصی
            </button>
          </div>
        </SectionCard>
      </form>

      <ActionBar status={<FormStatus msg={msg} />}>
        <button type="button" className="ef-btn-secondary" onClick={() => void saveSettings()} disabled={busy}>
          <Save size={15} /> ذخیره تنظیمات
        </button>
        <button type="button" className="btn-primary" onClick={() => void handleIssueEidi()} disabled={busy}>
          <Gift size={15} /> صدور عیدی سال {faYear(year)}
        </button>
      </ActionBar>
    </div>
  )
}
