import { useState } from 'react'
import {
  AlertTriangle,
  Archive,
  DoorOpen,
  Lock,
} from 'lucide-react'
import {
  fetchClosingPreview,
  fetchOpeningPreview,
  issueClosingEntry,
  issueOpeningEntry,
  type ClosingRow,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import {
  ActionBar,
  FormField,
  FormGrid,
  FormStatus,
} from '../../components/form/FormKit'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  AsyncBlock,
  BalanceFooter,
  OpsPage,
  fa,
  faAmount,
  faInt,
  jalaliYearStart,
  useAsync,
  type Msg,
} from './kit'

/**
 * چهار عملیاتِ *سندسازِ* پایانِ دوره.
 *
 * ترتیبشان در کارِ واقعی مهم است و صفحه‌ها همین ترتیب را به کاربر یادآوری می‌کنند:
 * اول **تسعیر** (تا مانده‌ی ارزی به نرخِ روز درآید)، بعد **بستنِ سود و زیان** (تا
 * حساب‌های موقت صفر شوند)، بعد **اختتامیه** (تا حساب‌های دائمی بسته شوند)، و در
 * سالِ بعد **افتتاحیه**. هر کدام پیش از صدور، دقیقاً همان سندی را که خواهد زد
 * نشان می‌دهد — هیچ سندی نادیده صادر نمی‌شود.
 */

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

// ═════════════════════ ۱) صدور سند تسعیر ارز ═════════════════════
//: هم‌سبکِ سند حسابداری، در فایلِ خودش؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { FxRevaluationPage } from './FxRevaluationPage'

// ═════════════════ ۲) بستن حساب‌های سود و زیان ═════════════════
//: هم‌سبکِ سند حسابداری، در فایلِ خودش؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { ClosePnlPage } from './ClosePnlPage'

// ═══════════ ۳) صدور سند اختتامیه و افتتاحیه ═══════════

export function ClosingOpeningPage({ token }: { token: string }) {
  const [tab, setTab] = useState<'closing' | 'opening'>('closing')
  return (
    <OpsPage
      canvas
      icon={Archive}
      title="صدور سند اختتامیه و افتتاحیه"
      description="پایانِ سال: اختتامیه همه‌ی حساب‌های دائمی را می‌بندد و افتتاحیه در سالِ بعد دقیقاً همان‌ها را باز می‌کند. اول باید سود و زیان بسته شده باشد."
      head={
        <div className="cc-head">
          <div className="cc-tabs">
            <button
              type="button"
              className={tab === 'closing' ? 'is-active' : ''}
              onClick={() => setTab('closing')}
            >
              <Lock size={14} /> سند اختتامیه
            </button>
            <button
              type="button"
              className={tab === 'opening' ? 'is-active' : ''}
              onClick={() => setTab('opening')}
            >
              <DoorOpen size={14} /> سند افتتاحیه
            </button>
          </div>
        </div>
      }
    >
      {tab === 'closing' ? <ClosingTab token={token} /> : <OpeningTab token={token} />}
    </OpsPage>
  )
}

function ClosingTab({ token }: { token: string }) {
  const [asOf, setAsOf] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const preview = useAsync(() => fetchClosingPreview(token, asOf), [token, asOf])

  async function issue() {
    if (!window.confirm(`سندِ اختتامیه با تاریخ ${formatJalali(asOf)} صادر شود؟`)) return
    try {
      const out = await issueClosingEntry(token, asOf, description)
      setMsg({ text: `سندِ اختتامیه با شماره ${fa(out.number ?? 0)} صادر شد.`, kind: 'ok' })
      setDescription('')
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = preview.data
  const rows = data?.rows ?? []
  const debit = rows.reduce((s, r) => s + Number(r.debit), 0)
  const credit = rows.reduce((s, r) => s + Number(r.credit), 0)
  const pnlOpen = Number(data?.open_pnl_total ?? 0) !== 0

  return (
    <>
      <SectionCard
        icon={Lock}
        title="سندِ اختتامیه"
        tip="هر حسابِ دائمی برعکسِ مانده‌اش زده می‌شود تا صفر شود؛ طرفِ مقابل، حسابِ اختتامیه است."
      >
        <FormGrid cols={2}>
          <FormField label="تاریخِ اختتامیه" required>
            {(id) => <JalaliDatePicker id={id} value={asOf} onChange={setAsOf} />}
          </FormField>
          <FormField label="شرحِ سند" optional>
            {(id) => (
              <input
                id={id}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={`سند اختتامیه ${formatJalali(asOf)}`}
              />
            )}
          </FormField>
        </FormGrid>

        {pnlOpen && (
          <p className="hint acc-note acc-note--err">
            <AlertTriangle size={14} />
            حساب‌های سود و زیان هنوز باز‌اند (گردشِ {fa(data?.open_pnl_total ?? 0)}). اول «بستن حساب‌های
            سود و زیان» را انجام دهید.
          </p>
        )}
        {data && data.temporary_count > 0 && (
          <p className="hint">
            {faInt(data.temporary_count)} سندِ موقت تا این تاریخ هست؛ بهتر است اول دائمشان کنید.
          </p>
        )}

        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={rows.length === 0}
          emptyText="هیچ حسابِ دائمیِ دارای مانده‌ای برای بستن نیست."
        >
          <ClosingTable rows={rows} />
          <EntryTotals rowDebit={debit} rowCredit={credit} label="حساب اختتامیه" />
        </AsyncBlock>
      </SectionCard>
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={pnlOpen ? 'اول «بستن حساب‌های سود و زیان» را انجام دهید.' : `${faInt(rows.length)} حساب بسته می‌شود.`}
          />
        }
      >
        <button
          type="button"
          className="btn-primary"
          disabled={rows.length === 0 || pnlOpen}
          onClick={() => void issue()}
        >
          <Lock size={15} /> صدورِ اختتامیه
        </button>
      </ActionBar>
    </>
  )
}

function OpeningTab({ token }: { token: string }) {
  const [sourceDate, setSourceDate] = useState(todayIso())
  const [asOf, setAsOf] = useState(jalaliYearStart())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const preview = useAsync(
    () => fetchOpeningPreview(token, asOf, sourceDate),
    [token, asOf, sourceDate],
  )

  async function issue() {
    if (!window.confirm(`سندِ افتتاحیه با تاریخ ${formatJalali(asOf)} صادر شود؟`)) return
    try {
      const out = await issueOpeningEntry(token, asOf, sourceDate, description)
      setMsg({ text: `سندِ افتتاحیه با شماره ${fa(out.number ?? 0)} صادر شد.`, kind: 'ok' })
      setDescription('')
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = preview.data
  const rows = data?.rows ?? []
  const debit = rows.reduce((s, r) => s + Number(r.debit), 0)
  const credit = rows.reduce((s, r) => s + Number(r.credit), 0)

  return (
    <>
      <SectionCard
        icon={DoorOpen}
        title="سندِ افتتاحیه"
        tip="دقیقاً معکوسِ سندِ اختتامیه‌ی سالِ قبل — پس سالِ جدید با همان مانده‌ای باز می‌شود که سالِ قبل بسته شد."
      >
        <FormGrid>
          <FormField label="تاریخِ اختتامیه‌ی سالِ قبل" required>
            {(id) => <JalaliDatePicker id={id} value={sourceDate} onChange={setSourceDate} />}
          </FormField>
          <FormField label="تاریخِ افتتاحیه" required>
            {(id) => <JalaliDatePicker id={id} value={asOf} onChange={setAsOf} />}
          </FormField>
          <FormField label="شرحِ سند" optional>
            {(id) => (
              <input
                id={id}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={`سند افتتاحیه ${formatJalali(asOf)}`}
              />
            )}
          </FormField>
        </FormGrid>

        {data?.closing_entry_number != null && (
          <p className="hint">
            مبنا: سندِ اختتامیه‌ی شماره {fa(data.closing_entry_number)} در تاریخ{' '}
            {formatJalali(sourceDate)}.
          </p>
        )}

        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={rows.length === 0}
          emptyText="در این تاریخ سندِ اختتامیه‌ای پیدا نشد؛ اول اختتامیه را صادر کنید."
        >
          <ClosingTable rows={rows} />
          <EntryTotals rowDebit={debit} rowCredit={credit} label="حساب افتتاحیه" />
        </AsyncBlock>
      </SectionCard>
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              rows.length === 0
                ? 'در این تاریخ سندِ اختتامیه‌ای پیدا نشد.'
                : `${faInt(rows.length)} حساب در سالِ تازه باز می‌شود.`
            }
          />
        }
      >
        <button type="button" className="btn-primary" disabled={rows.length === 0} onClick={() => void issue()}>
          <DoorOpen size={15} /> صدورِ افتتاحیه
        </button>
      </ActionBar>
    </>
  )
}

/** جمعِ سند = جمعِ ردیف‌ها **به‌اضافه‌ی خطِ توازن**. نشان‌دادنِ فقط جمعِ ردیف‌ها
 *  همیشه «نامتوازن» می‌گفت — و همان چیزی است که کاربر را از صدورِ سندِ درست می‌ترساند. */
function EntryTotals({ rowDebit, rowCredit, label }: { rowDebit: number; rowCredit: number; label: string }) {
  const net = rowDebit - rowCredit
  const balDebit = net < 0 ? -net : 0
  const balCredit = net > 0 ? net : 0
  return (
    <>
      <p className="hint">
        خطِ توازن — {label}: بدهکار {fa(balDebit)} / بستانکار {fa(balCredit)}
      </p>
      <BalanceFooter debit={rowDebit + balDebit} credit={rowCredit + balCredit} />
    </>
  )
}

function ClosingTable({ rows }: { rows: ClosingRow[] }) {
  const pg = usePagination(rows, 20)
  return (
    <div className="table-scroll ef-table-wrap">
      <table className="cards-on-mobile acc-table ef-table">
        <thead>
          <tr>
            <th>حساب</th>
            <th>نوع</th>
            <th>بدهکار</th>
            <th>بستانکار</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((r) => {
            // بُعدها ستونِ تازه نمی‌گیرند — هویتِ ردیف‌اند، پس زیرِ خودِ حساب
            // می‌نشینند. همان الگویِ جدولِ تسعیر، تا دو جدولِ هم‌خانواده دو جور دیده نشوند.
            const dims = [
              r.analytic_name
                ? `تفصیلی: ${r.analytic_code ? `${r.analytic_code} ` : ''}${r.analytic_name}`
                : null,
              r.cost_center_name ? `مرکز: ${r.cost_center_name}` : null,
            ].filter(Boolean)
            return (
            <tr key={`${r.account_id}-${r.analytic_id ?? '—'}-${r.cost_center_id ?? '—'}`}>
              <td className="card-title" data-label="حساب">
                <span dir="ltr">{r.account_code}</span> — {r.account_name}
                {dims.length > 0 && <span className="field-hint">{dims.join(' · ')}</span>}
              </td>
              <td data-label="نوع">{TYPE_LABELS[r.account_type] ?? r.account_type}</td>
              <td data-label="بدهکار" className="num">
                {faAmount(r.debit)}
              </td>
              <td data-label="بستانکار" className="num">
                {faAmount(r.credit)}
              </td>
            </tr>
            )
          })}
        </tbody>
      </table>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

// ═════════════════════ ۴) انتقال مانده به حساب دیگر ═════════════════════
//: هم‌سبکِ سند حسابداری، در فایلِ خودش؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { BalanceReclassPage } from './BalanceReclassPage'
