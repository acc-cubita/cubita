import { useEffect, useState } from 'react'
import { Briefcase, Building2, Percent, Plus, Save, Landmark, SlidersHorizontal } from 'lucide-react'
import {
  BRANCH_KIND_LABELS,
  FACTOR_CATEGORY_LABELS,
  FACTOR_KIND_LABELS,
  JOB_FAMILIES,
  TAX_CALC_METHOD_LABELS,
  TAX_GROUP_KIND_LABELS,
  createDefaultPayrollFactors,
  createInsuranceTaxBranch,
  createJobTitle,
  createPayrollFactor,
  createPayrollTaxGroup,
  createServiceLocation,
  fetchContacts,
  fetchCostCenters,
  fetchInsuranceTaxBranches,
  fetchJobTitles,
  fetchPayrollFactors,
  setFactorParticipation,
  fetchPayrollTaxGroups,
  fetchServiceLocations,
  updateInsuranceTaxBranch,
  type ContactRecord,
  type CostCenterRecord,
  type InsuranceTaxBranchRecord,
  type JobTitleRecord,
  FACTOR_PURPOSE_LABELS,
  type PayrollFactorRecord,
  type PayrollTaxGroupRecord,
  type ServiceLocationRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { SectionCard } from '../../components/SectionCard'
import { AsyncBlock, Note, OpsPage, type Msg } from '../accounting/kit'

/**
 * جدول‌های مرجعِ حقوق و دستمزد — محل خدمت، شغل، عوامل، گروه مالیاتی، شعب.
 *
 * هر پنج‌تا یک شکل دارند: فرمِ ساختِ کوتاه در بالا، دفترِ همان رکوردها زیرش. عمداً
 * یک الگو، چون کاربر پنج فرمِ متفاوت را یاد نمی‌گیرد.
 *
 * **حذف عمداً نیست.** رکوردی که در قراردادی استفاده شده نباید ناپدید شود؛ «غیرفعال»
 * آن را از فهرستِ انتخابِ فرمِ قرارداد بیرون می‌برد بی‌آنکه قراردادهای قدیمی
 * بی‌مرجع شوند.
 *
 * همین کامپوننت‌ها در فرمِ قرارداد هم به‌صورتِ «ساختِ درجا» استفاده می‌شوند: وقتی
 * عنوانِ موردنظر در فهرست نیست، کاربر باید همان‌جا بسازدش بی‌آنکه فرم را ترک کند.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

// ── محل خدمت ─────────────────────────────────────────────────────────────────

export function ServiceLocationPage({ token }: { token: string }) {
  const [rows, setRows] = useState<ServiceLocationRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [name2, setName2] = useState('')

  async function refresh() {
    try {
      setRows(await fetchServiceLocations(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createServiceLocation(token, { code: code.trim(), name: name.trim(), name2: name2.trim() })
      setMsg({ text: `محل خدمت «${name.trim()}» ساخته شد.`, kind: 'ok' })
      setCode('')
      setName('')
      setName2('')
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Building2}
      title="محل خدمت جدید"
      description="جایی که کارمند واقعاً کار می‌کند: انبار، شعبه‌ی ۳ فروشگاه، دفتر مرکزی."
    >
      <SectionCard icon={Plus} title="ثبت محل خدمت">
        <form className="cmp-form" onSubmit={submit}>
          <p className="muted cmp-form-wide">
            محل خدمت جدا از مرکز هزینه است: مرکز هزینه می‌گوید هزینه به کدام حساب
            می‌رود، محل خدمت می‌گوید خودِ کارمند کجاست.
          </p>
          <label>
            <span>کد *</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} required />
          </label>
          <label>
            <span>عنوان *</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} required />
          </label>
          <label>
            <span>عنوان (۲)</span>
            <input dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />
            <span className="field-hint">اختیاری — معمولاً همان عنوان به لاتین.</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !code.trim() || !name.trim()}>
              <Save size={13} /> ثبت محل خدمت
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={Building2} title={rows ? `${fa(rows.length)} محل خدمت` : 'در حال بارگذاری…'}>
        <RefTable
          rows={rows}
          error={error}
          emptyText="هنوز محل خدمتی ثبت نشده — اولی را با فرمِ بالا بسازید."
          head={['کد', 'عنوان', 'عنوان (۲)', 'وضعیت']}
          render={(r) => [r.code, r.name, r.name2 || '—', r.is_active ? 'فعال' : 'غیرفعال']}
        />
      </SectionCard>
    </OpsPage>
  )
}

// ── شغل ──────────────────────────────────────────────────────────────────────

export function JobTitlePage({ token }: { token: string }) {
  const [rows, setRows] = useState<JobTitleRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [name2, setName2] = useState('')
  const [family, setFamily] = useState('')
  const [insuranceCode, setInsuranceCode] = useState('')

  async function refresh() {
    try {
      setRows(await fetchJobTitles(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createJobTitle(token, {
        code: code.trim(),
        name: name.trim(),
        name2: name2.trim(),
        job_family: family,
        insurance_job_code: insuranceCode.trim(),
      })
      setMsg({ text: `شغل «${name.trim()}» ساخته شد.`, kind: 'ok' })
      setCode('')
      setName('')
      setName2('')
      setInsuranceCode('')
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Briefcase}
      title="شغل جدید"
      description="عنوان‌های شغلی و رسته‌شان — همان فهرستی که فرمِ قرارداد از آن انتخاب می‌کند."
    >
      <SectionCard icon={Plus} title="ثبت شغل">
        <form className="cmp-form" onSubmit={submit}>
          <label>
            <span>کد *</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} required />
          </label>
          <label>
            <span>عنوان *</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} required />
          </label>
          <label>
            <span>عنوان (۲)</span>
            <input dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />
          </label>
          <label>
            <span>رسته شغل</span>
            <select value={family} onChange={(e) => setFamily(e.target.value)}>
              <option value="">— انتخاب کنید —</option>
              {JOB_FAMILIES.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </label>
          <label>
            <span>کد شغل بیمه</span>
            <input dir="ltr" value={insuranceCode} onChange={(e) => setInsuranceCode(e.target.value)} maxLength={30} />
            <span className="field-hint">در لیستِ تأمین اجتماعی لازم است؛ روی شغل می‌ماند تا هر بار تایپ نشود.</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !code.trim() || !name.trim()}>
              <Save size={13} /> ثبت شغل
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={Briefcase} title={rows ? `${fa(rows.length)} شغل` : 'در حال بارگذاری…'}>
        <RefTable
          rows={rows}
          error={error}
          emptyText="هنوز شغلی ثبت نشده — اولی را با فرمِ بالا بسازید."
          head={['کد', 'عنوان', 'رسته', 'کد بیمه', 'وضعیت']}
          render={(r) => [r.code, r.name, r.job_family || '—', r.insurance_job_code || '—', r.is_active ? 'فعال' : 'غیرفعال']}
        />
      </SectionCard>
    </OpsPage>
  )
}

// ── عوامل حقوق و مزایا ───────────────────────────────────────────────────────

//: ترتیبِ ستون‌های ماتریس — همان ترتیبی که موتور در آن حساب می‌کند:
//: اول مبناهای ماهانه (بیمه، مالیات)، بعد سه مبنای مزایا.
const PURPOSES = ['insurance_base', 'tax_base', 'eidi_base', 'severance_base', 'leave_base'] as const

export function PayrollFactorPage({ token }: { token: string }) {
  const [rows, setRows] = useState<PayrollFactorRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [name2, setName2] = useState('')
  const [category, setCategory] = useState('benefit')
  const [kind, setKind] = useState('fixed')
  const [extraordinary, setExtraordinary] = useState(false)

  async function refresh() {
    try {
      setRows(await fetchPayrollFactors(token))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  /** تیکِ یک خانه‌ی ماتریس. سرور ردیفِ برابرِ پیش‌فرض را پاک می‌کند، پس
   *  برگرداندنِ یک تیک به حالتِ اولش داده‌ی اضافه جا نمی‌گذارد. */
  async function toggle(row: PayrollFactorRecord, purpose: string, on: boolean) {
    setBusy(true)
    setMsg(null)
    try {
      await setFactorParticipation(token, row.id, { [purpose]: on ? 1 : 0 })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createPayrollFactor(token, {
        name: name.trim(),
        name2: name2.trim(),
        category,
        kind,
        is_extraordinary: extraordinary,
      })
      setMsg({ text: `عاملِ «${name.trim()}» ساخته شد.`, kind: 'ok' })
      setName('')
      setName2('')
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function seed() {
    setBusy(true)
    setMsg(null)
    try {
      const all = await createDefaultPayrollFactors(token)
      setRows(all)
      setMsg({ text: 'عوامل پیش‌فرض آماده شدند.', kind: 'ok' })
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={SlidersHorizontal}
      title="عوامل حقوق و مزایا"
      description="حقوق پایه، حق اولاد، حق مسکن، حق خواروبار و هر عاملِ دیگری که خودتان می‌سازید."
    >
      <SectionCard
        icon={Plus}
        title="ثبت عامل"
        actions={
          <button type="button" onClick={seed} disabled={busy}>
            ساخت عوامل پیش‌فرض
          </button>
        }
      >
        <form className="cmp-form" onSubmit={submit}>
          <p className="muted cmp-form-wide">
            «مزایا» به حقوق اضافه می‌شود و «کسورات» از آن کم — مثلِ بیمه‌ی تکمیلی و
            اقساطِ وام. عوامل پیش‌فرض همان چهارتایی‌اند که موتورِ فیشِ حقوقی
            می‌شناسدشان؛ بقیه در «سایر مزایا» جمع می‌شوند.
          </p>
          <label>
            <span>عنوان *</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} required />
          </label>
          <label>
            <span>عنوان (۲)</span>
            <input dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />
          </label>
          <label>
            <span>طبقه</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {Object.entries(FACTOR_CATEGORY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            <span>نوع</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {Object.entries(FACTOR_KIND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <div className="cmp-form-wide role-picker">
            <label className="fy-check">
              <input type="checkbox" checked={extraordinary} onChange={(e) => setExtraordinary(e.target.checked)} />
              فوق‌العاده است
            </label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
              <Save size={13} /> ثبت عامل
            </button>
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={SlidersHorizontal} title={rows ? `${fa(rows.length)} عامل` : 'در حال بارگذاری…'}>
        <RefTable
          rows={rows}
          error={error}
          emptyText="هنوز عاملی نیست — «ساخت عوامل پیش‌فرض» را بزنید تا چهار عاملِ اصلی ساخته شوند."
          head={['عنوان', 'طبقه', 'نوع', 'فوق‌العاده', 'وضعیت']}
          render={(r) => [
            r.name,
            FACTOR_CATEGORY_LABELS[r.category] ?? r.category,
            FACTOR_KIND_LABELS[r.kind] ?? r.kind,
            r.is_extraordinary ? 'بله' : 'خیر',
            r.is_active ? 'فعال' : 'غیرفعال',
          ]}
        />
      </SectionCard>

      <SectionCard
        icon={SlidersHorizontal}
        title="مشارکت عوامل در مبناها"
        description="هر عامل در کدام محاسبه شمرده شود. تیک‌ها پیش‌فرضِ امروز را نشان می‌دهند؛ تا دست نزنید هیچ عددی عوض نمی‌شود."
      >
        <p className="field-hint">
          «مشمولِ بیمه» یک پرچمِ واحد نیست: یک عامل می‌تواند مبنای بیمه را بسازد ولی در مبنای عیدی نیاید.
          پیش‌فرضِ مبنای بیمه و مالیات «همهٔ عوامل» است و پیش‌فرضِ سه مبنای مزایا «فقط حقوق پایه» —
          دقیقاً همان فرمولی که تا امروز اجرا می‌شد.
        </p>
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText="اول یک عامل بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>عامل</th>
                  {PURPOSES.map((key) => <th key={key}>{FACTOR_PURPOSE_LABELS[key]}</th>)}
                </tr>
              </thead>
              <tbody>
                {(rows ?? []).map((row) => (
                  <tr key={row.id}>
                    <td className="card-title" data-label="عامل">{row.name}</td>
                    {PURPOSES.map((key) => (
                      <td key={key} data-label={FACTOR_PURPOSE_LABELS[key]}>
                        <input
                          type="checkbox"
                          checked={Number(row.participation?.[key] ?? 0) > 0}
                          disabled={busy}
                          onChange={(e) => void toggle(row, key, e.target.checked)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
        <Note msg={msg} />
      </SectionCard>
    </OpsPage>
  )
}

// ── گروه مالیاتی و شعب ───────────────────────────────────────────────────────

/**
 * فرمِ شعبه‌ی قانونی — **یک فرم برای هر سه نوع**.
 *
 * همه‌ی میدان‌ها همیشه در فرم هستند، ولی همه‌شان برای همه‌ی نوع‌ها معنا ندارند:
 * «نحوه محاسبه مالیات» فقط برای حوزه‌ی مالیاتی است، و پنهان‌کردنش این‌جا فقط
 * نیمی از کار است — سرور هم همان قید را دارد، چون یک درخواستِ مستقیمِ API
 * می‌تواند مرورگر را دور بزند.
 */
type BranchForm = {
  kind: string
  name: string
  code: string
  contact_id: string
  registration_code: string
  workplace_name: string
  workplace_address: string
  employer_name: string
  agreement_number: string
  insurance_exempt_count: string
  cost_center_id: string
  tax_calculation_method: string
}

const EMPTY_BRANCH: BranchForm = {
  kind: 'insurance',
  name: '',
  code: '',
  contact_id: '',
  registration_code: '',
  workplace_name: '',
  workplace_address: '',
  employer_name: '',
  agreement_number: '',
  insurance_exempt_count: '',
  cost_center_id: '',
  tax_calculation_method: '',
}

export function PayrollTaxGroupPage({ token }: { token: string }) {
  const [rows, setRows] = useState<PayrollTaxGroupRecord[] | null>(null)
  const [branches, setBranches] = useState<InsuranceTaxBranchRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [kind, setKind] = useState('normal')
  const [percent, setPercent] = useState('')
  const [form, setForm] = useState(EMPTY_BRANCH)
  //: خالی = «شعبه‌ی تازه». پر = همان شعبه دارد ویرایش می‌شود.
  const [editingBranch, setEditingBranch] = useState<InsuranceTaxBranchRecord | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])

  const set = (patch: Partial<BranchForm>) => setForm((f) => ({ ...f, ...patch }))

  async function refresh() {
    try {
      const [groups, allBranches, allContacts, allCenters] = await Promise.all([
        fetchPayrollTaxGroups(token),
        fetchInsuranceTaxBranches(token),
        fetchContacts(token),
        fetchCostCenters(token),
      ])
      setRows(groups)
      setBranches(allBranches)
      setContacts(allContacts.filter((c) => c.is_active))
      setCostCenters(allCenters)
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  function editBranch(branch: InsuranceTaxBranchRecord) {
    setEditingBranch(branch)
    setForm({
      kind: branch.kind,
      name: branch.name,
      code: branch.code,
      contact_id: branch.contact_id ?? '',
      registration_code: branch.registration_code,
      workplace_name: branch.workplace_name,
      workplace_address: branch.workplace_address,
      employer_name: branch.employer_name,
      agreement_number: branch.agreement_number,
      insurance_exempt_count: String(branch.insurance_exempt_count || ''),
      cost_center_id: branch.cost_center_id ?? '',
      tax_calculation_method: branch.tax_calculation_method,
    })
    setMsg(null)
  }

  function clearBranchForm() {
    setEditingBranch(null)
    setForm(EMPTY_BRANCH)
    setMsg(null)
  }

  useEffect(() => {
    void refresh()
  }, [token])

  async function submitGroup(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await createPayrollTaxGroup(token, {
        name: name.trim(),
        kind,
        ...(percent.trim() ? { percent: percent.trim() } : {}),
      })
      setMsg({ text: `گروه مالیاتی «${name.trim()}» ساخته شد.`, kind: 'ok' })
      setName('')
      setPercent('')
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function submitBranch(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      const body = {
        kind: form.kind,
        name: form.name.trim(),
        code: form.code.trim(),
        contact_id: form.contact_id || null,
        registration_code: form.registration_code.trim(),
        workplace_name: form.workplace_name.trim(),
        workplace_address: form.workplace_address.trim(),
        employer_name: form.employer_name.trim(),
        agreement_number: form.agreement_number.trim(),
        insurance_exempt_count: Number(form.insurance_exempt_count || 0),
        cost_center_id: form.cost_center_id || null,
        //: روشِ مالیات فقط با نوعِ مالیاتی فرستاده می‌شود. اگر کاربر نوع را بعدِ
        //: پرکردنش عوض کرده باشد، فرستادنش ۴۰۰ می‌گیرد — و همان مقدارِ جامانده
        //: چیزی است که کاربر دیگر نمی‌بیند تا پاکش کند.
        tax_calculation_method: form.kind === 'tax' ? form.tax_calculation_method : '',
      }
      if (editingBranch) {
        await updateInsuranceTaxBranch(token, editingBranch.id, body)
        setMsg({ text: `«${body.name}» به‌روز شد.`, kind: 'ok' })
      } else {
        await createInsuranceTaxBranch(token, body)
        setMsg({ text: `«${body.name}» ساخته شد.`, kind: 'ok' })
      }
      setEditingBranch(null)
      setForm(EMPTY_BRANCH)
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Percent}
      title="گروه مالیاتی و شعب"
      description="گروه‌های مالیاتی (مناطق عادی، محروم، معاف) و شعبه‌های بیمه و حوزه‌های مالیاتی."
    >
      <SectionCard icon={Percent} title="گروه مالیاتی جدید">
        <form className="cmp-form" onSubmit={submitGroup}>
          <p className="muted cmp-form-wide">
            درصد می‌گوید چند درصد از مالیاتِ محاسبه‌شده واقعاً وصول می‌شود: مناطق محروم
            نصف، معاف صفر. خالی بگذارید تا پیش‌فرضِ همان نوع بنشیند.
          </p>
          <label>
            <span>عنوان *</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} required />
          </label>
          <label>
            <span>نوع</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {Object.entries(TAX_GROUP_KIND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            <span>درصد</span>
            <input type="number" min="0" max="100" step="0.01" value={percent}
                   onChange={(e) => setPercent(e.target.value)} placeholder="پیش‌فرضِ نوع" />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
              <Save size={13} /> ثبت گروه
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        icon={Landmark}
        title={editingBranch ? `ویرایش «${editingBranch.name}»` : 'شعبه بیمه یا حوزه مالیاتی جدید'}
      >
        <form className="cmp-form" onSubmit={submitBranch}>
          <label>
            <span>نوع</span>
            <select
              value={form.kind}
              onChange={(e) => set({ kind: e.target.value })}
              disabled={editingBranch?.in_use}
            >
              {Object.entries(BRANCH_KIND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            {editingBranch?.in_use ? (
              <span className="field-hint">
                این شعبه روی حکم‌های حقوقی استفاده شده و نوعش دیگر عوض نمی‌شود. اگر نوعش
                اشتباه بوده، شعبه‌ی درست را بسازید و حکم‌ها را به آن ببرید.
              </span>
            ) : null}
          </label>
          <label>
            <span>عنوان *</span>
            <input value={form.name} onChange={(e) => set({ name: e.target.value })} maxLength={150} required />
          </label>
          <label>
            <span>کد تفصیلی شعبه</span>
            <input dir="ltr" value={form.code} onChange={(e) => set({ code: e.target.value })} maxLength={20} />
          </label>
          <label>
            <span>طرف حساب سازمان</span>
            <select value={form.contact_id} onChange={(e) => set({ contact_id: e.target.value })}>
              <option value="">— وصل نشده —</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <span className="field-hint">
              بدهیِ بیمه و مالیاتِ حقوق به همین سازمان پرداخت می‌شود؛ با این پیوند، مانده و
              تفصیلی‌اش در دفتر پیدا می‌شود. خالی گذاشتنش چیزی را خراب نمی‌کند.
            </span>
          </label>

          <label>
            <span>کد شرکت / شماره پرونده</span>
            <input
              dir="ltr"
              value={form.registration_code}
              onChange={(e) => set({ registration_code: e.target.value })}
              maxLength={50}
            />
            <span className="field-hint">
              {form.kind === 'tax' ? 'شماره پرونده مالیاتی.' : 'کد کارگاه نزد مرجع.'}
            </span>
          </label>
          <label>
            <span>نام کارگاه</span>
            <input
              value={form.workplace_name}
              onChange={(e) => set({ workplace_name: e.target.value })}
              maxLength={200}
            />
            <span className="field-hint">
              کارگاهِ ثبت‌شده نزد مرجع — با «محل خدمت» یکی نیست.
            </span>
          </label>
          <label className="cmp-form-wide">
            <span>نشانی کارگاه</span>
            <input
              value={form.workplace_address}
              onChange={(e) => set({ workplace_address: e.target.value })}
            />
          </label>
          <label>
            <span>نام کارفرما</span>
            <input
              value={form.employer_name}
              onChange={(e) => set({ employer_name: e.target.value })}
              maxLength={200}
            />
          </label>
          <label>
            <span>شماره پیمان</span>
            <input
              dir="ltr"
              value={form.agreement_number}
              onChange={(e) => set({ agreement_number: e.target.value })}
              maxLength={50}
            />
            <span className="field-hint">
              قرارداد کارفرما با مرجع قانونی — نه قرارداد استخدامی کارمند.
            </span>
          </label>
          <label>
            <span>نفرات معاف از بیمه</span>
            <input
              dir="ltr"
              type="number"
              min={0}
              value={form.insurance_exempt_count}
              onChange={(e) => set({ insurance_exempt_count: e.target.value })}
            />
            <span className="field-hint">
              عددِ سرصفحه‌ی ثبت کارگاه. معافیتِ هر کارمند روی حکمِ خودش تعیین می‌شود و این
              عدد در هیچ محاسبه‌ای استفاده نمی‌شود.
            </span>
          </label>
          <label>
            <span>مرکز هزینه</span>
            <select value={form.cost_center_id} onChange={(e) => set({ cost_center_id: e.target.value })}>
              <option value="">— ندارد —</option>
              {costCenters.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>

          {/* فقط برای حوزه مالیاتی — سرور هم همین را می‌سنجد، نه فقط این‌جا. */}
          {form.kind === 'tax' ? (
            <label>
              <span>نحوه محاسبه مالیات</span>
              <select
                value={form.tax_calculation_method}
                onChange={(e) => set({ tax_calculation_method: e.target.value })}
              >
                <option value="">— تعیین نشده —</option>
                {Object.entries(TAX_CALC_METHOD_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <span className="field-hint">
                فعلاً ثبت می‌شود ولی در محاسبه‌ی مالیات اعمال نمی‌شود؛ موتور امروز تعدیل
                تجمیعی انجام می‌دهد.
              </span>
            </label>
          ) : null}

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !form.name.trim()}>
              <Save size={13} /> {editingBranch ? 'ذخیره تغییرات' : 'ثبت شعبه'}
            </button>
            {editingBranch ? (
              <button type="button" onClick={clearBranchForm} disabled={busy}>
                انصراف
              </button>
            ) : null}
          </div>
          <Note msg={msg} />
        </form>
      </SectionCard>

      <SectionCard icon={Percent} title={rows ? `${fa(rows.length)} گروه مالیاتی` : 'در حال بارگذاری…'}>
        <RefTable
          rows={rows}
          error={error}
          emptyText="هنوز گروه مالیاتی‌ای ثبت نشده."
          head={['عنوان', 'نوع', 'درصد']}
          render={(r) => [r.name, TAX_GROUP_KIND_LABELS[r.kind] ?? r.kind, `${fa(Number(r.percent))}٪`]}
        />
      </SectionCard>

      <SectionCard icon={Landmark} title={branches ? `${fa(branches.length)} شعبه` : 'در حال بارگذاری…'}>
        <RefTable
          rows={branches}
          error={error}
          emptyText="هنوز شعبه‌ای ثبت نشده."
          head={[
            'عنوان',
            'نوع',
            'کد تفصیلی شعبه',
            'طرف حساب سازمان',
            'کد شرکت / شماره پرونده',
            'شماره پیمان',
            'نفرات معاف از بیمه',
            'نحوه محاسبه مالیات',
            'نام کارگاه',
            'نام کارفرما',
            'نشانی کارگاه',
            'مرکز هزینه',
            '',
          ]}
          render={(r) => [
            r.name,
            BRANCH_KIND_LABELS[r.kind] ?? r.kind,
            r.code ? <span key="code" dir="ltr">{r.code}</span> : '—',
            r.contact_name || '—',
            r.registration_code ? <span key="reg" dir="ltr">{r.registration_code}</span> : '—',
            r.agreement_number ? <span key="agr" dir="ltr">{r.agreement_number}</span> : '—',
            r.insurance_exempt_count ? fa(r.insurance_exempt_count) : '—',
            //: عمداً خالی برای شعبه‌ای که مالیاتی نیست — همان چیزی که فهرستِ
            //: سپیدار نشان می‌دهد، و همان قیدی که سرور دارد.
            TAX_CALC_METHOD_LABELS[r.tax_calculation_method] ?? '—',
            r.workplace_name || '—',
            r.employer_name || '—',
            r.workplace_address || '—',
            r.cost_center_name || '—',
            <button key="edit" type="button" onClick={() => editBranch(r)}>
              ویرایش
            </button>,
          ]}
        />
      </SectionCard>
    </OpsPage>
  )
}

// ── جدولِ مشترکِ هر پنج فهرست ─────────────────────────────────────────────────

function RefTable<T extends { id: string }>({
  rows,
  error,
  emptyText,
  head,
  render,
}: {
  rows: T[] | null
  error: string | null
  emptyText: string
  //: سرستونِ خالی یعنی ستونِ کنش — در نمای کارتیِ موبایل برچسب نمی‌خواهد.
  head: string[]
  render: (row: T) => React.ReactNode[]
}) {
  return (
    <AsyncBlock loading={rows == null} error={error} empty={rows != null && rows.length === 0} emptyText={emptyText}>
      {rows == null || rows.length === 0 ? (
        <EmptyState icon={Building2} text={emptyText} />
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>{head.map((h, i) => <th key={h || `col-${i}`}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const cells = render(row)
                return (
                  <tr key={row.id}>
                    {cells.map((cell, i) => (
                      <td
                        key={head[i] || `col-${i}`}
                        className={i === 0 ? 'card-title' : head[i] ? undefined : 'card-actions'}
                        data-label={head[i] || undefined}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </AsyncBlock>
  )
}
