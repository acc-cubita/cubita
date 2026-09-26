import { useMemo, useState } from 'react'
import { AlertTriangle, Download, Percent, Printer } from 'lucide-react'

import { fetchVatReport } from '../../api'
import { CountBadge } from '../../components/form/FormKit'
import { Amount } from '../../components/ReportViews'
import { SectionCard } from '../../components/SectionCard'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, isoToJalali, todayIso, toFaDigits } from '../../lib/jalali'
import { BREAKDOWN_ROWS, breakdownTotals, quarterRange, vatCsv, vatNet, vatRows } from '../../lib/vatSheet'
import { AsyncBlock, OpsPage, fa, useAsync } from './kit'

const QUARTERS = [
  { value: 1, label: 'بهار', months: 'فروردین تا خرداد' },
  { value: 2, label: 'تابستان', months: 'تیر تا شهریور' },
  { value: 3, label: 'پاییز', months: 'مهر تا آذر' },
  { value: 4, label: 'زمستان', months: 'دی تا اسفند' },
]

/**
 * «مالیات بر ارزش افزوده» با تمِ اکسلی (الگوی «د» از `cubita-excel-theme`).
 *
 * - سربرگ: سال و فصل به‌شکلِ نیمه‌های یک خانه، و بازه‌ی شمسیِ همان فصل.
 * - «محاسبه‌ی مالیاتِ فصل» برگه‌ای مثلِ اظهارنامه است (`lib/vatSheet.ts`): مالیاتِ فروش و اعتبارِ خرید هر کدام با
 *   برگشتش (منفی) و جمعِ خودش، و «مالیاتِ خالصِ فصل» در پانویس — عددِ `net_vat`ِ سرور با نشانِ پرداختنی/استردادی.
 *   سه کارتِ خلاصه‌ی بالای صفحه برداشته شدند؛ همین سه عدد در برگه‌اند.
 * - «ترکیبِ پایه» گریدِ مشمول/معاف با جمع در پانویس؛ فاکتورهای «معاف و مشمول با نرخِ غیرصفر» زیرش.
 */
export function VatPage({ token }: { token: string }) {
  const now = isoToJalali(todayIso())
  const [year, setYear] = useState(now.jy)
  const [quarter, setQuarter] = useState(Math.ceil(now.jm / 3))
  const { from, to } = useMemo(() => quarterRange(year, quarter), [year, quarter])
  const report = useAsync(() => fetchVatReport(token, from, to), [token, from, to])
  const data = report.data
  const years = [now.jy + 1, now.jy, now.jy - 1, now.jy - 2]
  const q = QUARTERS.find((x) => x.value === quarter)!
  const net = data ? vatNet(data) : null
  const base = data ? breakdownTotals(data) : null

  //: فروش و خرید در یک فهرست با برچسبِ نوع — کاربر دنبالِ «کدام فاکتور» است، نه
  //: دنبالِ دو جدولِ جدا که باید بینشان چشم بچرخاند.
  const mixed = [
    ...(data?.mixed_sales_invoices ?? []).map((m) => ({ ...m, kind: 'فروش' })),
    ...(data?.mixed_purchase_invoices ?? []).map((m) => ({ ...m, kind: 'خرید' })),
  ]
  const period = `${q.label} ${toFaDigits(year)} — ${formatJalali(from)} تا ${formatJalali(to)}`

  return (
    <OpsPage
      canvas
      icon={Percent}
      title="مالیات بر ارزش افزوده"
      description="مالیاتِ فروش منهای اعتبارِ مالیاتیِ خرید در یک فصل — همان عددی که در اظهارنامه‌ی فصلی می‌رود."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="فصلِ اظهارنامه">
          <div className="jh-row vat-row--period">
            <div className="jh-field">
              <span className="jh-label">سال</span>
              <div className="cc-presets rh-seg" role="group" aria-label="سال">
                {years.map((y) => (
                  <button
                    key={y}
                    type="button"
                    className={year === y ? 'is-active' : ''}
                    aria-pressed={year === y}
                    onClick={() => setYear(y)}
                  >
                    {toFaDigits(y)}
                  </button>
                ))}
              </div>
            </div>
            <div className="jh-field">
              <span className="jh-label">فصل</span>
              <div className="cc-presets rh-seg" role="group" aria-label="فصل">
                {QUARTERS.map((x) => (
                  <button
                    key={x.value}
                    type="button"
                    title={x.months}
                    className={quarter === x.value ? 'is-active' : ''}
                    aria-pressed={quarter === x.value}
                    onClick={() => setQuarter(x.value)}
                  >
                    {x.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="jh-field rp-hint-cell">
              <span className="jh-label">بازه</span>
              <p>
                {formatJalali(from)} تا {formatJalali(to)} ({q.months})
              </p>
            </div>
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Percent}
        title="محاسبه‌ی مالیاتِ فصل"
        description={period}
        tip="برگشت‌ها منفی‌اند تا هر بخش از بالا به پایین جمع بخورد. «مالیاتِ خالصِ فصل» = خالصِ مالیاتِ فروش − خالصِ اعتبارِ خرید؛ منفی یعنی طلب از سازمان (استرداد یا انتقال به فصلِ بعد)."
        actions={
          <div className="jg-head-actions">
            <button
              type="button"
              className="ef-btn-secondary"
              disabled={!data}
              onClick={() => data && downloadCsv(`vat-${year}-q${quarter}`, ['شرح', 'مبلغ خالص', 'مالیات'], vatCsv(data))}
            >
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" disabled={!data} onClick={() => window.print()}>
              <Printer size={14} /> چاپ
            </button>
          </div>
        }
      >
        <AsyncBlock loading={report.loading && !data} error={data ? null : report.error}>
          {data && net && (
            <div className={`rp-body${report.loading ? ' is-loading' : ''}`} aria-busy={report.loading}>
              {report.error && <p className="hint acc-note acc-note--err">{report.error}</p>}
              <div className="table-scroll ef-table-wrap rp-scroll">
                <table className="ef-table xl-grid cards-on-mobile rp-table rp-statement vat-calc">
                  <colgroup>
                    <col />
                    <col className="rp-c-amt" />
                    <col className="rp-c-amt" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>شرح</th>
                      <th className="num">مبلغِ خالص</th>
                      <th className="num">مالیات و عوارض</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vatRows(data).map((r) =>
                      r.kind === 'section' ? (
                        <tr key={r.label} className="rp-sec">
                          <td className="card-full" colSpan={3}>
                            {r.label}
                          </td>
                        </tr>
                      ) : (
                        <tr key={r.label} className={r.kind === 'subtotal' ? 'rp-sub' : undefined}>
                          <td className={`card-title${r.kind === 'line' ? ' rp-name' : ''}`}>{r.label}</td>
                          <td className="num" data-label="مبلغِ خالص">
                            <Amount value={r.net} />
                          </td>
                          <td className="num" data-label="مالیات و عوارض">
                            <Amount value={r.vat} />
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                  <tfoot>
                    <tr className="rp-total">
                      <td className="card-title">
                        مالیاتِ خالصِ فصل
                        <span
                          className={`xl-check ${net.amount > 0 ? 'xl-check--due' : 'xl-check--ok'}`}
                          title={net.amount < 0 ? 'طلب از سازمان: استرداد یا انتقال به فصلِ بعد' : undefined}
                        >
                          {net.label}
                        </span>
                      </td>
                      <td className="card-hide" />
                      <td className={`num${net.amount ? '' : ' rp-zero'}`} data-label="مالیاتِ خالص">
                        <Amount value={net.amount} />
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </AsyncBlock>
      </SectionCard>

      <SectionCard
        icon={Percent}
        title="ترکیبِ پایه"
        description="چقدر از فروش و خریدِ دوره مشمول بوده و چقدر معاف. وضعیت از لحظه‌ی معامله می‌آید، نه از وضعیتِ امروزِ کالا. برگشت‌ها در این جدول نمی‌آیند."
        badge={mixed.length > 0 ? <CountBadge>{fa(mixed.length)} فاکتورِ ناهمخوان</CountBadge> : undefined}
      >
        <AsyncBlock loading={report.loading && !data} error={data ? null : report.error}>
          {data && base && (
            <div className={`rp-body${report.loading ? ' is-loading' : ''}`}>
              <div className="table-scroll ef-table-wrap rp-scroll">
                <table className="ef-table xl-grid cards-on-mobile rp-table vat-base">
                  <thead>
                    <tr>
                      <th>طبقه</th>
                      <th className="num">فروش</th>
                      <th className="num">خرید</th>
                    </tr>
                  </thead>
                  <tbody>
                    {BREAKDOWN_ROWS.map(([label, key]) => (
                      <tr key={key} className={key.startsWith('exempt') ? 'vat-exempt' : undefined}>
                        <td className="card-title">{label}</td>
                        <td className="num" data-label="فروش">
                          <Amount value={data.sales_breakdown[key]} />
                        </td>
                        <td className="num" data-label="خرید">
                          <Amount value={data.purchase_breakdown[key]} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="rp-total">
                      <td className="card-title">جمع</td>
                      <td className="num" data-label="جمعِ فروش">
                        <Amount value={base.sales} />
                      </td>
                      <td className="num" data-label="جمعِ خرید">
                        <Amount value={base.purchase} />
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {mixed.length > 0 && (
                <>
                  <p className="fy-note fy-note--warn">
                    <AlertTriangle size={14} /> {fa(mixed.length)} فاکتور ردیفِ معاف و مشمول را با هم دارند و نرخِ
                    سربرگشان غیرصفر است — یعنی روی ردیفِ معاف هم مالیات گرفته شده.
                  </p>
                  <div className="table-scroll ef-table-wrap rp-scroll">
                    <table className="ef-table xl-grid cards-on-mobile rp-table vat-mixed">
                      <thead>
                        <tr>
                          <th>فاکتور</th>
                          <th>تاریخ</th>
                          <th className="num">خالصِ معاف</th>
                          <th className="num">مالیاتِ فاکتور</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mixed.map((m) => (
                          <tr key={m.invoice_id}>
                            <td className="card-title">
                              {m.kind} {m.number != null ? fa(m.number) : '—'}
                            </td>
                            <td data-label="تاریخ">{formatJalali(m.invoice_date)}</td>
                            <td className="num" data-label="خالصِ معاف">
                              <Amount value={m.exempt_net} />
                            </td>
                            <td className="num rp-late" data-label="مالیاتِ فاکتور">
                              <Amount value={m.tax_amount} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
