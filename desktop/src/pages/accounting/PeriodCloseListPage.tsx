import { useState } from 'react'
import { Archive, CalendarCheck, Lock } from 'lucide-react'

import { fetchPeriodCloses } from '../../api'
import { CountBadge } from '../../components/form/FormKit'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { Amount } from '../../components/ReportViews'
import { SectionCard } from '../../components/SectionCard'
import { formatJalali } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { closeRows, profitTotal } from '../../lib/periodCloses'
import { AsyncBlock, OpsPage, faInt, useAsync } from './kit'

/**
 * «دوره‌های بسته‌شده» با تمِ اکسلی — دفترِ قفل‌های دوره، تازه‌ترین اول (الگوی «د»).
 *
 * هر ردیف یک قفل است با **بازه‌ای که بست** (از روزِ بعد از قفلِ قبلی، یا ابتدای دفتر)، سود/زیانِ خالصِ همان بازه، یادداشت،
 * و سندِ بستنش — کلیک روی ردیف همان سند را باز می‌کند. آخرین قفل نشانِ «مرزِ ثبتِ سند» دارد، و «جمعِ دوره‌ها» ته گرید است.
 * خودِ بستن و قفل در «بستن حساب‌های سود و زیان» است؛ این صفحه فقط دفترِ آن است.
 */
export function PeriodCloseListPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const closes = useAsync(() => fetchPeriodCloses(token), [token])
  const rows = closeRows(closes.data ?? [])
  const [entryId, setEntryId] = useState<string | null>(null)
  const total = profitTotal(rows)

  return (
    <OpsPage
      canvas
      icon={Archive}
      title="دوره‌های بسته‌شده"
      description="هر بار که دوره قفل شده، یک ردیف اینجاست. تاریخِ آخرین قفل مرزِ ثبتِ سند است: هیچ سندی تا آن تاریخ ثبت یا اصلاح نمی‌شود."
      head={
        onNavigate && (
          <div className="jh-bar jh-bar--report" role="group" aria-label="میان‌برهای دوره‌های بسته‌شده">
            <div className="jh-row rh-row--tools">
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('closepnl')}>
                    <CalendarCheck size={14} aria-hidden="true" /> بستن حساب‌های سود و زیان
                  </button>
                  <button type="button" onClick={() => onNavigate('closingopening')}>
                    <Lock size={14} aria-hidden="true" /> صدور سند اختتامیه و افتتاحیه
                  </button>
                </div>
              </div>
            </div>
          </div>
        )
      }
    >
      <SectionCard
        icon={Archive}
        title="تاریخچه‌ی قفلِ دوره"
        description={rows.length ? `آخرین قفل: ${formatJalali(rows[0].closing_date)}` : undefined}
        tip="هر ردیف یک قفلِ دوره است: بازه‌ای که بسته شد، سود یا زیانِ خالصِ آن، و سندِ بستنش — روی ردیف کلیک کنید تا همان سند باز شود. آخرین قفل مرزِ ثبتِ سند است."
        badge={closes.data ? <CountBadge accent>{faInt(rows.length)} دوره</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={closes.loading && !closes.data}
          error={closes.data ? null : closes.error}
          empty={rows.length === 0}
          emptyText="هنوز هیچ دوره‌ای قفل نشده. قفلِ دوره گامِ دومِ «بستن حساب‌های سود و زیان» است."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table xl-grid rp-table pcl-sheet">
              <colgroup>
                <col className="pcl-c-rowhead" />
                <col className="pcl-c-date" />
                <col className="pcl-c-range" />
                <col className="pcl-c-amt" />
                <col />
              </colgroup>
              <thead>
                <tr>
                  <th className="xl-rowhead" aria-label="ردیف" />
                  <th>تاریخِ قفل</th>
                  <th>بازه</th>
                  <th className="num">سود / زیانِ خالص</th>
                  <th>یادداشت</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c, i) => (
                  <tr
                    key={c.id}
                    className={`acc-row--clickable${c.latest ? ' pcl-latest' : ''}`}
                    tabIndex={0}
                    title="بازکردنِ سندِ بستن"
                    onClick={() => setEntryId(c.journal_entry_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        setEntryId(c.journal_entry_id)
                      }
                    }}
                  >
                    <td className="xl-rowhead card-hide">{faInt(rows.length - i)}</td>
                    <td className="card-title">
                      {formatJalali(c.closing_date)}
                      {c.latest && <span className="xl-check xl-check--due pcl-edge">مرزِ ثبتِ سند</span>}
                    </td>
                    <td data-label="بازه">
                      {c.from ? `${formatJalali(c.from)} تا ${formatJalali(c.closing_date)}` : `ابتدای دفتر تا ${formatJalali(c.closing_date)}`}
                    </td>
                    <td className={`num ${Number(c.net_profit) < 0 ? 'pos-out' : 'pos-in'}`} data-label="سود / زیانِ خالص">
                      <Amount value={c.net_profit} />
                    </td>
                    <td className="card-wide" data-label="یادداشت">
                      {c.notes || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="rp-total">
                  <td className="xl-rowhead card-hide" />
                  <td className="card-title" colSpan={2}>
                    جمعِ دوره‌ها <small className="lr-foot-note">{faInt(rows.length)} دوره</small>
                  </td>
                  <td className="num" data-label="سود / زیانِ خالص">
                    <Amount value={total} />
                  </td>
                  <td className="card-hide" />
                </tr>
              </tfoot>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      {entryId && <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />}
    </OpsPage>
  )
}
