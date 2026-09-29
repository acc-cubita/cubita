import { CheckCircle2, AlertTriangle, Info } from 'lucide-react'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { entryAccountName, entryAmount, entryTotals } from '../lib/entryPresentation'
import { StatusChip, sourceText } from '../pages/accounting/kit'
import type { JournalEntryRecord } from '../api'

/** تنها نمای مشترکِ سند ثبت‌شده؛ بدون فرم و بدون تغییرِ دادهٔ حسابداری. */
export function EntryCard({ entry, accountNames, onOpenSource }: {
  entry: JournalEntryRecord
  accountNames?: Map<string, string>
  onOpenSource?: () => void
}) {
  const hasFx = entry.lines.some((line) => line.currency_code)
  const hasTracking = entry.lines.some((line) => line.tracking_no || line.tracking_date)
  const hasDimensions = entry.lines.some((line) => line.analytic_id || line.cost_center_id)
  const columns = 5 + Number(hasFx) + Number(hasTracking) + Number(hasDimensions)
  const totals = entryTotals(entry.lines)
  const balanceText = totals.state === 'balanced' ? 'سند تراز است'
    : totals.state === 'unbalanced' ? `اختلاف بدهکار و بستانکار: ${totals.difference} ریال`
    : totals.state === 'empty' ? 'مبلغی در ردیف‌های سند ثبت نشده است'
    : 'به علت مبلغ نامعتبر، توازن سند قابل بررسی نیست'
  const BalanceIcon = totals.state === 'balanced' ? CheckCircle2
    : totals.state === 'unbalanced' || totals.state === 'unknown' ? AlertTriangle : Info

  return (
    <article className="entry-document" aria-label="برگهٔ سند حسابداری">
      <header className="entry-document-head">
        <div>
          <span className="entry-document-eyebrow">مشخصات سند</span>
          <h3>{entry.number != null ? `سند شمارهٔ ${toFaDigits(entry.number)}` : 'سند بدون شماره'}</h3>
        </div>
        <div className="entry-document-badges">
          <StatusChip status={entry.status} voided={!!entry.voided_at} />
          {entry.reverses_entry_id && <span className="entry-reversal">سند برگشتی</span>}
        </div>
      </header>

      <dl className="entry-document-meta">
        <div><dt>تاریخ سند</dt><dd>{formatJalali(entry.entry_date)}</dd></div>
        <div><dt>شمارهٔ عطف</dt><dd>{entry.atf_number != null ? toFaDigits(entry.atf_number) : '—'}</dd></div>
        <div><dt>شمارهٔ فرعی</dt><dd><bdi>{entry.sub_number ? toFaDigits(entry.sub_number) : '—'}</bdi></dd></div>
        <div><dt>منشأ ثبت</dt><dd>{onOpenSource ? (
          <button type="button" className="link-btn" onClick={onOpenSource}>{sourceText(entry)}</button>
        ) : sourceText(entry)}</dd></div>
      </dl>

      <section className="entry-document-description" aria-label="شرح سند">
        <span className="entry-document-eyebrow">شرح سند</span>
        <p className={!entry.description ? 'muted' : undefined}>
          {entry.description || 'شرحی برای این سند ثبت نشده است.'}
        </p>
      </section>

      <div className="entry-document-table-head">
        <span>ردیف‌های سند <span className="entry-line-count">{toFaDigits(entry.lines.length)} ردیف</span></span>
        <span className="entry-unit">مبالغ به ریال</span>
      </div>
      <div className="table-scroll entry-document-grid" tabIndex={0} role="region" aria-label="جدول ردیف‌های سند؛ ستون‌های بیشتر با پیمایش افقی">
        <table className="cards-on-mobile acc-table entry-lines">
          <caption>ردیف‌های سند حسابداری، مبالغ به ریال</caption>
          <thead><tr>
            <th className="entry-row-no">ردیف</th>
            <th>حساب</th>
            <th>شرح ردیف</th>
            {hasDimensions && <th>تفصیلی / مرکز</th>}
            {hasFx && <th>اطلاعات ارزی</th>}
            {hasTracking && <th>پیگیری</th>}
            <th className="num">بدهکار</th>
            <th className="num">بستانکار</th>
          </tr></thead>
          <tbody>
            {entry.lines.length === 0 ? <tr><td colSpan={columns} data-label="ردیف‌ها" className="card-wide entry-empty">
              ردیفی برای این سند دریافت نشد. نمایش را ببندید و دوباره باز کنید.
            </td></tr> : null}
            {entry.lines.map((line, index) => (
              <tr key={line.id}>
                <td className="entry-row-no" data-label="ردیف">{toFaDigits(index + 1)}</td>
                <td className="card-title" data-label="حساب">
                  <div className="entry-account">
                    {line.account_code && <bdi className="entry-account-code">{toFaDigits(line.account_code)}</bdi>}
                    <span className={!line.account_name && !accountNames?.has(line.account_id) ? 'muted' : undefined}>
                      {entryAccountName(line, accountNames)}
                    </span>
                  </div>
                </td>
                <td data-label="شرح ردیف" className="entry-line-description card-wide">{line.description || '—'}</td>
                {hasDimensions && <td data-label="تفصیلی / مرکز" className="card-wide">
                  <div className="entry-line-details">
                    {line.analytic_id && <span><small>تفصیلی: </small>{line.analytic_code && `${toFaDigits(line.analytic_code)} — `}{line.analytic_name || 'نام در دسترس نیست'}</span>}
                    {line.cost_center_id && <span><small>مرکز: </small>{line.cost_center_code && `${toFaDigits(line.cost_center_code)} — `}{line.cost_center_name || 'نام در دسترس نیست'}</span>}
                    {!line.analytic_id && !line.cost_center_id && '—'}
                  </div>
                </td>}
                {hasFx && <td data-label="اطلاعات ارزی">
                  {line.currency_code ? <div className="entry-line-details">
                    <span className="num">{entryAmount(line.fx_amount)} <bdi>{line.currency_code}</bdi></span>
                    {line.fx_rate != null && <small>نرخ: <span className="num">{entryAmount(line.fx_rate)}</span></small>}
                  </div> : '—'}
                </td>}
                {hasTracking && <td data-label="پیگیری">
                  <div className="entry-line-details">
                    {line.tracking_no && <bdi>{toFaDigits(line.tracking_no)}</bdi>}
                    {line.tracking_date && <small>{formatJalali(line.tracking_date)}</small>}
                    {!line.tracking_no && !line.tracking_date && '—'}
                  </div>
                </td>}
                <td data-label="بدهکار" className="num">{entryAmount(line.debit, true)}</td>
                <td data-label="بستانکار" className="num">{entryAmount(line.credit, true)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="entry-totals">
              <td colSpan={columns - 2} data-label="جمع" className="card-wide">جمع سند <small>({toFaDigits(entry.lines.length)} ردیف)</small></td>
              <td className="num" data-label="جمع بدهکار">{totals.debit}</td>
              <td className="num" data-label="جمع بستانکار">{totals.credit}</td>
            </tr>
            <tr className="entry-balance-row"><td colSpan={columns} data-label="وضعیت توازن" className="card-wide">
              <span className={`entry-balance entry-balance--${totals.state}`}><BalanceIcon size={16} aria-hidden="true" />{balanceText}</span>
            </td></tr>
          </tfoot>
        </table>
      </div>
      <p className="entry-document-note">نام حساب‌ها و تفصیلی‌ها مطابق اطلاعات فعلی چارت نمایش داده می‌شود.</p>
    </article>
  )
}
