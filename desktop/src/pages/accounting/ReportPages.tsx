import { Download, FileSpreadsheet, Printer, Wallet } from 'lucide-react'
import { fetchLegalBook } from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { Pager, usePagination } from '../../components/Pager'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  AsyncBlock,
  BalanceFooter,
  Metric,
  OpsPage,
  RangeBar,
  StatusChip,
  fa,
  faAmount,
  faInt,
  useAsync,
  useRange,
} from './kit'

/**
 * چهار گزارشِ پایه‌ی دفترداری.
 *
 * سه‌تای اولش نمایشِ همان یک دادهٔ گردش‌اند در سه سطحِ ریزشدن — تراز (خلاصه)، دفتر
 * (سندبه‌سند)، دفاترِ قانونی (ردیف‌به‌ردیف با چیدمانِ رسمی). چهارمی مالیات است که
 * دادهٔ خودش را دارد. هر چهار تا خروجیِ CSV می‌دهند چون هر کدامشان دیر یا زود باید
 * جایی بیرون از برنامه تحویل شوند.
 */

/** «گزارش ترازها» فایلِ خودش را دارد (تمِ اکسلی)؛ از این‌جا هم صادر می‌شود تا واردکننده‌ها دست نخورند. */
export { BalanceReportPage } from './BalanceReportPage'

// ═══════════════════════ ۲) گزارش دفتر ═══════════════════════

/** «گزارش دفتر» فایلِ خودش را دارد (تمِ اکسلی)؛ از این‌جا هم صادر می‌شود تا واردکننده‌ها دست نخورند. */
export { LedgerReportPage } from './LedgerReportPage'

// ═════════════ ۳) مالیات بر ارزش افزوده ═════════════

/** «مالیات بر ارزش افزوده» فایلِ خودش را دارد (تمِ اکسلی)؛ از این‌جا هم صادر می‌شود تا واردکننده‌ها دست نخورند. */
export { VatPage } from './VatPage'

// ═════════════ ۴) دفاتر تجارت الکترونیک ═════════════

export function LegalBooksPage({ token }: { token: string }) {
  const range = useRange('year')
  const book = useAsync(
    () =>
      range.from && range.to
        ? fetchLegalBook(token, range.from, range.to)
        : fetchLegalBook(token, '1900-01-01', todayIso()),
    [token, range.from, range.to],
  )
  const data = book.data
  const rows = data?.rows ?? []
  const pg = usePagination(rows, 40)

  function exportCsv() {
    downloadCsv(
      `dafater-${range.from ?? 'all'}`,
      ['ردیف', 'شماره سند', 'تاریخ', 'کد حساب', 'نام حساب', 'شرح', 'بدهکار', 'بستانکار', 'وضعیت'],
      rows.map((r, i) => [
        i + 1,
        r.entry_number ?? '',
        formatJalali(r.entry_date),
        r.account_code,
        r.account_name,
        r.description,
        Number(r.debit),
        Number(r.credit),
        r.voided ? 'باطل' : r.status === 'permanent' ? 'دائم' : 'موقت',
      ]),
    )
  }

  return (
    <OpsPage
      canvas
      icon={FileSpreadsheet}
      title="دفاتر تجارت الکترونیک"
      description="ردیف‌های دفترِ روزنامه با چیدمانِ دفاترِ قانونی — آماده‌ی خروجی و بارگذاری در سامانه. اسنادِ باطل و معکوسشان هر دو می‌آیند، چون دفترِ قانونی باید اصلاح را هم نشان دهد."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<FileSpreadsheet size={14} />} label="ردیفِ دفتر" value={faInt(rows.length)} />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ بدهکار"
              value={data ? fa(data.total_debit) : '—'}
              tone="in"
            />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ بستانکار"
              value={data ? fa(data.total_credit) : '—'}
              tone="out"
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={FileSpreadsheet}
        title="دفترِ روزنامه (قانونی)"
        description="یک ردیف به‌ازای هر ردیفِ سند، به‌ترتیبِ تاریخ و شماره."
        actions={
          <>
            <button type="button" className="ef-btn-secondary" onClick={exportCsv} disabled={rows.length === 0}>
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" onClick={() => window.print()}>
              <Printer size={14} /> چاپ
            </button>
          </>
        }
      >
        <AsyncBlock
          loading={book.loading}
          error={book.error}
          empty={rows.length === 0}
          emptyText="در این بازه ردیفی ثبت نشده."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="ef-table cards-on-mobile acc-table acc-table--wide">
              <thead>
                <tr>
                  <th>سند</th>
                  <th>تاریخ</th>
                  <th>کدِ حساب</th>
                  <th>نامِ حساب</th>
                  <th>شرح</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r, i) => (
                  <tr key={`${r.entry_id}-${i}`} className={r.voided ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="سند">
                      {fa(r.entry_number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(r.entry_date)}</td>
                    <td data-label="کدِ حساب" dir="ltr">
                      {r.account_code}
                    </td>
                    <td data-label="نامِ حساب">{r.account_name}</td>
                    <td data-label="شرح">{r.description || '—'}</td>
                    <td data-label="بدهکار" className="num">
                      {faAmount(r.debit)}
                    </td>
                    <td data-label="بستانکار" className="num">
                      {faAmount(r.credit)}
                    </td>
                    <td data-label="وضعیت">
                      <StatusChip status={r.status} voided={r.voided} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
          {data && (
            <BalanceFooter debit={Number(data.total_debit)} credit={Number(data.total_credit)} />
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
