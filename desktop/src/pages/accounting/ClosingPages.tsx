import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  Check,
  Archive,
  ArrowLeftRight,
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
  issuePnlClose,
  fetchReclassSources,
  issueClosingEntry,
  issueFxRevaluation,
  issueOpeningEntry,
  issueReclass,
  previewReclass,
  type ChartAccount,
  type ReclassBody,
  type ReclassPreview,
  type ClosingRow,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import {
  ActionBar,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
} from '../../components/form/FormKit'
import { CurrenciesPanel } from '../../components/CurrenciesPanel'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  AsyncBlock,
  BalanceFooter,
  Metric,
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
      canvas
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
      <SectionCard
        icon={Scale}
        title="پیش‌نمایشِ تسعیر"
        tip="ارزشِ دفتری در برابرِ ارزشِ امروز؛ اختلاف همان سندی است که زده می‌شود."
        badge={data ? <CountBadge>{faInt(data.items.length)} حساب</CountBadge> : undefined}
      >
        {data && data.missing_rates.length > 0 && (
          <p className="hint acc-note acc-note--err">
            <AlertTriangle size={14} />
            برای {data.missing_rates.join('، ')} تا این تاریخ نرخی ثبت نشده؛ این ارزها در محاسبه نیامدند.
          </p>
        )}
        <div className="ef-block-top">
          <FormField label="شرحِ سند" optional>
            {(id) => (
              <input
                id={id}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={`سند تسعیر ارز تا ${formatJalali(asOf)}`}
              />
            )}
          </FormField>
        </div>

        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={(data?.items.length ?? 0) === 0}
          emptyText="هیچ حسابی مانده‌ی ارزی ندارد. برای ثبتِ ردیفِ ارزی، هنگامِ ثبتِ سند ارز و مبلغِ ارزی را وارد کنید."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
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
                  // بُعدها ستونِ تازه نمی‌گیرند: هویتِ ردیف‌اند، پس زیرِ خودِ حساب
                  // می‌نشینند تا جدول هفت‌ستونه بماند و در موبایل هم کارتِ خوانا بماند.
                  const dims = [
                    row.analytic_name
                      ? `تفصیلی: ${row.analytic_code ? `${row.analytic_code} ` : ''}${row.analytic_name}`
                      : null,
                    row.cost_center_name ? `مرکز: ${row.cost_center_name}` : null,
                  ].filter(Boolean)
                  // نرخِ کهنه حدس نیست ولی نرخِ روز هم نیست — باید دیده شود.
                  const stale = row.rate_date !== asOf
                  return (
                    <tr
                      key={`${row.account_id}-${row.analytic_id ?? '—'}-${row.cost_center_id ?? '—'}-${row.currency_code}`}
                    >
                      <td className="card-title" data-label="حساب">
                        <span dir="ltr">{row.account_code}</span> — {row.account_name}
                        {dims.length > 0 && <span className="field-hint">{dims.join(' · ')}</span>}
                      </td>
                      <td data-label="ارز" dir="ltr">
                        {row.currency_code}
                      </td>
                      <td data-label="مانده‌ی ارزی" className="num">
                        {fa(row.fx_balance)}
                      </td>
                      <td data-label="نرخِ روز" className="num">
                        {fa(row.rate)}
                        {stale && (
                          <span className="field-hint field-hint--warn">
                            نرخِ {formatJalali(row.rate_date)}
                          </span>
                        )}
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
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              net === 0
                ? 'اختلافِ تسعیری وجود ندارد؛ سندی لازم نیست.'
                : `${net >= 0 ? 'سودِ' : 'زیانِ'} تسعیر: ${fa(Math.abs(net))} ریال`
            }
          />
        }
      >
        <button type="button" className="btn-primary" disabled={!data || net === 0} onClick={() => void issue()}>
          <Coins size={15} /> صدورِ سند تسعیر
        </button>
      </ActionBar>
    </OpsPage>
  )
}

// ═════════════════ ۲) بستن حساب‌های سود و زیان ═════════════════

export function ClosePnlPage({ token }: { token: string }) {
  const [dateTo, setDateTo] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [notes, setNotes] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const preview = useAsync(() => fetchPnlClosePreview(token, dateTo), [token, dateTo, reloadKey])
  const closes = useAsync(() => fetchPeriodCloses(token), [token, reloadKey])

  /** گامِ اول — فقط سند. دوره باز می‌ماند و سند موقت است. */
  async function issue() {
    try {
      const out = await issuePnlClose(token, dateTo, description)
      setMsg({
        text: `سندِ بستن با ${faInt(out.line_count)} ردیف ثبت شد؛ سود/زیانِ خالص ${fa(out.net_profit)}. سند موقت است و دوره هنوز باز.`,
        kind: 'ok',
      })
      setDescription('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  /** گامِ دوم — قفل. برگشت ندارد. */
  async function lock() {
    if (
      !window.confirm(
        `دوره تا ${formatJalali(dateTo)} قفل می‌شود: دیگر هیچ سندی در این بازه ثبت یا اصلاح نمی‌شود ` +
          'و اسنادِ موقتِ داخلش دائم می‌شوند.\n\nاین کار برگشت ندارد. ادامه؟',
      )
    )
      return
    try {
      const out = await createPeriodClose(token, { closing_date: dateTo, notes })
      setMsg({
        text: `دوره تا ${formatJalali(out.closing_date)} قفل شد؛ سود/زیانِ خالص ${fa(out.net_profit)}.`,
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
  const difference = Number(data?.difference ?? 0)
  const alreadyClosed = data?.already_closed ?? false
  const hasDimensions = rows.some((r) => r.analytic_name || r.cost_center_name)

  return (
    <OpsPage
      canvas
      icon={CalendarCheck}
      title="بستن حساب‌های سود و زیان"
      description="حساب‌های موقت (درآمد و هزینه) صفر می‌شوند و سود/زیانِ خالص به سود انباشته می‌رود. سند موقت است؛ قفلِ دوره گامِ دومِ جداست."
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
              hint="با قفلِ دوره همه دائم می‌شوند"
              tone={data && data.temporary_in_range > 0 ? 'out' : 'plain'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Scale}
        title="گامِ ۱ — صدور سند بستن"
        description={
          data
            ? `${data.date_from ? `بازه: ${formatJalali(data.date_from)} تا ${formatJalali(data.date_to)}` : `از ابتدا تا ${formatJalali(dateTo)}`} · مقصد: ${data.destination_account_name}`
            : `از ابتدا تا ${formatJalali(dateTo)}`
        }
      >
        <div className="ef-block-top">
          <FormField label="شرحِ سند" optional tip="خالی بگذارید تا خودکار نوشته شود.">
            {(id) => (
              <input id={id} value={description} onChange={(e) => setDescription(e.target.value)} />
            )}
          </FormField>
        </div>

        {alreadyClosed && (
          <section className="fy-status">
            <p className="fy-note fy-note--ok">
              سندِ بستن برای این بازه از قبل زده شده. اگر بعد از آن سندی اضافه شده باشد، صدورِ
              دوباره فقط همان تفاوت را می‌بندد.
            </p>
          </section>
        )}

        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={rows.length === 0}
          emptyText="در این بازه هیچ فعالیتِ درآمد/هزینه‌ای برای بستن نیست."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th>حساب</th>
                  {hasDimensions && <th>تفصیلی / مرکز هزینه</th>}
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.account_id}-${r.analytic_id ?? ''}-${r.cost_center_id ?? ''}`}>
                    <td className="card-title" data-label="حساب">
                      <span dir="ltr">{r.account_code}</span> — {r.account_name}
                    </td>
                    {hasDimensions && (
                      <td data-label="تفصیلی / مرکز هزینه">
                        {[r.analytic_name, r.cost_center_name].filter(Boolean).join(' · ') || '—'}
                      </td>
                    )}
                    <td data-label="بدهکار" className="num">
                      {faAmount(r.debit)}
                    </td>
                    <td data-label="بستانکار" className="num">
                      {faAmount(r.credit)}
                    </td>
                  </tr>
                ))}
                <tr className="acc-row--total">
                  <td className="card-title" data-label="حساب">
                    انتقال به {data?.destination_account_name ?? 'سود انباشته'}
                  </td>
                  {hasDimensions && <td data-label="تفصیلی / مرکز هزینه">—</td>}
                  <td className="num" data-label="بدهکار">
                    {profit < 0 ? fa(Math.abs(profit)) : '—'}
                  </td>
                  <td className="num" data-label="بستانکار">
                    {profit > 0 ? fa(profit) : '—'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <BalanceFooter
            debit={Number(data?.total_debit ?? 0)}
            credit={Number(data?.total_credit ?? 0)}
          />
        </AsyncBlock>
      </SectionCard>

      <SectionCard
        icon={Lock}
        title="گامِ ۲ — قفل کردن دوره"
        tip="پس از قفل، هیچ سندی در این بازه ثبت یا اصلاح نمی‌شود و اسنادِ موقتِ داخلش دائم می‌شوند. این کار برگشت ندارد."
      >
        <FormGrid cols={2}>
          <FormField label="یادداشت" optional>
            {(id) => <input id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}
          </FormField>
        </FormGrid>
        {!alreadyClosed && rows.length > 0 && (
          <p className="ef-message ef-message--warn ef-block-note">
            هنوز سندِ بستن زده نشده. اگر مستقیم قفل کنید، سند همین‌جا خودکار زده می‌شود.
          </p>
        )}
        <div className="ef-card-foot">
          <button type="button" className="ef-btn-secondary" onClick={() => void lock()}>
            <Lock size={15} /> قفل کردن دوره
          </button>
        </div>
      </SectionCard>

      <SectionCard
        icon={Archive}
        title="دوره‌های بسته‌شده"
        badge={closes.data ? <CountBadge>{faInt(closes.data.length)} دوره</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={closes.loading}
          error={closes.error}
          empty={(closes.data?.length ?? 0) === 0}
          emptyText="هنوز هیچ دوره‌ای بسته نشده."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
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
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              rows.length === 0
                ? 'در این بازه فعالیتِ درآمد/هزینه‌ای برای بستن نیست.'
                : `${profit >= 0 ? 'سودِ' : 'زیانِ'} دوره: ${fa(Math.abs(profit))} ریال`
            }
          />
        }
      >
        <button
          type="button"
          className="btn-primary"
          disabled={rows.length === 0 || difference !== 0}
          onClick={() => void issue()}
        >
          <Scale size={15} /> صدور سند بستن
        </button>
      </ActionBar>
    </OpsPage>
  )
}

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
    () => fetchAccountBalances(token, { dateFrom: range.from, dateTo: range.to }),
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
      canvas
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
          <button type="button" className="ef-btn-secondary" onClick={() => window.print()}>
            <Printer size={14} /> چاپ
          </button>
        }
      >
        <AsyncBlock
          loading={accounts.loading || balances.loading}
          error={accounts.error ?? balances.error}
          empty={rows.length === 0}
          emptyText="در این بازه گردشی ثبت نشده."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
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


// ═════════════════════ ۵) اصلاح طبقه‌بندی مانده ═════════════════════

/**
 * مانده‌ی یک ترکیبِ (حساب، تفصیلی) را با یک سندِ متوازن به حسابِ درست می‌برد.
 *
 * **با «جابه‌جایی حساب در درختواره» یکی نیست.** آن یکی `parent_id`ِ خودِ حساب را
 * عوض می‌کند و گزارشِ گذشته را هم تغییر می‌دهد؛ این یکی اسنادِ گذشته را دست
 * نمی‌زند و اصلاح را به‌عنوان یک رویدادِ مالیِ تاریخ‌دار ثبت می‌کند.
 */
export function BalanceReclassPage({ token }: { token: string }) {
  const [asOf, setAsOf] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [destAccount, setDestAccount] = useState('')
  const [destAnalytic, setDestAnalytic] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [preview, setPreview] = useState<ReclassPreview | null>(null)

  const sources = useAsync(() => fetchReclassSources(token, asOf), [token, asOf])
  const accounts = useAsync(() => fetchChartAccounts(token), [token])

  //: کلیدِ ترکیبی، چون یک حساب می‌تواند چند تفصیلی داشته باشد.
  const keyOf = (r: { account_id: string; analytic_id: string | null }) =>
    `${r.account_id}|${r.analytic_id ?? ''}`

  const chosen = (sources.data ?? []).filter((r) => picked[keyOf(r)])

  const body = (): ReclassBody => ({
    as_of: asOf,
    sources: chosen.map((r) => ({ account_id: r.account_id, analytic_id: r.analytic_id })),
    dest_account_id: destAccount,
    dest_analytic_id: destAnalytic || null,
    description,
  })

  async function runPreview() {
    setMsg(null)
    setPreview(null)
    try {
      setPreview(await previewReclass(token, body()))
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function issue() {
    if (!window.confirm('سندِ اصلاح طبقه‌بندی صادر شود؟')) return
    try {
      const out = await issueReclass(token, body())
      setMsg({ text: `سند با شماره ${fa(out.number ?? 0)} صادر شد.`, kind: 'ok' })
      setPicked({})
      setPreview(null)
      sources.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const postable = (accounts.data ?? []).filter((a) => !a.is_group)
  const ready = preview !== null && Number(preview.difference) === 0

  return (
    <OpsPage
      canvas
      icon={ArrowLeftRight}
      title="اصلاح طبقه‌بندی مانده"
      description="مانده‌ی یک حساب/تفصیلی را با یک سندِ متوازن به جای درست می‌برد. اسنادِ گذشته دست‌نخورده می‌مانند و اصلاح به‌عنوان رویدادی تاریخ‌دار ثبت می‌شود."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              تاریخِ اصلاح
              <JalaliDatePicker value={asOf} onChange={setAsOf} />
            </label>
            <label className="acc-inline-field acc-merge-desc">
              شرحِ سند
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="اصلاح طبقه‌بندی مانده"
              />
            </label>
          </div>
          <div className="cc-summary">
            <Metric icon={<ArrowLeftRight size={14} />} label="انتخاب‌شده" value={faInt(chosen.length)} />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={ArrowLeftRight}
        title="گامِ ۱ — مبدأ"
        tip="مانده تا تاریخِ اصلاح. فقط همان ترکیبی که انتخاب می‌کنید منتقل می‌شود، نه کلِ حساب."
        badge={<CountBadge accent>{faInt(chosen.length)} انتخاب‌شده</CountBadge>}
      >
        <AsyncBlock
          loading={sources.loading}
          error={sources.error}
          empty={(sources.data?.length ?? 0) === 0}
          emptyText="در این تاریخ هیچ حسابی مانده ندارد."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th />
                  <th>حساب</th>
                  <th>مانده</th>
                </tr>
              </thead>
              <tbody>
                {(sources.data ?? []).map((r) => {
                  const k = keyOf(r)
                  return (
                    <tr key={k}>
                      <td data-label="انتخاب">
                        <input
                          type="checkbox"
                          checked={!!picked[k]}
                          onChange={(e) => setPicked({ ...picked, [k]: e.target.checked })}
                        />
                      </td>
                      <td className="card-title" data-label="حساب">
                        <span dir="ltr">{r.account_code}</span> — {r.account_name}
                        {r.analytic_name && (
                          <span className="field-hint">تفصیلی: {r.analytic_name}</span>
                        )}
                        {r.system_role && (
                          <span className="field-hint field-hint--warn">
                            نقشِ سیستمی — ثبت‌های خودکارِ آینده همچنان به همین حساب می‌آیند.
                          </span>
                        )}
                      </td>
                      <td data-label="مانده" className="num">{fa(r.balance)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      <SectionCard icon={ArrowLeftRight} title="گامِ ۲ — مقصد" tip="مانده به این حساب/تفصیلی منتقل می‌شود.">
        <FormGrid cols={2}>
          <FormField label="حسابِ مقصد" required>
            {(id) => (
              <SearchSelect id={id} value={destAccount} onChange={(e) => setDestAccount(e.target.value)}>
                <option value="">— انتخاب کنید —</option>
                {postable.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            )}
          </FormField>
          <FormField label="تفصیلیِ مقصد" optional tip="شناسه‌ی تفصیلی؛ خالی یعنی بدونِ تفصیلی.">
            {(id) => (
              <input
                id={id}
                value={destAnalytic}
                onChange={(e) => setDestAnalytic(e.target.value)}
                dir="ltr"
              />
            )}
          </FormField>
        </FormGrid>
        <div className="ef-card-foot">
          <button
            type="button"
            className="ef-btn-secondary"
            disabled={!chosen.length || !destAccount}
            onClick={() => void runPreview()}
          >
            <Scale size={15} /> پیش‌نمایشِ سند
          </button>
        </div>
      </SectionCard>

      {preview && (
        <SectionCard icon={Scale} title="گامِ ۳ — پیش‌نمایشِ سند" tip="تا اختلاف صفر نشود، سند صادر نمی‌شود.">
          {preview.warnings.map((w) => (
            <p key={w} className="fy-note fy-note--warn">
              <AlertTriangle size={14} /> {w}
            </p>
          ))}
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th>مبدأ</th>
                  <th>مانده</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((i) => (
                  <tr key={`${i.account_id}-${i.analytic_id ?? ''}`}>
                    <td className="card-title" data-label="مبدأ">
                      <span dir="ltr">{i.account_code}</span> — {i.account_name}
                      {i.analytic_name && <span className="field-hint">تفصیلی: {i.analytic_name}</span>}
                    </td>
                    <td data-label="مانده" className="num">{fa(i.balance)}</td>
                    <td data-label="بدهکار" className="num">{faAmount(i.source_debit)}</td>
                    <td data-label="بستانکار" className="num">{faAmount(i.source_credit)}</td>
                  </tr>
                ))}
                <tr className="acc-row--total">
                  <td className="card-title" data-label="مبدأ">
                    مقصد: {preview.dest_account_name}
                    {preview.dest_analytic_name ? ` / ${preview.dest_analytic_name}` : ''}
                  </td>
                  <td className="num" data-label="مانده">—</td>
                  <td className="num" data-label="بدهکار">{fa(preview.total_debit)}</td>
                  <td className="num" data-label="بستانکار">{fa(preview.total_credit)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className={Number(preview.difference) === 0 ? 'hint' : 'ef-message ef-message--warn ef-block-note'}>
            اختلاف: {fa(preview.difference)}
          </p>
        </SectionCard>
      )}
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              preview === null
                ? 'مبدأ و مقصد را انتخاب کنید و پیش‌نمایش بگیرید.'
                : ready
                  ? 'پیش‌نمایش متوازن است؛ سند صادر شدنی است.'
                  : `اختلافِ پیش‌نمایش: ${fa(preview.difference)}`
            }
          />
        }
      >
        <button type="button" className="btn-primary" disabled={!ready} onClick={() => void issue()}>
          <Check size={16} /> صدورِ سند اصلاح
        </button>
      </ActionBar>
    </OpsPage>
  )
}
