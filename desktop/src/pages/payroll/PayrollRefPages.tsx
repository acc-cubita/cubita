import { useEffect, useState } from 'react'
import { Briefcase, Building2, Percent, Plus, Save, Landmark, SlidersHorizontal } from 'lucide-react'
import {
  BRANCH_KIND_LABELS,
  FACTOR_CATEGORY_LABELS,
  FACTOR_KIND_LABELS,
  JOB_FAMILIES,
  TAX_GROUP_KIND_LABELS,
  createDefaultPayrollFactors,
  createInsuranceTaxBranch,
  createJobTitle,
  createPayrollFactor,
  createPayrollTaxGroup,
  createServiceLocation,
  fetchContacts,
  fetchInsuranceTaxBranches,
  fetchJobTitles,
  fetchPayrollFactors,
  fetchPayrollTaxGroups,
  fetchServiceLocations,
  updateInsuranceTaxBranch,
  type ContactRecord,
  type InsuranceTaxBranchRecord,
  type JobTitleRecord,
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
    </OpsPage>
  )
}

// ── گروه مالیاتی و شعب ───────────────────────────────────────────────────────

export function PayrollTaxGroupPage({ token }: { token: string }) {
  const [rows, setRows] = useState<PayrollTaxGroupRecord[] | null>(null)
  const [branches, setBranches] = useState<InsuranceTaxBranchRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [kind, setKind] = useState('normal')
  const [percent, setPercent] = useState('')
  const [branchName, setBranchName] = useState('')
  const [branchCode, setBranchCode] = useState('')
  const [branchKind, setBranchKind] = useState('insurance')
  const [branchContact, setBranchContact] = useState('')
  //: خالی = «شعبه‌ی تازه». پر = همان شعبه دارد ویرایش می‌شود.
  const [editingBranch, setEditingBranch] = useState<InsuranceTaxBranchRecord | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])

  async function refresh() {
    try {
      const [groups, allBranches, allContacts] = await Promise.all([
        fetchPayrollTaxGroups(token),
        fetchInsuranceTaxBranches(token),
        fetchContacts(token),
      ])
      setRows(groups)
      setBranches(allBranches)
      setContacts(allContacts.filter((c) => c.is_active))
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  function editBranch(branch: InsuranceTaxBranchRecord) {
    setEditingBranch(branch)
    setBranchName(branch.name)
    setBranchCode(branch.code)
    setBranchKind(branch.kind)
    setBranchContact(branch.contact_id ?? '')
    setMsg(null)
  }

  function clearBranchForm() {
    setEditingBranch(null)
    setBranchName('')
    setBranchCode('')
    setBranchContact('')
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
        name: branchName.trim(),
        code: branchCode.trim(),
        kind: branchKind,
        contact_id: branchContact || null,
      }
      if (editingBranch) {
        await updateInsuranceTaxBranch(token, editingBranch.id, body)
        setMsg({ text: `«${body.name}» به‌روز شد.`, kind: 'ok' })
      } else {
        await createInsuranceTaxBranch(token, body)
        setMsg({ text: `«${body.name}» ساخته شد.`, kind: 'ok' })
      }
      setEditingBranch(null)
      setBranchName('')
      setBranchCode('')
      setBranchContact('')
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
            <select value={branchKind} onChange={(e) => setBranchKind(e.target.value)}>
              {Object.entries(BRANCH_KIND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            <span>عنوان *</span>
            <input value={branchName} onChange={(e) => setBranchName(e.target.value)} maxLength={150} required />
          </label>
          <label>
            <span>کد</span>
            <input dir="ltr" value={branchCode} onChange={(e) => setBranchCode(e.target.value)} maxLength={20} />
          </label>
          <label>
            <span>طرف حساب سازمان</span>
            <select value={branchContact} onChange={(e) => setBranchContact(e.target.value)}>
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
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !branchName.trim()}>
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
          head={['عنوان', 'نوع', 'کد', 'طرف حساب سازمان', 'کد تفصیلی', '']}
          render={(r) => [
            r.name,
            BRANCH_KIND_LABELS[r.kind] ?? r.kind,
            r.code || '—',
            r.contact_name || '—',
            r.analytic_code ? <span key="analytic" dir="ltr">{r.analytic_code}</span> : '—',
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
