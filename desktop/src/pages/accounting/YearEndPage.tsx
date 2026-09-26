import { useEffect, useId, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { AlertTriangle, Archive, CalendarCheck, CheckCircle2, DoorOpen, Lock, Scale } from 'lucide-react'

import {
  fetchClosingPreview,
  fetchJournalEntriesPage,
  fetchOpeningPreview,
  issueClosingEntry,
  issueOpeningEntry,
  type BalancingLine,
  type ClosingRow,
} from '../../api'
import { DocFooter } from '../../components/DocFooter'
import { CountBadge } from '../../components/form/FormKit'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { formatJalali, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { dimsText } from '../../lib/pnlClose'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { TYPE_LABELS, closingOptions, closingRowKey, closingState, nextDay, openingState } from '../../lib/yearEnd'
import { AsyncBlock, OpsPage, fa, faAmount, faInt, useAsync, type Msg } from './kit'

type Kind = 'closing' | 'opening'

const LAYOUT = { fixed: ['rowhead'], auto: 'account' } as const

/** سربرگ و نوار روی گرید: [ردیف + حساب] [نوع + شرح ردیف] [بدهکار] [بستانکار] [—]. */
const YE_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('account'), w('type') + w('desc'), w('debit'), w('credit'), 0]
}

/**
 * «صدور سند اختتامیه و افتتاحیه» — هم‌سبکِ «سند حسابداری» (الگوی «ج»: پیش‌نمایشِ سندِ خودکار).
 *
 * دو سند با یک برگه: **اختتامیه** همه‌ی حساب‌های دائمی را برعکسِ مانده‌شان می‌زند تا صفر شوند، و **افتتاحیه** در سالِ
 * بعد دقیقاً وارونه‌ی همان اختتامیه است. گرید خودِ سند است — ردیف‌ها با شرحشان و خطِ توازن («حساب اختتامیه» /
 * «حساب افتتاحیه») ته آن، همه از سرور — و نوارِ پایین وضعیت و جمعِ بدهکار و بستانکار را زیرِ ستون‌هایشان می‌گوید.
 *
 * - اختتامیه تا سود و زیان باز است بسته می‌ماند (سرور هم رد می‌کند) و راهِ «بستن حساب‌های سود و زیان» همان‌جاست.
 * - افتتاحیه مبنایش را از **فهرستِ اختتامیه‌ها** می‌گیرد، نه از حدسِ تاریخ؛ و اگر از همان اختتامیه قبلاً افتتاحیه صادر
 *   شده، پیش از صدور گفته می‌شود — صدورِ دوباره هر مانده را دو برابر می‌کرد.
 */
export function ClosingOpeningPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const [kind, setKind] = useState<Kind>('closing')
  const switcher = (
    <div className="cc-presets ye-kind" role="group" aria-label="نوعِ سند">
      <button type="button" className={kind === 'closing' ? 'is-active' : ''} aria-pressed={kind === 'closing'} onClick={() => setKind('closing')}>
        <Lock size={13} aria-hidden="true" /> اختتامیه
      </button>
      <button type="button" className={kind === 'opening' ? 'is-active' : ''} aria-pressed={kind === 'opening'} onClick={() => setKind('opening')}>
        <DoorOpen size={13} aria-hidden="true" /> افتتاحیه
      </button>
    </div>
  )
  return (
    <OpsPage
      canvas
      icon={Archive}
      title="صدور سند اختتامیه و افتتاحیه"
      description="پایانِ سال: اختتامیه همه‌ی حساب‌های دائمی را می‌بندد و افتتاحیه در سالِ بعد دقیقاً همان‌ها را باز می‌کند. اول باید سود و زیان بسته شده باشد."
    >
      {kind === 'closing' ? (
        <ClosingSheet token={token} switcher={switcher} onNavigate={onNavigate} />
      ) : (
        <OpeningSheet token={token} switcher={switcher} onSwitch={() => setKind('closing')} />
      )}
    </OpsPage>
  )
}

// ═════════════ اختتامیه ═════════════

function ClosingSheet({ token, switcher, onNavigate }: { token: string; switcher: ReactNode; onNavigate?: (page: PageKey) => void }) {
  const [asOf, setAsOf] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const preview = useAsync(() => fetchClosingPreview(token, asOf), [token, asOf])
  const formRef = useRef<HTMLFormElement>(null)
  const uid = useId()
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.ye-sheet', slots: YE_SLOTS })

  const data = preview.data
  const state = data ? closingState(data) : 'none'
  const canIssue = Boolean(data) && !preview.loading && state === 'ready'

  async function issue() {
    if (!canIssue || busy) return
    if (!window.confirm(`سندِ اختتامیه با تاریخ ${formatJalali(asOf)} صادر شود؟ همه‌ی حساب‌های دائمی بسته می‌شوند.`)) return
    setBusy(true)
    try {
      const out = await issueClosingEntry(token, asOf, description)
      setMsg({ text: `سندِ اختتامیه با شماره ${fa(out.number ?? 0)} و ${faInt(out.line_count)} ردیف صادر شد.`, kind: 'ok' })
      setDescription('')
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <IssueForm formRef={formRef} onIssue={issue}>
      <SectionCard
        icon={Lock}
        title="سندِ اختتامیه"
        tip="هر حسابِ دائمی (دارایی، بدهی، سرمایه — به تفکیکِ تفصیلی و مرکز هزینه) برعکسِ مانده‌اش زده می‌شود تا صفر شود؛ طرفِ مقابل «حساب اختتامیه» است. روی شماره‌ی ردیف‌ها کلیک کنید تا جمعِ همان‌ها را ببینید."
        badge={data ? <CountBadge>{faInt(data.rows.length)} حساب</CountBadge> : undefined}
        actions={<div className="jg-head-actions">{switcher}</div>}
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
                placeholder={`سند اختتامیه ${formatJalali(asOf)}`}
              />
            </div>
            <div className="jh-field jh-field--rest">
              <label className="jh-label" htmlFor={`${uid}-date`}>
                تاریخِ اختتامیه <span className="jh-req" aria-hidden="true">*</span>
              </label>
              <JalaliDatePicker id={`${uid}-date`} value={asOf} onChange={setAsOf} />
            </div>
          </div>
        </div>

        {state === 'pnl-open' && data && (
          <p className="hint acc-note acc-note--err">
            <AlertTriangle size={14} />
            حساب‌های سود و زیان تا این تاریخ هنوز باز‌اند (گردشِ {fa(data.open_pnl_total)}). اول سود و زیان را ببندید.
            {onNavigate && (
              <button type="button" className="link-btn" onClick={() => onNavigate('closepnl')}>
                <CalendarCheck size={13} aria-hidden="true" /> بستن حساب‌های سود و زیان
              </button>
            )}
          </p>
        )}
        {data && data.temporary_count > 0 && (
          <p className="hint acc-note acc-note--warn">
            <AlertTriangle size={14} />
            {faInt(data.temporary_count)} سندِ موقت تا این تاریخ هست؛ بهتر است اول بازبینی و دائمشان کنید.
          </p>
        )}

        <AsyncBlock
          loading={preview.loading && !data}
          error={data ? null : preview.error}
          empty={(data?.rows.length ?? 0) === 0}
          emptyText="هیچ حسابِ دائمیِ دارای مانده‌ای برای بستن نیست."
        >
          {data && <EntryGrid rows={data.rows} balancing={data} loading={preview.loading} storageKey="cubita.grid.closing.shares" />}
        </AsyncBlock>
      </SectionCard>

      <DocFooter
        tone={state === 'pnl-open' ? 'err' : state === 'ready' ? 'ok' : 'empty'}
        columns
        submitting={busy}
        submittingLabel="در حال صدور…"
        submitLabel="صدور سند اختتامیه"
        submitDisabled={!canIssue}
        shortcut
        message={msg}
        groupLabel="جمعِ سندِ اختتامیه"
        statusLabel="وضعیتِ سند"
        statusKey={`${state}-${data?.total_debit ?? ''}`}
        status={
          !data ? (
            'در حال محاسبه…'
          ) : state === 'pnl-open' ? (
            <>
              <AlertTriangle aria-hidden="true" /> سود و زیان باز است
            </>
          ) : state === 'ready' ? (
            <>
              <CheckCircle2 aria-hidden="true" /> متوازن
            </>
          ) : (
            'حسابی برای بستن نیست'
          )
        }
        sub={
          data && state === 'pnl-open'
            ? { main: `گردشِ باز ${fa(data.open_pnl_total)}` }
            : data && state === 'ready'
              ? { main: `${faInt(data.rows.length)} حساب بسته می‌شود` }
              : undefined
        }
        stats={[
          { label: 'جمع بدهکار', value: data ? fa(data.total_debit) : '—', className: 'jb-stat--debit' },
          { label: 'جمع بستانکار', value: data ? fa(data.total_credit) : '—', className: 'jb-stat--credit' },
        ]}
      />
    </IssueForm>
  )
}

// ═════════════ افتتاحیه ═════════════

function OpeningSheet({ token, switcher, onSwitch }: { token: string; switcher: ReactNode; onSwitch: () => void }) {
  //: اختتامیه‌های مبنا از فهرستِ اسناد (منشأ «اختتامیه»)؛ تاریخ حدس زده نمی‌شود.
  const closings = useAsync(
    () =>
      fetchJournalEntriesPage(token, { sourceType: 'closing_entry' }, { limit: 50 })
        .then((p) => closingOptions(p.items))
        .catch(() => []),
    [token],
  )
  const options = useMemo(() => closings.data ?? [], [closings.data])
  const [baseId, setBaseId] = useState('')
  const base = options.find((o) => o.id === baseId) ?? options[0] ?? null
  const [asOf, setAsOf] = useState<string | null>(null)
  //: مبنای تازه یعنی تاریخِ افتتاحیه‌ی تازه — پیش‌فرض روزِ بعد از همان اختتامیه؛ کاربر عوضش می‌کند.
  useEffect(() => setAsOf(null), [base?.id])
  const openingDate = asOf ?? (base ? nextDay(base.date) : todayIso())

  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const preview = useAsync(
    () => (base ? fetchOpeningPreview(token, openingDate, base.date) : Promise.resolve(null)),
    [token, base?.date, openingDate],
  )
  const formRef = useRef<HTMLFormElement>(null)
  const uid = useId()
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.ye-sheet', slots: YE_SLOTS })

  const data = preview.data
  const state = data ? openingState(data) : null
  const canIssue = Boolean(data) && !preview.loading && state === 'ready'

  async function issue() {
    if (!canIssue || busy || !base) return
    if (!window.confirm(`سندِ افتتاحیه با تاریخ ${formatJalali(openingDate)} از روی اختتامیه‌ی شماره ${fa(base.number ?? 0)} صادر شود؟`)) return
    setBusy(true)
    try {
      const out = await issueOpeningEntry(token, openingDate, base.date, description)
      setMsg({ text: `سندِ افتتاحیه با شماره ${fa(out.number ?? 0)} و ${faInt(out.line_count)} ردیف صادر شد.`, kind: 'ok' })
      setDescription('')
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const tone = !data ? 'empty' : state === 'ready' ? 'ok' : state === 'repeat' ? 'warn' : state === 'order' ? 'err' : 'empty'

  return (
    <IssueForm formRef={formRef} onIssue={issue}>
      <SectionCard
        icon={DoorOpen}
        title="سندِ افتتاحیه"
        tip="دقیقاً وارونه‌ی سندِ اختتامیه‌ی مبنا — پس سالِ جدید با همان مانده‌ای باز می‌شود که سالِ قبل با آن بسته شد، با همان تفکیکِ تفصیلی و مرکز هزینه؛ طرفِ مقابل «حساب افتتاحیه» است."
        badge={data ? <CountBadge>{faInt(data.rows.length)} حساب</CountBadge> : undefined}
        actions={<div className="jg-head-actions">{switcher}</div>}
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
                placeholder={`سند افتتاحیه ${formatJalali(openingDate)}`}
              />
            </div>
            <div className="jh-field jh-field--rest">
              <label className="jh-label" htmlFor={`${uid}-date`}>
                تاریخِ افتتاحیه <span className="jh-req" aria-hidden="true">*</span>
              </label>
              <JalaliDatePicker id={`${uid}-date`} value={openingDate} onChange={setAsOf} />
            </div>
          </div>
          <div className="jh-row jh-row--sub">
            <div className="jh-field">
              <label className="jh-label" htmlFor={`${uid}-base`}>
                اختتامیه‌ی مبنا <span className="jh-req" aria-hidden="true">*</span>
              </label>
              <SearchSelect id={`${uid}-base`} aria-label="اختتامیه‌ی مبنا" value={base?.id ?? ''} onChange={(e) => setBaseId(e.target.value)}>
                {options.length === 0 && <option value="">— هنوز سندِ اختتامیه‌ای صادر نشده —</option>}
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    سند {o.number != null ? fa(o.number) : '—'} — {formatJalali(o.date)}
                  </option>
                ))}
              </SearchSelect>
            </div>
          </div>
        </div>

        {state === 'repeat' && data && (
          <p className="hint acc-note acc-note--warn">
            <AlertTriangle size={14} />
            از روی این اختتامیه قبلاً افتتاحیه‌ی شماره {fa(data.existing_opening_number ?? 0)} صادر شده. صدورِ دوباره هر مانده را دو برابر
            می‌کرد؛ اگر لازم است، اول همان سند را باطل کنید.
          </p>
        )}
        {state === 'order' && (
          <p className="hint acc-note acc-note--err">
            <AlertTriangle size={14} /> تاریخِ افتتاحیه باید بعد از تاریخِ اختتامیه‌ی مبنا ({base ? formatJalali(base.date) : '—'}) باشد.
          </p>
        )}

        {closings.data && options.length === 0 ? (
          <p className="hint acc-note">
            <DoorOpen size={14} /> افتتاحیه وارونه‌ی یک سندِ اختتامیه است و هنوز اختتامیه‌ای صادر نشده.
            <button type="button" className="link-btn" onClick={onSwitch}>
              <Lock size={13} aria-hidden="true" /> صدورِ اختتامیه
            </button>
          </p>
        ) : (
          <AsyncBlock
            loading={(preview.loading || closings.loading) && !data}
            error={data ? null : preview.error}
            empty={(data?.rows.length ?? 0) === 0}
            emptyText="اختتامیه‌ی مبنا ردیفی ندارد."
          >
            {data && <EntryGrid rows={data.rows} balancing={data} loading={preview.loading} storageKey="cubita.grid.opening.shares" />}
          </AsyncBlock>
        )}
      </SectionCard>

      <DocFooter
        tone={tone}
        columns
        submitting={busy}
        submittingLabel="در حال صدور…"
        submitLabel="صدور سند افتتاحیه"
        submitDisabled={!canIssue}
        shortcut
        message={msg}
        groupLabel="جمعِ سندِ افتتاحیه"
        statusLabel="وضعیتِ سند"
        statusKey={`${state ?? 'x'}-${data?.total_debit ?? ''}`}
        status={
          !base ? (
            'مبنایی نیست'
          ) : !data ? (
            'در حال محاسبه…'
          ) : state === 'ready' ? (
            <>
              <CheckCircle2 aria-hidden="true" /> متوازن
            </>
          ) : state === 'repeat' ? (
            <>
              <AlertTriangle aria-hidden="true" /> قبلاً صادر شده
            </>
          ) : state === 'order' ? (
            <>
              <AlertTriangle aria-hidden="true" /> تاریخِ نادرست
            </>
          ) : (
            'ردیفی نیست'
          )
        }
        sub={
          data && state === 'ready'
            ? { main: `${faInt(data.rows.length)} حساب باز می‌شود`, side: `از اختتامیه‌ی ${fa(data.closing_entry_number ?? 0)}` }
            : data && state === 'repeat'
              ? { main: `سند شماره ${fa(data.existing_opening_number ?? 0)}` }
              : undefined
        }
        stats={[
          { label: 'جمع بدهکار', value: data ? fa(data.total_debit) : '—', className: 'jb-stat--debit' },
          { label: 'جمع بستانکار', value: data ? fa(data.total_credit) : '—', className: 'jb-stat--credit' },
        ]}
      />
    </IssueForm>
  )
}

// ═════════════ مشترک ═════════════

/** فرمِ سند: Enter و Ctrl+S همان «صدور» است — مثلِ سند حسابداری، با همان تأیید. */
function IssueForm({
  formRef,
  onIssue,
  children,
}: {
  formRef: RefObject<HTMLFormElement | null>
  onIssue: () => void | Promise<void>
  children: ReactNode
}) {
  return (
    <form
      ref={formRef}
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        void onIssue()
      }}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
          e.preventDefault()
          void onIssue()
        }
      }}
    >
      {children}
    </form>
  )
}

/** گریدِ فقط‌خواندنیِ سند: ردیف‌ها با شرحِ سرور و خطِ توازن ته آن؛ شماره‌ی ردیف انتخاب می‌کند و جمعِ انتخاب پایین می‌آید. */
function EntryGrid({
  rows,
  balancing,
  loading,
  storageKey,
}: {
  rows: ClosingRow[]
  balancing: BalancingLine
  loading: boolean
  storageKey: string
}) {
  const cw = useColumnWidths(storageKey, LAYOUT)
  const { selected, click, clear } = useRowSelection()
  const order = rows.map(closingRowKey)
  const picked = rows.filter((r) => selected.has(closingRowKey(r)))
  const hasBalance = Number(balancing.balance_debit) !== 0 || Number(balancing.balance_credit) !== 0
  const head = (id: string, label: string, next?: string, cls?: string) => (
    <th data-col={id} className={cls}>
      {label}
      {next && cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  return (
    <>
      <div className="table-scroll ef-table-wrap">
        <table ref={cw.frame} className={`cards-on-mobile acc-table ef-table xl-grid ye-sheet${loading ? ' is-loading' : ''}`}>
          <colgroup>
            <col className="ye-c-rowhead" style={cw.col('rowhead')} />
            <col style={cw.col('account')} />
            <col className="ye-c-type" style={cw.col('type')} />
            <col className="ye-c-desc" style={cw.col('desc')} />
            <col className="ye-c-money" style={cw.col('debit')} />
            <col className="ye-c-money" style={cw.col('credit')} />
          </colgroup>
          <thead>
            <tr>
              <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="انتخاب" />
              {head('account', 'حساب', 'type')}
              {head('type', 'نوع', 'desc')}
              {head('desc', 'شرح ردیف', 'debit')}
              {head('debit', 'بدهکار', 'credit', 'num')}
              {head('credit', 'بستانکار', undefined, 'num')}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const key = closingRowKey(r)
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
                  <td data-label="نوع">{TYPE_LABELS[r.account_type] ?? r.account_type}</td>
                  <td data-label="شرح ردیف" className="ye-desc">
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
            {hasBalance && (
              //: خطِ توازن هم یک ردیفِ سند است — حساب و شرح از سرور، مبلغ خالصِ ردیف‌ها.
              <tr className="ye-bal">
                <td className="xl-rowhead card-hide" aria-hidden="true">
                  <Scale size={13} />
                </td>
                <td className="card-title">
                  <span dir="ltr">{balancing.balance_account_code}</span> — {balancing.balance_account_name}
                </td>
                <td data-label="نوع">{TYPE_LABELS.equity}</td>
                <td data-label="شرح ردیف" className="ye-desc">
                  {balancing.balance_description}
                </td>
                <td data-label="بدهکار" className="num">
                  {faAmount(balancing.balance_debit)}
                </td>
                <td data-label="بستانکار" className="num">
                  {faAmount(balancing.balance_credit)}
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
    </>
  )
}
