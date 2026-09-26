import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { AlertTriangle, CheckCircle2, ClipboardCheck, Combine, FileStack } from 'lucide-react'

import { fetchChartAccounts, fetchFiscalYears, fetchJournalEntriesFiltered, mergeEntries } from '../../api'
import { DocFooter } from '../../components/DocFooter'
import { CountBadge } from '../../components/form/FormKit'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { formatJalali } from '../../lib/jalali'
import {
  defaultMergeDescription,
  entryTotal,
  mergeRows,
  mergedLines,
  mergedTotals,
  pickedDate,
} from '../../lib/mergeSheet'
import type { PageKey } from '../../lib/navModel'
import { useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useCtrlS } from '../../lib/useCtrlS'
import { AsyncBlock, OpsPage, RangeCells, fa, faAmount, faInt, useAsync, useRange, type Msg } from './kit'

/** سقفِ اسنادِ هر درخواست (`MAX_LIMIT`ِ سرور). */
const LIST_LIMIT = 200
const LAYOUT = { fixed: ['rowhead'], auto: 'account' } as const

/** سربرگ و نوار روی سندِ ادغامی: [ردیف + سندِ اصلی + حساب] [شرح ردیف] [بدهکار] [بستانکار] [—]. */
const MG_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('src') + w('account'), w('desc'), w('debit'), w('credit'), 0]
}

/**
 * «ادغام اسناد» با تمِ اکسلی — چند سندِ موقتِ دستیِ هم‌تاریخ در یک سند؛ مانده‌ی هیچ حسابی تکان نمی‌خورد.
 *
 * - **سربرگ** (`jh-bar--report`): بازه و سالِ مالی، و «رفتن به».
 * - **برگه‌ی اسناد:** فقط روزهایی که بیش از یک سندِ موقتِ دستی دارند، هر روز یک سرگروه و سندهایش زیرش. کلیک روی سند
 *   انتخابش می‌کند و کلیک روی سرگروه همه‌ی سندهای آن روز را؛ سندِ روزِ دیگر تا انتخاب پاک نشود قفل است (ادغامِ دو تاریخ
 *   یعنی جابه‌جاکردنِ رویداد در زمان، و سرور ردش می‌کند).
 * - **سندِ ادغامی:** پیش‌نمایشِ دقیقِ سندی که ساخته می‌شود — سرور ردیف‌ها را به‌ترتیبِ شماره‌ی سند پشتِ هم می‌گذارد و چیزی
 *   جمع یا حذف نمی‌کند — با سربرگِ «شرح / تاریخ» و نوارِ سندِ ستون‌به‌ستون: «ادغامِ n سند» (Ctrl+S) و جمعِ بدهکار و بستانکار.
 */
export function MergeEntriesPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('month')
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const list = useAsync(
    () =>
      fetchJournalEntriesFiltered(token, {
        dateFrom: range.from,
        dateTo: range.to,
        status: 'temporary',
        sourceType: 'manual',
        limit: LIST_LIMIT,
      }),
    [token, range.from, range.to],
  )
  const entries = useMemo(() => (list.data ?? []).filter((e) => !e.voided_at), [list.data])
  const rows = useMemo(() => mergeRows(entries), [entries])
  const names = useMemo(() => new Map((accounts.data ?? []).map((a) => [a.id, `${a.code} — ${a.name}`])), [accounts.data])

  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const uid = useId()
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const cw = useColumnWidths('cubita.grid.merge.shares', LAYOUT)
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.mg-doc', slots: MG_SLOTS })

  // ── انتخاب: فقط سندهای یک روز ──
  const order = rows.flatMap((r) => (r.kind === 'entry' ? [r.entry.id] : []))
  const { selected, click, clear } = useRowSelection()
  useEffect(() => clear(), [range.from, range.to, clear])
  const day = pickedDate(entries, selected)
  const toggle = (id: string) => click(order, id, { shift: false, ctrl: true })
  function toggleDay(date: string) {
    const ids = entries.filter((e) => e.entry_date === date).map((e) => e.id)
    const allOn = ids.every((id) => selected.has(id))
    if (day && day !== date) clear()
    ids.forEach((id) => (allOn ? selected.has(id) : !selected.has(id)) && toggle(id))
  }

  const lines = mergedLines(entries, selected)
  const totals = mergedTotals(lines)
  const pickedCount = entries.filter((e) => selected.has(e.id)).length
  const balanced = Math.abs(totals.debit - totals.credit) < 0.5
  const canMerge = pickedCount >= 2 && balanced && !busy

  async function merge() {
    if (!canMerge) return
    if (!window.confirm(`${faInt(pickedCount)} سندِ ${day ? formatJalali(day) : ''} در یک سند ادغام می‌شوند و اصل‌ها حذف خواهند شد. ادامه؟`)) return
    setBusy(true)
    try {
      const ids = entries.filter((e) => selected.has(e.id)).map((e) => e.id)
      const out = await mergeEntries(token, ids, description)
      setMsg({ text: `سندِ ادغامی با شماره ${fa(out.number ?? 0)} و ${faInt(out.line_count)} ردیف ساخته شد.`, kind: 'ok' })
      clear()
      setDescription('')
      list.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  // ── صفحه‌کلیدِ برگه‌ی اسناد ──
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, rows.length - 1))
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const last = rows.length - 1
    if (last < 0) return
    const act = (i: number) => {
      const r = rows[i]
      if (r.kind === 'day') toggleDay(r.date)
      else if (!day || day === r.entry.entry_date) toggle(r.entry.id)
    }
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowUp': {
        e.preventDefault()
        const to = Math.max(0, Math.min(last, active + (e.key === 'ArrowDown' ? 1 : -1)))
        setActiveRow(to)
        document.getElementById(`mg-row-${to}`)?.scrollIntoView?.({ block: 'nearest' })
        break
      }
      case ' ':
      case 'Enter':
        e.preventDefault()
        act(active)
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
  const tone = pickedCount < 2 ? 'empty' : balanced ? 'ok' : 'err'
  const dayCount = rows.filter((r) => r.kind === 'day').length

  //: Ctrl+S از هر جای صفحه — سربرگِ بازه بیرونِ فرم است.
  useCtrlS(() => void merge())

  return (
    <OpsPage
      canvas
      icon={Combine}
      title="ادغام اسناد"
      description="چند سندِ موقتِ دستیِ هم‌تاریخ را در یک سند جمع می‌کند. مانده‌ی هیچ حسابی تکان نمی‌خورد — فقط تعدادِ اسناد کم می‌شود."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه‌ی ادغامِ اسناد">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          {onNavigate && (
            <div className="jh-row jh-row--sub rh-row--tools">
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
            </div>
          )}
        </div>
      }
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void merge()
        }}
      >
        <SectionCard
          icon={FileStack}
          title="اسنادِ موقتِ دستی"
          description={
            list.data
              ? `${faInt(dayCount)} روز با بیش از یک سند${day ? ` · انتخاب از ${formatJalali(day)}` : ''}`
              : undefined
          }
          tip="فقط روزهایی که بیش از یک سندِ موقتِ دستی دارند می‌آیند؛ ادغام بینِ دو تاریخ معنا ندارد. روی سند کلیک کنید تا انتخاب شود، یا روی سرگروهِ روز تا همه‌ی سندهای آن روز. سندِ روزِ دیگر تا انتخاب پاک نشود قفل است."
          badge={list.data ? <CountBadge accent>{faInt(order.length)} سند</CountBadge> : undefined}
        >
          {(list.data?.length ?? 0) >= LIST_LIMIT && (
            <p className="hint acc-note acc-note--warn">
              <AlertTriangle size={14} /> {faInt(LIST_LIMIT)} سندِ نخستِ بازه آمده؛ برای دیدنِ بقیه بازه را کوتاه‌تر کنید.
            </p>
          )}
          <AsyncBlock
            loading={list.loading && !list.data}
            error={list.data ? null : list.error}
            empty={rows.length === 0}
            emptyText="هیچ روزی در این بازه بیش از یک سندِ موقتِ دستی ندارد."
          >
            <div
              ref={gridRef}
              tabIndex={rows.length > 0 ? 0 : -1}
              className="table-scroll ef-table-wrap lr-scroll mg-scroll"
              onKeyDown={onGridKey}
              aria-label="اسنادِ قابلِ ادغام — ↑↓ حرکت، Space یا Enter انتخاب، Esc لغوِ انتخاب"
            >
              <table className="cards-on-mobile ef-table xl-grid mg-list">
                <colgroup>
                  <col className="mg-c-rowhead" />
                  <col className="mg-c-num" />
                  <col />
                  <col className="mg-c-acc" />
                  <col className="mg-c-lines" />
                  <col className="mg-c-amt" />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" aria-label="انتخاب" />
                    <th>سند</th>
                    <th>شرح</th>
                    <th>حساب‌ها</th>
                    <th className="num">ردیف</th>
                    <th className="num">مبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    if (r.kind === 'day') {
                      const on = entries.filter((e) => e.entry_date === r.date).every((e) => selected.has(e.id))
                      return (
                        <tr
                          key={r.date}
                          id={`mg-row-${i}`}
                          className={`mg-day acc-row--clickable${i === active ? ' is-active' : ''}${day && day !== r.date ? ' is-blocked' : ''}`}
                          title={on ? 'لغوِ انتخابِ این روز' : 'انتخابِ همه‌ی سندهای این روز'}
                          onClick={() => {
                            setActiveRow(i)
                            toggleDay(r.date)
                          }}
                        >
                          <td className="card-full" colSpan={6}>
                            <b>{formatJalali(r.date)}</b> <span className="mg-day-count">{faInt(r.count)} سند</span>
                          </td>
                        </tr>
                      )
                    }
                    const e = r.entry
                    const on = selected.has(e.id)
                    const blocked = day !== null && day !== e.entry_date
                    const accs = [...new Set(e.lines.map((l) => names.get(l.account_id) ?? ''))].filter(Boolean)
                    return (
                      <tr
                        key={e.id}
                        id={`mg-row-${i}`}
                        aria-selected={on}
                        aria-disabled={blocked || undefined}
                        title={blocked ? 'برای روزِ دیگر اول انتخاب را پاک کنید' : undefined}
                        className={`acc-row--clickable${on ? ' is-selected' : ''}${blocked ? ' is-blocked' : ''}${i === active ? ' is-active' : ''}`}
                        onClick={() => {
                          setActiveRow(i)
                          if (!blocked) toggle(e.id)
                        }}
                      >
                        <td className="xl-rowhead card-hide">
                          <button type="button" tabIndex={-1} className="xl-rowhead-btn" aria-pressed={on} disabled={blocked} aria-label={`انتخابِ سندِ ${fa(e.number ?? 0)}`}>
                            {on ? <CheckCircle2 size={13} aria-hidden="true" /> : ''}
                          </button>
                        </td>
                        <td className="card-title">سند {e.number != null ? fa(e.number) : '—'}</td>
                        <td className="card-wide" data-label="شرح" title={e.description || undefined}>
                          {e.description || '—'}
                        </td>
                        <td data-label="حساب‌ها" title={accs.join('، ')}>
                          {accs.slice(0, 3).join('، ')}
                          {accs.length > 3 ? ' …' : ''}
                        </td>
                        <td className="num" data-label="ردیف">
                          {faInt(e.lines.length)}
                        </td>
                        <td className="num" data-label="مبلغ">
                          {faAmount(entryTotal(e))}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {pickedCount > 0 && (
              <SelectionBar count={pickedCount} unit="سند" onClear={clear}>
                <span>
                  ردیف‌ها <b className="num">{faInt(lines.length)}</b>
                </span>
                <span>
                  جمع <b className="num">{faAmount(totals.debit)}</b>
                </span>
              </SelectionBar>
            )}
          </AsyncBlock>
        </SectionCard>

        <SectionCard
          icon={Combine}
          title="سندِ ادغامی"
          tip="پیش‌نمایشِ دقیقِ سندی که ساخته می‌شود: ردیف‌های اسنادِ انتخابی به‌ترتیبِ شماره‌شان پشتِ هم، بی جمع‌زدن یا حذف. اصل‌ها بعد از ادغام حذف می‌شوند (سندِ موقت هنوز قطعی نشده)."
          badge={pickedCount ? <CountBadge>{faInt(lines.length)} ردیف</CountBadge> : undefined}
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
                  placeholder={defaultMergeDescription(entries, selected)}
                />
              </div>
              <div className="jh-field jh-field--rest">
                <span className="jh-label">تاریخ</span>
                {/* تاریخ انتخابی نیست: تاریخِ همان اسناد است. */}
                <span className="jh-static">{day ? formatJalali(day) : '—'}</span>
              </div>
            </div>
          </div>
          {pickedCount === 0 ? (
            <p className="hint mg-empty">دو یا چند سندِ هم‌تاریخ را از برگه‌ی بالا انتخاب کنید تا سندِ ادغامی این‌جا ساخته شود.</p>
          ) : (
            <div className="table-scroll ef-table-wrap">
              <table ref={cw.frame} className="cards-on-mobile acc-table ef-table xl-grid mg-doc">
                <colgroup>
                  <col className="mg-c-rowhead" style={cw.col('rowhead')} />
                  <col className="mg-c-src" style={cw.col('src')} />
                  <col style={cw.col('account')} />
                  <col className="mg-c-desc" style={cw.col('desc')} />
                  <col className="mg-c-money" style={cw.col('debit')} />
                  <col className="mg-c-money" style={cw.col('credit')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" data-col="rowhead" aria-label="ردیف" />
                    {head('src', 'از سند', 'account')}
                    {head('account', 'حساب', 'desc')}
                    {head('desc', 'شرح ردیف', 'debit')}
                    {head('debit', 'بدهکار', 'credit', 'num')}
                    {head('credit', 'بستانکار', undefined, 'num')}
                  </tr>
                </thead>
                <tbody>
                  {lines.map(({ entryNumber, line }, i) => (
                    <tr key={`${line.id}`} className={i > 0 && lines[i - 1].entryNumber !== entryNumber ? 'mg-next' : undefined}>
                      <td className="xl-rowhead card-hide">{faInt(i + 1)}</td>
                      <td data-label="از سند">{entryNumber != null ? fa(entryNumber) : '—'}</td>
                      <td className="card-title" title={names.get(line.account_id)}>
                        {names.get(line.account_id) ?? '—'}
                      </td>
                      <td data-label="شرح ردیف" className="mg-desc">
                        {line.description || '—'}
                      </td>
                      <td data-label="بدهکار" className="num">
                        {faAmount(line.debit)}
                      </td>
                      <td data-label="بستانکار" className="num">
                        {faAmount(line.credit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <DocFooter
          tone={tone}
          columns
          submitting={busy}
          submittingLabel="در حال ادغام…"
          submitLabel={pickedCount > 1 ? `ادغامِ ${faInt(pickedCount)} سند` : 'ادغامِ اسناد'}
          submitDisabled={!canMerge}
          shortcut
          message={msg}
          groupLabel="جمعِ سندِ ادغامی"
          statusLabel="وضعیتِ سند"
          statusKey={`${tone}-${pickedCount}`}
          status={
            pickedCount < 2 ? (
              pickedCount === 1 ? 'یک سندِ دیگر انتخاب کنید' : 'سندی انتخاب نشده'
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
          sub={pickedCount >= 2 ? { main: `${faInt(pickedCount)} سند ← یک سند · ${faInt(lines.length)} ردیف` } : undefined}
          stats={[
            { label: 'جمع بدهکار', value: pickedCount ? fa(totals.debit) : '—', className: 'jb-stat--debit' },
            { label: 'جمع بستانکار', value: pickedCount ? fa(totals.credit) : '—', className: 'jb-stat--credit' },
          ]}
        />
      </form>
    </OpsPage>
  )
}
