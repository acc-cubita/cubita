import { useId, useRef, useState } from 'react'
import { AlertTriangle, Coins, Minus, RefreshCw, Scale, TrendingDown, TrendingUp } from 'lucide-react'
import { fetchFxPreview, issueFxRevaluation, type FxRow } from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { CurrenciesPanel } from '../../components/CurrenciesPanel'
import { DocFooter } from '../../components/DocFooter'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { CountBadge } from '../../components/form/FormKit'
import { formatJalali, todayIso } from '../../lib/jalali'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { AsyncBlock, fa, faInt, OpsPage, useAsync, type Msg } from './kit'

/**
 * صدورِ سندِ تسعیرِ ارز — هم‌سبکِ «سند حسابداری» (خواسته‌ی آرش: صفحه‌ها یکی‌یکی با همان تم).
 *
 * مانده‌ی ارزیِ هر حساب با نرخِ روز سنجیده می‌شود و اختلافِ ریالی به سود/زیانِ تسعیر می‌رود. صفحه
 * پیش‌نمایشِ همان سندی است که صادر می‌شود: سربرگِ خانه‌ای (شرح و تاریخ)، گریدِ اکسلیِ فقط‌خواندنی (سرستونِ
 * خاکستری، شماره‌ی ردیف با انتخاب و جمعِ انتخاب، عرضِ کشیدنی)، و نوارِ پایینِ سند — ستون‌به‌ستون با گرید:
 * «جمع ارزش دفتری» زیرِ ارزشِ دفتری، «جمع ارزش امروز» زیرِ ارزشِ امروز، و سود/زیانِ خالص زیرِ «اختلاف».
 *
 * فقط ردیف‌هایی که هنگامِ ثبت مبلغِ ارزی داشته‌اند وارد محاسبه می‌شوند. ارزی که تا این تاریخ نرخ ندارد
 * بیرون می‌ماند و هشدارش هم بالای گرید است هم در نوارِ پایین؛ نرخ را همین پایین در «ارزها» ثبت کنید.
 */

const LAYOUT = { fixed: ['rowhead'], auto: 'account' } as const

/** سربرگ و پایین روی گرید: [ردیف…مانده‌ی ارزی] [نرخ] [دفتری] [امروز] [اختلاف]. */
const FX_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('account') + w('currency') + w('fxbal'), w('rate'), w('book'), w('market'), w('diff')]
}

const rowKey = (r: FxRow) => `${r.account_id}-${r.analytic_id ?? '—'}-${r.cost_center_id ?? '—'}-${r.currency_code}`
const sum = (rows: readonly FxRow[], f: 'book_value' | 'market_value' | 'difference') =>
  rows.reduce((s, r) => s + Number(r[f] || 0), 0)

export function FxRevaluationPage({ token }: { token: string }) {
  const [asOf, setAsOf] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const preview = useAsync(() => fetchFxPreview(token, asOf), [token, asOf])
  const formRef = useRef<HTMLFormElement>(null)
  const uid = useId()
  const cw = useColumnWidths('cubita.grid.fx.shares', LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.fx-sheet', slots: FX_SLOTS })

  const data = preview.data
  const items = data?.items ?? []
  const net = Number(data?.total_difference ?? 0)
  const missing = data?.missing_rates ?? []
  const order = items.map(rowKey)
  const picked = items.filter((r) => selected.has(rowKey(r)))
  const canIssue = Boolean(data) && !preview.loading && net !== 0

  async function issue() {
    if (!canIssue || busy) return
    if (!window.confirm(`سندِ تسعیر با تاریخ ${formatJalali(asOf)} صادر شود؟`)) return
    setBusy(true)
    try {
      const out = await issueFxRevaluation(token, asOf, description)
      setMsg({
        text: `سندِ تسعیر با شماره ${fa(out.number ?? 0)} و خالصِ ${fa(out.net_difference)} صادر شد.`,
        kind: 'ok',
      })
      setDescription('')
      clear()
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const head = (id: string, label: string, next?: string) => (
    <th data-col={id}>
      {label}
      {next && cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  //: سود سبز، زیان قرمز (قراردادِ حسابداری، نه خطا)، بی‌اختلاف خاکستری — و ارزِ بی‌نرخ زرد.
  const tone = !data ? 'empty' : net > 0 ? 'ok' : net < 0 ? 'err' : missing.length > 0 ? 'warn' : 'empty'
  const missingNote = missing.length > 0 ? `· ${missing.join('، ')} بی‌نرخ` : undefined

  return (
    <OpsPage
      canvas
      icon={Coins}
      title="صدور سند تسعیر ارز"
      description="مانده‌ی ارزیِ هر حساب با نرخِ روز سنجیده می‌شود و اختلافِ ریالی به سود/زیانِ تسعیر می‌رود. فقط ردیف‌هایی که هنگامِ ثبت مبلغِ ارزی داشته‌اند وارد محاسبه می‌شوند."
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void issue()
        }}
        onKeyDown={(e) => {
          //: Ctrl+S مثلِ سند حسابداری — همان دکمه، همان تأیید.
          if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
            e.preventDefault()
            void issue()
          }
        }}
      >
        <SectionCard
          icon={Scale}
          title="پیش‌نمایشِ تسعیر"
          tip="ارزشِ دفتری در برابرِ ارزشِ امروز؛ اختلاف همان سندی است که زده می‌شود. روی شماره‌ی ردیف‌ها کلیک کنید تا جمعِ همان‌ها را ببینید."
          badge={data ? <CountBadge>{faInt(items.length)} حساب</CountBadge> : undefined}
          actions={
            <button
              type="button"
              className="btn-ghost jk-trigger"
              onClick={preview.reload}
              title="نرخ‌ها یا اسناد عوض شده‌اند؟ دوباره حساب کنید."
            >
              <RefreshCw size={15} aria-hidden="true" /> محاسبه‌ی دوباره
            </button>
          }
        >
          <div className="jh-bar">
            <div className="jh-row">
              <div className="jh-field jh-field--grow">
                <label className="jh-label" htmlFor={`${uid}-desc`}>
                  شرح سند
                </label>
                <input
                  id={`${uid}-desc`}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={`سند تسعیر ارز تا ${formatJalali(asOf)}`}
                />
              </div>
              <div className="jh-field jh-field--rest">
                <label className="jh-label" htmlFor={`${uid}-date`}>
                  تاریخِ تسعیر <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <JalaliDatePicker id={`${uid}-date`} value={asOf} onChange={setAsOf} />
              </div>
            </div>
          </div>

          {missing.length > 0 && (
            <p className="hint acc-note acc-note--err">
              <AlertTriangle size={14} />
              برای {missing.join('، ')} تا این تاریخ نرخی ثبت نشده؛ این ارزها در محاسبه نیامدند — نرخ را در «ارزها»ی
              پایینِ صفحه ثبت کنید.
            </p>
          )}

          <AsyncBlock
            loading={preview.loading && !data}
            error={data ? null : preview.error}
            empty={items.length === 0}
            emptyText="هیچ حسابی مانده‌ی ارزی ندارد. برای ثبتِ ردیفِ ارزی، هنگامِ ثبتِ سند ارز و مبلغِ ارزی را وارد کنید."
          >
            <div className="table-scroll ef-table-wrap">
              <table
                ref={cw.frame}
                className={`cards-on-mobile acc-table ef-table xl-grid fx-sheet${preview.loading ? ' is-loading' : ''}`}
              >
                <colgroup>
                  <col className="fx-c-rowhead" style={cw.col('rowhead')} />
                  <col style={cw.col('account')} />
                  <col className="fx-c-cur" style={cw.col('currency')} />
                  <col className="fx-c-num" style={cw.col('fxbal')} />
                  <col className="fx-c-num" style={cw.col('rate')} />
                  <col className="fx-c-money" style={cw.col('book')} />
                  <col className="fx-c-money" style={cw.col('market')} />
                  <col className="fx-c-money" style={cw.col('diff')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="انتخاب" />
                    {head('account', 'حساب', 'currency')}
                    {head('currency', 'ارز', 'fxbal')}
                    {head('fxbal', 'مانده‌ی ارزی', 'rate')}
                    {head('rate', 'نرخِ روز', 'book')}
                    {head('book', 'ارزشِ دفتری', 'market')}
                    {head('market', 'ارزشِ امروز', 'diff')}
                    {head('diff', 'اختلاف')}
                  </tr>
                </thead>
                <tbody>
                  {items.map((row, i) => {
                    const key = rowKey(row)
                    const diff = Number(row.difference)
                    const on = selected.has(key)
                    // بُعدها ستونِ تازه نمی‌گیرند: هویتِ ردیف‌اند، پس زیرِ خودِ حساب می‌نشینند.
                    const dims = [
                      row.analytic_name
                        ? `تفصیلی: ${row.analytic_code ? `${row.analytic_code} ` : ''}${row.analytic_name}`
                        : null,
                      row.cost_center_name ? `مرکز: ${row.cost_center_name}` : null,
                    ].filter(Boolean)
                    // نرخِ کهنه حدس نیست ولی نرخِ روز هم نیست — باید دیده شود.
                    const stale = row.rate_date !== asOf
                    return (
                      <tr key={key} className={on ? 'is-selected' : undefined}>
                        <td className="xl-rowhead card-hide">
                          <button
                            type="button"
                            className="xl-rowhead-btn"
                            aria-pressed={on}
                            aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}
                            onClick={(e) => click(order, key, modsOf(e))}
                          >
                            {faInt(i + 1)}
                          </button>
                        </td>
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
                          {stale && <span className="field-hint field-hint--warn">نرخِ {formatJalali(row.rate_date)}</span>}
                        </td>
                        <td data-label="ارزشِ دفتری" className="num">
                          {fa(row.book_value)}
                        </td>
                        <td data-label="ارزشِ امروز" className="num">
                          {fa(row.market_value)}
                        </td>
                        <td data-label="اختلاف" className={`num ${diff >= 0 ? 'pos-in' : 'pos-out'}`}>
                          {fa(diff)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {picked.length > 0 && (
              <SelectionBar count={picked.length} unit="حساب" onClear={clear}>
                <span>
                  ارزشِ دفتری <b className="num">{fa(sum(picked, 'book_value'))}</b>
                </span>
                <span>
                  ارزشِ امروز <b className="num">{fa(sum(picked, 'market_value'))}</b>
                </span>
                <span>
                  اختلاف <b className="num">{fa(sum(picked, 'difference'))}</b>
                </span>
              </SelectionBar>
            )}
          </AsyncBlock>
        </SectionCard>

        <DocFooter
          tone={tone}
          columns
          statusEnd
          submitting={busy}
          submittingLabel="در حال صدور…"
          submitLabel="صدور سند تسعیر"
          submitDisabled={!canIssue}
          shortcut
          message={msg}
          groupLabel="خلاصه‌ی تسعیر"
          statusLabel="سود / زیانِ تسعیر"
          statusKey={`${tone}-${net}`}
          status={
            !data ? (
              'در حال محاسبه…'
            ) : net > 0 ? (
              <>
                <TrendingUp aria-hidden="true" /> سودِ تسعیر
              </>
            ) : net < 0 ? (
              <>
                <TrendingDown aria-hidden="true" /> زیانِ تسعیر
              </>
            ) : (
              <>
                <Minus aria-hidden="true" /> بی‌اختلاف
              </>
            )
          }
          sub={
            data
              ? net !== 0
                ? { main: fa(Math.abs(net)), side: missingNote }
                : { main: missing.length > 0 ? `${missing.join('، ')} بی‌نرخ` : 'سندی لازم نیست' }
              : undefined
          }
          stats={[
            { label: 'جمع ارزش دفتری', value: fa(sum(items, 'book_value')), className: 'jb-stat--a' },
            { label: 'جمع ارزش امروز', value: fa(sum(items, 'market_value')), className: 'jb-stat--b' },
          ]}
        />
      </form>

      {/* نرخِ تازه همین‌جا ثبت می‌شود و پیش‌نمایش بی «محاسبه‌ی دوباره» به‌روز می‌شود. */}
      <CurrenciesPanel token={token} onSaved={preview.reload} />
    </OpsPage>
  )
}
