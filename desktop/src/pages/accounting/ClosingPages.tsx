import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  Archive,
  BookOpenCheck,
  CalendarCheck,
  Coins,
  DoorOpen,
  FileSpreadsheet,
  Lock,
  Printer,
  RefreshCw,
  Scale,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import {
  createPeriodClose,
  fetchAccountBalances,
  fetchChartAccounts,
  fetchClosingPreview,
  fetchFxPreview,
  fetchOpeningPreview,
  fetchPeriodCloses,
  fetchPnlClosePreview,
  issueClosingEntry,
  issueFxRevaluation,
  issueOpeningEntry,
  type ChartAccount,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { CurrenciesPanel } from '../../components/CurrenciesPanel'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  AsyncBlock,
  BalanceFooter,
  Metric,
  Note,
  OpsPage,
  RangeBar,
  fa,
  faAmount,
  faInt,
  jalaliYearStart,
  useAsync,
  useRange,
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

export function FxRevaluationPage({ token }: { token: string }) {
  const [asOf, setAsOf] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const preview = useAsync(() => fetchFxPreview(token, asOf), [token, asOf])

  async function issue() {
    if (!window.confirm(`سندِ تسعیر با تاریخ ${formatJalali(asOf)} صادر شود؟`)) return
    try {
      const out = await issueFxRevaluation(token, asOf, description)
      setMsg({
        text: `سندِ تسعیر با شماره ${fa(out.number ?? 0)} و خالصِ ${fa(out.net_difference)} صادر شد.`,
        kind: 'ok',
      })
      setDescription('')
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = preview.data
  const net = Number(data?.total_difference ?? 0)

  return (
    <OpsPage
      icon={Coins}
      title="صدور سند تسعیر ارز"
      description="مانده‌ی ارزیِ هر حساب با نرخِ روز سنجیده می‌شود و اختلافِ ریالی به سود/زیانِ تسعیر می‌رود. فقط ردیف‌هایی که هنگامِ ثبت مبلغِ ارزی داشته‌اند وارد محاسبه می‌شوند."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              تاریخِ تسعیر
              <JalaliDatePicker value={asOf} onChange={setAsOf} />
            </label>
            <button type="button" onClick={preview.reload}>
              <RefreshCw size={13} /> محاسبه‌ی دوباره
            </button>
          </div>
          <div className="cc-summary">
            <Metric
              icon={<Coins size={14} />}
              label="حساب‌های ارزی"
              value={data ? faInt(data.items.length) : '—'}
            />
            <Metric
              icon={net >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              label={net >= 0 ? 'سودِ تسعیر' : 'زیانِ تسعیر'}
              value={data ? fa(Math.abs(net)) : '—'}
              tone={net >= 0 ? 'in' : 'out'}
            />
            <Metric
              icon={<AlertTriangle size={14} />}
              label="ارزِ بدونِ نرخ"
              value={data ? faInt(data.missing_rates.length) : '—'}
              hint={data?.missing_rates.join('، ') || undefined}
              tone={data && data.missing_rates.length > 0 ? 'out' : 'plain'}
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={Scale}
        title="پیش‌نمایشِ تسعیر"
        description="ارزشِ دفتری در برابرِ ارزشِ امروز؛ اختلاف همان سندی است که زده می‌شود."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={!data || net === 0}
            onClick={() => void issue()}
          >
            <Coins size={14} /> صدورِ سند
          </button>
        }
      >
        {data && data.missing_rates.length > 0 && (
          <p className="hint acc-note acc-note--err">
            <AlertTriangle size={14} />
            برای {data.missing_rates.join('، ')} تا این تاریخ نرخی ثبت نشده؛ این ارزها در محاسبه نیامدند.
          </p>
        )}
        <label className="acc-inline-field acc-merge-desc">
          شرحِ سند (اختیاری)
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={`سند تسعیر ارز تا ${formatJalali(asOf)}`}
          />
        </label>

        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={(data?.items.length ?? 0) === 0}
          emptyText="هیچ حسابی مانده‌ی ارزی ندارد. برای ثبتِ ردیفِ ارزی، هنگامِ ثبتِ سند ارز و مبلغِ ارزی را وارد کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>حساب</th>
                  <th>ارز</th>
                  <th>مانده‌ی ارزی</th>
                  <th>نرخِ روز</th>
                  <th>ارزشِ دفتری</th>
                  <th>ارزشِ امروز</th>
                  <th>اختلاف</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((row) => {
                  const diff = Number(row.difference)
                  return (
                    <tr key={`${row.account_id}-${row.currency_code}`}>
                      <td className="card-title" data-label="حساب">
                        <span dir="ltr">{row.account_code}</span> — {row.account_name}
                      </td>
                      <td data-label="ارز" dir="ltr">
                        {row.currency_code}
                      </td>
                      <td data-label="مانده‌ی ارزی" className="num">
                        {fa(row.fx_balance)}
                      </td>
                      <td data-label="نرخِ روز" className="num">
                        {fa(row.rate)}
                      </td>
                      <td data-label="ارزشِ دفتری" className="num">
                        {fa(row.book_value)}
                      </td>
                      <td data-label="ارزشِ امروز" className="num">
                        {fa(row.market_value)}
                      </td>
                      <td
                        data-label="اختلاف"
                        className={`num ${diff >= 0 ? 'pos-in' : 'pos-out'}`}
                      >
                        {fa(diff)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      <CurrenciesPanel token={token} />
    </OpsPage>
  )
}

// ═════════════════ ۲) بستن حساب‌های سود و زیان ═════════════════

export function ClosePnlPage({ token }: { token: string }) {
  const [dateTo, setDateTo] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const preview = useAsync(() => fetchPnlClosePreview(token, dateTo), [token, dateTo, reloadKey])
  const closes = useAsync(() => fetchPeriodCloses(token), [token, reloadKey])

  async function run() {
    if (
      !window.confirm(
        `حساب‌های درآمد و هزینه تا ${formatJalali(dateTo)} صفر می‌شوند و سود/زیان به سود انباشته می‌رود.\n` +
          'پس از آن ثبتِ سند در این بازه قفل می‌شود و اسنادِ موقتِ داخلش دائم می‌شوند. ادامه؟',
      )
    )
      return
    try {
      const out = await createPeriodClose(token, { closing_date: dateTo, notes })
      setMsg({
        text: `دوره تا ${formatJalali(out.closing_date)} بسته شد؛ سود/زیانِ خالص ${fa(out.net_profit)} منتقل شد.`,
        kind: 'ok',
      })
      setNotes('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = preview.data
  const profit = Number(data?.net_profit ?? 0)
  const rows = data?.rows ?? []
  const debit = rows.filter((r) => r.side === 'debit').reduce((s, r) => s + Number(r.amount), 0)
  const credit = rows.filter((r) => r.side === 'credit').reduce((s, r) => s + Number(r.amount), 0)

  return (
    <OpsPage
      icon={CalendarCheck}
      title="بستن حساب‌های سود و زیان"
      description="حساب‌های موقت (درآمد و هزینه) صفر می‌شوند و سود/زیانِ خالص به سود انباشته می‌رود. پس از این، دوره رسماً قفل است."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              بستن تا تاریخ
              <JalaliDatePicker value={dateTo} onChange={setDateTo} />
            </label>
          </div>
          <div className="cc-summary">
            <Metric
              icon={<TrendingUp size={14} />}
              label="جمعِ درآمد"
              value={data ? fa(data.total_income) : '—'}
              tone="in"
            />
            <Metric
              icon={<TrendingDown size={14} />}
              label="جمعِ هزینه"
              value={data ? fa(data.total_expenses) : '—'}
              tone="out"
            />
            <Metric
              icon={<Scale size={14} />}
              label={profit >= 0 ? 'سودِ دوره' : 'زیانِ دوره'}
              value={data ? fa(Math.abs(profit)) : '—'}
              tone={profit >= 0 ? 'in' : 'out'}
            />
            <Metric
              icon={<AlertTriangle size={14} />}
              label="سندِ موقت در بازه"
              value={data ? faInt(data.temporary_in_range) : '—'}
              hint="با بستنِ دوره همه دائم می‌شوند"
              tone={data && data.temporary_in_range > 0 ? 'out' : 'plain'}
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={Lock}
        title="سندی که زده می‌شود"
        description={
          data?.date_from
            ? `بازه: ${formatJalali(data.date_from)} تا ${formatJalali(data.date_to)}`
            : `از ابتدا تا ${formatJalali(dateTo)}`
        }
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={rows.length === 0}
            onClick={() => void run()}
          >
            <Lock size={14} /> بستنِ دوره
          </button>
        }
      >
        <label className="acc-inline-field acc-merge-desc">
          یادداشت
          <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={rows.length === 0}
          emptyText="در این بازه هیچ فعالیتِ درآمد/هزینه‌ای برای بستن نیست."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>حساب</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.account_id}>
                    <td className="card-title" data-label="حساب">
                      <span dir="ltr">{r.account_code}</span> — {r.account_name}
                    </td>
                    <td data-label="بدهکار" className="num">
                      {r.side === 'debit' ? fa(r.amount) : '—'}
                    </td>
                    <td data-label="بستانکار" className="num">
                      {r.side === 'credit' ? fa(r.amount) : '—'}
                    </td>
                  </tr>
                ))}
                <tr className="acc-row--total">
                  <td className="card-title" data-label="حساب">انتقال به سود انباشته</td>
                  <td className="num" data-label="بدهکار">{profit < 0 ? fa(Math.abs(profit)) : '—'}</td>
                  <td className="num" data-label="بستانکار">{profit > 0 ? fa(profit) : '—'}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <BalanceFooter
            debit={debit + (profit < 0 ? Math.abs(profit) : 0)}
            credit={credit + (profit > 0 ? profit : 0)}
          />
        </AsyncBlock>
      </SectionCard>

      <SectionCard icon={Archive} title="دوره‌های بسته‌شده">
        <AsyncBlock
          loading={closes.loading}
          error={closes.error}
          empty={(closes.data?.length ?? 0) === 0}
          emptyText="هنوز هیچ دوره‌ای بسته نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخِ بستن</th>
                  <th>سود/زیانِ خالص</th>
                  <th>یادداشت</th>
                </tr>
              </thead>
              <tbody>
                {(closes.data ?? []).map((c) => (
                  <tr key={c.id}>
                    <td className="card-title" data-label="تاریخِ بستن">
                      {formatJalali(c.closing_date)}
                    </td>
                    <td data-label="سود/زیانِ خالص" className="num">
                      {fa(c.net_profit)}
                    </td>
                    <td data-label="یادداشت">{c.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════ ۳) صدور سند اختتامیه و افتتاحیه ═══════════

export function ClosingOpeningPage({ token }: { token: string }) {
  const [tab, setTab] = useState<'closing' | 'opening'>('closing')
  return (
    <OpsPage
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
      <Note msg={msg} />
      <SectionCard
        icon={Lock}
        title="سندِ اختتامیه"
        description="هر حسابِ دائمی برعکسِ مانده‌اش زده می‌شود تا صفر شود؛ طرفِ مقابل، حسابِ اختتامیه است."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={rows.length === 0 || pnlOpen}
            onClick={() => void issue()}
          >
            <Lock size={14} /> صدورِ اختتامیه
          </button>
        }
      >
        <div className="acc-filters">
          <label className="acc-inline-field">
            تاریخِ اختتامیه
            <JalaliDatePicker value={asOf} onChange={setAsOf} />
          </label>
          <label className="acc-inline-field acc-merge-desc">
            شرحِ سند
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={`سند اختتامیه ${formatJalali(asOf)}`}
            />
          </label>
        </div>

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
      <Note msg={msg} />
      <SectionCard
        icon={DoorOpen}
        title="سندِ افتتاحیه"
        description="دقیقاً معکوسِ سندِ اختتامیه‌ی سالِ قبل — پس سالِ جدید با همان مانده‌ای باز می‌شود که سالِ قبل بسته شد."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={rows.length === 0}
            onClick={() => void issue()}
          >
            <DoorOpen size={14} /> صدورِ افتتاحیه
          </button>
        }
      >
        <div className="acc-filters">
          <label className="acc-inline-field">
            تاریخِ اختتامیه‌ی سالِ قبل
            <JalaliDatePicker value={sourceDate} onChange={setSourceDate} />
          </label>
          <label className="acc-inline-field">
            تاریخِ افتتاحیه
            <JalaliDatePicker value={asOf} onChange={setAsOf} />
          </label>
          <label className="acc-inline-field acc-merge-desc">
            شرحِ سند
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={`سند افتتاحیه ${formatJalali(asOf)}`}
            />
          </label>
        </div>

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

function ClosingTable({ rows }: { rows: { account_id: string; account_code: string; account_name: string; account_type: string; debit: string; credit: string }[] }) {
  const pg = usePagination(rows, 20)
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile acc-table">
        <thead>
          <tr>
            <th>حساب</th>
            <th>نوع</th>
            <th>بدهکار</th>
            <th>بستانکار</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((r) => (
            <tr key={r.account_id}>
              <td className="card-title" data-label="حساب">
                <span dir="ltr">{r.account_code}</span> — {r.account_name}
              </td>
              <td data-label="نوع">{TYPE_LABELS[r.account_type] ?? r.account_type}</td>
              <td data-label="بدهکار" className="num">
                {faAmount(r.debit)}
              </td>
              <td data-label="بستانکار" className="num">
                {faAmount(r.credit)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

// ═════════════════════ ۴) صدور سند کل ═════════════════════

/** سطحِ «کل» یعنی نزدیک‌ترین جدِ گروهیِ حساب. بدونِ این، تجمیع روی حسابِ سطحِ آخر
 *  انجام می‌شد و «سند کل» با تراز آزمایشی فرقی نداشت. */
function generalAncestor(account: ChartAccount, byId: Map<string, ChartAccount>): ChartAccount {
  let node = account
  const seen = new Set<string>()
  while (node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    // یک سطح زیرِ ریشه = حسابِ کل. ریشه‌ها گروهِ اصلی‌اند (دارایی، بدهی، …).
    if (!parent.parent_id) return node
    node = parent
  }
  return node
}

export function GeneralDocumentPage({ token }: { token: string }) {
  const range = useRange('month')
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const balances = useAsync(
    () => fetchAccountBalances(token, range.from, range.to),
    [token, range.from, range.to],
  )

  const rows = useMemo(() => {
    const list = accounts.data ?? []
    const byId = new Map(list.map((a) => [a.id, a]))
    const totals = new Map<string, { account: ChartAccount; debit: number; credit: number }>()
    for (const row of balances.data ?? []) {
      const leaf = byId.get(row.account_id)
      if (!leaf) continue
      const parent = generalAncestor(leaf, byId)
      const bucket = totals.get(parent.id) ?? { account: parent, debit: 0, credit: 0 }
      bucket.debit += Number(row.period_debit)
      bucket.credit += Number(row.period_credit)
      totals.set(parent.id, bucket)
    }
    return [...totals.values()]
      .filter((r) => r.debit !== 0 || r.credit !== 0)
      .sort((a, b) => a.account.code.localeCompare(b.account.code))
  }, [accounts.data, balances.data])

  const debit = rows.reduce((s, r) => s + r.debit, 0)
  const credit = rows.reduce((s, r) => s + r.credit, 0)

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="صدور سند کل"
      description="خلاصه‌ی گردشِ یک بازه در سطحِ حسابِ کل — همان برگه‌ای که در پایانِ ماه چاپ و بایگانی می‌شود. سندِ تازه‌ای ثبت نمی‌کند؛ فقط اسنادِ موجود را تجمیع می‌کند."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<BookOpenCheck size={14} />} label="حسابِ کل" value={faInt(rows.length)} />
            <Metric icon={<Wallet size={14} />} label="جمعِ بدهکار" value={fa(debit)} tone="in" />
            <Metric icon={<Wallet size={14} />} label="جمعِ بستانکار" value={fa(credit)} tone="out" />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={FileSpreadsheet}
        title="سند کل"
        description={
          range.from
            ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())}`
            : 'از ابتدای دفتر'
        }
        actions={
          <button type="button" onClick={() => window.print()}>
            <Printer size={13} /> چاپ
          </button>
        }
      >
        <AsyncBlock
          loading={accounts.loading || balances.loading}
          error={accounts.error ?? balances.error}
          empty={rows.length === 0}
          emptyText="در این بازه گردشی ثبت نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کدِ کل</th>
                  <th>نامِ حسابِ کل</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.account.id}>
                    <td className="card-title" data-label="کدِ کل" dir="ltr">
                      {r.account.code}
                    </td>
                    <td data-label="نامِ حسابِ کل">{r.account.name}</td>
                    <td data-label="بدهکار" className="num">
                      {faAmount(r.debit)}
                    </td>
                    <td data-label="بستانکار" className="num">
                      {faAmount(r.credit)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <BalanceFooter debit={debit} credit={credit} />
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
