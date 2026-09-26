import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { AlertTriangle, ArrowLeftRight, CheckCircle2, ListTree, Search } from 'lucide-react'

import {
  fetchAnalytics,
  fetchChartAccounts,
  fetchReclassSources,
  issueReclass,
  previewReclass,
  type ReclassPreview,
} from '../../api'
import { DocFooter } from '../../components/DocFooter'
import { CountBadge } from '../../components/form/FormKit'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import {
  destTotals,
  filterSources,
  itemsByKey,
  pickedBalance,
  reclassBody,
  sourceKey,
} from '../../lib/balanceReclass'
import { formatJalali, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { AsyncBlock, OpsPage, fa, faAmount, faInt, useAsync, type Msg } from './kit'

const LAYOUT = { fixed: ['rowhead'], auto: 'account' } as const

/** سربرگ و نوار روی گرید: [ردیف + حساب] [تفصیلی + مانده] [بدهکار] [بستانکار] [—]. */
const RB_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('account'), w('analytic') + w('balance'), w('debit'), w('credit'), 0]
}
/** جابه‌جاییِ PageUp/PageDown. */
const PAGE_STEP = 10

/** مانده با سمت: مانده‌ی بستانکار عادی است، نه منفیِ قرمز. */
function SideAmount({ value }: { value: string | number }) {
  const v = Number(value || 0)
  if (!v) return <>—</>
  return (
    <>
      {fa(Math.abs(v))} <span className="rp-side">{v > 0 ? 'بد' : 'بس'}</span>
    </>
  )
}

/**
 * «انتقال مانده به حساب دیگر» — هم‌سبکِ «سند حسابداری» (الگوی «ج»: پیش‌نمایشِ سندِ خودکار).
 *
 * مانده‌ی یک یا چند ترکیبِ (حساب، تفصیلی) را با یک سندِ متوازن به حساب/تفصیلیِ درست می‌برد. **با «انتقال حساب به
 * سرفصل دیگر» یکی نیست:** آن یکی جای خودِ حساب را در درخت عوض می‌کند و گزارشِ گذشته را هم؛ این یکی اسنادِ گذشته را
 * دست نمی‌زند و اصلاح را رویدادی تاریخ‌دار ثبت می‌کند.
 *
 * - **سربرگ:** شرحِ سند و تاریخِ اصلاح، و در سطرِ دوم حساب و تفصیلیِ مقصد (تفصیلی پیش از این شناسه‌ی خام بود که باید
 *   تایپ می‌شد).
 * - **برگه:** همه‌ی مبدأهای مانده‌دار؛ کلیک روی ردیف (یا Space) انتخابش می‌کند و Shift بازه را. هر بار که انتخاب یا مقصد
 *   عوض شود، پیش‌نمایشِ سرور خودش می‌آید — بدهکار و بستانکارِ هر مبدأ در خانه‌های خودش و «مقصد» در پانویس.
 * - **نوار:** «صدورِ سند اصلاح» (Ctrl+S)، وضعیتِ توازن و جمعِ بدهکار و بستانکارِ کلِ سند.
 */
export function BalanceReclassPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const [asOf, setAsOf] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [destAccount, setDestAccount] = useState('')
  const [destAnalytic, setDestAnalytic] = useState('')
  const [query, setQuery] = useState('')
  const [onlyPicked, setOnlyPicked] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const uid = useId()
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const cw = useColumnWidths('cubita.grid.balreclass.shares', LAYOUT)
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.rb-sheet', slots: RB_SLOTS })

  const sources = useAsync(() => fetchReclassSources(token, asOf), [token, asOf])
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const analytics = useAsync(() => fetchAnalytics(token).catch(() => []), [token])
  const postable = useMemo(
    () => (accounts.data ?? []).filter((a) => !a.is_group && a.is_active).sort((a, b) => a.code.localeCompare(b.code)),
    [accounts.data],
  )
  const all = useMemo(() => sources.data ?? [], [sources.data])

  // ── انتخابِ مبدأها: کلیک روی ردیف یکی را روشن/خاموش می‌کند، Shift بازه را اضافه ──
  const { selected, click, clear } = useRowSelection()
  const shown = filterSources(all, query, onlyPicked, selected)
  const order = shown.map(sourceKey)
  const pickedCount = all.filter((s) => selected.has(sourceKey(s))).length
  const toggle = (key: string, shift = false) => click(order, key, { shift, ctrl: true })
  //: تاریخِ دیگر یعنی مانده‌های دیگر؛ انتخابِ قبلی شاید دیگر مانده نداشته باشد.
  useEffect(() => clear(), [asOf, clear])

  // ── پیش‌نمایشِ خودکار: هر بار که مبدأ، مقصد یا تاریخ عوض شود؛ پاسخِ دیررسیده روی انتخابِ تازه نمی‌نشیند ──
  const body = reclassBody(all, selected, { asOf, destAccountId: destAccount, destAnalyticId: destAnalytic, description })
  const bodyKey = JSON.stringify([body.as_of, body.sources, body.dest_account_id, body.dest_analytic_id])
  const [preview, setPreview] = useState<{ key: string; data: ReclassPreview | null; error: string | null; loading: boolean }>({
    key: '',
    data: null,
    error: null,
    loading: false,
  })
  const liveKey = useRef('')
  const ready = body.sources.length > 0 && Boolean(destAccount)
  useEffect(() => {
    liveKey.current = bodyKey
    if (!ready) return
    //: دادهٔ انتخابِ قبلی نگه داشته نمی‌شود؛ وگرنه مبلغِ مبدأیی که تازه برداشته شده تا رسیدنِ پاسخ در جمع می‌ماند.
    setPreview({ key: bodyKey, data: null, error: null, loading: true })
    const t = setTimeout(() => {
      previewReclass(token, body)
        .then((data) => liveKey.current === bodyKey && setPreview({ key: bodyKey, data, error: null, loading: false }))
        .catch(
          (err) =>
            liveKey.current === bodyKey &&
            setPreview({ key: bodyKey, data: null, error: err instanceof Error ? err.message : 'خطای ناشناخته', loading: false }),
        )
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, bodyKey, ready])
  const current = ready && preview.key === bodyKey ? preview : null
  const data = current?.data ?? null
  const items = itemsByKey(data)
  const dest = data ? destTotals(data) : null
  const balanced = data !== null && Number(data.difference) === 0
  const canIssue = balanced && !current?.loading && !busy

  async function issue() {
    if (!canIssue || !data) return
    if (!window.confirm(`سندِ انتقالِ مانده‌ی ${faInt(body.sources.length)} مبدأ به «${data.dest_account_name}» با تاریخ ${formatJalali(asOf)} صادر شود؟`))
      return
    setBusy(true)
    try {
      const out = await issueReclass(token, body)
      setMsg({ text: `سندِ اصلاح با شماره ${fa(out.number ?? 0)} و ${faInt(out.line_count)} ردیف صادر شد.`, kind: 'ok' })
      setDescription('')
      clear()
      sources.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  // ── صفحه‌کلید ──
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, shown.length - 1))
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`rb-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(shown.length - 1, i)))
  }
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault()
      findRef.current?.focus()
      return
    }
    const last = shown.length - 1
    if (last < 0) return
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowUp': {
        e.preventDefault()
        const to = active + (e.key === 'ArrowDown' ? 1 : -1)
        if (to < 0 || to > last) break
        moveTo(to)
        //: Shift+↑↓ مبدأ را به انتخاب اضافه می‌کند، مثلِ کشیدنِ ماوس روی شماره‌ی ردیف‌ها.
        if (e.shiftKey && !selected.has(order[to])) toggle(order[to])
        break
      }
      case 'PageDown':
      case 'PageUp':
        e.preventDefault()
        moveTo(active + (e.key === 'PageDown' ? PAGE_STEP : -PAGE_STEP))
        break
      case 'Home':
      case 'End':
        e.preventDefault()
        moveTo(e.key === 'Home' ? 0 : last)
        break
      case ' ':
      case 'Enter':
        e.preventDefault()
        toggle(order[active])
        break
      case 'Escape':
        if (selected.size > 0) {
          e.preventDefault()
          clear()
        }
        break
    }
  }

  const head = (id: string, label: string, next?: string, cls?: string) => (
    <th data-col={id} className={cls}>
      {label}
      {next && cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const tone = !ready ? 'empty' : current?.error ? 'err' : !data ? 'empty' : balanced ? 'ok' : 'err'
  const destName = data
    ? `${data.dest_account_code} — ${data.dest_account_name}${data.dest_analytic_name ? ` / ${data.dest_analytic_name}` : ''}`
    : ''

  return (
    <OpsPage
      canvas
      icon={ArrowLeftRight}
      title="انتقال مانده به حساب دیگر"
      description="مانده‌ی یک حساب/تفصیلی را با یک سندِ متوازن به حساب یا تفصیلیِ درست می‌برد (اصلاحِ طبقه‌بندیِ مانده). اسنادِ گذشته دست‌نخورده می‌مانند و انتقال به‌عنوان رویدادی تاریخ‌دار ثبت می‌شود. برای جابه‌جاییِ خودِ حساب در درختواره، «انتقال حساب به سرفصل دیگر» را باز کنید."
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
          icon={ArrowLeftRight}
          title="مبدأها و سندِ اصلاح"
          description={
            pickedCount
              ? `${faInt(pickedCount)} مبدأ انتخاب شده${destAccount ? '' : ' — حسابِ مقصد را در سربرگ انتخاب کنید'}`
              : 'روی ردیف‌هایی که مانده‌شان باید منتقل شود کلیک کنید.'
          }
          tip="مانده تا تاریخِ اصلاح. فقط همان ترکیبی که انتخاب می‌کنید منتقل می‌شود، نه کلِ حساب. جهتِ سند از خودِ مانده می‌آید: مانده‌ی بدهکار بستانکار می‌شود تا صفر شود و مقصد همان را می‌گیرد."
          badge={sources.data ? <CountBadge accent>{faInt(all.length)} مبدأ</CountBadge> : undefined}
          actions={
            <div className="jg-head-actions">
              <div className="cc-presets rb-view" role="group" aria-label="نمایشِ مبدأها">
                <button type="button" className={onlyPicked ? '' : 'is-active'} aria-pressed={!onlyPicked} onClick={() => setOnlyPicked(false)}>
                  همه
                </button>
                <button type="button" className={onlyPicked ? 'is-active' : ''} aria-pressed={onlyPicked} onClick={() => setOnlyPicked(true)}>
                  انتخاب‌شده‌ها
                </button>
              </div>
              <div className={`jg-find${query ? ' has-query' : ''}`} role="search">
                <Search size={14} aria-hidden="true" />
                <input
                  ref={findRef}
                  type="search"
                  value={query}
                  placeholder="کد یا نامِ حساب و تفصیلی  (Ctrl+F)"
                  aria-label="جست‌وجوی مبدأ"
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      e.preventDefault()
                      setQuery('')
                      gridRef.current?.focus()
                    } else if (e.key === 'ArrowDown' || e.key === 'Enter') {
                      e.preventDefault()
                      gridRef.current?.focus()
                    }
                  }}
                />
              </div>
            </div>
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
                  placeholder={`انتقال مانده به حساب دیگر تا ${formatJalali(asOf)}`}
                />
              </div>
              <div className="jh-field jh-field--rest">
                <label className="jh-label" htmlFor={`${uid}-date`}>
                  تاریخِ اصلاح <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <JalaliDatePicker id={`${uid}-date`} value={asOf} onChange={setAsOf} />
              </div>
            </div>
            <div className="jh-row jh-row--sub">
              <div className="jh-field">
                <label className="jh-label" htmlFor={`${uid}-dest`}>
                  حسابِ مقصد <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <SearchSelect id={`${uid}-dest`} aria-label="حسابِ مقصد" value={destAccount} onChange={(e) => setDestAccount(e.target.value)}>
                  <option value="">— انتخابِ حسابِ مقصد —</option>
                  {postable.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </SearchSelect>
              </div>
              <div className="jh-field">
                <label className="jh-label" htmlFor={`${uid}-dan`}>
                  تفصیلیِ مقصد
                </label>
                <SearchSelect id={`${uid}-dan`} aria-label="تفصیلیِ مقصد" value={destAnalytic} onChange={(e) => setDestAnalytic(e.target.value)}>
                  <option value="">— بدونِ تفصیلی —</option>
                  {(analytics.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </SearchSelect>
              </div>
            </div>
          </div>

          {(data?.warnings ?? []).map((w) => (
            <p key={w} className="hint acc-note acc-note--warn">
              <AlertTriangle size={14} /> {w}
            </p>
          ))}

          <AsyncBlock
            loading={sources.loading && !sources.data}
            error={sources.data ? null : sources.error}
            empty={all.length === 0}
            emptyText="در این تاریخ هیچ حسابی مانده ندارد."
          >
            <div
              ref={gridRef}
              tabIndex={shown.length > 0 ? 0 : -1}
              className="table-scroll ef-table-wrap lr-scroll rb-scroll"
              onKeyDown={onGridKey}
              aria-label="مبدأها — ↑↓ حرکت، Space یا Enter انتخاب، Shift+↓ افزودن، Esc لغوِ انتخاب، Ctrl+F جست‌وجو"
            >
              <table
                ref={cw.frame}
                className={`cards-on-mobile ef-table xl-grid rp-table rb-sheet${current?.loading ? ' is-loading' : ''}`}
              >
                <colgroup>
                  <col className="rb-c-rowhead" style={cw.col('rowhead')} />
                  <col style={cw.col('account')} />
                  <col className="rb-c-analytic" style={cw.col('analytic')} />
                  <col className="rb-c-money" style={cw.col('balance')} />
                  <col className="rb-c-money" style={cw.col('debit')} />
                  <col className="rb-c-money" style={cw.col('credit')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="انتخاب" />
                    {head('account', 'حساب', 'analytic')}
                    {head('analytic', 'تفصیلی', 'balance')}
                    {head('balance', 'مانده', 'debit', 'num')}
                    {head('debit', 'بدهکار', 'credit', 'num')}
                    {head('credit', 'بستانکار', undefined, 'num')}
                  </tr>
                </thead>
                <tbody>
                  {shown.length === 0 ? (
                    <tr>
                      <td className="card-full rp-status" colSpan={6}>
                        {onlyPicked ? 'هنوز مبدأیی انتخاب نشده.' : 'مبدأیی با این جست‌وجو پیدا نشد.'}
                      </td>
                    </tr>
                  ) : (
                    shown.map((s, i) => {
                      const key = sourceKey(s)
                      const on = selected.has(key)
                      const item = on ? items.get(key) : undefined
                      return (
                        <tr
                          key={key}
                          id={`rb-row-${i}`}
                          aria-selected={on}
                          className={`acc-row--clickable${on ? ' is-selected' : ''}${i === active ? ' is-active' : ''}`}
                          onClick={(e) => {
                            setActiveRow(i)
                            toggle(key, e.shiftKey)
                          }}
                        >
                          <td className="xl-rowhead card-hide">
                            <button
                              type="button"
                              tabIndex={-1}
                              className="xl-rowhead-btn"
                              aria-pressed={on}
                              aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}
                            >
                              {faInt(i + 1)}
                            </button>
                          </td>
                          {/* نقشِ سیستمی نشانِ ردیف نمی‌گیرد — در چارتِ پیش‌فرض بیشترِ حساب‌ها سیستمی‌اند و نشان روی همه
                              یعنی هیچ؛ هشدارش برای مبدأهای انتخاب‌شده از پیش‌نمایشِ سرور بالای برگه می‌آید. */}
                          <td
                            className="card-title"
                            title={`${s.account_code} — ${s.account_name}${s.system_role ? ' (نقشِ سیستمی: ثبت‌های خودکارِ آینده همچنان به همین حساب می‌آیند)' : ''}`}
                          >
                            <span dir="ltr">{s.account_code}</span> — {s.account_name}
                          </td>
                          <td data-label="تفصیلی">
                            {s.analytic_name ? `${s.analytic_code ? `${s.analytic_code} ` : ''}${s.analytic_name}` : '—'}
                          </td>
                          <td data-label="مانده" className="num">
                            <SideAmount value={s.balance} />
                          </td>
                          <td data-label="بدهکار" className="num">
                            {item ? faAmount(item.source_debit) : on && current?.loading ? '…' : '—'}
                          </td>
                          <td data-label="بستانکار" className="num">
                            {item ? faAmount(item.source_credit) : on && current?.loading ? '…' : '—'}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
                <tfoot>
                  {/* خطِ مقصد: در سند یک ردیف به‌ازای هر مبدأ است («دریافتِ مانده‌ی …»)؛ این‌جا جمعشان. */}
                  <tr className="rp-total rb-dest">
                    <td className="xl-rowhead card-hide" />
                    <td className="card-title" colSpan={3}>
                      <ArrowLeftRight size={13} aria-hidden="true" /> مقصد:{' '}
                      {data ? destName : destAccount ? (postable.find((a) => a.id === destAccount)?.name ?? '…') : 'هنوز انتخاب نشده'}
                      {data && <small className="lr-foot-note"> {faInt(data.items.length)} ردیف در سند</small>}
                    </td>
                    <td className="num" data-label="بدهکارِ مقصد">
                      {dest ? faAmount(dest.debit) : '—'}
                    </td>
                    <td className="num" data-label="بستانکارِ مقصد">
                      {dest ? faAmount(dest.credit) : '—'}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
            {pickedCount > 0 && (
              <SelectionBar count={pickedCount} unit="مبدأ" onClear={clear}>
                <span>
                  جمعِ مانده <b className="num"><SideAmount value={pickedBalance(all, selected)} /></b>
                </span>
              </SelectionBar>
            )}
            {onNavigate && (
              <p className="ab-keys lr-keys">
                جابه‌جاییِ خودِ حساب در درختواره کارِ دیگری است:{' '}
                <button type="button" className="link-btn" onClick={() => onNavigate('reclassify')}>
                  <ListTree size={13} aria-hidden="true" /> انتقال حساب به سرفصل دیگر
                </button>
              </p>
            )}
          </AsyncBlock>
        </SectionCard>

        <DocFooter
          tone={tone}
          columns
          submitting={busy}
          submittingLabel="در حال صدور…"
          submitLabel="صدور سند اصلاح"
          submitDisabled={!canIssue}
          shortcut
          message={msg}
          groupLabel="جمعِ سندِ اصلاح"
          statusLabel="وضعیتِ سند"
          statusKey={`${tone}-${current?.loading ? 'l' : ''}-${data?.difference ?? ''}`}
          status={
            !pickedCount ? (
              'مبدأ انتخاب نشده'
            ) : !destAccount ? (
              'مقصد انتخاب نشده'
            ) : current?.error ? (
              <>
                <AlertTriangle aria-hidden="true" /> رد شد
              </>
            ) : !data ? (
              'در حال محاسبه…'
            ) : balanced ? (
              <>
                <CheckCircle2 aria-hidden="true" /> متوازن
              </>
            ) : (
              <>
                <AlertTriangle aria-hidden="true" /> ناتراز
              </>
            )
          }
          sub={
            current?.error
              ? { main: current.error }
              : data
                ? {
                    main: `${faInt(data.items.length * 2)} ردیف · به ${data.dest_account_name}${data.dest_analytic_name ? ` / ${data.dest_analytic_name}` : ''}`,
                    side: balanced ? undefined : `اختلاف ${fa(data.difference)}`,
                  }
                : undefined
          }
          stats={[
            { label: 'جمع بدهکار', value: data ? fa(data.total_debit) : '—', className: 'jb-stat--debit' },
            { label: 'جمع بستانکار', value: data ? fa(data.total_credit) : '—', className: 'jb-stat--credit' },
          ]}
        />
      </form>
    </OpsPage>
  )
}
