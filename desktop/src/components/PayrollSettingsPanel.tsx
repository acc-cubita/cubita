import { useCallback, useEffect, useMemo, useState } from 'react'
import { Settings, Save, Plus, Trash2, Sparkles, ShieldCheck, AlertTriangle } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { fetchPayrollSettings, upsertPayrollSettings, type PayrollSettingsRecord } from '../api'
import { isoToJalali, todayIso } from '../lib/jalali'

const fa = (v: string | number) => Math.round(Number(v || 0)).toLocaleString('fa-IR')

type BracketRow = { up_to: string; rate: string }

// درصد ذخیره‌شده (۰..۱) → نمایشِ درصدی (۰..۱۰۰) و برعکس
const toPct = (frac: string | number) => {
  const n = Number(frac || 0) * 100
  return Number.isInteger(n) ? String(n) : String(Number(n.toFixed(4)))
}
const fromPct = (pct: string) => (Number(pct || 0) / 100)

// ارقامِ نمونه (نه مرجعِ قانونی) — ساختارِ متداولِ مالیاتِ حقوق برای شروع؛ کاربر باید
// پیش از صدورِ فیشِ واقعی، ارقام را با بخش‌نامه‌ی رسمیِ همان سال تطبیق دهد.
const EXAMPLE = {
  empRate: '7',
  employerRate: '23',
  exemption: '1728000000', // معافیتِ سالانه ≈ ماهانه ۱۴۴٬۰۰۰٬۰۰۰ ریال × ۱۲
  minWage: '100000000',
  leaveDays: '26',
  brackets: [
    { up_to: '2304000000', rate: '10' },
    { up_to: '4608000000', rate: '15' },
    { up_to: '9216000000', rate: '20' },
    { up_to: '', rate: '30' },
  ] as BracketRow[],
}

/**
 * ویرایشگرِ تنظیماتِ حقوق برای هر سالِ شمسی: نرخِ بیمه‌ی سهمِ کارمند/کارفرما،
 * معافیتِ مالیاتیِ سالانه و پلکانِ مالیات. تا وقتی این تنظیمات (با پلکانِ نرخ‌غیرصفر)
 * ثبت نشود، سرور صدورِ فیشِ حقوق را مسدود می‌کند — پس این پنل پیش‌نیازِ کلِ ماژول است.
 */
export function PayrollSettingsPanel({
  token,
  onSaved,
}: {
  token: string
  onSaved?: () => void
}) {
  const [all, setAll] = useState<PayrollSettingsRecord[]>([])
  const [year, setYear] = useState(isoToJalali(todayIso()).jy)
  const [empRate, setEmpRate] = useState('')
  const [employerRate, setEmployerRate] = useState('')
  const [exemption, setExemption] = useState('')
  const [minWage, setMinWage] = useState('')
  const [leaveDays, setLeaveDays] = useState('26')
  const [notes, setNotes] = useState('')
  const [brackets, setBrackets] = useState<BracketRow[]>([{ up_to: '', rate: '' }])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const current = useMemo(() => all.find((s) => s.year === year) ?? null, [all, year])

  const populate = useCallback((s: PayrollSettingsRecord | null) => {
    if (!s) {
      setEmpRate(''); setEmployerRate(''); setExemption(''); setMinWage('')
      setLeaveDays('26'); setNotes(''); setBrackets([{ up_to: '', rate: '' }])
      return
    }
    setEmpRate(toPct(s.insurance_employee_rate))
    setEmployerRate(toPct(s.insurance_employer_rate))
    setExemption(String(Math.round(Number(s.tax_exemption_annual || 0))))
    setMinWage(String(Math.round(Number(s.min_base_wage || 0))))
    setLeaveDays(String(s.annual_leave_days ?? 26))
    setNotes(s.notes ?? '')
    setBrackets(
      (s.tax_brackets && s.tax_brackets.length
        ? s.tax_brackets.map((b) => ({ up_to: b.up_to == null ? '' : String(Math.round(Number(b.up_to))), rate: toPct(b.rate) }))
        : [{ up_to: '', rate: '' }]),
    )
  }, [])

  const load = useCallback(async () => {
    setError(null)
    try {
      const list = await fetchPayrollSettings(token)
      setAll(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void load() }, [load])
  useEffect(() => { populate(current) }, [current, populate])

  // آیا پلکانِ سالِ جاری هنوز placeholderِ نرخ‌صفر است؟ (همان گاردِ سرور)
  const isPlaceholder = !current || !current.tax_brackets?.length || current.tax_brackets.every((b) => Number(b.rate) === 0)

  function setBracket(i: number, patch: Partial<BracketRow>) {
    setBrackets((prev) => prev.map((b, idx) => (idx === i ? { ...b, ...patch } : b)))
  }
  function addBracket() {
    setBrackets((prev) => [...prev, { up_to: '', rate: '' }])
  }
  function removeBracket(i: number) {
    setBrackets((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i)))
  }
  function loadExample() {
    setEmpRate(EXAMPLE.empRate); setEmployerRate(EXAMPLE.employerRate)
    setExemption(EXAMPLE.exemption); setMinWage(EXAMPLE.minWage); setLeaveDays(EXAMPLE.leaveDays)
    setBrackets(EXAMPLE.brackets.map((b) => ({ ...b })))
    setNotes('ارقامِ نمونه — پیش از صدورِ فیشِ واقعی با بخش‌نامه‌ی رسمیِ همان سال تطبیق دهید.')
    setMessage('ارقامِ نمونه بارگذاری شد؛ آن‌ها را بازبینی و ذخیره کنید.')
  }

  async function save() {
    setError(null); setMessage(null)
    if (!(Number(empRate) >= 0) || !(Number(employerRate) >= 0)) {
      setError('نرخِ بیمه معتبر نیست.'); return
    }
    const rows = brackets.filter((b) => b.rate !== '' || b.up_to !== '')
    if (rows.length === 0) { setError('حداقل یک پلکانِ مالیاتی لازم است.'); return }
    // آخرین پلکان همیشه نامحدود (up_to = null) است
    const payloadBrackets = rows.map((b, i) => ({
      up_to: i === rows.length - 1 ? null : (b.up_to === '' ? null : Number(b.up_to)),
      rate: fromPct(b.rate),
    }))
    if (payloadBrackets.slice(0, -1).some((b) => b.up_to == null)) {
      setError('فقط ردیفِ آخر می‌تواند سقفِ نامحدود داشته باشد؛ برای بقیه سقف وارد کنید.'); return
    }
    if (payloadBrackets.some((b) => b.rate < 0 || b.rate > 1)) {
      setError('نرخِ هر پلکان باید بین ۰ تا ۱۰۰ درصد باشد.'); return
    }
    try {
      await upsertPayrollSettings(token, {
        year,
        insurance_employee_rate: fromPct(empRate),
        insurance_employer_rate: fromPct(employerRate),
        tax_exemption_annual: Number(exemption) || 0,
        tax_brackets: payloadBrackets,
        min_base_wage: Number(minWage) || 0,
        annual_leave_days: Number(leaveDays) || 26,
        notes,
      })
      setMessage(`تنظیماتِ حقوقِ سال ${year} ذخیره شد.`)
      await load()
      onSaved?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const years = Array.from(new Set([year, ...all.map((s) => s.year)])).sort((a, b) => b - a)

  return (
    <SectionCard
      icon={Settings}
      title="تنظیماتِ حقوق — نرخِ بیمه و پلکانِ مالیات"
      description="پیش‌نیازِ صدورِ فیش: نرخِ بیمه‌ی سهمِ کارمند/کارفرما، معافیتِ مالیاتی و پلکانِ مالیاتِ هر سال."
    >
      <div className="payroll-settings-bar">
        <label>
          سال (شمسی)
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value) || year)} style={{ width: 100 }} list="payroll-setting-years" />
          <datalist id="payroll-setting-years">
            {years.map((y) => <option key={y} value={y} />)}
          </datalist>
        </label>
        <span className={`status-badge ${isPlaceholder ? 'tone-warning' : 'tone-success'}`}>
          {isPlaceholder
            ? <><AlertTriangle size={13} /> تنظیماتِ این سال ناقص است</>
            : <><ShieldCheck size={13} /> تنظیماتِ این سال آماده است</>}
        </span>
        <button type="button" onClick={loadExample}><Sparkles size={13} /> بارگذاریِ ارقامِ نمونه</button>
      </div>

      {isPlaceholder && (
        <p className="field-hint payroll-warn">
          تا وقتی پلکانِ مالیاتِ این سال با نرخِ واقعی (غیرصفر) ثبت نشود، صدورِ فیشِ حقوق مسدود است. اعدادِ مالیات/بیمه هرسال طبق بخش‌نامه تغییر می‌کنند؛ مسئولیتِ صحتِ ارقام با کارفرماست.
        </p>
      )}

      <div className="payroll-settings-grid">
        <label>
          نرخِ بیمه — سهمِ کارمند (٪)
          <input type="number" min="0" step="any" value={empRate} onChange={(e) => setEmpRate(e.target.value)} placeholder="مثلاً ۷" />
        </label>
        <label>
          نرخِ بیمه — سهمِ کارفرما (٪)
          <input type="number" min="0" step="any" value={employerRate} onChange={(e) => setEmployerRate(e.target.value)} placeholder="مثلاً ۲۳" />
        </label>
        <label>
          معافیتِ مالیاتیِ سالانه (ریال)
          <input type="number" min="0" value={exemption} onChange={(e) => setExemption(e.target.value)} />
          <span className="field-hint">{exemption ? `${fa(exemption)} ریال — ماهانه ≈ ${fa(Number(exemption) / 12)}` : 'مبلغِ سالانه‌ی معاف از مالیات'}</span>
        </label>
        <label>
          حداقلِ حقوقِ ماهانه (پایه‌ی سقفِ عیدی، ریال)
          <input type="number" min="0" value={minWage} onChange={(e) => setMinWage(e.target.value)} />
          <span className="field-hint">{minWage ? `${fa(minWage)} ریال` : '۰ = بدون سقفِ عیدی'}</span>
        </label>
        <label>
          روزهای مرخصیِ استحقاقیِ سالانه
          <input type="number" min="0" value={leaveDays} onChange={(e) => setLeaveDays(e.target.value)} />
        </label>
      </div>

      <h3 className="panel-subhead">پلکانِ مالیاتِ سالانه</h3>
      <p className="field-hint">هر پلکان روی «مشمولِ سالانه پس از کسرِ معافیت» اعمال می‌شود. سقف‌ها تجمعی و صعودی‌اند؛ ردیفِ آخر خودبه‌خود نامحدود (به‌بالا) در نظر گرفته می‌شود.</p>
      <div className="entity-table-wrap">
        <table className="entity-table tax-bracket-table">
          <thead>
            <tr><th>ردیف</th><th>تا سقفِ سالانه (ریال)</th><th>نرخ (٪)</th><th></th></tr>
          </thead>
          <tbody>
            {brackets.map((b, i) => {
              const last = i === brackets.length - 1
              return (
                <tr key={i}>
                  <td data-label="ردیف">{fa(i + 1)}</td>
                  <td data-label="تا سقفِ سالانه (ریال)">
                    {last ? (
                      <span className="muted">به‌بالا (نامحدود)</span>
                    ) : (
                      <input type="number" min="0" value={b.up_to} onChange={(e) => setBracket(i, { up_to: e.target.value })} placeholder="سقفِ تجمعی" />
                    )}
                  </td>
                  <td data-label="نرخ (٪)">
                    <input type="number" min="0" max="100" step="any" value={b.rate} onChange={(e) => setBracket(i, { rate: e.target.value })} />
                  </td>
                  <td className="tax-bracket-action">
                    <button type="button" className="icon-btn-danger" title="حذفِ ردیف" onClick={() => removeBracket(i)} disabled={brackets.length <= 1}>
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="check-actions" style={{ marginTop: 8 }}>
        <button type="button" onClick={addBracket}><Plus size={13} /> افزودنِ پلکان</button>
      </div>

      <label className="payroll-notes">
        یادداشت
        <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="مرجعِ بخش‌نامه یا توضیح" />
      </label>

      <div className="invoice-form-footer">
        <button type="button" className="btn-primary" onClick={() => void save()}><Save size={14} /> ذخیرهٔ تنظیماتِ سال {year}</button>
      </div>
      {message && <div className="hint">{message}</div>}
      {error && <div className="error">{error}</div>}
    </SectionCard>
  )
}
