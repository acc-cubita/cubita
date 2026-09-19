import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, ClipboardList, FileSignature, List, Plus, Save, Sparkles, Trash2, X } from 'lucide-react'
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
import { NumberInput } from '../../components/NumberInput'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { ActionBar, FormField, FormGrid, FormTabs, SelectWithAdd, TabHead } from '../../components/form/FormKit'
import type { PageKey } from '../../lib/navModel'
import { EmployeePicker } from './EmployeePicker'

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
 *
 * چیدمان با اجزای فرمِ سازمانی (`components/form/FormKit`) است: دو کارتِ جدا (مشخصات و
 * جزئیات)، گریدِ حداکثر سه‌ستونه با فیلدهای هم‌ارتفاع، راهنما در «؟» کنارِ برچسب، و
 * نوارِ عملیاتِ چسبیده به پایین.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

type Msg = { text: string; kind: 'ok' | 'err' } | null
type DraftLine = { factor_id: string; amount: string }
type TabKey = 'employment' | 'pay' | 'deductions' | 'other' | 'notes'

const EMPLOYEE_FIELD_ID = 'contract-employee'

export function ContractFormPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey) => void
}) {
  const [locations, setLocations] = useState<ServiceLocationRecord[]>([])
  const [jobs, setJobs] = useState<JobTitleRecord[]>([])
  const [factors, setFactors] = useState<PayrollFactorRecord[]>([])
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [taxGroups, setTaxGroups] = useState<PayrollTaxGroupRecord[]>([])
  const [branches, setBranches] = useState<InsuranceTaxBranchRecord[]>([])

  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<TabKey>('employment')

  // ── مشخصات ──
  const [employee, setEmployee] = useState<EmployeeCandidate | null>(null)
  const contactId = employee?.contact_id ?? ''
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
    //: مرکزِ غیرفعال دیگر برچسب نمی‌خورد (سرور هم ردش می‌کند)، پس اصلاً پیشنهاد
    //: نمی‌شود — همان کاری که چهار فرمِ دیگر از قبل می‌کردند و این‌جا جا افتاده بود.
    setCostCenters(cc.filter((c) => c.is_active))
    setTaxGroups(tax)
    setBranches(br)
  }

  useEffect(() => {
    void loadRefs()
  }, [token])

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
      document.getElementById(EMPLOYEE_FIELD_ID)?.focus()
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
        text: `${CONTRACT_TYPE_LABELS[contractType]} برای «${employee?.name ?? ''}» ثبت شد.`,
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

  //: نوارِ پایین همیشه چیزی مفید می‌گوید: نتیجه‌ی آخرین ثبت، وگرنه جمعِ ماهانه‌ی قرارداد.
  const status = msg ? (
    <span className={msg.kind === 'ok' ? 'is-ok' : 'is-err'} role={msg.kind === 'ok' ? 'status' : 'alert'}>
      {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />} {msg.text}
    </span>
  ) : payTotal > 0 ? (
    <span>
      جمعِ حقوق و مزایای ثابت: <b>{fa(payTotal)}</b> ریال
      {deductionTotal > 0 && <> · کسورات: <b>{fa(deductionTotal)}</b> ریال</>}
    </span>
  ) : null

  return (
    <div className="page panels">
      <PageHeader
        icon={FileSignature}
        title="قرارداد جدید"
        description="استخدام یا اصلاحِ قرارداد یک کارمند — با اطلاعات استخدامی، حقوق و مزایای ثابت، کسورات و اطلاعات بیمه و مالیات."
      />

      <form className="ef-form" onSubmit={submit} noValidate>
        <SectionCard icon={FileSignature} title="مشخصات قرارداد">
          <FormGrid>
            <FormField
              id={EMPLOYEE_FIELD_ID}
              label="نام کارمند"
              required
              tip="فهرست از طرف‌حساب‌هایی می‌آید که تیکِ «کارمند» دارند. اگر کسی نیست، اول او را در «شرکت ← طرف حساب جدید» با تیکِ کارمند ثبت کنید."
            >
              {(id) => <EmployeePicker id={id} token={token} selected={employee} onSelect={setEmployee} />}
            </FormField>
            <FormField
              label="نوع قرارداد"
              required
              tip={
                allowedTypes.includes('hire')
                  ? 'اولین قراردادِ این شخص است، پس «استخدام» است.'
                  : 'استخدامِ این شخص از قبل ثبت شده، پس تغییرِ بعدی «اصلاح قرارداد» است.'
              }
            >
              {(id) => (
                <select id={id} value={contractType} onChange={(e) => setContractType(e.target.value)}>
                  {allowedTypes.map((t) => (
                    <option key={t} value={t}>
                      {CONTRACT_TYPE_LABELS[t] ?? t}
                    </option>
                  ))}
                </select>
              )}
            </FormField>
            <FormField label="شماره" tip="شماره‌ی داخلیِ قرارداد، اگر دارید — اختیاری.">
              {(id) => <input id={id} dir="ltr" value={number} onChange={(e) => setNumber(e.target.value)} maxLength={30} />}
            </FormField>

            <FormField label="تاریخ صدور" required tip="محاسبه‌ی حقوق از این تاریخ شروع می‌شود.">
              {(id) => <JalaliDatePicker id={id} value={issueDate} onChange={setIssueDate} />}
            </FormField>
            <FormField label="تاریخ اعتبار" tip="تا این تاریخ طبقِ همین قرارداد محاسبه می‌شود.">
              {(id) => <JalaliDatePicker id={id} value={validUntil} onChange={setValidUntil} />}
            </FormField>
            <FormField label="تاریخ پایان خدمت" tip="از این تاریخ به بعد کارکرد محاسبه نمی‌شود.">
              {(id) => <JalaliDatePicker id={id} value={serviceEnd} onChange={setServiceEnd} />}
            </FormField>
          </FormGrid>
        </SectionCard>

        <SectionCard icon={ClipboardList} title="جزئیات">
          <FormTabs
            label="جزئیاتِ قرارداد"
            active={tab}
            onChange={(k) => setTab(k as TabKey)}
            tabs={[
              { key: 'employment', label: 'اطلاعات استخدامی' },
              { key: 'pay', label: 'حقوق و مزایای ثابت', badge: payLines.length ? fa(payLines.length) : undefined },
              { key: 'deductions', label: 'سایر مبالغ', badge: deductionLines.length ? fa(deductionLines.length) : undefined },
              { key: 'other', label: 'سایر اطلاعات' },
              { key: 'notes', label: 'شرح' },
            ]}
          >
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
                tip="ردیفِ «حقوق پایه» الزامی است. عواملی که خودتان می‌سازید در «سایر مزایا» جمع می‌شوند و محاسبه را نمی‌شکنند."
                emptyText="هنوز عاملی برای حقوق و مزایا تعریف نشده."
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
                tip="کسوراتِ ثابت مثلِ بیمه‌ی تکمیلی — هر ماه از خالصِ فیش کم می‌شوند. اقساطِ وامِ پرسنلی جای خودش را دارد و خودکار کسر می‌شود؛ اگر این‌جا هم بنویسیدش، دو بار از حقوق کم می‌شود."
                emptyText="هنوز عاملِ کسوراتی تعریف نشده — از «حقوق و دستمزد ← عوامل حقوق و مزایا» بسازید."
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
              <FormGrid>
                <FormField label="شرح" span="full">
                  {(id) => <textarea id={id} rows={5} value={description} onChange={(e) => setDescription(e.target.value)} />}
                </FormField>
              </FormGrid>
            )}
          </FormTabs>
        </SectionCard>

        <ActionBar status={status}>
          <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('contractlist')}>
            <List size={15} /> فهرست قراردادها
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={15} /> {busy ? 'در حال ثبت…' : 'ثبت قرارداد'}
          </button>
        </ActionBar>
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
    <FormGrid>
      {/* عمداً جدا از تاریخِ صدور: شرکتی که تا دیروز با اکسل حقوق می‌داد، کارمندش را
          که تازه استخدام نکرده. این تاریخ روی خودِ کارمند می‌نشیند. */}
      <FormField label="تاریخ استخدام" tip="تاریخِ واقعیِ شروعِ کار — می‌تواند خیلی قبل‌تر از تاریخ صدور باشد.">
        {(id) => <JalaliDatePicker id={id} value={p.hireDate} onChange={p.setHireDate} />}
      </FormField>
      <FormField label="نوع استخدام">
        {(id) => (
          <select id={id} value={p.employmentType} onChange={(e) => p.setEmploymentType(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {EMPLOYMENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <FormField label="مرکز هزینه" tip="هزینه‌ی حقوقِ این نفر به این مرکز می‌رود.">
        {(id) => (
          <select id={id} value={p.costCenterId} onChange={(e) => p.setCostCenterId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {p.costCenters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
        )}
      </FormField>

      <FormField label="محل خدمت">
        {(id) => (
          <SelectWithAdd
            id={id}
            value={p.locationId}
            onChange={p.setLocationId}
            options={p.locations.filter((l) => l.is_active).map((l) => ({ value: l.id, label: `${l.code} — ${l.name}` }))}
            addLabel="افزودن محل خدمت تازه"
            adding={addLocation}
            onToggleAdd={() => setAddLocation((v) => !v)}
          />
        )}
      </FormField>
      <FormField label="شغل">
        {(id) => (
          <SelectWithAdd
            id={id}
            value={p.jobId}
            onChange={p.setJobId}
            options={p.jobs.filter((j) => j.is_active).map((j) => ({ value: j.id, label: `${j.code} — ${j.name}` }))}
            addLabel="افزودن شغل تازه"
            adding={addJob}
            onToggleAdd={() => setAddJob((v) => !v)}
          />
        )}
      </FormField>

      {/* ساختِ درجا — همان رفتارِ سپیدار: اگر عنوانِ موردنظر در فهرست نبود، کاربر
          باید همان‌جا بسازدش بی‌آنکه فرمِ قرارداد را ترک کند و ورودی‌هایش برود. */}
      {addLocation && (
        <InlineCreate
          label="محل خدمت تازه"
          onClose={() => setAddLocation(false)}
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
          onClose={() => setAddJob(false)}
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
    </FormGrid>
  )
}

// ── ساختِ درجای یک رکوردِ مرجع ────────────────────────────────────────────────

function InlineCreate({
  label,
  fields,
  onCreate,
  onClose,
}: {
  label: string
  fields: { key: string; label: string; required?: boolean; options?: string[] }[]
  onCreate: (values: Record<string, string>) => Promise<void>
  onClose: () => void
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
    <section className="ef-inline-create" aria-label={label}>
      <div className="ef-inline-create-head">
        {label}
        <button type="button" className="ef-tip-btn" onClick={onClose} aria-label="بستن">
          <X size={14} />
        </button>
      </div>
      <FormGrid>
        {fields.map((f) => (
          <FormField key={f.key} label={f.label} required={f.required}>
            {(id) =>
              f.options ? (
                <select id={id} value={values[f.key] ?? ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}>
                  <option value="">— انتخاب کنید —</option>
                  {f.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input id={id} value={values[f.key] ?? ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
              )
            }
          </FormField>
        ))}
      </FormGrid>
      <div className="ef-inline-create-foot">
        <button type="button" className="btn-primary" onClick={go} disabled={busy || !ready}>
          <Plus size={14} /> بساز و انتخاب کن
        </button>
        {error && <p className="ef-message ef-message--warn">{error}</p>}
      </div>
    </section>
  )
}

// ── تبِ ردیف‌های مبلغ ─────────────────────────────────────────────────────────

function LinesTab({
  title,
  tip,
  emptyText,
  factors,
  rows,
  setRows,
  total,
  onSeed,
}: {
  title: string
  tip: string
  emptyText: string
  factors: PayrollFactorRecord[]
  rows: DraftLine[]
  setRows: Setter<DraftLine[]>
  total: number
  onSeed?: () => void
}) {
  const update = (i: number, patch: Partial<DraftLine>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  return (
    <div>
      <TabHead
        title={title}
        tip={tip}
        actions={
          factors.length === 0 ? (
            onSeed && (
              <button type="button" onClick={onSeed}>
                <Sparkles size={14} /> ساخت عوامل پیش‌فرض
              </button>
            )
          ) : (
            <button type="button" onClick={() => setRows([...rows, { factor_id: '', amount: '' }])}>
              <Plus size={14} /> افزودن ردیف
            </button>
          )
        }
      />

      {factors.length === 0 ? (
        <div className="ef-empty">{emptyText}</div>
      ) : rows.length === 0 ? (
        <div className="ef-empty">هنوز ردیفی اضافه نشده — «افزودن ردیف» را بزنید.</div>
      ) : (
        <>
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>عامل</th>
                  <th>مبلغ (ریال)</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={`${row.factor_id}-${i}`}>
                    <td className="card-title" data-label="عامل">
                      <select aria-label="عامل" value={row.factor_id} onChange={(e) => update(i, { factor_id: e.target.value })}>
                        <option value="">— انتخاب کنید —</option>
                        {factors.map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="num" data-label="مبلغ (ریال)">
                      <NumberInput aria-label="مبلغ (ریال)" value={row.amount} onChange={(v) => update(i, { amount: v })} />
                    </td>
                    <td className="card-actions">
                      <button type="button" className="ef-icon-btn" onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="حذفِ ردیف" title="حذفِ ردیف">
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="ef-lines-total">
            جمع: <b>{fa(total)}</b> ریال
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
  const check = (checked: boolean, set: Setter<boolean>, text: string) => (
    <label className="fy-check">
      <input type="checkbox" checked={checked} onChange={(e) => set(e.target.checked)} />
      {text}
    </label>
  )

  return (
    <FormGrid>
      <div className="ef-subhead">مالیات</div>
      <FormField label="گروه مالیاتی" tip="مناطق عادی، مناطق محروم یا معاف — درصدِ وصولِ مالیات را تعیین می‌کند.">
        {(id) => (
          <select id={id} value={p.taxGroupId} onChange={(e) => p.setTaxGroupId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {p.taxGroups.filter((g) => g.is_active).map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} — {TAX_GROUP_KIND_LABELS[g.kind] ?? g.kind}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <FormField label="حوزه مالیاتی">
        {(id) => (
          <select id={id} value={p.taxBranchId} onChange={(e) => p.setTaxBranchId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {tax.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <FormField label="قسط وام مسکن معاف از مالیات (ریال)">
        {(id) => <NumberInput id={id} value={p.housingLoanExempt} onChange={p.setHousingLoanExempt} placeholder="۰" />}
      </FormField>

      <div className="ef-subhead">بیمه</div>
      <div className="ef-checks">
        {check(p.isInsured, p.setIsInsured, 'مشمول بیمه تأمین اجتماعی')}
        {check(p.isHardJob, p.setIsHardJob, 'شغل سخت و زیان‌آور')}
        {check(p.exemptEmployee, p.setExemptEmployee, 'معاف از بیمه سهم کارمند')}
        {check(p.exemptEmployer, p.setExemptEmployer, 'معاف از بیمه سهم کارفرما')}
        {check(p.exemptUnemployment, p.setExemptUnemployment, 'معاف از بیمه بیکاری')}
      </div>
      {p.isInsured && (
        <FormField label="شعبه بیمه">
          {(id) => (
            <select id={id} value={p.insuranceBranchId} onChange={(e) => p.setInsuranceBranchId(e.target.value)}>
              <option value="">— انتخاب کنید —</option>
              {insurance.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          )}
        </FormField>
      )}
      {p.exemptEmployer && (
        <FormField label="درصد معافیت سهم کارفرما">
          {(id) => (
            <NumberInput id={id} value={p.employerExemptPercent} onChange={p.setEmployerExemptPercent} allowDecimal placeholder="۰" />
          )}
        </FormField>
      )}
      <FormField label="کارفرما">
        {(id) => <input id={id} value={p.employerName} onChange={(e) => p.setEmployerName(e.target.value)} maxLength={200} />}
      </FormField>

      <div className="ef-subhead">بیمه تکمیلی</div>
      <div className="ef-checks">{check(p.hasSupplementary, p.setHasSupplementary, 'مشمول بیمه تکمیلی')}</div>
      {p.hasSupplementary && (
        <>
          <FormField label="شعبه">
            {(id) => <input id={id} value={p.supplementaryBranch} onChange={(e) => p.setSupplementaryBranch(e.target.value)} maxLength={150} />}
          </FormField>
          <FormField label="نام بیمه">
            {(id) => <input id={id} value={p.supplementaryInsurer} onChange={(e) => p.setSupplementaryInsurer(e.target.value)} maxLength={150} />}
          </FormField>
        </>
      )}
    </FormGrid>
  )
}
