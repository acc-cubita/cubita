import { Fragment, useEffect, useState } from 'react'
import { Briefcase, Building2, Landmark, Percent, Plus, Save, SlidersHorizontal, Sparkles, X } from 'lucide-react'
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
  fetchAccountsLive,
  fetchPayrollFactors,
  setFactorParticipation,
  updatePayrollFactor,
  fetchPayrollTaxGroups,
  fetchServiceLocations,
  updateInsuranceTaxBranch,
  type ContactRecord,
  type CostCenterRecord,
  type InsuranceTaxBranchRecord,
  type JobTitleRecord,
  FACTOR_DETAIL_CLASS_LABELS,
  FACTOR_PURPOSE_LABELS,
  type PayrollFactorRecord,
  type PayrollTaxGroupRecord,
  type ServiceLocationRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import {
  ActionBar,
  FormField,
  FormGrid,
  FormStatus,
  FormTabs,
  InfoTip,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { ActiveChip, AsyncBlock, Note, OpsPage, type Msg } from '../accounting/kit'

/**
 * جدول‌های مرجعِ حقوق و دستمزد — محل خدمت، شغل، عوامل، گروه مالیاتی، شعب.
 *
 * هر پنج‌تا یک شکل دارند: کارتِ فرمِ ساخت با نوارِ «ثبت» زیرش، و کارتِ دفترِ همان
 * رکوردها. عمداً یک الگو، چون کاربر پنج فرمِ متفاوت را یاد نمی‌گیرد. چیدمان با اجزای
 * فرمِ سازمانی است (`components/form/FormKit`) — همان «قرارداد جدید».
 *
 * **حذف عمداً نیست.** رکوردی که در قراردادی استفاده شده نباید ناپدید شود؛ «غیرفعال»
 * آن را از فهرستِ انتخابِ فرمِ قرارداد بیرون می‌برد بی‌آنکه قراردادهای قدیمی
 * بی‌مرجع شوند.
 *
 * محل خدمت و شغل در فرمِ قرارداد هم «ساختِ درجا» دارند (دکمه‌ی «+» کنارِ فهرست): وقتی
 * عنوانِ موردنظر در فهرست نیست، کاربر همان‌جا می‌سازدش بی‌آنکه فرم را ترک کند.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

/** دکمه‌ی ثبتِ نوارِ عملیات — در حینِ ثبت متنش عوض می‌شود، نه اینکه بی‌صدا خاموش شود. */
function SubmitButton({ busy, label }: { busy: boolean; label: string }) {
  return (
    <button type="submit" className="btn-primary" disabled={busy}>
      <Save size={15} /> {busy ? 'در حال ثبت…' : label}
    </button>
  )
}

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
    const missing = firstMissing([
      [code, 'sl-code', 'کد را وارد کنید.'],
      [name, 'sl-name', 'عنوان را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard
            icon={Plus}
            title="ثبت محل خدمت"
            tip="محل خدمت جدا از مرکز هزینه است: مرکز هزینه می‌گوید هزینه به کدام حساب می‌رود، محل خدمت می‌گوید خودِ کارمند کجاست."
          >
            <FormGrid>
              <FormField id="sl-code" label="کد" required>
                {(id) => <input id={id} value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} />}
              </FormField>
              <FormField id="sl-name" label="عنوان" required>
                {(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="عنوان (۲)" tip="اختیاری — معمولاً همان عنوان به لاتین.">
                {(id) => <input id={id} dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            <SubmitButton busy={busy} label="ثبت محل خدمت" />
          </ActionBar>
        </form>

        <SectionCard icon={Building2} title={rows ? `${fa(rows.length)} محل خدمت` : 'در حال بارگذاری…'}>
          <RefTable
            rows={rows}
            error={error}
            emptyText="هنوز محل خدمتی ثبت نشده — اولی را با فرمِ بالا بسازید."
            head={['کد', 'عنوان', 'عنوان (۲)', 'وضعیت']}
            render={(r) => [r.code, r.name, r.name2 || '—', <ActiveChip key="st" active={r.is_active} />]}
          />
        </SectionCard>
      </div>
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
    const missing = firstMissing([
      [code, 'jt-code', 'کد را وارد کنید.'],
      [name, 'jt-name', 'عنوان را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard icon={Plus} title="ثبت شغل">
            <FormGrid>
              <FormField id="jt-code" label="کد" required>
                {(id) => <input id={id} value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} />}
              </FormField>
              <FormField id="jt-name" label="عنوان" required>
                {(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="عنوان (۲)" tip="اختیاری — معمولاً همان عنوان به لاتین.">
                {(id) => <input id={id} dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="رسته شغل">
                {(id) => (
                  <select id={id} value={family} onChange={(e) => setFamily(e.target.value)}>
                    <option value="">— انتخاب کنید —</option>
                    {JOB_FAMILIES.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
              <FormField label="کد شغل بیمه" tip="در لیستِ تأمین اجتماعی لازم است؛ روی شغل می‌ماند تا هر بار تایپ نشود.">
                {(id) => (
                  <input id={id} dir="ltr" value={insuranceCode} onChange={(e) => setInsuranceCode(e.target.value)} maxLength={30} />
                )}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            <SubmitButton busy={busy} label="ثبت شغل" />
          </ActionBar>
        </form>

        <SectionCard icon={Briefcase} title={rows ? `${fa(rows.length)} شغل` : 'در حال بارگذاری…'}>
          <RefTable
            rows={rows}
            error={error}
            emptyText="هنوز شغلی ثبت نشده — اولی را با فرمِ بالا بسازید."
            head={['کد', 'عنوان', 'رسته', 'کد بیمه', 'وضعیت']}
            render={(r) => [
              r.code,
              r.name,
              r.job_family || '—',
              r.insurance_job_code ? <span key="ins" dir="ltr">{r.insurance_job_code}</span> : '—',
              <ActiveChip key="st" active={r.is_active} />,
            ]}
          />
        </SectionCard>
      </div>
    </OpsPage>
  )
}

// ── عوامل حقوق و مزایا ───────────────────────────────────────────────────────

/** حسابِ برگی — تنها چیزی که ردیفِ سند می‌گیرد. */
type PostableAccount = { id: string; code: string; name: string; is_group: number }

//: ترتیبِ ستون‌های ماتریس — همان ترتیبی که موتور در آن حساب می‌کند:
//: اول مبناهای ماهانه (بیمه، مالیات)، بعد سه مبنای مزایا.
const PURPOSES = ['insurance_base', 'tax_base', 'eidi_base', 'severance_base', 'leave_base'] as const

export function PayrollFactorPage({ token }: { token: string }) {
  const [rows, setRows] = useState<PayrollFactorRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  //: پیامِ کنش‌های ردیفیِ فهرست و ماتریس — کنارِ همان جدول، نه در نوارِ فرمِ بالا.
  const [listMsg, setListMsg] = useState<Msg>(null)
  const [matrixMsg, setMatrixMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [name2, setName2] = useState('')
  const [category, setCategory] = useState('benefit')
  const [kind, setKind] = useState('fixed')
  const [extraordinary, setExtraordinary] = useState(false)
  const [editing, setEditing] = useState<PayrollFactorRecord | null>(null)
  const [priority, setPriority] = useState('0')
  const [expenseAccount, setExpenseAccount] = useState('')
  const [expenseDetail, setExpenseDetail] = useState('')
  const [payableAccount, setPayableAccount] = useState('')
  const [payableDetail, setPayableDetail] = useState('')
  const [accounts, setAccounts] = useState<PostableAccount[]>([])

  async function refresh() {
    try {
      const [factorRows, accountRows] = await Promise.all([
        fetchPayrollFactors(token),
        fetchAccountsLive(token),
      ])
      setRows(factorRows)
      //: فقط حسابِ برگی سند می‌گیرد؛ حسابِ گروه ردیف نمی‌پذیرد و سرور هم ردش
      //: می‌کند، پس نشان‌دادنش در فهرست فقط کاربر را به خطا می‌برد.
      setAccounts(accountRows.filter((a) => !a.is_group))
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
    setMatrixMsg(null)
    try {
      await setFactorParticipation(token, row.id, { [purpose]: on ? 1 : 0 })
      await refresh()
    } catch (err) {
      setMatrixMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  function clearForm() {
    setEditing(null)
    setName('')
    setName2('')
    setCategory('benefit')
    setKind('fixed')
    setExtraordinary(false)
    setPriority('0')
    setExpenseAccount('')
    setExpenseDetail('')
    setPayableAccount('')
    setPayableDetail('')
    setMsg(null)
  }

  function edit(row: PayrollFactorRecord) {
    setEditing(row)
    setName(row.name)
    setName2(row.name2)
    setCategory(row.category)
    setKind(row.kind)
    setExtraordinary(row.is_extraordinary)
    setPriority(String(row.display_priority ?? 0))
    setExpenseAccount(row.expense_account_id ?? '')
    setExpenseDetail(row.expense_detail_class ?? '')
    setPayableAccount(row.payable_account_id ?? '')
    setPayableDetail(row.payable_detail_class ?? '')
    setMsg(null)
    //: فرم بالای صفحه است و دکمه‌ی «ویرایش» پایینِ جدول؛ فوکوس صفحه را به فرم می‌برد.
    document.getElementById('pf-name')?.focus()
  }

  /** فعال/غیرفعال. **غیرفعال یعنی «دیگر انتخاب نشو»، نه «از گذشته پاک شو»** —
   *  حکم‌های موجود و فیش‌های صادرشده دست نمی‌خورند. */
  async function toggleActive(row: PayrollFactorRecord) {
    setBusy(true)
    setListMsg(null)
    try {
      await updatePayrollFactor(token, row.id, { is_active: !row.is_active })
      setListMsg({
        text: row.is_active
          ? `«${row.name}» غیرفعال شد؛ به حکمِ تازه اضافه نمی‌شود.`
          : `«${row.name}» فعال شد.`,
        kind: 'ok',
      })
      await refresh()
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const missing = firstMissing([[name, 'pf-name', 'عنوانِ عامل را وارد کنید.']])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const body = {
        name: name.trim(),
        name2: name2.trim(),
        category,
        kind,
        is_extraordinary: extraordinary,
        display_priority: Number(priority) || 0,
        expense_account_id: expenseAccount || null,
        expense_detail_class: expenseAccount ? expenseDetail : '',
        payable_account_id: payableAccount || null,
        payable_detail_class: payableAccount ? payableDetail : '',
      }
      if (editing) {
        await updatePayrollFactor(token, editing.id, body)
      } else {
        await createPayrollFactor(token, body)
      }
      clearForm()
      setMsg({ text: editing ? `«${body.name}» به‌روز شد.` : `عاملِ «${body.name}» ساخته شد.`, kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function seed() {
    setBusy(true)
    setListMsg(null)
    try {
      const all = await createDefaultPayrollFactors(token)
      setRows(all)
      setListMsg({ text: 'عوامل پیش‌فرض آماده شدند.', kind: 'ok' })
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const benefit = category === 'benefit'

  return (
    <OpsPage
      icon={SlidersHorizontal}
      title="عوامل حقوق و مزایا"
      description="حقوق پایه، حق اولاد، حق مسکن، حق خواروبار و هر عاملِ دیگری که خودتان می‌سازید."
    >
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard
            icon={Plus}
            title={editing ? `ویرایش «${editing.name}»` : 'ثبت عامل'}
            tip="«مزایا» به حقوق اضافه می‌شود و «کسورات» از آن کم — مثلِ بیمه‌ی تکمیلی و اقساطِ وام. عوامل پیش‌فرض همان چهارتایی‌اند که موتورِ فیشِ حقوقی می‌شناسدشان؛ بقیه در «سایر مزایا» جمع می‌شوند."
          >
            <FormGrid>
              <FormField id="pf-name" label="عنوان" required>
                {(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="عنوان (۲)" tip="اختیاری — معمولاً همان عنوان به لاتین.">
                {(id) => <input id={id} dir="ltr" value={name2} onChange={(e) => setName2(e.target.value)} maxLength={150} />}
              </FormField>
              <FormField label="طبقه">
                {(id) => (
                  <select id={id} value={category} onChange={(e) => setCategory(e.target.value)}>
                    {Object.entries(FACTOR_CATEGORY_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
              <FormField
                label="نوع"
                tip="«قراردادی» مبلغش روی حکمِ حقوقی نوشته می‌شود. «متغیر» مبلغش هر دوره جدا وارد می‌شود (کارکرد و صدور فیش ← ورودیِ عوامل) و روی حکم نمی‌نشیند."
              >
                {(id) => (
                  <select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                    {Object.entries(FACTOR_KIND_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
              <FormField
                label="اولویت نمایش"
                tip="ترتیبِ ردیف‌های فیش. فقط نمایشی است؛ هیچ محاسبه‌ای از آن نمی‌خوانَد و فیشِ صادرشده را هم تکان نمی‌دهد."
              >
                {(id) => <NumberInput id={id} group={false} value={priority} onChange={setPriority} />}
              </FormField>
              <div className="ef-checks">
                <span className="ef-check-tip">
                  <label className="fy-check">
                    <input type="checkbox" checked={extraordinary} onChange={(e) => setExtraordinary(e.target.checked)} />
                    فوق‌العاده است
                  </label>
                  {/* صادق باشیم: این پرچم امروز هیچ عددی را عوض نمی‌کند. گذاشتنش بدونِ این
                      توضیح یعنی کاربر فکر کند مالیات یا بیمه را تکان می‌دهد. */}
                  <InfoTip text="فقط برای دسته‌بندی و گزارش. هیچ محاسبه‌ای — نه مالیات، نه بیمه، نه اضافه‌کار — از این گزینه نمی‌خوانَد." />
                </span>
              </div>

              <div className="ef-subhead">حساب در سند</div>
              <FormField
                label={benefit ? 'حساب معین هزینه' : 'حساب معین پرداختنی'}
                tip={
                  benefit
                    ? 'خالی یعنی سهمِ این عامل مثلِ امروز به «هزینه حقوق» می‌رود.'
                    : 'مثلاً بیمه‌گرِ تکمیلی: پولی که از کارمند نگه داشته‌ایم و به او بدهکاریم.'
                }
              >
                {(id) => (
                  <select
                    id={id}
                    value={benefit ? expenseAccount : payableAccount}
                    onChange={(e) => (benefit ? setExpenseAccount : setPayableAccount)(e.target.value)}
                  >
                    <option value="">{benefit ? '— حساب عمومی حقوق —' : '— حساب عمومی سایر کسور —'}</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
              <FormField label="طبقه تفصیلی">
                {(id) => (
                  <select
                    id={id}
                    value={benefit ? expenseDetail : payableDetail}
                    onChange={(e) => (benefit ? setExpenseDetail : setPayableDetail)(e.target.value)}
                    disabled={benefit ? !expenseAccount : !payableAccount}
                  >
                    {Object.entries(FACTOR_DETAIL_CLASS_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                )}
              </FormField>
            </FormGrid>
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            {editing && (
              <button type="button" className="ef-btn-secondary" onClick={clearForm} disabled={busy}>
                <X size={15} /> انصراف
              </button>
            )}
            <SubmitButton busy={busy} label={editing ? 'ذخیره تغییرات' : 'ثبت عامل'} />
          </ActionBar>
        </form>

        <SectionCard
          icon={SlidersHorizontal}
          title={rows ? `${fa(rows.length)} عامل` : 'در حال بارگذاری…'}
          actions={
            <button type="button" onClick={seed} disabled={busy}>
              <Sparkles size={14} /> ساخت عوامل پیش‌فرض
            </button>
          }
        >
          <RefTable
            rows={rows}
            error={error}
            emptyText="هنوز عاملی نیست — «ساخت عوامل پیش‌فرض» را بزنید تا چهار عاملِ اصلی ساخته شوند."
            head={['عنوان', 'طبقه', 'نوع', 'فوق‌العاده', 'اولویت', 'حساب اختصاصی', 'وضعیت', '']}
            render={(r) => [
              r.name,
              FACTOR_CATEGORY_LABELS[r.category] ?? r.category,
              FACTOR_KIND_LABELS[r.kind] ?? r.kind,
              r.is_extraordinary ? 'بله' : 'خیر',
              fa(r.display_priority ?? 0),
              r.expense_account_id || r.payable_account_id ? 'دارد' : '—',
              <ActiveChip key="st" active={r.is_active} />,
              <Fragment key="actions">
                <button type="button" onClick={() => edit(r)} disabled={busy}>
                  ویرایش
                </button>
                <button
                  type="button"
                  onClick={() => void toggleActive(r)}
                  disabled={busy}
                  title={r.is_active ? 'دیگر به حکمِ تازه اضافه نمی‌شود' : 'دوباره قابلِ انتخاب می‌شود'}
                >
                  {r.is_active ? 'غیرفعال کن' : 'فعال کن'}
                </button>
              </Fragment>,
            ]}
          />
          <Note msg={listMsg} />
        </SectionCard>

        <SectionCard
          icon={SlidersHorizontal}
          title="مشارکت عوامل در مبناها"
          description="هر عامل در کدام محاسبه شمرده شود. تا دست نزنید هیچ عددی عوض نمی‌شود."
          tip="«مشمولِ بیمه» یک پرچمِ واحد نیست: یک عامل می‌تواند مبنای بیمه را بسازد ولی در مبنای عیدی نیاید. پیش‌فرضِ مبنای بیمه و مالیات «همهٔ عوامل» است و پیش‌فرضِ سه مبنای مزایا «فقط حقوق پایه» — دقیقاً همان فرمولی که تا امروز اجرا می‌شد."
        >
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
                    {PURPOSES.map((key) => (
                      <th key={key}>{FACTOR_PURPOSE_LABELS[key]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(rows ?? []).map((row) => (
                    <tr key={row.id}>
                      <td className="card-title" data-label="عامل">
                        {row.name}
                      </td>
                      {PURPOSES.map((key) => (
                        <td key={key} data-label={FACTOR_PURPOSE_LABELS[key]}>
                          <input
                            type="checkbox"
                            aria-label={`${row.name} — ${FACTOR_PURPOSE_LABELS[key]}`}
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
          <Note msg={matrixMsg} />
        </SectionCard>
      </div>
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

type TaxGroupTab = 'groups' | 'branches'

/**
 * دو دفترِ کنارِ هم در دو تب: گروه‌های مالیاتی و شعب. هر تب فرمِ ساخت و فهرستِ خودش را
 * دارد — پیش‌تر دو فرم و دو جدول پشتِ هم می‌آمدند و فرمِ دوم زیرِ جدولِ اول گم می‌شد.
 */
export function PayrollTaxGroupPage({ token }: { token: string }) {
  const [tab, setTab] = useState<TaxGroupTab>('groups')
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
    document.getElementById('br-name')?.focus()
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
    const missing = firstMissing([[name, 'tg-name', 'عنوانِ گروه را وارد کنید.']])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
    const missing = firstMissing([[form.name, 'br-name', 'عنوانِ شعبه را وارد کنید.']])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
        <FormTabs
          label="گروه مالیاتی و شعب"
          active={tab}
          onChange={(k) => {
            setTab(k as TaxGroupTab)
            setMsg(null)
          }}
          tabs={[
            { key: 'groups', label: 'گروه‌های مالیاتی', badge: rows?.length ? fa(rows.length) : undefined },
            { key: 'branches', label: 'شعب بیمه و حوزه‌های مالیاتی', badge: branches?.length ? fa(branches.length) : undefined },
          ]}
        >
          {tab === 'groups' ? (
            <div className="ef-form">
              <form onSubmit={submitGroup} noValidate>
                <SectionCard icon={Plus} title="گروه مالیاتی جدید">
                  <FormGrid>
                    <FormField id="tg-name" label="عنوان" required>
                      {(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={150} />}
                    </FormField>
                    <FormField label="نوع">
                      {(id) => (
                        <select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                          {Object.entries(TAX_GROUP_KIND_LABELS).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                      )}
                    </FormField>
                    <FormField
                      label="درصد"
                      tip="چند درصد از مالیاتِ محاسبه‌شده واقعاً وصول می‌شود: مناطق محروم نصف، معاف صفر. خالی بگذارید تا پیش‌فرضِ همان نوع بنشیند."
                    >
                      {(id) => <NumberInput id={id} allowDecimal value={percent} onChange={setPercent} />}
                    </FormField>
                  </FormGrid>
                </SectionCard>
                <ActionBar status={<FormStatus msg={msg} />}>
                  <SubmitButton busy={busy} label="ثبت گروه" />
                </ActionBar>
              </form>

              <SectionCard icon={Percent} title={rows ? `${fa(rows.length)} گروه مالیاتی` : 'در حال بارگذاری…'}>
                <RefTable
                  rows={rows}
                  error={error}
                  emptyText="هنوز گروه مالیاتی‌ای ثبت نشده."
                  head={['عنوان', 'نوع', 'درصد']}
                  render={(r) => [r.name, TAX_GROUP_KIND_LABELS[r.kind] ?? r.kind, `${fa(Number(r.percent))}٪`]}
                />
              </SectionCard>
            </div>
          ) : (
            <div className="ef-form">
              <form onSubmit={submitBranch} noValidate>
                <SectionCard
                  icon={Landmark}
                  title={editingBranch ? `ویرایش «${editingBranch.name}»` : 'شعبه بیمه یا حوزه مالیاتی جدید'}
                >
                  <FormGrid>
                    <FormField
                      label="نوع"
                      message={
                        editingBranch?.in_use
                          ? 'این شعبه روی حکم‌های حقوقی استفاده شده و نوعش دیگر عوض نمی‌شود. اگر نوعش اشتباه بوده، شعبه‌ی درست را بسازید و حکم‌ها را به آن ببرید.'
                          : undefined
                      }
                    >
                      {(id) => (
                        <select
                          id={id}
                          value={form.kind}
                          onChange={(e) => set({ kind: e.target.value })}
                          disabled={editingBranch?.in_use}
                        >
                          {Object.entries(BRANCH_KIND_LABELS).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                      )}
                    </FormField>
                    <FormField id="br-name" label="عنوان" required>
                      {(id) => <input id={id} value={form.name} onChange={(e) => set({ name: e.target.value })} maxLength={150} />}
                    </FormField>
                    <FormField label="کد تفصیلی شعبه">
                      {(id) => <input id={id} dir="ltr" value={form.code} onChange={(e) => set({ code: e.target.value })} maxLength={20} />}
                    </FormField>

                    <FormField
                      label="طرف حساب سازمان"
                      tip="بدهیِ بیمه و مالیاتِ حقوق به همین سازمان پرداخت می‌شود؛ با این پیوند، مانده و تفصیلی‌اش در دفتر پیدا می‌شود. خالی گذاشتنش چیزی را خراب نمی‌کند."
                    >
                      {(id) => (
                        <select id={id} value={form.contact_id} onChange={(e) => set({ contact_id: e.target.value })}>
                          <option value="">— وصل نشده —</option>
                          {contacts.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </FormField>
                    <FormField
                      label="کد شرکت / شماره پرونده"
                      tip={form.kind === 'tax' ? 'شماره پرونده مالیاتی.' : 'کد کارگاه نزد مرجع.'}
                    >
                      {(id) => (
                        <input
                          id={id}
                          dir="ltr"
                          value={form.registration_code}
                          onChange={(e) => set({ registration_code: e.target.value })}
                          maxLength={50}
                        />
                      )}
                    </FormField>
                    <FormField label="مرکز هزینه">
                      {(id) => (
                        <select id={id} value={form.cost_center_id} onChange={(e) => set({ cost_center_id: e.target.value })}>
                          <option value="">— ندارد —</option>
                          {costCenters.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </FormField>

                    <div className="ef-subhead">کارگاه و کارفرما</div>
                    <FormField label="نام کارگاه" tip="کارگاهِ ثبت‌شده نزد مرجع — با «محل خدمت» یکی نیست.">
                      {(id) => (
                        <input id={id} value={form.workplace_name} onChange={(e) => set({ workplace_name: e.target.value })} maxLength={200} />
                      )}
                    </FormField>
                    <FormField label="نام کارفرما">
                      {(id) => (
                        <input id={id} value={form.employer_name} onChange={(e) => set({ employer_name: e.target.value })} maxLength={200} />
                      )}
                    </FormField>
                    <FormField label="شماره پیمان" tip="قرارداد کارفرما با مرجع قانونی — نه قرارداد استخدامی کارمند.">
                      {(id) => (
                        <input
                          id={id}
                          dir="ltr"
                          value={form.agreement_number}
                          onChange={(e) => set({ agreement_number: e.target.value })}
                          maxLength={50}
                        />
                      )}
                    </FormField>
                    <FormField label="نشانی کارگاه" span="full">
                      {(id) => <input id={id} value={form.workplace_address} onChange={(e) => set({ workplace_address: e.target.value })} />}
                    </FormField>
                    <FormField
                      label="نفرات معاف از بیمه"
                      tip="عددِ سرصفحه‌ی ثبت کارگاه. معافیتِ هر کارمند روی حکمِ خودش تعیین می‌شود و این عدد در هیچ محاسبه‌ای استفاده نمی‌شود."
                    >
                      {(id) => (
                        <NumberInput
                          id={id}
                          group={false}
                          value={form.insurance_exempt_count}
                          onChange={(v) => set({ insurance_exempt_count: v })}
                        />
                      )}
                    </FormField>

                    {/* فقط برای حوزه مالیاتی — سرور هم همین را می‌سنجد، نه فقط این‌جا. */}
                    {form.kind === 'tax' && (
                      <FormField
                        label="نحوه محاسبه مالیات"
                        tip="فعلاً ثبت می‌شود ولی در محاسبه‌ی مالیات اعمال نمی‌شود؛ موتور امروز تعدیل تجمیعی انجام می‌دهد."
                      >
                        {(id) => (
                          <select
                            id={id}
                            value={form.tax_calculation_method}
                            onChange={(e) => set({ tax_calculation_method: e.target.value })}
                          >
                            <option value="">— تعیین نشده —</option>
                            {Object.entries(TAX_CALC_METHOD_LABELS).map(([k, v]) => (
                              <option key={k} value={k}>
                                {v}
                              </option>
                            ))}
                          </select>
                        )}
                      </FormField>
                    )}
                  </FormGrid>
                </SectionCard>
                <ActionBar status={<FormStatus msg={msg} />}>
                  {editingBranch && (
                    <button type="button" className="ef-btn-secondary" onClick={clearBranchForm} disabled={busy}>
                      <X size={15} /> انصراف
                    </button>
                  )}
                  <SubmitButton busy={busy} label={editingBranch ? 'ذخیره تغییرات' : 'ثبت شعبه'} />
                </ActionBar>
              </form>

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
            </div>
          )}
        </FormTabs>
      </div>
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
              <tr>
                {head.map((h, i) => (
                  <th key={h || `col-${i}`}>{h}</th>
                ))}
              </tr>
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
