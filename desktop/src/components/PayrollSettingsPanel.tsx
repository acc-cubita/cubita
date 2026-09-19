import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ClipboardList, Plus, Save, Settings, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { ActionBar, FormField, FormGrid, FormStatus, FormTabs, InfoTip, TabHead } from './form/FormKit'
import {
  fetchPayrollFactors,
  fetchPayrollSettings,
  upsertPayrollSettings,
  type PayrollFactorRecord,
  type PayrollSettingsRecord,
} from '../api'
import { isoToJalali, todayIso } from '../lib/jalali'
import type { Msg } from '../pages/accounting/kit'

const fa = (v: string | number) => Math.round(Number(v || 0)).toLocaleString('fa-IR')
const faYear = (y: number) => y.toLocaleString('fa-IR', { useGrouping: false })

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

type SettingsTab = 'params' | 'exempt' | 'brackets' | 'notes'

/**
 * ویرایشگرِ تنظیماتِ حقوق برای هر سالِ شمسی: نرخِ بیمه‌ی سهمِ کارمند/کارفرما،
 * معافیتِ مالیاتیِ سالانه و پلکانِ مالیات. تا وقتی این تنظیمات (با پلکانِ نرخ‌غیرصفر)
 * ثبت نشود، سرور صدورِ فیشِ حقوق را مسدود می‌کند — پس این پنل پیش‌نیازِ کلِ ماژول است.
 *
 * چیدمان همان «قرارداد جدید» است: کارتِ اصلی (سال و نرخ‌های پایه) و کارتِ جزئیات با
 * تب، و نوارِ ذخیره‌ی چسبیده به پایین.
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
  const [msg, setMsg] = useState<Msg>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<SettingsTab>('params')

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
    setLoadError(null)
    try {
      const [list, factorRows] = await Promise.all([fetchPayrollSettings(token), fetchPayrollFactors(token)])
      setAll(list)
      setFactors(factorRows)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void load() }, [load])
  useEffect(() => { populate(current) }, [current, populate])

  //: نقشِ بیمهٔ تکمیلی/درمانِ سهمِ کارمند فقط روی عاملِ **کسور** معنی دارد؛
  //: سهمِ کارفرما می‌تواند مزایا هم باشد، پس آن‌جا فهرست محدود نمی‌شود.
  const deductionFactors = factors.filter((f) => f.category === 'deduction')

  // آیا پلکانِ سالِ جاری هنوز placeholderِ نرخ‌صفر است؟ (همان گاردِ سرور)
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
    setMsg({ text: 'ارقامِ نمونه بارگذاری شد؛ آن‌ها را بازبینی و ذخیره کنید.', kind: 'ok' })
  }

  /** خطای پلکان کاربر را به تبِ پلکان می‌برد — وگرنه پیام به ردیفی اشاره می‌کرد که پیدا نبود. */
  function bracketError(text: string) {
    setTab('brackets')
    setMsg({ text, kind: 'err' })
  }

  async function save() {
    setMsg(null)
    if (!(Number(empRate) >= 0) || !(Number(employerRate) >= 0)) {
      setMsg({ text: 'نرخِ بیمه معتبر نیست.', kind: 'err' })
      return
    }
    const rows = brackets.filter((b) => b.rate !== '' || b.up_to !== '')
    if (rows.length === 0) { bracketError('حداقل یک پلکانِ مالیاتی لازم است.'); return }
    // آخرین پلکان همیشه نامحدود (up_to = null) است
    const payloadBrackets = rows.map((b, i) => ({
      up_to: i === rows.length - 1 ? null : (b.up_to === '' ? null : Number(b.up_to)),
      rate: fromPct(b.rate),
    }))
    if (payloadBrackets.slice(0, -1).some((b) => b.up_to == null)) {
      bracketError('فقط ردیفِ آخر می‌تواند سقفِ نامحدود داشته باشد؛ برای بقیه سقف وارد کنید.'); return
    }
    if (payloadBrackets.some((b) => b.rate < 0 || b.rate > 1)) {
      bracketError('نرخِ هر پلکان باید بین ۰ تا ۱۰۰ درصد باشد.'); return
    }
    setBusy(true)
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
      setMsg({ text: `تنظیماتِ حقوقِ سال ${faYear(year)} ذخیره شد.`, kind: 'ok' })
      await load()
      onSaved?.()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const years = Array.from(new Set([year, ...all.map((s) => s.year)])).sort((a, b) => b - a)

  /** فیلدِ عددیِ یک پارامتر. `note` پیامِ زنده‌ی زیرِ فیلد است (مثلاً معادلِ ماهانه). */
  const paramField = (key: keyof StatutoryDraft, label: string, opts: { tip?: string; decimal?: boolean; note?: string } = {}) => (
    <FormField label={label} tip={opts.tip} message={opts.note}>
      {(id) => (
        <NumberInput
          id={id}
          allowDecimal={opts.decimal}
          value={params[key] as string}
          onChange={(v) => setParam(key, v as never)}
        />
      )}
    </FormField>
  )

  const factorSelect = (key: 'suppEmployee' | 'suppEmployer' | 'medical', label: string, list: PayrollFactorRecord[]) => (
    <FormField label={label}>
      {(id) => (
        <select id={id} value={params[key]} onChange={(e) => setParam(key, e.target.value)}>
          <option value="">— نسبت داده نشده —</option>
          {list.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      )}
    </FormField>
  )

  return (
    <form
      className="ef-form"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        void save()
      }}
    >
      <SectionCard
        icon={Settings}
        title="تنظیماتِ حقوقِ سال"
        tip="پیش‌نیازِ صدورِ فیش: نرخِ بیمه‌ی سهمِ کارمند/کارفرما، معافیتِ مالیاتی و پلکانِ مالیاتِ هر سال. اعدادِ مالیات و بیمه هر سال طبقِ بخش‌نامه تغییر می‌کنند؛ مسئولیتِ صحتِ ارقام با کارفرماست."
        actions={
          <>
            <span className={`status-badge ${isPlaceholder ? 'tone-warning' : 'tone-success'}`}>
              {isPlaceholder ? (
                <>
                  <AlertTriangle size={13} /> ناقص
                </>
              ) : (
                <>
                  <ShieldCheck size={13} /> آماده
                </>
              )}
            </span>
            <button type="button" onClick={loadExample}>
              <Sparkles size={14} /> بارگذاریِ ارقامِ نمونه
            </button>
          </>
        }
      >
        {loadError && <p className="ef-message ef-message--warn" role="alert">{loadError}</p>}
        <FormGrid>
          <FormField label="سال (شمسی)" tip="برای دیدن یا ویرایشِ سالِ دیگر، عددش را بنویسید؛ سال‌های ثبت‌شده در فهرستِ پیشنهادی می‌آیند.">
            {(id) => (
              <>
                <NumberInput
                  id={id}
                  group={false}
                  value={year}
                  onChange={(v) => setYear(Number(v) || year)}
                  list="payroll-setting-years"
                />
                <datalist id="payroll-setting-years">
                  {years.map((y) => (
                    <option key={y} value={y} />
                  ))}
                </datalist>
              </>
            )}
          </FormField>
          <FormField label="نرخِ بیمه — سهمِ کارمند (٪)">
            {(id) => <NumberInput id={id} allowDecimal value={empRate} onChange={setEmpRate} placeholder="۷" />}
          </FormField>
          <FormField label="نرخِ بیمه — سهمِ کارفرما (٪)">
            {(id) => <NumberInput id={id} allowDecimal value={employerRate} onChange={setEmployerRate} placeholder="۲۳" />}
          </FormField>
          <FormField
            label="معافیتِ مالیاتیِ سالانه (ریال)"
            tip="مبلغِ سالانه‌ی معاف از مالیات."
            message={Number(exemption) > 0 ? `ماهانه ≈ ${fa(Number(exemption) / 12)} ریال` : undefined}
          >
            {(id) => <NumberInput id={id} value={exemption} onChange={setExemption} />}
          </FormField>
          <FormField label="حداقلِ حقوقِ ماهانه (ریال)" tip="پایه‌ی سقفِ عیدی. ۰ یعنی عیدی سقف ندارد.">
            {(id) => <NumberInput id={id} value={minWage} onChange={setMinWage} />}
          </FormField>
          <FormField label="روزهای مرخصیِ استحقاقیِ سالانه">
            {(id) => <NumberInput id={id} value={leaveDays} onChange={setLeaveDays} />}
          </FormField>
        </FormGrid>
        {isPlaceholder && (
          <p className="ef-message ef-message--warn ef-block-note" role="status">
            تا وقتی پلکانِ مالیاتِ این سال با نرخِ واقعی (غیرصفر) ثبت نشود، صدورِ فیشِ حقوق مسدود است.
          </p>
        )}
      </SectionCard>

      <SectionCard icon={ClipboardList} title="جزئیات">
        <FormTabs
          label="جزئیاتِ تنظیماتِ حقوق"
          active={tab}
          onChange={(k) => setTab(k as SettingsTab)}
          tabs={[
            { key: 'params', label: 'پارامترهای قانونی' },
            { key: 'exempt', label: 'معافیت بیمه از مالیات' },
            {
              key: 'brackets',
              label: 'پلکان مالیات',
              badge: brackets.length ? brackets.length.toLocaleString('fa-IR') : undefined,
            },
            { key: 'notes', label: 'یادداشت' },
          ]}
        >
          {tab === 'params' && (
            <>
              <TabHead
                title="پارامترهای قانونی"
                tip="تا پیش از این، این عددها در کدِ سرور ثابت بودند. پیش‌فرضِ هرکدام همان عددِ قبلی است، پس تا وقتی دست نزنید هیچ محاسبه‌ای فرق نمی‌کند."
              />
              <FormGrid>
                {paramField('ceiling', 'سقفِ روزانهٔ دستمزدِ مشمولِ بیمه (ریال)', {
                  tip: '۰ یعنی بی‌سقف (رفتارِ پیش‌فرض).',
                  note:
                    Number(params.ceiling) > 0
                      ? `ماهانه ≈ ${fa(Number(params.ceiling) * (Number(params.monthDays) || 30))} ریال`
                      : undefined,
                })}
                {paramField('unemployment', 'نرخِ بیمهٔ بیکاری (٪)', {
                  decimal: true,
                  tip: 'سهمِ کارفرماست و به نرخِ کارفرما اضافه می‌شود.',
                })}
                {paramField('hardJob', 'نرخِ بیمهٔ مشاغل سخت (٪)', {
                  decimal: true,
                  tip: 'ثبت می‌شود ولی هنوز اعمال نمی‌شود: شمولِ آن به کارمند وابسته است و کوبیتا هنوز آن پرچم را ندارد.',
                })}
                {paramField('eidiMult', 'ضریبِ مبنای عیدی', { decimal: true, tip: '۲ یعنی دو برابرِ مبنا.' })}
                {paramField('sevDays', 'روزهای مبنای سنوات در هر سال', { tip: '۳۰ یعنی یک ماه به‌ازای هر سال سابقه.' })}
                {paramField('monthDays', 'مبنای روزِ کاریِ ماه', {
                  decimal: true,
                  tip: 'مقسومٌ‌علیهِ نسبتِ کارکرد و دستمزدِ روزانه.',
                })}
                {paramField('monthHours', 'ساعتِ کارِ ماهانهٔ قانونی', { decimal: true })}
                {paramField('otMult', 'ضریبِ اضافه‌کار', { decimal: true })}
                {paramField('roundDigits', 'رندِ خالصِ پرداختی (تعدادِ رقم)', {
                  tip: '۰ یعنی بدونِ رند (رفتارِ پیش‌فرض). اختلافِ رند به حسابِ «تعدیل رند حقوق» می‌رود.',
                  note:
                    Number(params.roundDigits) > 0
                      ? `تا ${fa(10 ** Number(params.roundDigits))} ریال گِرد می‌شود.`
                      : undefined,
                })}
              </FormGrid>
            </>
          )}

          {tab === 'exempt' && (
            <>
              <TabHead
                title="معافیتِ بیمه از مالیات"
                tip="چه کسری از هر بیمه پیش از اعمالِ پلکان، از مبنای مالیات کم شود. برای بیمهٔ تکمیلی و درمان باید بگویید کدام عاملِ کسور همان است، وگرنه ضریب روی هیچ مبلغی نمی‌نشیند."
              />
              <FormGrid>
                {paramField('coefSocial', 'ضریبِ معافیتِ تأمین اجتماعی (٪)', { decimal: true })}
                {paramField('coefSupp', 'ضریبِ معافیتِ بیمهٔ تکمیلی (٪)', { decimal: true })}
                {paramField('coefMedical', 'ضریبِ معافیتِ بیمهٔ درمان (٪)', { decimal: true })}
                {factorSelect('suppEmployee', 'عاملِ بیمهٔ تکمیلی — سهمِ کارمند', deductionFactors)}
                {factorSelect('suppEmployer', 'عاملِ بیمهٔ تکمیلی — سهمِ کارفرما', factors)}
                {factorSelect('medical', 'عاملِ بیمهٔ درمان', deductionFactors)}
                <div className="ef-checks">
                  <span className="ef-check-tip">
                    <label className="fy-check">
                      <input
                        type="checkbox"
                        checked={params.allowNegativeTax}
                        onChange={(e) => setParam('allowNegativeTax', e.target.checked)}
                      />
                      مالیاتِ منفی محاسبه شود (استرداد در همان فیش)
                    </label>
                    <InfoTip text="خاموش (پیش‌فرض) یعنی ماهِ کم‌درآمد مالیاتِ منفی نمی‌گیرد؛ استرداد کارِ تعدیلِ پایانِ سال است." />
                  </span>
                </div>
              </FormGrid>
            </>
          )}

          {tab === 'brackets' && (
            <>
              <TabHead
                title="پلکانِ مالیاتِ سالانه"
                tip="هر پلکان روی «مشمولِ سالانه پس از کسرِ معافیت» اعمال می‌شود. سقف‌ها تجمعی و صعودی‌اند؛ ردیفِ آخر خودبه‌خود نامحدود (به‌بالا) در نظر گرفته می‌شود."
                actions={
                  <button type="button" onClick={addBracket}>
                    <Plus size={14} /> افزودنِ پلکان
                  </button>
                }
              />
              <div className="table-scroll">
                <table className="entity-table tax-bracket-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>ردیف</th>
                      <th>تا سقفِ سالانه (ریال)</th>
                      <th>نرخ (٪)</th>
                      <th></th>
                    </tr>
                  </thead>
                  {/* audit-r9-exempt: پلکانِ فرم همیشه دستِ‌کم یک ردیف دارد و
                      به‌جای حالتِ خالی دکمه‌ی «افزودنِ پلکان» می‌گیرد. */}
                  <tbody>
                    {brackets.map((b, i) => {
                      const last = i === brackets.length - 1
                      return (
                        <tr key={i}>
                          <td data-label="ردیف">{(i + 1).toLocaleString('fa-IR')}</td>
                          <td data-label="تا سقفِ سالانه (ریال)">
                            {last ? (
                              <span className="muted">به‌بالا (نامحدود)</span>
                            ) : (
                              <NumberInput
                                aria-label="تا سقفِ سالانه (ریال)"
                                value={b.up_to}
                                onChange={(v) => setBracket(i, { up_to: v })}
                              />
                            )}
                          </td>
                          <td data-label="نرخ (٪)">
                            <NumberInput aria-label="نرخ (٪)" allowDecimal value={b.rate} onChange={(v) => setBracket(i, { rate: v })} />
                          </td>
                          <td className="tax-bracket-action card-actions">
                            <button
                              type="button"
                              className="ef-icon-btn"
                              aria-label="حذفِ ردیف"
                              title="حذفِ ردیف"
                              onClick={() => removeBracket(i)}
                              disabled={brackets.length <= 1}
                            >
                              <Trash2 size={15} />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === 'notes' && (
            <FormGrid>
              <FormField label="یادداشت" span="full">
                {(id) => (
                  <textarea
                    id={id}
                    rows={4}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="مرجعِ بخش‌نامه یا توضیح"
                  />
                )}
              </FormField>
            </FormGrid>
          )}
        </FormTabs>
      </SectionCard>

      <ActionBar status={<FormStatus msg={msg} />}>
        <button type="submit" className="btn-primary" disabled={busy}>
          <Save size={15} /> {busy ? 'در حال ذخیره…' : `ذخیرهٔ تنظیماتِ سال ${faYear(year)}`}
        </button>
      </ActionBar>
    </form>
  )
}
