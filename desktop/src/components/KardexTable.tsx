import { ArrowDownToLine, ArrowUpFromLine, Boxes, History, TriangleAlert } from 'lucide-react'
import type { KardexReport } from '../api'
import { formatJalali } from '../lib/jalali'

const faQty = (s: string) => (Number(s) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })
//: بها و ارزش به ریالِ صحیح نمایش داده می‌شوند؛ میانگین چهار رقم اعشار دارد ولی دفتر
//: به ریالِ صحیح می‌نویسد و کسرِ نمایشی فقط عدد را از دفتر ناخواناتر می‌کند.
const faMoney = (s: string) => Math.round(Number(s) || 0).toLocaleString('fa-IR')
const faNo = (n: number) => n.toLocaleString('fa-IR', { useGrouping: false })

/**
 * خلاصه‌ی کاردکس — مانده‌ی اول، ورود، خروج و مانده‌ی پایان، به تعداد و ریال.
 *
 * یک نمایش برای سه جا (تبِ «کاردکس» در انبار، کشوی کالا، گزارش‌ها). تا امروز هر سه
 * جدولِ خودشان را داشتند و ستونِ ارزش در هیچ‌کدام نبود.
 */
export function KardexSummary({ data }: { data: KardexReport }) {
  return (
    <>
      <div className="kardex-summary">
        <div className="kardex-stat">
          <History size={14} /><span>موجودی اول</span><strong>{faQty(data.opening_qty)}</strong>
          <small>{faMoney(data.opening_value)} ریال</small>
        </div>
        <div className="kardex-stat">
          <ArrowDownToLine size={14} /><span>کل ورود</span><strong className="pos-in">{faQty(data.total_in)}</strong>
          <small>{faMoney(data.total_value_in)} ریال</small>
        </div>
        <div className="kardex-stat">
          <ArrowUpFromLine size={14} /><span>کل خروج</span><strong className="pos-out">{faQty(data.total_out)}</strong>
          <small>{faMoney(data.total_value_out)} ریال</small>
        </div>
        <div className="kardex-stat">
          <Boxes size={14} /><span>موجودی پایان</span><strong>{faQty(data.closing_qty)}</strong>
          <small>{faMoney(data.closing_value)} ریال · میانگین {faMoney(data.average_cost)}</small>
        </div>
      </div>
      {data.stale_count > 0 && (
        <p className="hint kardex-stale-note">
          <TriangleAlert size={14} />{' '}
          {`${faNo(data.stale_count)} حرکت با بهایی ثبت شده که با میانگینِ همان تاریخ نمی‌خواند — معمولاً چون سندی بعداً با تاریخِ گذشته ثبت یا باطل شده. «بهای واحد» بهای درست است و بهای سند کنارش آمده؛ سندِ حسابداریِ آن حرکات هنوز بهای سند را دارد.`}
        </p>
      )}
    </>
  )
}

/**
 * ردیف‌های کاردکس، به ترتیبِ تاریخ — با بها، مبلغ، موجودی و ارزشِ در حال اجرا.
 *
 * «بهای واحد» بهای ارزش‌گذاری است (بازپخشِ دفتر به ترتیبِ تاریخ)؛ وقتی با بهایی که سند
 * نوشته فرق کند، نشانِ «منقضی» همراهِ بهای سند می‌آید — روی موبایل هم دیده شود، نه در
 * راهنمای شناور. ردیفِ سندِ باطل و جبرانش کم‌رنگ‌اند: جمعشان صفر است و میانگین را
 * تکان نمی‌دهند.
 */
export function KardexTable({
  data,
  className = 'kardex-table',
  grid = false,
}: {
  data: KardexReport
  className?: string
  /** گریدِ اکسلی (`xl-grid`) — صفحه‌ی «گزارش‌ها». پیش‌فرض همان جدولِ کارتیِ انبار. */
  grid?: boolean
}) {
  if (data.lines.length === 0) return <p className="muted">هیچ حرکتی برای این کالا ثبت نشده.</p>
  return (
    <div className="entity-table-wrap">
      <div className={grid ? 'table-scroll ef-table-wrap rp-scroll' : 'table-scroll'}>
        <table className={`${grid ? 'ef-table xl-grid rp-table' : 'entity-table'} ${className} cards-on-mobile`}>
          <thead>
            <tr>
              <th>تاریخ</th>
              <th>شرح</th>
              <th>ورود</th>
              <th>خروج</th>
              <th>بهای واحد</th>
              <th>مبلغ</th>
              <th>مانده</th>
              <th>ارزش مانده</th>
              <th>میانگین</th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((l, i) => {
              const amount = Number(l.value_in) > 0 ? l.value_in : l.value_out
              return (
                <tr key={i} className={l.voided ? 'kardex-voided' : undefined}>
                  <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                  <td data-label="شرح">
                    {l.source_label}
                    {l.source_number != null && ` شماره ${faNo(l.source_number)}`}
                    {l.voided && <span className="status-badge tone-muted">باطل</span>}
                  </td>
                  <td data-label="ورود" className="pos-in">{Number(l.qty_in) > 0 ? faQty(l.qty_in) : '—'}</td>
                  <td data-label="خروج" className="pos-out">{Number(l.qty_out) > 0 ? faQty(l.qty_out) : '—'}</td>
                  <td data-label="بهای واحد" className="money-cell">
                    {faMoney(l.unit_cost)}
                    {l.stale && (
                      <span className="status-badge tone-warning">منقضی · سند {faMoney(l.recorded_unit_cost)}</span>
                    )}
                    {!l.stale && l.adjusted && <span className="status-badge tone-muted">اصلاح‌شده</span>}
                  </td>
                  <td data-label="مبلغ" className="money-cell">{Number(amount) ? faMoney(amount) : '—'}</td>
                  <td data-label="مانده" className="money-cell"><strong>{faQty(l.balance_qty)}</strong></td>
                  <td data-label="ارزش مانده" className="money-cell">{faMoney(l.balance_value)}</td>
                  <td data-label="میانگین" className="money-cell">{faMoney(l.average_cost)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
