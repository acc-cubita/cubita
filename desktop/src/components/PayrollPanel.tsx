import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Ban,
  CalendarDays,
  CalendarPlus,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileSignature,
  FileText,
  Gift,
  RotateCcw,
  Save,
  Settings,
  SlidersHorizontal,
  UserPlus,
  Users,
} from 'lucide-react'
import { Tabs } from './Tabs'
import { BenefitsPanel } from './BenefitsPanel'
import { Pager, usePagination } from './Pager'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { PayrollSettingsPanel } from './PayrollSettingsPanel'
import { PayslipDrawer } from './PayslipDrawer'
import { SectionCard } from './SectionCard'
import {
  ActionBar,
  FormField,
  FormGrid,
  FormStatus,
  InfoTip,
  ListToolbar,
  SearchField,
  TabHead,
} from './form/FormKit'
import { firstMissing } from './form/firstMissing'
import { formatJalali, JALALI_MONTH_NAMES } from '../lib/jalali'
import type { PageKey } from '../lib/navModel'
import { fetchEmployees, updateEmployee, type EmployeeRecord, type PayrollPeriodRecord } from '../api'
import { useEmployeeDraft } from '../lib/employeeDraft'
import { usePayrollRunDraft, type PayrollRunDraft } from '../lib/payrollRunDraft'
import { Note, type Msg } from '../pages/accounting/kit'

/**
 * ماژولِ «حقوق و دستمزد» — چهار بخش: پرسنل و احکام، کارکرد و صدور فیش، مزایا، تنظیمات.
 *
 * هر بخش با اجزای فرمِ سازمانی (`components/form/FormKit`) ساخته شده — همان «قرارداد
 * جدید»: کارت‌های جدا با سایه‌ی نرم، فیلدهای هم‌ارتفاع در گریدِ حداکثر سه‌ستونه، راهنما در
 * «؟» کنارِ برچسب، و نوارِ عملیاتِ چسبیده به پایین.
 *
 * پیش‌تر «پرسنل» و «کارکرد» در پوسته‌ی «راهنما» ویزاردِ مرحله‌ای بودند و در پوسته‌ی
 * کلاسیک فرمِ ساده. حالا یک فرم برای هر دو پوسته است، مثلِ بقیه‌ی صفحه‌های همین ماژول:
 * ویزاردِ دومرحله‌ای برای چهار فیلد فقط یک کلیکِ اضافه بود، و «کارکرد» روی یک صفحه
 * هر سه قدمش (دوره ← کارکرد ← فیش) را پشتِ هم نشان می‌دهد.
 */

// دوره‌ی حقوق شمسی است: ماه‌ها فروردین..اسفند (JALALI_MONTH_NAMES)
const faYear = (y: number) => y.toLocaleString('fa-IR', { useGrouping: false })
const faMoney = (v: string | number) => Number(v).toLocaleString('fa-IR')
const periodLabel = (p: PayrollPeriodRecord) => `${JALALI_MONTH_NAMES[p.month - 1] ?? p.month} ${faYear(p.year)}`

export function PayrollPanel({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey) => void
}) {
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const refreshEmployees = useCallback(async () => {
    setEmployees(await fetchEmployees(token))
  }, [token])
  useEffect(() => {
    void refreshEmployees()
  }, [refreshEmployees])

  // فرایندِ کارکرد/فیش (دوره‌ها/کارکرد/فیش) — در سطحِ پنل نگه داشته می‌شود تا با جابه‌جایی
  // بین تب‌ها داده از دست نرود.
  const run = usePayrollRunDraft({ token, employees })

  return (
    <Tabs
      syncPage="payroll"
      tabs={[
        {
          key: 'staff',
          label: 'پرسنل و احکام',
          icon: Users,
          content: (
            <div className="ef-form">
              <EmployeeForm token={token} onCreated={refreshEmployees} />
              <ContractPointer onNavigate={onNavigate} />
              <EmployeeList employees={employees} token={token} onChanged={refreshEmployees} />
            </div>
          ),
        },
        {
          key: 'run',
          label: 'کارکرد و صدور فیش',
          icon: CalendarPlus,
          content: <PayrollRun d={run} employees={employees} />,
        },
        {
          key: 'benefits',
          label: 'مزایا',
          icon: Gift,
          content: <BenefitsPanel token={token} />,
        },
        {
          key: 'settings',
          label: 'تنظیماتِ حقوق',
          icon: Settings,
          content: <PayrollSettingsPanel token={token} onSaved={() => void refreshEmployees()} />,
        },
      ]}
    />
  )
}

/* ───────────────────────── پرسنل و احکام ───────────────────────── */

function EmployeeForm({ token, onCreated }: { token: string; onCreated: () => void }) {
  const d = useEmployeeDraft({ token, onCreated })
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        const missing = firstMissing([
          [d.firstName, 'emp-first', 'نامِ کارمند را وارد کنید.'],
          [d.lastName, 'emp-last', 'نام‌خانوادگی را وارد کنید.'],
          [d.nationalId, 'emp-nid', 'کد ملی را وارد کنید.'],
        ])
        if (missing) {
          d.setMessage({ text: missing, kind: 'err' })
          return
        }
        void d.submit()
      }}
    >
      <SectionCard icon={UserPlus} title="افزودن پرسنل">
        <FormGrid>
          <FormField id="emp-first" label="نام" required>
            {(id) => <input id={id} value={d.firstName} onChange={(e) => d.setFirstName(e.target.value)} />}
          </FormField>
          <FormField id="emp-last" label="نام‌خانوادگی" required>
            {(id) => <input id={id} value={d.lastName} onChange={(e) => d.setLastName(e.target.value)} />}
          </FormField>
          <FormField id="emp-nid" label="کد ملی" required>
            {(id) => (
              <input id={id} dir="ltr" inputMode="numeric" value={d.nationalId} onChange={(e) => d.setNationalId(e.target.value)} />
            )}
          </FormField>
          <FormField label="تاریخ استخدام">
            {(id) => <JalaliDatePicker id={id} value={d.hireDate} onChange={d.setHireDate} />}
          </FormField>
        </FormGrid>
      </SectionCard>
      <ActionBar status={<FormStatus msg={d.message} />}>
        <button type="submit" className="btn-primary" disabled={d.submitting}>
          <Save size={15} /> {d.submitting ? 'در حال ثبت…' : 'ثبت پرسنل'}
        </button>
      </ActionBar>
    </form>
  )
}

type StatusFilter = '' | 'active' | 'inactive'

export function EmployeeList({
  employees,
  token,
  onChanged,
}: {
  employees: EmployeeRecord[]
  token: string
  onChanged: () => void | Promise<void>
}) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('')
  const [msg, setMsg] = useState<Msg>(null)

  //: فهرستِ پرسنل همین حالا کامل در دستِ پنل است (برای جدولِ کارکرد هم لازم است)؛
  //: فیلتر روی همان می‌نشیند، نه درخواستِ تازه.
  const shown = useMemo(() => {
    const q = query.trim()
    return employees.filter((e) => {
      if (status === 'active' && !e.is_active) return false
      if (status === 'inactive' && e.is_active) return false
      if (!q) return true
      return `${e.first_name} ${e.last_name}`.includes(q) || (e.national_id ?? '').includes(q)
    })
  }, [employees, query, status])
  const pg = usePagination(shown, 10, `${query}|${status}`)

  /** **این ستون وضعیتی نشان می‌داد که کاربر نمی‌توانست عوضش کند.**
   *
   * و آن وضعیت تزئینی نبود: `is_active` تنها گاردِ صدورِ فیش است. پس تا امروز
   * کارمندی که رفته بود هر دوره فیشِ کامل می‌گرفت و هیچ راهی در رابط نبود که
   * جلویش را بگیرد.
   *
   * فقط همین یک فیلد فرستاده می‌شود — تاریخ استخدام و شماره‌حساب دست نمی‌خورند.
   */
  async function toggle(e: EmployeeRecord) {
    const next = !e.is_active
    const name = `${e.first_name} ${e.last_name}`.trim()
    if (
      !next &&
      !window.confirm(
        `«${name}» غیرفعال شود؟ از دوره‌های بعدی فیش نمی‌گیرد. فیش‌ها، حکم‌ها و سندهای گذشته‌اش دست‌نخورده می‌مانند.

` +
          'توجه: این کار «تاریخ پایان خدمت» را تغییر نمی‌دهد — آن روی حکم ثبت می‌شود و محاسبه‌ی سنوات به آن تکیه دارد.',
      )
    )
      return
    setMsg(null)
    try {
      await updateEmployee(token, e.id, { is_active: next })
      await onChanged()
      setMsg({ text: next ? `«${name}» به کار برگشت.` : `همکاریِ «${name}» پایان یافت.`, kind: 'ok' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const filtered = Boolean(query.trim() || status)

  return (
    <SectionCard icon={Users} title={`${employees.length.toLocaleString('fa-IR')} پرسنل`}>
      {employees.length > 0 && (
        <ListToolbar>
          <SearchField value={query} onChange={setQuery} placeholder="نام یا کد ملی…" />
          <select aria-label="وضعیت" value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)}>
            <option value="">همه‌ی وضعیت‌ها</option>
            <option value="active">فعال</option>
            <option value="inactive">غیرفعال</option>
          </select>
        </ListToolbar>
      )}
      {shown.length === 0 ? (
        <EmptyState
          icon={Users}
          text={filtered ? 'کسی با این فیلترها پیدا نشد — جست‌وجو یا وضعیت را تغییر دهید.' : 'پرسنلی ثبت نشده — اولی را با فرمِ بالا اضافه کنید.'}
        />
      ) : (
        <>
          <div className="table-scroll">
            <table className="entity-table payroll-emp-table cards-on-mobile">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>کد ملی</th>
                  <th>تاریخ استخدام</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((e) => (
                  <tr key={e.id}>
                    <td className="entity-name" data-label="نام">
                      {e.first_name} {e.last_name}
                    </td>
                    <td data-label="کد ملی">
                      <span dir="ltr">{e.national_id}</span>
                    </td>
                    <td data-label="تاریخ استخدام">{formatJalali(e.hire_date)}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${e.is_active ? 'tone-success' : 'tone-muted'}`}>
                        {e.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td className="card-actions">
                      <button type="button" onClick={() => void toggle(e)}>
                        {e.is_active ? (
                          <>
                            <Ban size={13} /> پایانِ همکاری
                          </>
                        ) : (
                          <>
                            <RotateCcw size={13} /> بازگشت به کار
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </>
      )}
      <Note msg={msg} />
    </SectionCard>
  )
}

/**
 * جای حکمِ حقوقی این‌جا نیست — «قرارداد جدید» است.
 *
 * تا امروز یک فرمِ کوتاهِ «ثبت حکم حقوقی» همین‌جا بود که فقط کارمند، تاریخ اجرا و
 * چهار مبلغ می‌گرفت و به همان `/api/salary-contracts` می‌فرستاد که فرمِ کاملِ
 * قرارداد می‌فرستد. دو نمای یک داده بود، و بدتر: چون نوعِ قرارداد پیش‌فرض
 * «استخدام» است، حکمی که از این‌جا ثبت می‌شد **جای استخدامِ واقعی را می‌گرفت** و
 * فرمِ کامل بعد از آن فقط «اصلاح قرارداد» می‌توانست بزند — بی‌آنکه شماره، نوع
 * استخدام، محل خدمت، شغل و اطلاعات بیمه و مالیات هیچ‌وقت پر شده باشند.
 */
function ContractPointer({ onNavigate }: { onNavigate?: (page: PageKey) => void }) {
  return (
    <div className="ef-callout">
      <FileSignature size={18} />
      <p>
        قرارداد و حکمِ حقوقیِ هر کارمند در «قرارداد جدید» ثبت می‌شود.{' '}
        <InfoTip text="آن‌جا نوعِ قرارداد، سه تاریخ، اطلاعات استخدامی، عوامل حقوق و مزایا و اطلاعات بیمه و مالیات هم پرسیده می‌شوند." />
      </p>
      {onNavigate && (
        <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('contractnew')}>
          <FileSignature size={14} /> قرارداد جدید
        </button>
      )}
    </div>
  )
}

/* ───────────────────────── کارکرد و صدور فیش ───────────────────────── */

/**
 * هر سه قدمِ دوره روی یک صفحه: انتخاب/ساختِ دوره، کارکرد و ورودیِ عوامل، و فیش‌ها.
 * کارت‌های دوم به بعد فقط وقتی دوره‌ای انتخاب شده دیده می‌شوند؛ نوارِ پایین صدورِ فیش است.
 */
function PayrollRun({ d, employees }: { d: PayrollRunDraft; employees: EmployeeRecord[] }) {
  const [generating, setGenerating] = useState(false)

  async function generate() {
    setGenerating(true)
    try {
      await d.generate()
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="ef-form">
      <PeriodCard d={d} />
      {!d.selectedPeriod ? (
        <div className="ef-empty">یک دوره را انتخاب یا ایجاد کنید تا جدولِ کارکرد و صدورِ فیش نمایش داده شود.</div>
      ) : employees.length === 0 ? (
        <div className="ef-empty">پرسنلی ثبت نشده — ابتدا از «پرسنل و احکام» کارمند اضافه کنید.</div>
      ) : (
        <>
          <SectionCard
            icon={ClipboardCheck}
            title={`کارکردِ ${periodLabel(d.selectedPeriod)}`}
            tip="روزِ کارکرد و ساعتِ اضافه‌کارِ هر نفر را وارد و همان ردیف را ذخیره کنید. پیش‌فرض ۳۰ روز است."
          >
            <AttendanceTable d={d} employees={employees} />
          </SectionCard>
          <SectionCard
            icon={SlidersHorizontal}
            title="ورودیِ عوامل متغیرِ این دوره"
            tip="مأموریت، پاداش، کارانه، مساعده. این مبالغ فقط همین دوره را تغییر می‌دهند و به نسبتِ کارکرد کوچک نمی‌شوند. خالی یا صفر یعنی این ماه ندارد."
          >
            <FactorInputsTable d={d} employees={employees} />
          </SectionCard>
          <PayslipsCard d={d} />
          <ActionBar status={<FormStatus msg={d.message} />}>
            <button type="button" className="btn-primary" onClick={() => void generate()} disabled={generating}>
              <FileCheck2 size={15} /> {generating ? 'در حال صدور…' : 'صدور فیش‌های حقوقی این دوره'}
            </button>
          </ActionBar>
        </>
      )}
    </div>
  )
}

/** انتخاب/ساختِ دوره‌ی حقوقی. */
function PeriodCard({ d }: { d: PayrollRunDraft }) {
  return (
    <SectionCard icon={CalendarDays} title="دوره‌ی حقوقی">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void d.createPeriod()
        }}
      >
        <FormGrid>
          <FormField label="سال">
            {(id) => <NumberInput id={id} group={false} value={d.year} onChange={(v) => d.setYear(Number(v))} />}
          </FormField>
          <FormField label="ماه">
            {(id) => (
              <select id={id} value={d.month} onChange={(e) => d.setMonth(Number(e.target.value))}>
                {JALALI_MONTH_NAMES.map((name, idx) => (
                  <option key={idx} value={idx + 1}>
                    {name}
                  </option>
                ))}
              </select>
            )}
          </FormField>
          <div className="ef-field ef-field--action">
            <button type="submit">
              <CalendarPlus size={15} /> ایجاد دوره جدید
            </button>
          </div>
        </FormGrid>
      </form>
      {d.periodError && <p className="ef-message ef-message--warn" role="alert">{d.periodError}</p>}

      <div className="ef-block">
        <TabHead title="دوره‌ها" tip="دوره‌ی «نهایی‌شده» فیشِ صادرشده دارد؛ «پیش‌نویس» هنوز قابلِ ویرایش است." />
        {d.periods.length === 0 ? (
          <div className="ef-empty">هنوز دوره‌ای ساخته نشده — سال و ماه را انتخاب کنید و «ایجاد دوره جدید» را بزنید.</div>
        ) : (
          <div className="ef-chips" role="group" aria-label="دوره‌های حقوقی">
            {d.periods.map((p) => (
              <button
                key={p.id}
                type="button"
                className="ef-chip-btn"
                aria-pressed={p.id === d.selectedPeriodId}
                onClick={() => d.setSelectedPeriodId(p.id)}
              >
                {periodLabel(p)}
                <span className={`status-badge ${p.status === 'finalized' ? 'tone-success' : 'tone-muted'}`}>
                  {p.status === 'finalized' ? 'نهایی‌شده' : 'پیش‌نویس'}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </SectionCard>
  )
}

/** جدولِ کارکردِ همه‌ی پرسنل (روز کارکرد + اضافه‌کار). */
function AttendanceTable({ d, employees }: { d: PayrollRunDraft; employees: EmployeeRecord[] }) {
  return (
    <div className="table-scroll">
      <table className="entity-table payroll-attend-table cards-on-mobile">
        <thead>
          <tr>
            <th>کارمند</th>
            <th>روز کارکرد</th>
            <th>ساعت اضافه‌کار</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {employees.map((emp) => (
            <tr key={emp.id}>
              <td className="entity-name" data-label="کارمند">
                {emp.first_name} {emp.last_name}
              </td>
              <td data-label="روز کارکرد">
                <NumberInput
                  aria-label={`روز کارکردِ ${emp.first_name} ${emp.last_name}`}
                  value={d.attendance[emp.id]?.worked ?? '30'}
                  onChange={(v) => d.setAttendanceField(emp.id, { worked: v })}
                />
              </td>
              <td data-label="ساعت اضافه‌کار">
                <NumberInput
                  aria-label={`اضافه‌کارِ ${emp.first_name} ${emp.last_name}`}
                  value={d.attendance[emp.id]?.overtime ?? '0'}
                  onChange={(v) => d.setAttendanceField(emp.id, { overtime: v })}
                />
              </td>
              <td className="attend-action card-actions">
                <button type="button" onClick={() => void d.saveAttendance(emp.id)}>
                  <Save size={13} /> ذخیره کارکرد
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * ورودیِ عواملِ **متغیر** در یک دوره — مأموریت، پاداش، کارانه، مساعده.
 *
 * **لایه‌ای که نبود.** تا مهاجرتِ ۰۱۴۷ عاملِ «متغیر» دقیقاً مثلِ «قراردادی»
 * رفتار می‌کرد: مبلغش از حکم می‌آمد، پس دو ماهِ پیاپی یک عدد می‌داد. برای
 * عوض‌کردنِ پاداشِ یک ماه باید حکمِ حقوقیِ کارمند ویرایش می‌شد.
 *
 * کنارِ جدولِ کارکرد نشسته چون هر دو یک جنس‌اند: **دادهٔ همین دوره**، نه شرطِ
 * ماندگارِ استخدام.
 */
function FactorInputsTable({ d, employees }: { d: PayrollRunDraft; employees: EmployeeRecord[] }) {
  if (d.variableFactors.length === 0) {
    return (
      <div className="ef-empty">
        عاملِ متغیری تعریف نشده. از «عوامل حقوق و مزایا» عاملی با نوعِ «متغیر» بسازید تا مبلغش را هر دوره جدا وارد کنید.
      </div>
    )
  }
  return (
    <>
      {d.inputError && <p className="ef-message ef-message--warn" role="alert">{d.inputError}</p>}
      <div className="table-scroll">
        <table className="entity-table cards-on-mobile">
          <thead>
            <tr>
              <th>کارمند</th>
              {d.variableFactors.map((f) => (
                <th key={f.id}>
                  {f.name}
                  {f.category === 'deduction' ? ' (کسر)' : ''}
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {employees.map((emp) => (
              <tr key={emp.id}>
                <td className="card-title" data-label="کارمند">
                  {emp.first_name} {emp.last_name}
                </td>
                {d.variableFactors.map((f) => (
                  <td key={f.id} data-label={f.name}>
                    <NumberInput
                      aria-label={`${f.name} — ${emp.first_name} ${emp.last_name}`}
                      value={d.factorInputs[`${emp.id}|${f.id}`] ?? ''}
                      onChange={(v) => d.setFactorInput(emp.id, f.id, v)}
                    />
                  </td>
                ))}
                <td className="card-actions">
                  <button type="button" onClick={() => void d.saveFactorInput(emp.id)}>
                    <Save size={13} /> ذخیره
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/** فیش‌های دوره‌ی انتخاب‌شده + سه خروجی + کشوی چاپ. */
function PayslipsCard({ d }: { d: PayrollRunDraft }) {
  const pg = usePagination(d.payslips, 10)
  const has = d.payslips.length > 0
  return (
    <SectionCard
      icon={FileText}
      title={has ? `${d.payslips.length.toLocaleString('fa-IR')} فیشِ این دوره` : 'فیش‌های این دوره'}
      tip={
        has
          ? 'قالبِ ستون‌های فایلِ بیمه و مالیات عمومی است؛ پیش از ارسالِ رسمی، با آخرین مشخصاتِ سامانه‌ی مربوطه تطبیقش دهید. دیسکتِ پرداخت شماره‌حسابِ کارمند را از پرونده‌اش می‌خواند — کارمندِ بی‌شماره‌حساب حذف نمی‌شود، ستونش خالی می‌آید تا ببینیدش.'
          : undefined
      }
      actions={
        //: سه خروجیِ همان دوره: بیمه برای تأمین اجتماعی، مالیات برای سازمان مالیاتی، و
        //: پرداخت برای بانک. هر سه از عددِ *همان فیش* می‌خوانند، نه محاسبه‌ی دوباره —
        //: وگرنه فایلِ اداره و فیشِ کارمند دو تا می‌شوند.
        has && (
          <>
            <button type="button" onClick={() => void d.downloadCsv('insurance-list')}>
              <Download size={13} /> لیست بیمه
            </button>
            <button type="button" onClick={() => void d.downloadCsv('tax-list')}>
              <Download size={13} /> فایل مالیات
            </button>
            <button type="button" onClick={() => void d.downloadCsv('payment-list')}>
              <Download size={13} /> دیسکت پرداخت
            </button>
          </>
        )
      }
    >
      {!has ? (
        <div className="ef-empty">هنوز فیشی برای این دوره صادر نشده — کارکرد را ذخیره کنید و «صدور فیش‌های حقوقی» را بزنید.</div>
      ) : (
        <>
          <div className="table-scroll">
            <table className="entity-table payslip-table cards-on-mobile">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>کارمند</th>
                  <th>ناخالص</th>
                  <th>بیمه</th>
                  <th>مالیات</th>
                  <th>خالص پرداختی</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((p) => {
                  const emp = d.empById.get(p.employee_id)
                  return (
                    <tr key={p.id}>
                      <td data-label="شماره">{p.number == null ? '—' : p.number.toLocaleString('fa-IR')}</td>
                      <td className="entity-name" data-label="کارمند">
                        {emp ? `${emp.first_name} ${emp.last_name}` : '—'}
                      </td>
                      <td data-label="ناخالص" className="money-cell">
                        {faMoney(p.gross_pay)}
                      </td>
                      <td data-label="بیمه" className="money-cell">
                        {faMoney(p.insurance_employee_share)}
                      </td>
                      <td data-label="مالیات" className="money-cell">
                        {faMoney(p.tax_amount)}
                      </td>
                      <td data-label="خالص پرداختی" className="money-cell">
                        <strong>{faMoney(p.net_pay)}</strong>
                      </td>
                      <td className="payslip-action card-actions">
                        <button type="button" onClick={() => d.setOpenPayslip(p)}>
                          <FileText size={13} /> فیش / چاپ
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </>
      )}

      {d.openPayslip && (
        <PayslipDrawer
          payslip={d.openPayslip}
          employee={d.empById.get(d.openPayslip.employee_id)}
          period={d.selectedPeriod}
          onClose={() => d.setOpenPayslip(null)}
        />
      )}
    </SectionCard>
  )
}
