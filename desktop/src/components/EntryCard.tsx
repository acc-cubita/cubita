import { formatJalali } from '../lib/jalali'
import { StatusChip, sourceText } from '../pages/accounting/kit'
import type { JournalEntryRecord } from '../api'

const fa = (n: number | string) => Math.round(Number(n) || 0).toLocaleString('fa-IR')
const faAmount = (n: number | string) => (Number(n) ? fa(n) : '—')

/**
 * یک سند با ردیف‌هایش — **تنها رندرِ این شکل در کلِ برنامه**.
 *
 * پیش از این فقط داخلِ `DaybookCard` وجود داشت. وقتی drill-down لازم شد
 * («ردیفِ دفتر → خودِ سند»)، وسوسه این بود که همان جدول دوباره در درایو نوشته
 * شود — یعنی دو نمای یک داده که روزی از هم جدا می‌افتند. به‌جایش همین‌جا بیرون
 * کشیده شد و هر دو از آن استفاده می‌کنند.
 *
 * `accountNames` اختیاری است: دفترِ روزنامه چارت را از قبل در دست دارد، ولی
 * درایو که تنها باز می‌شود ممکن است نداشته باشد — آن‌وقت نامِ حساب از خودِ ردیف
 * می‌آید اگر سرور فرستاده باشد.
 */
export function EntryCard({
  entry,
  accountNames,
  onOpenSource,
}: {
  entry: JournalEntryRecord
  accountNames?: Map<string, string>
  onOpenSource?: () => void
}) {
  const hasFx = entry.lines.some((l) => l.currency_code)
  const hasTracking = entry.lines.some((l) => l.tracking_no)

  return (
    <div className="acc-day">
      <h4 className="acc-day-head">
        سند {fa(entry.number ?? 0)} — {formatJalali(entry.entry_date)}
        <span>
          <StatusChip status={entry.status} voided={!!entry.voided_at} />{' '}
          {onOpenSource ? (
            <button type="button" className="link-btn" onClick={onOpenSource}>
              {sourceText(entry)}
            </button>
          ) : (
            sourceText(entry)
          )}
        </span>
      </h4>
      {entry.description && <p className="hint">{entry.description}</p>}
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>حساب</th>
              <th>شرح ردیف</th>
              {hasFx && <th>ارز</th>}
              {hasTracking && <th>پیگیری</th>}
              <th>بدهکار</th>
              <th>بستانکار</th>
            </tr>
          </thead>
          {/* audit-r9-exempt: سندِ ثبت‌شده همیشه دستِ‌کم دو ردیف دارد (دوطرفه
              بودن)؛ جدولِ خالی این‌جا حالتِ ممکنی نیست. */}
          <tbody>
            {entry.lines.map((l) => (
              <tr key={l.id}>
                <td className="card-title" data-label="حساب">
                  {accountNames?.get(l.account_id) ?? '—'}
                </td>
                <td data-label="شرح ردیف">{l.description || '—'}</td>
                {hasFx && (
                  <td data-label="ارز" className="num">
                    {l.currency_code ? `${fa(l.fx_amount ?? 0)} ${l.currency_code}` : '—'}
                  </td>
                )}
                {hasTracking && (
                  <td data-label="پیگیری">
                    {l.tracking_no ? (
                      <>
                        <span dir="ltr">{l.tracking_no}</span>
                        {l.tracking_date ? ` — ${formatJalali(l.tracking_date)}` : ''}
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                )}
                <td data-label="بدهکار" className="num">
                  {faAmount(l.debit)}
                </td>
                <td data-label="بستانکار" className="num">
                  {faAmount(l.credit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
