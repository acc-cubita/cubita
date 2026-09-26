import { useId, useRef, useState } from 'react'
import { AlertTriangle, CalendarCheck, Lock, Minus, Scale, TrendingDown, TrendingUp } from 'lucide-react'

import { createPeriodClose, fetchPeriodCloses, fetchPnlClosePreview, issuePnlClose, type FiscalPeriodCloseRecord } from '../../api'
import { DocFooter } from '../../components/DocFooter'
import { CountBadge, FormStatus } from '../../components/form/FormKit'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { formatJalali, todayIso } from '../../lib/jalali'
import { PNL_TONE, destinationLine, dimsText, pnlRowKey, pnlState } from '../../lib/pnlClose'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { AsyncBlock, OpsPage, fa, faAmount, faInt, useAsync, type Msg } from './kit'

const LAYOUT = { fixed: ['rowhead'], auto: 'account' } as const

/** سربرگ و نوار روی گرید، همان پنج خانه‌ی سند حسابداری: [ردیف + حساب] [شرح ردیف] [بدهکار] [بستانکار] [—]. */
const PNL_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('account'), w('desc'), w('debit'), w('credit'), 0]
}

/**
 * «بستن حساب‌های سود و زیان» — هم‌سبکِ «سند حسابداری» (الگوی «ج»: پیش‌نمایشِ سندِ خودکار).
 *
 * **گامِ ۱** پیش‌نمایشِ دقیقِ سندی است که زده می‌شود: سربرگِ خانه‌ای (شرحِ سند، از تاریخ، بستن تا تاریخ) روی گریدِ
 * فقط‌خواندنیِ ردیف‌های سند — حساب (بُعدها زیرش)، شرحِ ردیف از سرور، بدهکار، بستانکار — و خطِ «سود انباشته» ته آن؛
 * نوارِ پایینِ سند ستون‌به‌ستون: جمعِ بدهکار و بستانکار زیرِ ستونِ خودشان و سود/زیانِ دوره زیرِ شرح. سند موقت است.
 *
 * **گامِ ۲** قفلِ دوره است، جدا و برگشت‌ناپذیر؛ کارتِ خودش را بعد از سند دارد و بی تأییدِ صریح اجرا نمی‌شود.
 */
export function ClosePnlPage({ token }: { token: string }) {
  const [dateTo, setDateTo] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [notes, setNotes] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [lockMsg, setLockMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const preview = useAsync(() => fetchPnlClosePreview(token, dateTo), [token, dateTo])
  const closes = useAsync(() => fetchPeriodCloses(token), [token])
  const formRef = useRef<HTMLFormElement>(null)
  const uid = useId()
  const cw = useColumnWidths('cubita.grid.pnlclose.shares', LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.pc-sheet', slots: PNL_SLOTS })

  const data = preview.data
  const rows = data?.rows ?? []
  const state = data ? pnlState(data) : 'none'
  const profit = Number(data?.net_profit ?? 0)
  const dest = data ? destinationLine(data) : null
  const order = rows.map(pnlRowKey)
  const picked = rows.filter((r) => selected.has(pnlRowKey(r)))
  const canIssue = Boolean(data) && !preview.loading && (state === 'profit' || state === 'loss' || state === 'even')
  //: تاریخِ آخرین قفل مرزِ ثبتِ سند است — همان چیزی که پیش از قفلِ تازه باید دید.
  const lastClose = (closes.data ?? []).reduce<FiscalPeriodCloseRecord | null>(
    (best, c) => (!best || c.closing_date > best.closing_date ? c : best),
    null,
  )

  /** گامِ اول — فقط سند. دوره باز می‌ماند و سند موقت است. */
  async function issue() {
    if (!canIssue || busy) return
    if (!window.confirm(`سندِ بستنِ حساب‌های سود و زیان تا ${formatJalali(dateTo)} صادر شود؟ سند موقت است و دوره باز می‌ماند.`))
      return
    setBusy(true)
    try {
      const out = await issuePnlClose(token, dateTo, description)
      setMsg({
        text: `سندِ بستن با شماره ${fa(out.number ?? 0)} و ${faInt(out.line_count)} ردیف ثبت شد؛ ${Number(out.net_profit) >= 0 ? 'سودِ' : 'زیانِ'} خالص ${fa(Math.abs(Number(out.net_profit)))}. سند موقت است و دوره هنوز باز.`,
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
      setLockMsg({
        text: `دوره تا ${formatJalali(out.closing_date)} قفل شد؛ سود/زیانِ خالص ${fa(out.net_profit)}.`,
        kind: 'ok',
      })
      setNotes('')
      preview.reload()
      closes.reload()
    } catch (err) {
      setLockMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const head = (id: string, label: string, next?: string, cls?: string) => (
    <th data-col={id} className={cls}>
      {label}
      {next && cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const fromText = data?.date_from ? formatJalali(data.date_from) : 'ابتدای دفتر'

  return (
    <OpsPage
      canvas
      icon={CalendarCheck}
      title="بستن حساب‌های سود و زیان"
      description="حساب‌های موقت (درآمد و هزینه) صفر می‌شوند و سود/زیانِ خالص به سود انباشته می‌رود. سند موقت است؛ قفلِ دوره گامِ دومِ جداست."
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
          title="گامِ ۱ — سندِ بستن"
          description={
            data
              ? `درآمد ${fa(data.total_income)} · هزینه ${fa(data.total_expenses)} · مقصد: ${data.destination_account_name}`
              : undefined
          }
          tip="پیش‌نمایشِ همان سندی که زده می‌شود: هر حسابِ درآمد و هزینه (به تفکیکِ تفصیلی و مرکز هزینه) عکسِ مانده‌اش زده می‌شود تا صفر شود، و خالص به سود انباشته می‌رود. روی شماره‌ی ردیف‌ها کلیک کنید تا جمعِ همان‌ها را ببینید."
          badge={data ? <CountBadge>{faInt(rows.length + (dest ? 1 : 0))} ردیف</CountBadge> : undefined}
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
                  placeholder={`سند بستن حساب‌های سود و زیان تا تاریخ ${formatJalali(dateTo)}`}
                />
              </div>
              <div className="jh-field jh-field--date">
                <span className="jh-label">از تاریخ</span>
                {/* شروعِ بازه انتخابی نیست: روزِ بعد از آخرین قفل، یا ابتدای دفتر. */}
                <span className="jh-static" title="روزِ بعد از آخرین دوره‌ی قفل‌شده">
                  {fromText}
                </span>
              </div>
              <div className="jh-field jh-field--tail">
                <label className="jh-label" htmlFor={`${uid}-date`}>
                  بستن تا تاریخ <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <JalaliDatePicker id={`${uid}-date`} value={dateTo} onChange={setDateTo} />
              </div>
            </div>
          </div>

          {data?.already_closed && (
            <p className="hint acc-note">
              <CalendarCheck size={14} />
              سندِ بستن برای این بازه از قبل زده شده. اگر بعد از آن سندی اضافه شده باشد، صدورِ دوباره فقط همان تفاوت را
              می‌بندد.
            </p>
          )}

          <AsyncBlock
            loading={preview.loading && !data}
            error={data ? null : preview.error}
            empty={rows.length === 0}
            emptyText="در این بازه هیچ فعالیتِ درآمد/هزینه‌ای برای بستن نیست."
          >
            <div className="table-scroll ef-table-wrap">
              <table
                ref={cw.frame}
                className={`cards-on-mobile acc-table ef-table xl-grid pc-sheet${preview.loading ? ' is-loading' : ''}`}
              >
                <colgroup>
                  <col className="pc-c-rowhead" style={cw.col('rowhead')} />
                  <col style={cw.col('account')} />
                  <col className="pc-c-desc" style={cw.col('desc')} />
                  <col className="pc-c-money" style={cw.col('debit')} />
                  <col className="pc-c-money" style={cw.col('credit')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="انتخاب" />
                    {head('account', 'حساب', 'desc')}
                    {head('desc', 'شرح ردیف', 'debit')}
                    {head('debit', 'بدهکار', 'credit', 'num')}
                    {head('credit', 'بستانکار', undefined, 'num')}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const key = pnlRowKey(r)
                    const on = selected.has(key)
                    const dims = dimsText(r)
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
                        <td className="card-title" title={`${r.account_code} — ${r.account_name}`}>
                          <span dir="ltr">{r.account_code}</span> — {r.account_name}
                          {dims && <span className="field-hint">{dims}</span>}
                        </td>
                        <td data-label="شرح ردیف" className="xl-txt">
                          {r.description || '—'}
                        </td>
                        <td data-label="بدهکار" className="num">
                          {faAmount(r.debit)}
                        </td>
                        <td data-label="بستانکار" className="num">
                          {faAmount(r.credit)}
                        </td>
                      </tr>
                    )
                  })}
                  {data && dest && (
                    //: خطِ مقصد هم یک ردیفِ سند است — از سرور (کد، نام، شرح) و مبلغش خالصِ دوره.
                    <tr className="pc-dest">
                      <td className="xl-rowhead card-hide" aria-hidden="true">
                        <Scale size={13} />
                      </td>
                      <td className="card-title">
                        <span dir="ltr">{data.destination_account_code}</span> — {data.destination_account_name}
                      </td>
                      <td data-label="شرح ردیف" className="xl-txt">
                        {data.destination_description}
                      </td>
                      <td data-label="بدهکار" className="num">
                        {faAmount(dest.debit)}
                      </td>
                      <td data-label="بستانکار" className="num">
                        {faAmount(dest.credit)}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {picked.length > 0 && (
              <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>
                <span>
                  بدهکار <b className="num">{fa(picked.reduce((s, r) => s + Number(r.debit), 0))}</b>
                </span>
                <span>
                  بستانکار <b className="num">{fa(picked.reduce((s, r) => s + Number(r.credit), 0))}</b>
                </span>
              </SelectionBar>
            )}
          </AsyncBlock>
        </SectionCard>

        <DocFooter
          tone={PNL_TONE[state]}
          columns
          submitting={busy}
          submittingLabel="در حال صدور…"
          submitLabel="صدور سند بستن"
          submitDisabled={!canIssue}
          shortcut
          message={msg}
          groupLabel="جمعِ سندِ بستن"
          statusLabel="نتیجه‌ی دوره"
          statusKey={`${state}-${profit}`}
          status={
            !data ? (
              'در حال محاسبه…'
            ) : state === 'profit' ? (
              <>
                <TrendingUp aria-hidden="true" /> سودِ دوره
              </>
            ) : state === 'loss' ? (
              <>
                <TrendingDown aria-hidden="true" /> زیانِ دوره
              </>
            ) : state === 'off' ? (
              <>
                <AlertTriangle aria-hidden="true" /> ناتراز
              </>
            ) : state === 'even' ? (
              <>
                <Minus aria-hidden="true" /> بی سود و زیان
              </>
            ) : (
              'سندی لازم نیست'
            )
          }
          sub={
            data && (state === 'profit' || state === 'loss')
              ? { main: fa(Math.abs(profit)), side: 'به سود انباشته' }
              : data && state === 'off'
                ? { main: `اختلاف ${fa(data.difference)}` }
                : undefined
          }
          stats={[
            { label: 'جمع بدهکار', value: data ? fa(data.total_debit) : '—', className: 'jb-stat--debit' },
            { label: 'جمع بستانکار', value: data ? fa(data.total_credit) : '—', className: 'jb-stat--credit' },
          ]}
        />
      </form>

      <SectionCard
        icon={Lock}
        title="گامِ ۲ — قفلِ دوره"
        tip="پس از قفل، هیچ سندی در این بازه ثبت یا اصلاح نمی‌شود و اسنادِ موقتِ داخلش دائم می‌شوند. این کار برگشت ندارد."
        actions={
          <button type="button" className="ef-btn-secondary pc-lock" onClick={() => void lock()}>
            <Lock size={15} /> قفل کردنِ دوره تا {formatJalali(dateTo)}
          </button>
        }
      >
        <div className="jh-bar">
          <div className="jh-row">
            <div className="jh-field jh-field--grow">
              <label className="jh-label" htmlFor={`${uid}-notes`}>
                یادداشتِ قفل
              </label>
              <input id={`${uid}-notes`} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="اختیاری" />
            </div>
            <div className="jh-field jh-field--rest">
              <span className="jh-label">آخرین دوره‌ی قفل‌شده</span>
              {/* جدولِ کاملِ دوره‌ها فقط در فهرستِ «دوره‌های بسته‌شده» است (دو نمای یک داده نمی‌سازیم). */}
              <span className="jh-static">
                {lastClose
                  ? `تا ${formatJalali(lastClose.closing_date)} — ${Number(lastClose.net_profit) >= 0 ? 'سود' : 'زیان'} ${fa(Math.abs(Number(lastClose.net_profit)))}`
                  : 'هنوز دوره‌ای قفل نشده'}
              </span>
            </div>
          </div>
        </div>
        {data && !data.already_closed && rows.length > 0 && (
          <p className="hint acc-note acc-note--warn">
            <AlertTriangle size={14} />
            هنوز سندِ بستن زده نشده. اگر مستقیم قفل کنید، سند همین‌جا خودکار زده می‌شود.
          </p>
        )}
        {data && data.temporary_in_range > 0 && (
          <p className="hint acc-note acc-note--warn">
            <AlertTriangle size={14} />
            {faInt(data.temporary_in_range)} سندِ موقت در این بازه هست؛ با قفلِ دوره همه دائم می‌شوند.
          </p>
        )}
        <FormStatus msg={lockMsg} />
      </SectionCard>
    </OpsPage>
  )
}
