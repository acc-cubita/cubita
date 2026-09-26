import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { BookOpen, CalendarCheck, CheckCircle2, ClipboardCheck, Eye, FileStack, Inbox, Lock, Search } from 'lucide-react'

import { fetchCartable, fetchFiscalYears, finalizeEntries } from '../../api'
import { DocFooter } from '../../components/DocFooter'
import { CountBadge } from '../../components/form/FormKit'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { filterCartable, isTruncated, pickedTotals, scopeBody, type FinalizeBody } from '../../lib/cartable'
import { formatJalali, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { AsyncBlock, OpsPage, RangeCells, fa, faAmount, faInt, sourceLabel, useAsync, useRange, type Msg } from './kit'

const LAYOUT = { fixed: ['rowhead', 'go'], auto: 'desc' } as const

/** نوار روی گرید: [ردیف…تاریخ] [شرح] [منشأ + حساب‌ها] [مبلغ] [نمایش]. */
const CB_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('rowhead') + w('number') + w('atf') + w('sub') + w('date'), w('desc'), w('source') + w('accounts'), w('amount'), w('go')]
}
/** جابه‌جاییِ PageUp/PageDown. */
const PAGE_STEP = 10

/**
 * «کارتابل اسناد موقت» با تمِ اکسلی — صفِ بازبینی: هرچه ثبت شده ولی هنوز دائم نشده.
 *
 * - **سربرگ** (`jh-bar--report`): بازه و سالِ مالی، و «رفتن به».
 * - **منشأ** خانه‌ی سربرگ است (هر گزینه با شمار و مبلغش): برگه را به همان منشأ می‌برد و «دائم‌کردنِ همه‌ی …» همان منشأ
 *   (یا کلِ بازه) را یک‌جا دائم می‌کند — تصمیم معمولاً دسته‌ای است.
 * - **برگه:** کلیک روی ردیف (یا Space) انتخابش می‌کند و Shift بازه را؛ «نمایش» (یا Enter) خودِ سند را باز می‌کند تا
 *   بازبینی شود. سرستونِ ردیف همه‌ی ردیف‌های دیده‌شده را انتخاب می‌کند.
 * - **نوار:** «دائم‌کردنِ انتخاب‌شده‌ها» (Ctrl+S) با شمار و مبلغِ انتخاب زیرِ ستون‌های خودشان.
 *
 * دائم‌کردن اثرِ مالی ندارد ولی برگشت ندارد: سندِ دائم دیگر ادغام یا بازشماره‌گذاری نمی‌شود — هر سه راه تأیید می‌خواهند.
 */
export function EntryCartablePage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('all')
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const cartable = useAsync(() => fetchCartable(token, range.from, range.to), [token, range.from, range.to])
  const [source, setSource] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [entryId, setEntryId] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const cw = useColumnWidths('cubita.grid.cartable.shares', LAYOUT)
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.cb-sheet', slots: CB_SLOTS })

  const data = cartable.data
  const all = data?.entries ?? []
  const groups = data?.groups ?? []
  //: منشأیی که با بازه‌ی تازه دیگر سندی ندارد، فیلترِ خالی می‌ساخت.
  const activeSource = source && groups.some((g) => g.source_type === source) ? source : null
  const shown = filterCartable(all, activeSource, query)
  const order = shown.map((e) => e.id)

  const { selected, click, clear } = useRowSelection()
  const picked = pickedTotals(all, selected)
  const toggle = (id: string, shift = false) => click(order, id, { shift, ctrl: true })
  const allShownPicked = shown.length > 0 && shown.every((e) => selected.has(e.id))
  function pickAllShown() {
    if (allShownPicked) {
      shown.forEach((e) => selected.has(e.id) && click(order, e.id, { shift: false, ctrl: true }))
      return
    }
    shown.forEach((e) => !selected.has(e.id) && click(order, e.id, { shift: false, ctrl: true }))
  }
  //: بازه‌ی دیگر یعنی سندهای دیگر.
  useEffect(() => clear(), [range.from, range.to, clear])

  async function finalize(body: FinalizeBody, label: string) {
    if (busy) return
    if (!window.confirm(`${label}\nسندِ دائم دیگر ادغام یا بازشماره‌گذاری نمی‌شود. ادامه؟`)) return
    setBusy(true)
    try {
      const out = await finalizeEntries(token, body)
      setMsg({ text: `${faInt(out.count)} سند دائم شد.`, kind: 'ok' })
      clear()
      cartable.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }
  const finalizePicked = () => {
    const ids = all.filter((e) => selected.has(e.id)).map((e) => e.id)
    if (ids.length === 0) return
    void finalize({ entry_ids: ids }, `دائم‌کردنِ ${faInt(ids.length)} سندِ انتخابی.`)
  }
  const rangeText = range.from
    ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())}`
    : 'کلِ دفتر'
  const scopeGroup = groups.find((g) => g.source_type === activeSource)
  const scopeCount = scopeGroup ? scopeGroup.count : (data?.total_count ?? 0)
  const finalizeScope = () =>
    void finalize(
      scopeBody(range, activeSource),
      activeSource
        ? `دائم‌کردنِ همه‌ی ${faInt(scopeCount)} سندِ «${sourceLabel(activeSource)}» در ${rangeText}.`
        : `دائم‌کردنِ همه‌ی ${faInt(scopeCount)} سندِ موقتِ ${rangeText}.`,
    )

  // ── صفحه‌کلید ──
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, shown.length - 1))
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`cb-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(shown.length - 1, i)))
  }
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (entryId) return
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
        e.preventDefault()
        toggle(order[active])
        break
      case 'Enter':
        e.preventDefault()
        setEntryId(order[active])
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

  return (
    <OpsPage
      canvas
      icon={ClipboardCheck}
      title="کارتابل اسناد موقت"
      description="هرچه ثبت شده ولی هنوز بازبینی نشده. سند را ببینید، بعد دائمش کنید — تکی، یک منشأ با هم، یا کلِ بازه در پایانِ ماه. دائم‌کردن اثرِ مالی ندارد ولی برگشت ندارد."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه‌ی کارتابل اسناد موقت">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            {/* منشأ فیلترِ برگه است و دامنه‌ی «دائم‌کردنِ همه‌ی …»؛ هر گزینه شمار و مبلغش را دارد. فهرست به‌جای خانه‌های
                جدا: در دفترِ واقعی بیست‌وچند منشأ هست و خانه‌هایشان چهار سطر بالای برگه را می‌گرفتند. */}
            <div className="jh-field">
              <label className="jh-label" htmlFor="cb-source">
                منشأ
              </label>
              <SearchSelect id="cb-source" aria-label="منشأ" value={activeSource ?? ''} onChange={(e) => setSource(e.target.value || null)}>
                <option value="">همه‌ی منشأها — {faInt(data?.total_count ?? 0)} سند</option>
                {groups.map((g) => (
                  <option key={g.source_type} value={g.source_type}>
                    {sourceLabel(g.source_type)} — {faInt(g.count)} سند · {fa(g.total)}
                  </option>
                ))}
              </SearchSelect>
            </div>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('entrylist')}>
                    <FileStack size={14} aria-hidden="true" /> اسناد حسابداری
                  </button>
                  <button type="button" onClick={() => onNavigate('journalentry')}>
                    <BookOpen size={14} aria-hidden="true" /> سند حسابداری
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
          finalizePicked()
        }}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
            e.preventDefault()
            finalizePicked()
          }
        }}
      >
        <SectionCard
          icon={Inbox}
          title="اسنادِ در انتظار"
          description={
            data
              ? `${rangeText} · ${faInt(data.total_count)} سند · ${fa(groups.reduce((s, g) => s + Number(g.total), 0))} ریال`
              : rangeText
          }
          tip="روی ردیف‌هایی که بازبینی کرده‌اید کلیک کنید تا انتخاب شوند (Shift برای یک بازه) و از نوارِ پایین دائمشان کنید. «نمایش» یا Enter خودِ سند را باز می‌کند. برای تصمیمِ دسته‌ای، منشأ را در سربرگ انتخاب کنید و «دائم‌کردنِ همه‌ی …» را بزنید."
          badge={data ? <CountBadge accent>{faInt(data.total_count)} سند</CountBadge> : undefined}
          actions={
            <div className="jg-head-actions">
              <div className={`jg-find${query ? ' has-query' : ''}`} role="search">
                <Search size={14} aria-hidden="true" />
                <input
                  ref={findRef}
                  type="search"
                  value={query}
                  placeholder="شماره، شرح یا حساب  (Ctrl+F)"
                  aria-label="جست‌وجوی سند در کارتابل"
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
              <button
                type="button"
                className="ef-btn-secondary"
                disabled={!data || scopeCount === 0 || busy}
                onClick={finalizeScope}
                title={activeSource ? 'همه‌ی سندهای این منشأ در بازه، حتی آن‌هایی که در برگه نیامده‌اند' : 'همه‌ی سندهای موقتِ بازه — بستنِ ماه'}
              >
                <CalendarCheck size={14} />{' '}
                {activeSource ? `دائم‌کردنِ همه‌ی «${sourceLabel(activeSource)}»` : 'دائم‌کردنِ کلِ بازه'}
              </button>
            </div>
          }
        >
          <AsyncBlock
            loading={cartable.loading && !data}
            error={data ? null : cartable.error}
            empty={(data?.total_count ?? 0) === 0}
            emptyText="هیچ سندِ موقتی در این بازه نیست — کارتابل خالی است."
          >
            <div
              ref={gridRef}
              tabIndex={shown.length > 0 ? 0 : -1}
              className="table-scroll ef-table-wrap lr-scroll cb-scroll"
              onKeyDown={onGridKey}
              aria-label="اسنادِ موقت — ↑↓ حرکت، Space انتخاب، Enter نمایشِ سند، Shift+↓ افزودن، Esc لغوِ انتخاب، Ctrl+F جست‌وجو"
            >
              <table ref={cw.frame} className={`cards-on-mobile ef-table xl-grid cb-sheet${cartable.loading ? ' is-loading' : ''}`}>
                <colgroup>
                  <col className="cb-c-rowhead" style={cw.col('rowhead')} />
                  <col className="cb-c-num" style={cw.col('number')} />
                  <col className="cb-c-num" style={cw.col('atf')} />
                  <col className="cb-c-sub" style={cw.col('sub')} />
                  <col className="cb-c-date" style={cw.col('date')} />
                  <col style={cw.col('desc')} />
                  <col className="cb-c-src" style={cw.col('source')} />
                  <col className="cb-c-acc" style={cw.col('accounts')} />
                  <col className="cb-c-amt" style={cw.col('amount')} />
                  <col className="cb-c-go" style={cw.col('go')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead card-hide" data-col="rowhead">
                      <button
                        type="button"
                        className="xl-rowhead-btn"
                        aria-pressed={allShownPicked}
                        aria-label={allShownPicked ? 'لغوِ انتخابِ همه' : 'انتخابِ همه‌ی ردیف‌های دیده‌شده'}
                        title={allShownPicked ? 'لغوِ انتخابِ همه' : 'انتخابِ همه‌ی ردیف‌های دیده‌شده'}
                        onClick={pickAllShown}
                        disabled={shown.length === 0}
                      >
                        <CheckCircle2 size={13} aria-hidden="true" />
                      </button>
                    </th>
                    {head('number', 'شماره', 'atf')}
                    {head('atf', 'عطف', 'sub')}
                    {head('sub', 'فرعی', 'date')}
                    {head('date', 'تاریخ', 'desc')}
                    {head('desc', 'شرح', 'source')}
                    {head('source', 'منشأ', 'accounts')}
                    {head('accounts', 'حساب‌ها', 'amount')}
                    {head('amount', 'مبلغ', undefined, 'num')}
                    <th data-col="go" aria-label="نمایش" />
                  </tr>
                </thead>
                <tbody>
                  {shown.length === 0 ? (
                    <tr>
                      <td className="card-full cb-status" colSpan={10}>
                        سندی با این جست‌وجو یا منشأ پیدا نشد.
                      </td>
                    </tr>
                  ) : (
                    shown.map((e, i) => {
                      const on = selected.has(e.id)
                      return (
                        <tr
                          key={e.id}
                          id={`cb-row-${i}`}
                          aria-selected={on}
                          className={`acc-row--clickable${on ? ' is-selected' : ''}${i === active ? ' is-active' : ''}`}
                          onClick={(ev) => {
                            setActiveRow(i)
                            toggle(e.id, ev.shiftKey)
                          }}
                        >
                          <td className="xl-rowhead card-hide">
                            <button type="button" tabIndex={-1} className="xl-rowhead-btn" aria-pressed={on} aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}>
                              {faInt(i + 1)}
                            </button>
                          </td>
                          <td className="card-title">سند {e.number != null ? fa(e.number) : '—'}</td>
                          <td className="num" data-label="عطف">
                            {e.atf_number === null ? '—' : faInt(e.atf_number)}
                          </td>
                          <td data-label="فرعی">{e.sub_number || '—'}</td>
                          <td data-label="تاریخ">{formatJalali(e.entry_date)}</td>
                          <td className="card-wide" data-label="شرح" title={e.description || undefined}>
                            {e.description || '—'}
                          </td>
                          <td data-label="منشأ">{sourceLabel(e.source_type)}</td>
                          <td data-label="حساب‌ها" title={e.accounts.join('، ')}>
                            {e.accounts.slice(0, 3).join('، ')}
                            {e.accounts.length > 3 ? ' …' : ''}
                          </td>
                          <td className="num" data-label="مبلغ">
                            {faAmount(e.total)}
                          </td>
                          <td className="card-actions">
                            <button
                              type="button"
                              className="cb-open"
                              tabIndex={-1}
                              title="نمایشِ سند"
                              onClick={(ev) => {
                                ev.stopPropagation()
                                setActiveRow(i)
                                setEntryId(e.id)
                              }}
                            >
                              <Eye size={14} aria-hidden="true" /> <span className="cb-open-label">نمایش</span>
                            </button>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
            {data && isTruncated(data) && (
              <p className="hint acc-note acc-note--warn">
                <Lock size={14} />
                برگه {faInt(data.entries.length)} سندِ اول از {faInt(data.total_count)} را نشان می‌دهد. بازه را کوتاه‌تر کنید، یا با «دائم‌کردنِ
                همه‌ی …» کلِ منشأ یا بازه را یک‌جا دائم کنید.
              </p>
            )}
            {picked.count > 0 && (
              <SelectionBar count={picked.count} unit="سند" onClear={clear}>
                <span>
                  جمع مبلغ <b className="num">{faAmount(picked.total)}</b>
                </span>
              </SelectionBar>
            )}
          </AsyncBlock>
        </SectionCard>

        <DocFooter
          tone={picked.count > 0 ? 'auto' : 'empty'}
          columns
          submitting={busy}
          submittingLabel="در حال دائم‌کردن…"
          submitLabel={picked.count > 0 ? `دائم‌کردنِ ${faInt(picked.count)} سند` : 'دائم‌کردنِ انتخاب‌شده‌ها'}
          submitDisabled={picked.count === 0}
          shortcut
          message={msg}
          groupLabel="انتخابِ کارتابل"
          statusLabel="در انتظار"
          statusKey={`${data?.total_count ?? ''}-${picked.count}`}
          status={data ? `${faInt(data.total_count)} سندِ موقت` : 'در حال بارگذاری…'}
          sub={data && data.total_count > 0 ? { main: picked.count ? `${faInt(picked.count)} انتخاب‌شده` : 'سندی انتخاب نشده' } : undefined}
          stats={[
            { label: 'سندِ انتخابی', value: faInt(picked.count), className: 'jb-stat--a' },
            { label: 'مبلغِ انتخابی', value: fa(picked.total), className: 'jb-stat--b' },
          ]}
        />
      </form>

      {entryId && (
        <JournalEntryDrawer
          token={token}
          entryId={entryId}
          onClose={() => {
            setEntryId(null)
            //: شاید سند در کشو اصلاح یا باطل شده باشد.
            cartable.reload()
          }}
        />
      )}
    </OpsPage>
  )
}
