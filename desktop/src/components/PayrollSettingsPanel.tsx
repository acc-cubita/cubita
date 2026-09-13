import { useCallback, useEffect, useMemo, useState } from 'react'
import { Settings, Save, Plus, Trash2, Sparkles, ShieldCheck, AlertTriangle } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import {
  fetchPayrollFactors,
  fetchPayrollSettings,
  upsertPayrollSettings,
  type PayrollFactorRecord,
  type PayrollSettingsRecord,
} from '../api'
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
 * پارامترهای قانونی — **پیش‌فرض‌ها عمداً همان رفتارِ پیش از مهاجرتِ ۰۱۳۸‌اند.**
 *
 * تا آن مهاجرت این عددها در سورس‌کدِ سرور ثابت بودند، پس هر تغییرِ مصوبه یک
 * استقرار می‌خواست. حالا سالِ تازه عددهای خودش را می‌گیرد.
 */
type StatutoryDraft = {
  ceiling: string
  unemployment: string
  hardJob: string
  eidiMult: string
  sevDays: string
  monthDays: string
  monthHours: string
  otMult: string
  coefSocial: string
  coefSupp: string
  coefMedical: string
  suppEmployee: string
  suppEmployer: string
  medical: string
  allowNegativeTax: boolean
  roundDigits: string
}

const DEFAULT_PARAMS: StatutoryDraft = {
  ceiling: '0',
  unemployment: '0',
  hardJob: '0',
  eidiMult: '2',
  sevDays: '30',
  monthDays: '30',
  monthHours: '194',
  otMult: '1.4',
  coefSocial: '100',
  coefSupp: '100',
  coefMedical: '100',
  suppEmployee: '',
  suppEmployer: '',
  medical: '',
  allowNegativeTax: false,
  roundDigits: '0',
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
  const [params, setParams] = useState<StatutoryDraft>(DEFAULT_PARAMS)
  const [factors, setFactors] = useState<PayrollFactorRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const current = useMemo(() => all.find((s) => s.year === year) ?? null, [all, year])

  const populate = useCallback((s: PayrollSettingsRecord | null) => {
    if (!s) {
      setEmpRate(''); setEmployerRate(''); setExemption(''); setMinWage('')
      setLeaveDays('26'); setNotes(''); setBrackets([{ up_to: '', rate: '' }])
      setParams(DEFAULT_PARAMS)
      return
    }
    setEmpRate(toPct(s.insurance_employee_rate))
    setEmployerRate(toPct(s.insurance_employer_rate))
    setExemption(String(Math.round(Number(s.tax_exemption_annual || 0))))
    setMinWage(String(Math.round(Number(s.min_base_wage || 0))))
    setLeaveDays(String(s.annual_leave_days ?? 26))
    setNotes(s.notes ?? '')
    setParams({
      ceiling: String(Math.round(Number(s.insurance_daily_ceiling || 0))),
      unemployment: toPct(s.unemployment_rate ?? 0),
      hardJob: toPct(s.hard_job_rate ?? 0),
      eidiMult: String(Number(s.eidi_base_multiplier ?? 2)),
      sevDays: String(s.severance_days_per_year ?? 30),
      monthDays: String(Number(s.monthly_work_days ?? 30)),
      monthHours: String(Number(s.standard_monthly_hours ?? 194)),
      otMult: String(Number(s.overtime_multiplier ?? 1.4)),
      coefSocial: toPct(s.tax_exempt_coef_social ?? 1),
      coefSupp: toPct(s.tax_exempt_coef_supplementary ?? 1),
      coefMedical: toPct(s.tax_exempt_coef_medical ?? 1),
      suppEmployee: s.supplementary_employee_factor_id ?? '',
      suppEmployer: s.supplementary_employer_factor_id ?? '',
      medical: s.medical_factor_id ?? '',
      allowNegativeTax: Boolean(s.allow_negative_tax),
      roundDigits: String(s.payment_rounding_digits ?? 0),
    })
    setBrackets(
      (s.tax_brackets && s.tax_brackets.length
        ? s.tax_brackets.map((b) => ({ up_to: b.up_to == null ? '' : String(Math.round(Number(b.up_to))), rate: toPct(b.rate) }))
        : [{ up_to: '', rate: '' }]),
    )
  }, [])

  const load = useCallback(async () => {
    setError(null)
    try {
      const [list, factorRows] = await Promise.all([fetchPayrollSettings(token), fetchPayrollFactors(token)])
      setAll(list)
      setFactors(factorRows)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void load() }, [load])
  useEffect(() => { populate(current) }, [current, populate])

  // آیا پلکانِ سالِ جاری هنوز placeholderِ نرخ‌صفر است؟ (همان گاردِ سرور)
  //: نقشِ بیمهٔ تکمیلی/درمانِ سهمِ کارمند فقط روی عاملِ **کسور** معنی دارد؛
  //: سهمِ کارفرما می‌تواند مزایا هم باشد، پس آن‌جا فهرست محدود نمی‌شود.
  const deductionFactors = factors.filter((f) => f.category === 'deduction')

  const isPlaceholder = !current || !current.tax_brackets?.length || current.tax_brackets.every((b) => Number(b.rate) === 0)

  function setParam<K extends keyof StatutoryDraft>(key: K, value: StatutoryDraft[K]) {
    setParams((prev) => ({ ...prev, [key]: value }))
  }

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
        insurance_daily_ceiling: Number(params.ceiling) || 0,
        unemployment_rate: fromPct(params.unemployment),
        hard_job_rate: fromPct(params.hardJob),
        eidi_base_multiplier: Number(params.eidiMult) || 2,
        severance_days_per_year: Number(params.sevDays) || 30,
        monthly_work_days: Number(params.monthDays) || 30,
        standard_monthly_hours: Number(params.monthHours) || 194,
        overtime_multiplier: Number(params.otMult) || 1.4,
        tax_exempt_coef_social: fromPct(params.coefSocial),
        tax_exempt_coef_supplementary: fromPct(params.coefSupp),
        tax_exempt_coef_medical: fromPct(params.coefMedical),
        supplementary_employee_factor_id: params.suppEmployee || null,
        supplementary_employer_factor_id: params.suppEmployer || null,
        medical_factor_id: params.medical || null,
        allow_negative_tax: params.allowNegativeTax,
        payment_rounding_digits: Number(params.roundDigits) || 0,
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
          <NumberInput group={false} value={year} onChange={(v) => setYear(Number(v) || year)} style={{ width: 100 }} list="payroll-setting-years" />
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
          <NumberInput allowDecimal value={empRate} onChange={setEmpRate} placeholder="مثلاً ۷" />
        </label>
        <label>
          نرخِ بیمه — سهمِ کارفرما (٪)
          <NumberInput allowDecimal value={employerRate} onChange={setEmployerRate} placeholder="مثلاً ۲۳" />
        </label>
        <label>
          معافیتِ مالیاتیِ سالانه (ریال)
          <NumberInput value={exemption} onChange={setExemption} />
          <span className="field-hint">{exemption ? `${fa(exemption)} ریال — ماهانه ≈ ${fa(Number(exemption) / 12)}` : 'مبلغِ سالانه‌ی معاف از مالیات'}</span>
        </label>
        <label>
          حداقلِ حقوقِ ماهانه (پایه‌ی سقفِ عیدی، ریال)
          <NumberInput value={minWage} onChange={setMinWage} />
          <span className="field-hint">{minWage ? `${fa(minWage)} ریال` : '۰ = بدون سقفِ عیدی'}</span>
        </label>
        <label>
          روزهای مرخصیِ استحقاقیِ سالانه
          <NumberInput value={leaveDays} onChange={setLeaveDays} />
        </label>
      </div>

      <h3 className="panel-subhead">پارامترهای قانونی</h3>
      <p className="field-hint">
        تا پیش از این، این عددها در کدِ سرور ثابت بودند. پیش‌فرضِ هرکدام همان عددِ قبلی است،
        پس تا وقتی دست نزنید هیچ محاسبه‌ای فرق نمی‌کند.
      </p>
      <div className="payroll-settings-grid">
        <label>
          سقفِ روزانهٔ دستمزدِ مشمولِ بیمه (ریال)
          <NumberInput value={params.ceiling} onChange={(v) => setParam('ceiling', v)} />
          <span className="field-hint">
            {Number(params.ceiling) > 0
              ? `ماهانه ≈ ${fa(Number(params.ceiling) * (Number(params.monthDays) || 30))} ریال`
              : '۰ = بی‌سقف (رفتارِ پیش‌فرض)'}
          </span>
        </label>
        <label>
          نرخِ بیمهٔ بیکاری (٪)
          <NumberInput allowDecimal value={params.unemployment} onChange={(v) => setParam('unemployment', v)} />
          <span className="field-hint">سهمِ کارفرماست و به نرخِ کارفرما اضافه می‌شود.</span>
        </label>
        <label>
          نرخِ بیمهٔ مشاغل سخت (٪)
          <NumberInput allowDecimal value={params.hardJob} onChange={(v) => setParam('hardJob', v)} />
          <span className="field-hint">
            ثبت می‌شود ولی هنوز اعمال نمی‌شود: شمولِ آن به کارمند وابسته است و کوبیتا هنوز آن پرچم را ندارد.
          </span>
        </label>
        <label>
          ضریبِ مبنای عیدی
          <NumberInput allowDecimal value={params.eidiMult} onChange={(v) => setParam('eidiMult', v)} />
          <span className="field-hint">۲ = دو برابرِ مبنا.</span>
        </label>
        <label>
          روزهای مبنای سنوات در هر سال
          <NumberInput value={params.sevDays} onChange={(v) => setParam('sevDays', v)} />
          <span className="field-hint">۳۰ = یک ماه به‌ازای هر سال سابقه.</span>
        </label>
        <label>
          مبنای روزِ کاریِ ماه
          <NumberInput allowDecimal value={params.monthDays} onChange={(v) => setParam('monthDays', v)} />
          <span className="field-hint">مقسومٌ‌علیهِ نسبتِ کارکرد و دستمزدِ روزانه.</span>
        </label>
        <label>
          ساعتِ کارِ ماهانهٔ قانونی
          <NumberInput allowDecimal value={params.monthHours} onChange={(v) => setParam('monthHours', v)} />
        </label>
        <label>
          ضریبِ اضافه‌کار
          <NumberInput allowDecimal value={params.otMult} onChange={(v) => setParam('otMult', v)} />
        </label>
        <label>
          رندِ خالصِ پرداختی (تعدادِ رقم)
          <NumberInput value={params.roundDigits} onChange={(v) => setParam('roundDigits', v)} />
          <span className="field-hint">
            {Number(params.roundDigits) > 0
              ? `تا ${fa(10 ** Number(params.roundDigits))} ریال گِرد می‌شود؛ اختلاف به حسابِ «تعدیل رند حقوق» می‌رود.`
              : '۰ = بدونِ رند (رفتارِ پیش‌فرض)'}
          </span>
        </label>
      </div>

      <h3 className="panel-subhead">معافیتِ بیمه از مالیات</h3>
      <p className="field-hint">
        چه کسری از هر بیمه پیش از اعمالِ پلکان، از مبنای مالیات کم شود. برای بیمهٔ تکمیلی و درمان
        باید بگویید کدام عاملِ کسور همان است، وگرنه ضریب روی هیچ مبلغی نمی‌نشیند.
      </p>
      <div className="payroll-settings-grid">
        <label>
          ضریبِ معافیتِ تأمین اجتماعی (٪)
          <NumberInput allowDecimal value={params.coefSocial} onChange={(v) => setParam('coefSocial', v)} />
        </label>
        <label>
          ضریبِ معافیتِ بیمهٔ تکمیلی (٪)
          <NumberInput allowDecimal value={params.coefSupp} onChange={(v) => setParam('coefSupp', v)} />
        </label>
        <label>
          ضریبِ معافیتِ بیمهٔ درمان (٪)
          <NumberInput allowDecimal value={params.coefMedical} onChange={(v) => setParam('coefMedical', v)} />
        </label>
        <label>
          عاملِ بیمهٔ تکمیلی — سهمِ کارمند
          <select value={params.suppEmployee} onChange={(e) => setParam('suppEmployee', e.target.value)}>
            <option value="">— نسبت داده نشده —</option>
            {deductionFactors.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
        <label>
          عاملِ بیمهٔ تکمیلی — سهمِ کارفرما
          <select value={params.suppEmployer} onChange={(e) => setParam('suppEmployer', e.target.value)}>
            <option value="">— نسبت داده نشده —</option>
            {factors.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
        <label>
          عاملِ بیمهٔ درمان
          <select value={params.medical} onChange={(e) => setParam('medical', e.target.value)}>
            <option value="">— نسبت داده نشده —</option>
            {deductionFactors.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
      </div>
      <label className="payroll-notes">
        <input
          type="checkbox"
          checked={params.allowNegativeTax}
          onChange={(e) => setParam('allowNegativeTax', e.target.checked)}
        />
        {' '}مالیاتِ منفی محاسبه شود (استرداد در همان فیش)
      </label>
      <p className="field-hint">
        خاموش (پیش‌فرض) یعنی ماهِ کم‌درآمد مالیاتِ منفی نمی‌گیرد؛ استرداد کارِ تعدیلِ پایانِ سال است.
      </p>

      <h3 className="panel-subhead">پلکانِ مالیاتِ سالانه</h3>
      <p className="field-hint">هر پلکان روی «مشمولِ سالانه پس از کسرِ معافیت» اعمال می‌شود. سقف‌ها تجمعی و صعودی‌اند؛ ردیفِ آخر خودبه‌خود نامحدود (به‌بالا) در نظر گرفته می‌شود.</p>
      <div className="entity-table-wrap">
        <div className="table-scroll">
          <table className="entity-table tax-bracket-table cards-on-mobile">
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
                        <NumberInput value={b.up_to} onChange={(v) => setBracket(i, { up_to: v })} placeholder="سقفِ تجمعی" />
                      )}
                    </td>
                    <td data-label="نرخ (٪)">
                      <NumberInput allowDecimal value={b.rate} onChange={(v) => setBracket(i, { rate: v })} />
                    </td>
                    <td className="tax-bracket-action card-actions">
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
