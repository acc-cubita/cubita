import { Fragment, useEffect, useMemo, useState } from 'react'
import { Receipt } from 'lucide-react'
import {
  fetchEmployees,
  fetchPayrollPeriods,
  fetchPayslipLedger,
  type EmployeeRecord,
  type PayrollPeriodRecord,
  type PayslipLineRecord,
  type PayslipRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { Pager, usePagination } from '../../components/Pager'
import { SectionCard } from '../../components/SectionCard'
import { JALALI_MONTH_NAMES } from '../../lib/jalali'
import { AsyncBlock, OpsPage } from '../accounting/kit'

/**
 * «مرور حقوق» — دفترِ فیش‌های صادرشده در همه‌ی دوره‌ها.
 *
 * چرا این با تبِ «کارکرد و صدور فیش» یکی نیست: آن‌جا **کارِ** یک دوره انجام می‌شود
 * (دوره ساخته می‌شود، کارکرد وارد می‌شود، فیش صادر می‌شود) و جدولش فقط فیش‌های
 * همان دوره را دارد. این‌جا **مرور** است — چند دوره کنارِ هم، فیلترِ کارمند، و
 * جمع‌های ستونی. همان مرزِ «عملیات ↔ فهرست» که بقیه‌ی ماژول‌ها دارند.
 *
 * فیلتر سمتِ سرور می‌رود (`period_id` / `employee_id`)، نه اینکه کلِ دفتر کشیده
 * شود و در مرورگر غربال شود — با چند سالِ فیش، آن روش از کار می‌افتد.
 */

const ORIGIN_LABELS: Record<string, string> = {
  contract: 'حکم حقوقی',
  attendance: 'کارکرد دوره',
  settings: 'تنظیمات حقوق',
  loan: 'وام کارکنان',
}

const fa = (n: number) => n.toLocaleString('fa-IR')
const faAmount = (v: string | number) => (Number(v) === 0 ? '—' : Math.round(Number(v)).toLocaleString('fa-IR'))
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

const periodLabel = (p: PayrollPeriodRecord) =>
  `${JALALI_MONTH_NAMES[p.month - 1] ?? p.month} ${fa(p.year)}`

/**
 * تفکیکِ یک فیش — «این خالص از چه ساخته شد».
 *
 * تا مهاجرتِ ۰۱۲۸ این سؤال جواب نداشت: مزایا یک عدد بود و هر عاملی که مسکن یا
 * خوار‌وبار نبود در همان یک عدد گم می‌شد. حالا هر عامل ردیفِ خودش را دارد، با
 * **نامی که در لحظه‌ی صدور داشت** — نه نامِ امروزش.
 *
 * ستونِ «منشأ» می‌گوید برای عوض‌کردنِ هر جزء کجا باید رفت؛ بدونش کاربر عدد را
 * می‌بیند و نمی‌داند کدام فرم را باز کند.
 */
function PayslipBreakdown({ lines, net }: { lines: PayslipLineRecord[]; net: string }) {
  const earnings = lines.filter((l) => l.direction === 'earning')
  const deductions = lines.filter((l) => l.direction === 'deduction')
  const sum = (rows: PayslipLineRecord[]) => rows.reduce((t, l) => t + Number(l.amount || 0), 0)

  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr>
            <th>جزء</th>
            <th>منشأ</th>
            <th>توضیح</th>
            <th>مبلغ</th>
          </tr>
        </thead>
        <tbody>
          {earnings.map((l) => (
            <tr key={l.id}>
              <td className="card-title" data-label="جزء">{l.factor_name}</td>
              <td data-label="منشأ">{ORIGIN_LABELS[l.origin] ?? l.origin}</td>
              <td className="card-wide" data-label="توضیح">{l.note || '—'}</td>
              <td className="num" data-label="مبلغ">{faAmount(l.amount)}</td>
            </tr>
          ))}
          <tr>
            <td className="card-title" data-label="جمع" colSpan={3}>جمعِ درآمدها</td>
            <td className="num" data-label="مبلغ">{faAmount(sum(earnings))}</td>
          </tr>
          {deductions.map((l) => (
            <tr key={l.id}>
              <td className="card-title" data-label="جزء">{l.factor_name}</td>
              <td data-label="منشأ">{ORIGIN_LABELS[l.origin] ?? l.origin}</td>
              <td className="card-wide" data-label="توضیح">{l.note || '—'}</td>
              <td className="num" data-label="مبلغ">‎−{faAmount(l.amount)}</td>
            </tr>
          ))}
          <tr>
            <td className="card-title" data-label="جمع" colSpan={3}>جمعِ کسورات</td>
            <td className="num" data-label="مبلغ">‎−{faAmount(sum(deductions))}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td className="card-title" data-label="خالص" colSpan={3}>خالص پرداختی</td>
            <td className="num" data-label="خالص">{faAmount(net)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

export function PayslipLedgerPage({ token }: { token: string }) {
  const [rows, setRows] = useState<PayslipRecord[] | null>(null)
  const [periods, setPeriods] = useState<PayrollPeriodRecord[]>([])
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  // کدام فیش تفکیکش باز است — یکی در هر لحظه، وگرنه جدول خوانده نمی‌شود.
  const [openId, setOpenId] = useState<string | null>(null)
  const [periodId, setPeriodId] = useState('')
  const [employeeId, setEmployeeId] = useState('')

  useEffect(() => {
    void fetchPayrollPeriods(token).then(setPeriods).catch(() => {})
    void fetchEmployees(token).then(setEmployees).catch(() => {})
  }, [token])

  useEffect(() => {
    let alive = true
    setRows(null)
    setError(null)
    void fetchPayslipLedger(token, { periodId, employeeId })
      .then((r) => { if (alive) setRows(r) })
      .catch((err) => { if (alive) setError(errText(err)) })
    return () => { alive = false }
  }, [token, periodId, employeeId])

  const empName = useMemo(
    () => new Map(employees.map((e) => [e.id, `${e.first_name} ${e.last_name}`.trim()])),
    [employees],
  )
  const periodName = useMemo(() => new Map(periods.map((p) => [p.id, periodLabel(p)])), [periods])

  //: جمع‌ها روی همان ردیف‌هایی است که سرور برگردانده — یعنی همان چیزی که کاربر
  //: می‌بیند. جمعِ کلِ دفتر وقتی فیلتر فعال است گمراه‌کننده می‌شد.
  const totals = useMemo(() => {
    const sum = (pick: (p: PayslipRecord) => string) =>
      (rows ?? []).reduce((acc, r) => acc + Number(pick(r) || 0), 0)
    return {
      gross: sum((r) => r.gross_pay),
      insurance: sum((r) => r.insurance_employee_share),
      tax: sum((r) => r.tax_amount),
      loan: sum((r) => r.loan_deduction),
      other: sum((r) => r.other_deductions),
      net: sum((r) => r.net_pay),
    }
  }, [rows])

  const pg = usePagination(rows ?? [], 15, `${periodId}|${employeeId}`)
  const filtered = Boolean(periodId || employeeId)

  return (
    <OpsPage
      icon={Receipt}
      title="مرور حقوق"
      description="دفترِ فیش‌های حقوقیِ صادرشده در همه‌ی دوره‌ها، با جمعِ ناخالص، بیمه، مالیات و خالص."
    >
      <SectionCard
        icon={Receipt}
        title={rows ? `${fa(rows.length)} فیش` : 'در حال بارگذاری…'}
        actions={
          <>
            <select value={periodId} onChange={(e) => setPeriodId(e.target.value)}>
              <option value="">همه‌ی دوره‌ها</option>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>{periodLabel(p)}</option>
              ))}
            </select>
            <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
              <option value="">همه‌ی پرسنل</option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>{`${e.first_name} ${e.last_name}`.trim()}</option>
              ))}
            </select>
          </>
        }
      >
        <AsyncBlock
          loading={rows == null}
          error={error}
          empty={rows != null && rows.length === 0}
          emptyText={
            filtered
              ? 'فیشی با این فیلترها نیست — دوره یا کارمندِ دیگری را انتخاب کنید.'
              : 'هنوز فیشی صادر نشده — در «حقوق و دستمزد ← کارکرد و صدور فیش» دوره بسازید و فیش صادر کنید.'
          }
        >
          {rows != null && rows.length === 0 ? (
            <EmptyState
              icon={Receipt}
              text={
                filtered
                  ? 'فیشی با این فیلترها نیست — دوره یا کارمندِ دیگری را انتخاب کنید.'
                  : 'هنوز فیشی صادر نشده — در «حقوق و دستمزد ← کارکرد و صدور فیش» دوره بسازید و فیش صادر کنید.'
              }
            />
          ) : (
            <>
              <div className="table-scroll">
                <table className="cards-on-mobile">
                  <thead>
                    <tr>
                      <th>شماره</th>
                      <th>کارمند</th>
                      <th>دوره</th>
                      <th>حقوق پایه</th>
                      <th>مزایا</th>
                      <th>اضافه‌کاری</th>
                      <th>ناخالص</th>
                      <th>بیمه سهم کارمند</th>
                      <th>مالیات</th>
                      <th>قسط وام</th>
                      <th>سایر کسورات</th>
                      <th>خالص پرداختی</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {pg.pageItems.map((r) => (
                      <Fragment key={r.id}>
                      <tr>
                        <td className="card-title" data-label="شماره">{r.number == null ? '—' : fa(r.number)}</td>
                        <td data-label="کارمند">{empName.get(r.employee_id) ?? '—'}</td>
                        <td data-label="دوره">{periodName.get(r.period_id) ?? '—'}</td>
                        <td className="num" data-label="حقوق پایه">{faAmount(r.base_salary)}</td>
                        <td className="num" data-label="مزایا">{faAmount(r.allowances_total)}</td>
                        <td className="num" data-label="اضافه‌کاری">{faAmount(r.overtime_pay)}</td>
                        <td className="num" data-label="ناخالص">{faAmount(r.gross_pay)}</td>
                        <td className="num" data-label="بیمه سهم کارمند">{faAmount(r.insurance_employee_share)}</td>
                        <td className="num" data-label="مالیات">{faAmount(r.tax_amount)}</td>
                        <td className="num" data-label="قسط وام">{faAmount(r.loan_deduction)}</td>
                        <td className="num" data-label="سایر کسورات">{faAmount(r.other_deductions)}</td>
                        <td className="num" data-label="خالص پرداختی">{faAmount(r.net_pay)}</td>
                        <td className="card-actions">
                          {r.lines.length > 0 ? (
                            <button
                              type="button"
                              className="btn-ghost"
                              onClick={() => setOpenId(openId === r.id ? null : r.id)}
                            >
                              {openId === r.id ? 'بستنِ تفکیک' : 'تفکیک'}
                            </button>
                          ) : (
                            <span className="field-hint">تفکیک ندارد</span>
                          )}
                        </td>
                      </tr>
                      {openId === r.id && (
                        <tr>
                          <td className="card-full" colSpan={13}>
                            <PayslipBreakdown lines={r.lines} net={r.net_pay} />
                          </td>
                        </tr>
                      )}
                      </Fragment>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td className="card-title" data-label="جمع" colSpan={6}>جمعِ ردیف‌های نمایش‌داده‌شده</td>
                      <td className="num" data-label="ناخالص">{faAmount(totals.gross)}</td>
                      <td className="num" data-label="بیمه سهم کارمند">{faAmount(totals.insurance)}</td>
                      <td className="num" data-label="مالیات">{faAmount(totals.tax)}</td>
                      <td className="num" data-label="قسط وام">{faAmount(totals.loan)}</td>
                      <td className="num" data-label="سایر کسورات">{faAmount(totals.other)}</td>
                      <td className="num" data-label="خالص پرداختی">{faAmount(totals.net)}</td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
