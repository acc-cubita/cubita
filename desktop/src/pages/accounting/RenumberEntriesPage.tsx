import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { AlertTriangle, CheckCircle2, ClipboardCheck, FileStack, Hash, Minus } from 'lucide-react'

import { fetchFiscalYears, fetchRenumberPreview, renumberEntries } from '../../api'
import { DocFooter } from '../../components/DocFooter'
import { CountBadge } from '../../components/form/FormKit'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { formatJalali } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { numberSpan, planNumbers, renumberState } from '../../lib/renumberSheet'
import { useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useCtrlS } from '../../lib/useCtrlS'
import { useDebounced } from '../../lib/useDebounced'
import { AsyncBlock, OpsPage, RangeCells, fa, faInt, sourceLabel, useAsync, useRange, type Msg } from './kit'

const LAYOUT = { fixed: ['rowhead'], auto: 'desc' } as const

/** نوار روی گرید: [ردیف + تاریخ + شرح] [منشأ + عطف] [شماره‌ی فعلی] [شماره‌ی تازه] [—]. */
const RN_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('date') + w('desc'), w('source') + w('atf'), w('old'), w('new'), 0]
}
/** جابه‌جاییِ PageUp/PageDown. */
const PAGE_STEP = 10

/**
 * «شماره‌گذاری مجدد اسناد» با تمِ اکسلی — شماره‌ی اسنادِ موقت را به‌ترتیبِ تاریخ از نو می‌دهد.
 *
 * - **سربرگ** (`jh-bar--report`): بازه و سالِ مالی؛ «شروع از شماره» و «رفتن به».
 * - **برگه** نقشه‌ی شماره‌هاست: تاریخ، شرح، منشأ، **عطف (ثابت)**، شماره‌ی فعلی و شماره‌ی تازه — شماره‌ای که عوض می‌شود
 *   پررنگ است. کلیک روی ردیف (یا Space) انتخابش می‌کند: انتخابِ دستی **جای** بازه می‌نشیند و شماره‌ی تازه‌ی هر سند را هم
 *   عوض می‌کند، پس برگه نقشه‌ی همان انتخاب را از سرور می‌گیرد (سندِ بیرونِ انتخاب «—»).
 * - **نوار:** «اعمالِ شماره‌گذاری» (Ctrl+S)، و شمارِ عوض‌شونده‌ها و بازه‌ی تازه زیرِ ستون‌هایشان. اگر شماره‌ای از نقشه را
 *   سندی بیرونِ آن دارد، پیش از زدنِ دکمه گفته می‌شود و اعمال بسته است (پیش از این فقط پیامِ خطای اجرا بود).
 *
 * سندِ دائم شماره‌ی امضاشده دارد و در نقشه نمی‌آید.
 */
export function RenumberEntriesPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('year')
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const [start, setStart] = useState('1')
  const startNumber = Math.max(1, Number(start) || 1)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const cw = useColumnWidths('cubita.grid.renumber.shares', LAYOUT)
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.rn-sheet', slots: RN_SLOTS })

  const full = useAsync(
    () => fetchRenumberPreview(token, range.from, range.to, startNumber),
    [token, range.from, range.to, startNumber],
  )
  const rows = full.data?.rows ?? []
  const order = rows.map((r) => r.id)

  // ── انتخابِ دستی و نقشه‌ی همان انتخاب ──
  const { selected, click, clear } = useRowSelection()
  const toggle = (id: string, shift = false) => click(order, id, { shift, ctrl: true })
  //: بازه‌ی دیگر یعنی سندهای دیگر؛ شناسه‌هایی که دیگر در فهرست نیستند نباید در انتخاب بمانند.
  useEffect(() => clear(), [range.from, range.to, clear])
  const pickedIds = order.filter((id) => selected.has(id))
  const idsNow = pickedIds.join(',')
  const idsKey = useDebounced(idsNow, 250)
  const subset = useAsync(
    () => (idsKey ? fetchRenumberPreview(token, undefined, undefined, startNumber, idsKey.split(',')) : Promise.resolve(null)),
    [token, startNumber, idsKey],
  )
  const manual = pickedIds.length > 0
  //: نقشه‌ای که اجرا می‌شود: انتخاب اگر هست، وگرنه کلِ بازه. نقشه‌ی انتخابِ کهنه (پیش از رسیدنِ پاسخ) نشان داده نمی‌شود.
  const plan = manual ? (idsKey === idsNow && !subset.loading ? subset.data : null) : full.data
  const numbers = planNumbers(plan)
  const state = plan ? renumberState(plan) : null
  const canApply = Boolean(plan) && state === 'ready' && !busy && !full.loading

  async function apply() {
    if (!canApply || !plan) return
    if (
      !window.confirm(
        `شماره‌ی ${faInt(plan.count)} سند${manual ? 'ِ انتخابی' : 'ِ موقتِ بازه'} به‌ترتیبِ تاریخ از ${fa(startNumber)} بازنویسی می‌شود.\nادامه می‌دهید؟`,
      )
    )
      return
    setBusy(true)
    try {
      //: انتخابِ دستی **جای** بازه می‌نشیند نه کنارش — سرور هم همین‌طور رفتار می‌کند.
      const out = await renumberEntries(token, {
        date_from: manual ? null : range.from,
        date_to: manual ? null : range.to,
        entry_ids: manual ? pickedIds : null,
        start_number: startNumber,
      })
      clear()
      setMsg({
        text: `${faInt(out.changed_count)} سند شماره‌ی تازه گرفت (${fa(out.first_number)} تا ${fa(out.last_number)}).`,
        kind: 'ok',
      })
      full.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  // ── صفحه‌کلید ──
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, rows.length - 1))
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`rn-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(rows.length - 1, i)))
  }
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const last = rows.length - 1
    if (last < 0) return
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowUp': {
        e.preventDefault()
        const to = active + (e.key === 'ArrowDown' ? 1 : -1)
        if (to < 0 || to > last) break
        moveTo(to)
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
  const span = plan ? numberSpan(startNumber, plan.count) : null
  const tone = !plan ? 'empty' : state === 'clash' ? 'err' : state === 'ready' ? 'ok' : 'empty'

  //: Ctrl+S از هر جای صفحه — سربرگِ بازه بیرونِ فرم است.
  useCtrlS(() => void apply())

  return (
    <OpsPage
      canvas
      icon={Hash}
      title="شماره‌گذاری مجدد اسناد"
      description="شماره‌ی اسناد را به‌ترتیبِ تاریخ از نو می‌دهد. فقط روی اسنادِ موقت — سندِ دائم شماره‌ی امضاشده دارد و جابه‌جا نمی‌شود."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه و شروعِ شماره‌گذاری">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            <label className="jh-field rn-start">
              <span className="jh-label">شروع از شماره</span>
              <NumberInput value={start} onChange={setStart} group={false} aria-label="شروع از شماره" />
            </label>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('entrycartable')}>
                    <ClipboardCheck size={14} aria-hidden="true" /> کارتابل اسناد موقت
                  </button>
                  <button type="button" onClick={() => onNavigate('entrylist')}>
                    <FileStack size={14} aria-hidden="true" /> اسناد حسابداری
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      }
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void apply()
        }}
      >
        <SectionCard
          icon={Hash}
          title="نقشه‌ی شماره‌ها"
          description={
            full.data
              ? `${faInt(full.data.count)} سندِ موقت${full.data.skipped_permanent ? ` · ${faInt(full.data.skipped_permanent)} سندِ دائم دست نمی‌خورد` : ''}`
              : undefined
          }
          tip="«عطف» شماره‌ی ثابتِ سند است و این‌جا فقط دیده می‌شود تا روشن باشد عوض نمی‌شود. روی ردیف‌ها کلیک کنید (Shift برای یک بازه) تا فقط همان‌ها بازشماره شوند — شماره‌ی تازه‌شان با انتخاب عوض می‌شود. بی انتخاب، همه‌ی اسنادِ موقتِ بازه."
          badge={full.data ? <CountBadge accent>{faInt(full.data.count)} سند</CountBadge> : undefined}
        >
          {state === 'clash' && plan && (
            <p className="hint acc-note acc-note--err">
              <AlertTriangle size={14} />
              شماره‌ی {fa(plan.first_clash ?? 0)} را سندی بیرونِ این نقشه دارد؛ شماره‌ی شروعِ دیگری بزنید.
            </p>
          )}
          {full.data?.truncated && (
            <p className="hint acc-note acc-note--warn">
              <AlertTriangle size={14} />
              فقط {faInt(rows.length)} ردیفِ نخست از {faInt(full.data.count)} نمایش داده می‌شود؛ اعمالِ بازه روی همه انجام می‌شود.
            </p>
          )}
          <AsyncBlock
            loading={full.loading && !full.data}
            error={full.data ? null : full.error}
            empty={(full.data?.count ?? 0) === 0}
            emptyText="در این بازه سندِ موقتی نیست."
          >
            <div
              ref={gridRef}
              tabIndex={rows.length > 0 ? 0 : -1}
              className="table-scroll ef-table-wrap lr-scroll"
              onKeyDown={onGridKey}
              aria-label="نقشه‌ی شماره‌ها — ↑↓ حرکت، Space یا Enter انتخاب، Shift+↓ افزودن، Esc لغوِ انتخاب"
            >
              <table ref={cw.frame} className={`cards-on-mobile ef-table xl-grid rn-sheet${full.loading || (manual && !plan) ? ' is-loading' : ''}`}>
                <colgroup>
                  <col className="rn-c-rowhead" style={cw.col('rowhead')} />
                  <col className="rn-c-date" style={cw.col('date')} />
                  <col style={cw.col('desc')} />
                  <col className="rn-c-src" style={cw.col('source')} />
                  <col className="rn-c-num" style={cw.col('atf')} />
                  <col className="rn-c-num" style={cw.col('old')} />
                  <col className="rn-c-num" style={cw.col('new')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="انتخاب" />
                    {head('date', 'تاریخ', 'desc')}
                    {head('desc', 'شرح', 'source')}
                    {head('source', 'منشأ', 'atf')}
                    {head('atf', 'عطف (ثابت)', 'old', 'num')}
                    {head('old', 'شماره‌ی فعلی', 'new', 'num')}
                    {head('new', 'شماره‌ی تازه', undefined, 'num')}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const on = selected.has(r.id)
                    const next = numbers.get(r.id)
                    const changed = next != null && next !== r.old_number
                    return (
                      <tr
                        key={r.id}
                        id={`rn-row-${i}`}
                        aria-selected={on}
                        className={`acc-row--clickable${on ? ' is-selected' : ''}${i === active ? ' is-active' : ''}${manual && !on ? ' rn-out' : ''}`}
                        onClick={(ev) => {
                          setActiveRow(i)
                          toggle(r.id, ev.shiftKey)
                        }}
                      >
                        <td className="xl-rowhead card-hide">
                          <button type="button" tabIndex={-1} className="xl-rowhead-btn" aria-pressed={on} aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}>
                            {faInt(i + 1)}
                          </button>
                        </td>
                        <td className="card-title">{formatJalali(r.entry_date)}</td>
                        <td className="card-wide" data-label="شرح" title={r.description || undefined}>
                          {r.description || sourceLabel(r.source_type)}
                        </td>
                        <td data-label="منشأ">{sourceLabel(r.source_type)}</td>
                        <td className="num rn-fixed" data-label="عطف (ثابت)">
                          {r.atf_number == null ? '—' : fa(r.atf_number)}
                        </td>
                        <td className="num" data-label="شماره‌ی فعلی">
                          {r.old_number == null ? '—' : fa(r.old_number)}
                        </td>
                        <td className={`num${changed ? ' rn-changed' : ' rn-same'}`} data-label="شماره‌ی تازه">
                          {next == null ? (manual && on ? '…' : '—') : fa(next)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {manual && (
              <SelectionBar count={pickedIds.length} unit="سند" onClear={clear}>
                <span>فقط همین‌ها بازشماره می‌شوند</span>
              </SelectionBar>
            )}
          </AsyncBlock>
        </SectionCard>

        <DocFooter
          tone={tone}
          columns
          submitting={busy}
          submittingLabel="در حال شماره‌گذاری…"
          submitLabel={manual ? `بازشماره‌ی ${faInt(pickedIds.length)} سند` : 'اعمالِ شماره‌گذاری'}
          submitDisabled={!canApply}
          shortcut
          message={msg}
          groupLabel="نقشه‌ی شماره‌گذاری"
          statusLabel="وضعیت"
          statusKey={`${state ?? 'x'}-${plan?.changed_count ?? ''}-${manual}`}
          status={
            !plan ? (
              'در حال محاسبه…'
            ) : state === 'clash' ? (
              <>
                <AlertTriangle aria-hidden="true" /> شماره‌ی {fa(plan.first_clash ?? 0)} تکراری
              </>
            ) : state === 'ready' ? (
              <>
                <CheckCircle2 aria-hidden="true" /> آماده
              </>
            ) : state === 'same' ? (
              <>
                <Minus aria-hidden="true" /> شماره‌ها درست‌اند
              </>
            ) : (
              'سندِ موقتی نیست'
            )
          }
          sub={
            plan && state === 'clash'
              ? { main: 'شروعِ دیگری بزنید' }
              : plan && state === 'ready'
                ? { main: manual ? `فقط ${faInt(plan.count)} سندِ انتخابی` : `همه‌ی ${faInt(plan.count)} سندِ موقتِ بازه` }
                : undefined
          }
          stats={[
            { label: 'عوض می‌شود', value: plan ? `${faInt(plan.changed_count)} سند` : '—', className: 'jb-stat--a' },
            { label: 'شماره‌های تازه', value: span ? `${fa(span[0])} — ${fa(span[1])}` : '—', className: 'jb-stat--b' },
          ]}
        />
      </form>
    </OpsPage>
  )
}
