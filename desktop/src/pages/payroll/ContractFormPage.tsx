import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileSignature, Plus, Save, Trash2 } from 'lucide-react'
import {
  CONTRACT_TYPE_LABELS,
  EMPLOYMENT_TYPES,
  JOB_FAMILIES,
  TAX_GROUP_KIND_LABELS,
  createDefaultPayrollFactors,
  createJobTitle,
  createSalaryContract,
  createServiceLocation,
  fetchAllowedContractTypes,
  fetchCostCenters,
  fetchEmployeeCandidates,
  fetchInsuranceTaxBranches,
  fetchJobTitles,
  fetchPayrollFactors,
  fetchPayrollTaxGroups,
  fetchServiceLocations,
  type CostCenterRecord,
  type EmployeeCandidate,
  type InsuranceTaxBranchRecord,
  type JobTitleRecord,
  type PayrollFactorRecord,
  type PayrollTaxGroupRecord,
  type ServiceLocationRecord,
} from '../../api'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import type { PageKey } from '../../lib/navModel'

/**
 * «قرارداد جدید» — فرمِ استخدام و اصلاحِ قرارداد، به ساختارِ سپیدار.
 *
 * جریانِ استخدام از طرف‌حساب شروع می‌شود و این فرم حلقه‌ی دومِ آن است:
 * اول شخص در «طرف حساب جدید» با تیکِ **کارمند** ثبت می‌شود، بعد این‌جا نامش در
 * فهرست می‌آید و اولین قرارداد پرونده‌ی حقوق و دستمزدش را می‌سازد. کاربر یک آدم را
 * دو بار ثبت نمی‌کند.
 *
 * سه تاریخ عمداً سه فیلدِ جدا هستند و یکی نمی‌شوند:
 *
 * * **تاریخ صدور** — محاسبه‌ی حقوق از این تاریخ شروع می‌شود.
 * * **تاریخ اعتبار** — تا این تاریخ طبقِ همین قرارداد محاسبه می‌شود.
 * * **تاریخ پایان خدمت** — از این تاریخ به بعد کارکرد اصلاً محاسبه نمی‌شود.
 *
 * و **تاریخ استخدام** چهارمی است، در تبِ اطلاعات استخدامی: تاریخِ واقعیِ شروعِ کار،
 * که می‌تواند سال‌ها قبل‌تر باشد — شرکتی که تا دیروز با اکسل حقوق می‌داد، کارمندش را
 * که تازه استخدام نکرده.
 *
 * «استخدام» اولین قراردادِ هر شخص است؛ **تا وقتی ثبت نشده «اصلاح قرارداد» در فهرست
 * نمی‌آید** و بعد از آن دیگر «استخدام» نمی‌آید. تصمیمش با سرور است نه این فرم.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

type Msg = { text: string; kind: 'ok' | 'err' } | null
type DraftLine = { factor_id: string; amount: string }

export function ContractFormPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey) => void
}) {
  const [candidates, setCandidates] = useState<EmployeeCandidate[]>([])
  const [locations, setLocations] = useState<ServiceLocationRecord[]>([])
  const [jobs, setJobs] = useState<JobTitleRecord[]>([])
  const [factors, setFactors] = useState<PayrollFactorRecord[]>([])
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [taxGroups, setTaxGroups] = useState<PayrollTaxGroupRecord[]>([])
  const [branches, setBranches] = useState<InsuranceTaxBranchRecord[]>([])

  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<'employment' | 'pay' | 'deductions' | 'other' | 'notes'>('employment')

  // ── سرصفحه ──
  const [search, setSearch] = useState('')
  const [contactId, setContactId] = useState('')
  const [allowedTypes, setAllowedTypes] = useState<string[]>(['hire'])
  const [contractType, setContractType] = useState('hire')
  const [number, setNumber] = useState('')
  const [issueDate, setIssueDate] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [serviceEnd, setServiceEnd] = useState('')

  // ── اطلاعات استخدامی ──
  const [hireDate, setHireDate] = useState('')
  const [employmentType, setEmploymentType] = useState('')
  const [locationId, setLocationId] = useState('')
  const [jobId, setJobId] = useState('')
  const [costCenterId, setCostCenterId] = useState('')

  // ── مبالغ ──
  const [payLines, setPayLines] = useState<DraftLine[]>([])
  const [deductionLines, setDeductionLines] = useState<DraftLine[]>([])

  // ── سایر اطلاعات ──
  const [taxGroupId, setTaxGroupId] = useState('')
  const [taxBranchId, setTaxBranchId] = useState('')
  const [insuranceBranchId, setInsuranceBranchId] = useState('')
  const [housingLoanExempt, setHousingLoanExempt] = useState('')
  const [isInsured, setIsInsured] = useState(true)
  const [isHardJob, setIsHardJob] = useState(false)
  const [exemptEmployee, setExemptEmployee] = useState(false)
  const [exemptEmployer, setExemptEmployer] = useState(false)
  const [employerExemptPercent, setEmployerExemptPercent] = useState('')
  const [exemptUnemployment, setExemptUnemployment] = useState(false)
  const [employerName, setEmployerName] = useState('')
  const [hasSupplementary, setHasSupplementary] = useState(false)
  const [supplementaryBranch, setSupplementaryBranch] = useState('')
  const [supplementaryInsurer, setSupplementaryInsurer] = useState('')
  const [description, setDescription] = useState('')

  async function loadRefs() {
    const [loc, job, fac, cc, tax, br] = await Promise.all([
      fetchServiceLocations(token).catch(() => []),
      fetchJobTitles(token).catch(() => []),
      fetchPayrollFactors(token).catch(() => []),
      fetchCostCenters(token).catch(() => []),
      fetchPayrollTaxGroups(token).catch(() => []),
      fetchInsuranceTaxBranches(token).catch(() => []),
    ])
    setLocations(loc)
    setJobs(job)
    setFactors(fac)
    setCostCenters(cc)
    setTaxGroups(tax)
    setBranches(br)
  }

  useEffect(() => {
    void loadRefs()
  }, [token])

  //: فهرستِ کارمند سمتِ سرور جست‌وجو می‌شود، نه در مرورگر — با چند صد طرف‌حساب،
  //: کشیدنِ همه برای فیلترکردنشان این‌جا از کار می‌افتد.
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      fetchEmployeeCandidates(token, search)
        .then((rows) => !cancelled && setCandidates(rows))
        .catch(() => !cancelled && setCandidates([]))
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [token, search])

  //: نوعِ قرارداد را سرور تعیین می‌کند: «اصلاح» تا وقتی استخدام نباشد اصلاً نمی‌آید.
  useEffect(() => {
    if (!contactId) {
      setAllowedTypes(['hire'])
      setContractType('hire')
      return
    }
    let cancelled = false
    fetchAllowedContractTypes(token, contactId)
      .then((res) => {
        if (cancelled) return
        setAllowedTypes(res.allowed)
        setContractType(res.allowed[0] ?? 'hire')
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token, contactId])

  const benefitFactors = useMemo(() => factors.filter((f) => f.category === 'benefit' && f.is_active), [factors])
  const deductionFactors = useMemo(() => factors.filter((f) => f.category === 'deduction' && f.is_active), [factors])
  const selected = candidates.find((c) => c.contact_id === contactId)

  const payTotal = payLines.reduce((sum, l) => sum + (Number(l.amount) || 0), 0)
  const deductionTotal = deductionLines.reduce((sum, l) => sum + (Number(l.amount) || 0), 0)

  async function seedFactors() {
    try {
      setFactors(await createDefaultPayrollFactors(token))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!contactId) {
      setMsg({ text: 'نام کارمند را انتخاب کنید.', kind: 'err' })
      return
    }
    if (!issueDate) {
      setMsg({ text: 'تاریخ صدور الزامی است — محاسبه‌ی حقوق از آن شروع می‌شود.', kind: 'err' })
      return
    }
    const lines = [...payLines, ...deductionLines]
      .filter((l) => l.factor_id && Number(l.amount) > 0)
      .map((l) => ({ factor_id: l.factor_id, amount: Number(l.amount) }))
    if (!lines.length) {
      setTab('pay')
      setMsg({ text: 'دستِ‌کم یک ردیفِ «حقوق و مزایای ثابت» لازم است.', kind: 'err' })
      return
    }

    setBusy(true)
    setMsg(null)
    try {
      await createSalaryContract(token, {
        contact_id: contactId,
        contract_type: contractType,
        number: number.trim(),
        effective_from: issueDate,
        valid_until: validUntil || null,
        service_end_date: serviceEnd || null,
        hire_date: hireDate || null,
        employment_type: employmentType,
        service_location_id: locationId || null,
        job_title_id: jobId || null,
        cost_center_id: costCenterId || null,
        lines,
        tax_group_id: taxGroupId || null,
        tax_branch_id: taxBranchId || null,
        insurance_branch_id: insuranceBranchId || null,
        housing_loan_exempt_amount: Number(housingLoanExempt) || 0,
        is_insured: isInsured,
        is_hard_job: isHardJob,
        exempt_employee_insurance: exemptEmployee,
        exempt_employer_insurance: exemptEmployer,
        employer_exempt_percent: Number(employerExemptPercent) || 0,
        exempt_unemployment_insurance: exemptUnemployment,
        employer_name: employerName.trim(),
        has_supplementary_insurance: hasSupplementary,
        supplementary_branch: supplementaryBranch.trim(),
        supplementary_insurer: supplementaryInsurer.trim(),
        description: description.trim(),
      })
      setMsg({
        text: `${CONTRACT_TYPE_LABELS[contractType]} برای «${selected?.name ?? ''}» ثبت شد.`,
        kind: 'ok',
      })
      setPayLines([])
      setDeductionLines([])
      setNumber('')
      setDescription('')
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={FileSignature}
        title="قرارداد جدید"
        description="استخدام یا اصلاحِ قرارداد یک کارمند — با اطلاعات استخدامی، حقوق و مزایای ثابت، کسورات و اطلاعات بیمه و مالیات."
      />

      {msg && (
        <section className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{msg.text}</div>
        </section>
      )}

      <form onSubmit={submit}>
        <SectionCard icon={FileSignature} title="مشخصات قرارداد">
          <div className="cmp-form">
            <label className="cmp-form-wide">
              <span>نام کارمند *</span>
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جست‌وجو در نامِ کارمندان…" />
              <span className="field-hint">
                فهرست از طرف‌حساب‌هایی می‌آید که تیکِ «کارمند» دارند. اگر کسی نیست، اول او را در
                «شرکت ← طرف حساب جدید» با تیکِ کارمند ثبت کنید.
              </span>
            </label>
            <label className="cmp-form-wide">
              <span>انتخاب</span>
              <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
                <option value="">— انتخاب کنید —</option>
                {candidates.map((c) => (
                  <option key={c.contact_id} value={c.contact_id}>
                    {c.name}
                    {c.national_id ? ` — ${c.national_id}` : ''}
                    {c.has_contract ? ' (دارای قرارداد)' : ''}
                  </option>
                ))}
              </select>
              {candidates.length === 0 && (
                <span className="field-hint">
                  کارمندی پیدا نشد — طرف‌حسابی با تیکِ «کارمند» بسازید.
                </span>
              )}
            </label>

            <label>
              <span>نوع قرارداد *</span>
              <select value={contractType} onChange={(e) => setContractType(e.target.value)}>
                {allowedTypes.map((t) => (
                  <option key={t} value={t}>{CONTRACT_TYPE_LABELS[t] ?? t}</option>
                ))}
              </select>
              <span className="field-hint">
                {allowedTypes.includes('hire')
                  ? 'اولین قرارداد این شخص، پس «استخدام» است.'
                  : 'استخدامِ این شخص از قبل ثبت شده، پس تغییرِ بعدی «اصلاح قرارداد» است.'}
              </span>
            </label>
            <label>
              <span>شماره</span>
              <input dir="ltr" value={number} onChange={(e) => setNumber(e.target.value)} maxLength={30} />
            </label>
            <label>
              <span>تاریخ صدور *</span>
              <JalaliDatePicker value={issueDate} onChange={setIssueDate} />
              <span className="field-hint">محاسبه‌ی حقوق از این تاریخ شروع می‌شود.</span>
            </label>
            <label>
              <span>تاریخ اعتبار</span>
              <JalaliDatePicker value={validUntil} onChange={setValidUntil} />
              <span className="field-hint">تا این تاریخ طبقِ همین قرارداد محاسبه می‌شود.</span>
            </label>
            <label>
              <span>تاریخ پایان خدمت</span>
              <JalaliDatePicker value={serviceEnd} onChange={setServiceEnd} />
              <span className="field-hint">از این تاریخ به بعد کارکرد محاسبه نمی‌شود.</span>
            </label>
          </div>
        </SectionCard>

        <SectionCard icon={FileSignature} title="جزئیات">
          <div className="cc-tabs">
            {([
              ['employment', 'اطلاعات استخدامی'],
              ['pay', `حقوق و مزایای ثابت${payLines.length ? ` (${fa(payLines.length)})` : ''}`],
              ['deductions', `سایر مبالغ${deductionLines.length ? ` (${fa(deductionLines.length)})` : ''}`],
              ['other', 'سایر اطلاعات'],
              ['notes', 'شرح'],
            ] as const).map(([key, label]) => (
              <button key={key} type="button" className={tab === key ? 'is-active' : ''} onClick={() => setTab(key)}>
                {label}
              </button>
            ))}
          </div>

          {tab === 'employment' && (
            <EmploymentTab
              {...{ token, hireDate, setHireDate, employmentType, setEmploymentType,
                    locationId, setLocationId, jobId, setJobId, costCenterId, setCostCenterId,
                    locations, setLocations, jobs, setJobs, costCenters }}
            />
          )}

          {tab === 'pay' && (
            <LinesTab
              title="حقوق و مزایای ثابت"
              hint="ردیفِ «حقوق پایه» الزامی است. عواملی که خودتان می‌سازید در «سایر مزایا» جمع می‌شوند و محاسبه را نمی‌شکنند."
              factors={benefitFactors}
              rows={payLines}
              setRows={setPayLines}
              total={payTotal}
              onSeed={benefitFactors.length === 0 ? seedFactors : undefined}
            />
          )}

          {tab === 'deductions' && (
            <LinesTab
              title="سایر مبالغ (کسورات)"
              hint="کسوراتِ ثابت مثلِ بیمه‌ی تکمیلی. اقساطِ وامِ پرسنلی جای خودش را دارد و این‌جا دوباره تایپ نمی‌شود."
              factors={deductionFactors}
              rows={deductionLines}
              setRows={setDeductionLines}
              total={deductionTotal}
            />
          )}

          {tab === 'other' && (
            <OtherTab
              {...{ taxGroups, branches, taxGroupId, setTaxGroupId, taxBranchId, setTaxBranchId,
                    insuranceBranchId, setInsuranceBranchId, housingLoanExempt, setHousingLoanExempt,
                    isInsured, setIsInsured, isHardJob, setIsHardJob,
                    exemptEmployee, setExemptEmployee, exemptEmployer, setExemptEmployer,
                    employerExemptPercent, setEmployerExemptPercent,
                    exemptUnemployment, setExemptUnemployment, employerName, setEmployerName,
                    hasSupplementary, setHasSupplementary, supplementaryBranch, setSupplementaryBranch,
                    supplementaryInsurer, setSupplementaryInsurer }}
            />
          )}

          {tab === 'notes' && (
            <div className="cmp-form">
              <label className="cmp-form-wide">
                <span>شرح</span>
                <textarea rows={5} value={description} onChange={(e) => setDescription(e.target.value)} />
              </label>
            </div>
          )}
        </SectionCard>

        <div className="invoice-form-footer">
          <button type="button" onClick={() => onNavigate('contractlist')}>فهرستِ قراردادها</button>
          <button type="submit" className="btn-primary" disabled={busy || !contactId}>
            <Save size={13} /> ثبت قرارداد
          </button>
        </div>
      </form>
    </div>
  )
}

// ── تبِ اطلاعات استخدامی ──────────────────────────────────────────────────────

type Setter<T> = (v: T) => void

function EmploymentTab(p: {
  token: string
  hireDate: string; setHireDate: Setter<string>
  employmentType: string; setEmploymentType: Setter<string>
  locationId: string; setLocationId: Setter<string>
  jobId: string; setJobId: Setter<string>
  costCenterId: string; setCostCenterId: Setter<string>
  locations: ServiceLocationRecord[]; setLocations: Setter<ServiceLocationRecord[]>
  jobs: JobTitleRecord[]; setJobs: Setter<JobTitleRecord[]>
  costCenters: CostCenterRecord[]
}) {
  const [addLocation, setAddLocation] = useState(false)
  const [addJob, setAddJob] = useState(false)

  return (
    <div className="cmp-form">
      <label>
        <span>تاریخ استخدام</span>
        <JalaliDatePicker value={p.hireDate} onChange={p.setHireDate} />
        {/* عمداً جدا از تاریخِ صدور: شرکتی که تا دیروز با اکسل حقوق می‌داد، کارمندش
            را که تازه استخدام نکرده. این تاریخ روی خودِ کارمند می‌نشیند. */}
        <span className="field-hint">تاریخِ واقعیِ شروعِ کار — می‌تواند خیلی قبل‌تر از تاریخ صدور باشد.</span>
      </label>
      <label>
        <span>نوع استخدام</span>
        <select value={p.employmentType} onChange={(e) => p.setEmploymentType(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {EMPLOYMENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>

      <label>
        <span>محل خدمت</span>
        <select value={p.locationId} onChange={(e) => p.setLocationId(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {p.locations.filter((l) => l.is_active).map((l) => (
            <option key={l.id} value={l.id}>{l.code} — {l.name}</option>
          ))}
        </select>
        <span className="field-hint">
          <button type="button" onClick={() => setAddLocation((v) => !v)}>
            {addLocation ? 'انصراف' : 'محل خدمت تازه بسازید'}
          </button>
        </span>
      </label>
      <label>
        <span>شغل</span>
        <select value={p.jobId} onChange={(e) => p.setJobId(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {p.jobs.filter((j) => j.is_active).map((j) => (
            <option key={j.id} value={j.id}>{j.code} — {j.name}</option>
          ))}
        </select>
        <span className="field-hint">
          <button type="button" onClick={() => setAddJob((v) => !v)}>
            {addJob ? 'انصراف' : 'شغل تازه بسازید'}
          </button>
        </span>
      </label>
      <label>
        <span>مرکز هزینه</span>
        <select value={p.costCenterId} onChange={(e) => p.setCostCenterId(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {p.costCenters.map((c) => (
            <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
          ))}
        </select>
        <span className="field-hint">هزینه‌ی حقوقِ این نفر به این مرکز می‌رود.</span>
      </label>

      {/* ساختِ درجا — همان رفتارِ سپیدار: اگر عنوانِ موردنظر در فهرست نبود، کاربر
          باید همان‌جا بسازدش بی‌آنکه فرمِ قرارداد را ترک کند و ورودی‌هایش برود. */}
      {addLocation && (
        <InlineCreate
          label="محل خدمت تازه"
          fields={[
            { key: 'code', label: 'کد', required: true },
            { key: 'name', label: 'عنوان', required: true },
          ]}
          onCreate={async (values) => {
            const row = await createServiceLocation(p.token, { code: values.code, name: values.name })
            p.setLocations([...p.locations, row])
            p.setLocationId(row.id)
            setAddLocation(false)
          }}
        />
      )}
      {addJob && (
        <InlineCreate
          label="شغل تازه"
          fields={[
            { key: 'code', label: 'کد', required: true },
            { key: 'name', label: 'عنوان', required: true },
            { key: 'job_family', label: 'رسته شغل', options: JOB_FAMILIES },
          ]}
          onCreate={async (values) => {
            const row = await createJobTitle(p.token, {
              code: values.code, name: values.name, job_family: values.job_family ?? '',
            })
            p.setJobs([...p.jobs, row])
            p.setJobId(row.id)
            setAddJob(false)
          }}
        />
      )}
    </div>
  )
}

// ── ساختِ درجای یک رکوردِ مرجع ────────────────────────────────────────────────

function InlineCreate({
  label,
  fields,
  onCreate,
}: {
  label: string
  fields: { key: string; label: string; required?: boolean; options?: string[] }[]
  onCreate: (values: Record<string, string>) => Promise<void>
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ready = fields.every((f) => !f.required || (values[f.key] ?? '').trim())

  async function go() {
    setBusy(true)
    setError(null)
    try {
      await onCreate(values)
      setValues({})
    } catch (err) {
      setError(errText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="cmp-form-wide fy-status">
      <div className="pz-effects-head">{label}</div>
      <div className="cmp-form">
        {fields.map((f) => (
          <label key={f.key}>
            <span>{f.label}{f.required ? ' *' : ''}</span>
            {f.options ? (
              <select value={values[f.key] ?? ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}>
                <option value="">— انتخاب کنید —</option>
                {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input value={values[f.key] ?? ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
            )}
          </label>
        ))}
        <div className="invoice-form-footer">
          <button type="button" onClick={go} disabled={busy || !ready}>
            <Plus size={13} /> بساز و انتخاب کن
          </button>
        </div>
        {error && <p className="cmp-form-wide fy-note fy-note--err">{error}</p>}
      </div>
    </section>
  )
}

// ── تبِ ردیف‌های مبلغ ─────────────────────────────────────────────────────────

function LinesTab({
  title,
  hint,
  factors,
  rows,
  setRows,
  total,
  onSeed,
}: {
  title: string
  hint: string
  factors: PayrollFactorRecord[]
  rows: DraftLine[]
  setRows: Setter<DraftLine[]>
  total: number
  onSeed?: () => void
}) {
  return (
    <div className="cmp-form">
      <p className="muted cmp-form-wide">{hint}</p>
      {factors.length === 0 ? (
        <div className="cmp-form-wide">
          <p className="muted">
            هنوز عاملی تعریف نشده.
            {onSeed && ' عوامل پیش‌فرض (حقوق پایه، حق مسکن، حق خواروبار، حق اولاد) را بسازید:'}
          </p>
          {onSeed && (
            <button type="button" onClick={onSeed}><Plus size={13} /> ساخت عوامل پیش‌فرض</button>
          )}
        </div>
      ) : (
        <>
          <div className="cmp-form-wide table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>{title}</th>
                  <th>مبلغ (ریال)</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td className="card-title" data-label={title} colSpan={3}>
                      هنوز ردیفی اضافه نشده.
                    </td>
                  </tr>
                ) : (
                  rows.map((row, i) => (
                    <tr key={`${row.factor_id}-${i}`}>
                      <td className="card-title" data-label="عامل">
                        <select
                          value={row.factor_id}
                          onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, factor_id: e.target.value } : r)))}
                        >
                          <option value="">— انتخاب کنید —</option>
                          {factors.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                        </select>
                      </td>
                      <td className="num" data-label="مبلغ">
                        <input
                          type="number"
                          min="0"
                          value={row.amount}
                          onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, amount: e.target.value } : r)))}
                        />
                      </td>
                      <td className="card-actions" data-label="">
                        <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                          <Trash2 size={13} /> حذف
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="cmp-form-wide invoice-form-footer">
            <button type="button" onClick={() => setRows([...rows, { factor_id: '', amount: '' }])}>
              <Plus size={13} /> افزودن ردیف
            </button>
            <strong>جمع: {fa(total)} ریال</strong>
          </div>
        </>
      )}
    </div>
  )
}

// ── تبِ سایر اطلاعات ─────────────────────────────────────────────────────────

function OtherTab(p: {
  taxGroups: PayrollTaxGroupRecord[]
  branches: InsuranceTaxBranchRecord[]
  taxGroupId: string; setTaxGroupId: Setter<string>
  taxBranchId: string; setTaxBranchId: Setter<string>
  insuranceBranchId: string; setInsuranceBranchId: Setter<string>
  housingLoanExempt: string; setHousingLoanExempt: Setter<string>
  isInsured: boolean; setIsInsured: Setter<boolean>
  isHardJob: boolean; setIsHardJob: Setter<boolean>
  exemptEmployee: boolean; setExemptEmployee: Setter<boolean>
  exemptEmployer: boolean; setExemptEmployer: Setter<boolean>
  employerExemptPercent: string; setEmployerExemptPercent: Setter<string>
  exemptUnemployment: boolean; setExemptUnemployment: Setter<boolean>
  employerName: string; setEmployerName: Setter<string>
  hasSupplementary: boolean; setHasSupplementary: Setter<boolean>
  supplementaryBranch: string; setSupplementaryBranch: Setter<string>
  supplementaryInsurer: string; setSupplementaryInsurer: Setter<string>
}) {
  const insurance = p.branches.filter((b) => b.kind === 'insurance' && b.is_active)
  const tax = p.branches.filter((b) => b.kind === 'tax' && b.is_active)

  return (
    <div className="cmp-form">
      <div className="cmp-form-wide pz-effects-head">مالیات</div>
      <label>
        <span>گروه مالیاتی</span>
        <select value={p.taxGroupId} onChange={(e) => p.setTaxGroupId(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {p.taxGroups.filter((g) => g.is_active).map((g) => (
            <option key={g.id} value={g.id}>
              {g.name} — {TAX_GROUP_KIND_LABELS[g.kind] ?? g.kind}
            </option>
          ))}
        </select>
        <span className="field-hint">مناطق عادی، مناطق محروم یا معاف — درصدِ وصولِ مالیات را تعیین می‌کند.</span>
      </label>
      <label>
        <span>حوزه مالیاتی</span>
        <select value={p.taxBranchId} onChange={(e) => p.setTaxBranchId(e.target.value)}>
          <option value="">— انتخاب کنید —</option>
          {tax.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </label>
      <label>
        <span>قسط وام مسکن معاف از مالیات (ریال)</span>
        <input type="number" min="0" value={p.housingLoanExempt}
               onChange={(e) => p.setHousingLoanExempt(e.target.value)} placeholder="۰" />
      </label>

      <div className="cmp-form-wide pz-effects-head">بیمه</div>
      <div className="cmp-form-wide role-picker">
        <label className="fy-check">
          <input type="checkbox" checked={p.isInsured} onChange={(e) => p.setIsInsured(e.target.checked)} />
          مشمول بیمه تأمین اجتماعی
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.isHardJob} onChange={(e) => p.setIsHardJob(e.target.checked)} />
          شغل سخت و زیان‌آور
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.exemptEmployee} onChange={(e) => p.setExemptEmployee(e.target.checked)} />
          معاف از بیمه سهم کارمند
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.exemptEmployer} onChange={(e) => p.setExemptEmployer(e.target.checked)} />
          معاف از بیمه سهم کارفرما
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.exemptUnemployment} onChange={(e) => p.setExemptUnemployment(e.target.checked)} />
          معاف از بیمه بیکاری
        </label>
      </div>
      {p.isInsured && (
        <label>
          <span>شعبه بیمه</span>
          <select value={p.insuranceBranchId} onChange={(e) => p.setInsuranceBranchId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {insurance.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
      )}
      {p.exemptEmployer && (
        <label>
          <span>درصد معافیت سهم کارفرما</span>
          <input type="number" min="0" max="100" step="0.01" value={p.employerExemptPercent}
                 onChange={(e) => p.setEmployerExemptPercent(e.target.value)} placeholder="۰" />
        </label>
      )}
      <label>
        <span>کارفرما</span>
        <input value={p.employerName} onChange={(e) => p.setEmployerName(e.target.value)} maxLength={200} />
      </label>

      <div className="cmp-form-wide pz-effects-head">بیمه تکمیلی</div>
      <div className="cmp-form-wide role-picker">
        <label className="fy-check">
          <input type="checkbox" checked={p.hasSupplementary} onChange={(e) => p.setHasSupplementary(e.target.checked)} />
          مشمول بیمه تکمیلی
        </label>
      </div>
      {p.hasSupplementary && (
        <>
          <label>
            <span>شعبه</span>
            <input value={p.supplementaryBranch} onChange={(e) => p.setSupplementaryBranch(e.target.value)} maxLength={150} />
          </label>
          <label>
            <span>نام بیمه</span>
            <input value={p.supplementaryInsurer} onChange={(e) => p.setSupplementaryInsurer(e.target.value)} maxLength={150} />
          </label>
        </>
      )}
    </div>
  )
}
