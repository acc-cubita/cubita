import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { BookOpenCheck, Download, FileSpreadsheet, FileStack, Printer, Search } from 'lucide-react'

import { fetchFiscalYears, fetchLegalBook } from '../../api'
import { CountBadge } from '../../components/form/FormKit'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { Amount, CheckChip } from '../../components/ReportViews'
import { SectionCard } from '../../components/SectionCard'
import { SelectionBar } from '../../components/XlGrid'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  LEGAL_SCOPES,
  entryCount,
  isBalanced,
  legalCsv,
  legalRows,
  legalTotals,
  type LegalScope,
} from '../../lib/legalBook'
import { selectionSums } from '../../lib/ledgerReport'
import type { PageKey } from '../../lib/navModel'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { AsyncBlock, OpsPage, RangeCells, fa, faAmount, faInt, useAsync, useRange } from './kit'

/** ردیف‌هایی که یک‌جا ساخته می‌شوند. دفترِ یک‌ساله ده‌ها هزار ردیف است و همه‌اش با هم مرورگر را می‌خواباند. */
const CHUNK = 500
/** جابه‌جاییِ PageUp/PageDown. */
const PAGE_STEP = 10

/**
 * «دفاتر تجارت الکترونیک» با تمِ اکسلی (الگوی «د» از `cubita-excel-theme`).
 *
 * دفترِ روزنامه‌ی قانونی: یک ردیف به‌ازای هر ردیفِ سند با **شماره‌ی ردیفِ پیوسته**، شماره و تاریخِ سند فقط روی ردیفِ
 * اولِ هر سند، و «جمعِ دفتر» با نشانِ توازن ته گرید. گرید همان گریدِ دفترِ حسابِ «گزارش دفتر» است (`lr-ledger`) —
 * انتخاب با شماره‌ی ردیف و جمعِ انتخاب، صفحه‌کلید، ستون‌های مبلغِ میخ‌شده — بی ستونِ مانده.
 *
 * با روزنامه‌ی «گزارش دفتر» دو نمای یک داده نیست: آن‌جا سند واحد است (سرگروه و ردیف‌ها) و صفحه‌به‌صفحه از سرور؛
 * این‌جا ردیف واحد است، شماره‌ی ردیف معنا دارد، و خروجی و چاپ کلِ دفتر را می‌برند.
 */
export function LegalBooksPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('year')
  const [scope, setScope] = useState<LegalScope>('all')
  const [query, setQuery] = useState('')
  const [entryId, setEntryId] = useState<string | null>(null)
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const book = useAsync(
    () =>
      range.from && range.to
        ? fetchLegalBook(token, range.from, range.to)
        : fetchLegalBook(token, '1900-01-01', todayIso()),
    [token, range.from, range.to],
  )
  const data = book.data
  const rows = useMemo(() => legalRows(data?.rows ?? [], scope, query), [data, scope, query])
  const searching = query.trim() !== ''
  const totals = useMemo(() => legalTotals(rows), [rows])
  const entries = useMemo(() => entryCount(rows), [rows])

  // ── ردیف‌های ساخته‌شده، انتخاب و صفحه‌کلید ──
  const [limit, setLimit] = useState(CHUNK)
  const shown = rows.length > limit ? rows.slice(0, limit) : rows
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const { selected, click, clear } = useRowSelection()
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, shown.length - 1))
  const order = shown.map((r) => String(r.n))
  const picked = rows.filter((r) => selected.has(String(r.n)))
  const sums = selectionSums(picked)
  //: دفترِ دیگر (بازه، دامنه، جست‌وجو) یعنی ردیف‌های دیگر؛ انتخاب و ردیفِ فعالِ قبلی معنا ندارند.
  const viewKey = `${range.from}|${range.to}|${scope}|${query}`
  useEffect(() => {
    clear()
    setActiveRow(0)
    setLimit(CHUNK)
  }, [viewKey, clear])
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`eb-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(shown.length - 1, i)))
  }
  /** Shift+↑↓: انتخاب از ردیفِ فعلی تا مقصد — اگر لنگری نیست، همین ردیف لنگر می‌شود. */
  const extendTo = (to: number) => {
    if (selected.size === 0) click(order, order[active], { shift: false, ctrl: true })
    click(order, order[to], { shift: true, ctrl: false })
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    //: کشوی سند کیبوردِ خودش را دارد (Esc)؛ این‌جا نباید همان کلید را دوباره بخورد.
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
        if (e.shiftKey) extendTo(to)
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
        click(order, order[active], { shift: false, ctrl: true })
        break
      case 'Enter':
        e.preventDefault()
        setEntryId(shown[active].entry_id)
        break
      case 'Escape':
        if (selected.size > 0) {
          e.preventDefault()
          clear()
        }
        break
    }
  }

  //: چاپ و خروجی کلِ دفترِ انتخاب‌شده را می‌برند، نه فقط ردیف‌های ساخته‌شده. چاپ اول همه را می‌سازد و بعد از نقش‌بستن چاپ
  //: می‌کند؛ وگرنه برگه‌ی چاپی بی‌صدا در ردیفِ ۵۰۰ تمام می‌شد.
  const [printPending, setPrintPending] = useState(false)
  useEffect(() => {
    if (!printPending) return
    setPrintPending(false)
    window.print()
  }, [printPending])
  const print = () => {
    setLimit(Number.POSITIVE_INFINITY)
    setPrintPending(true)
  }
  const exportCsv = () => {
    const csv = legalCsv(rows, formatJalali)
    downloadCsv(`dafater-${scope === 'all' ? '' : `${scope}-`}${range.from ?? 'all'}`, csv.headers, csv.rows)
  }

  const rangeText = range.from
    ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())}`
    : `از ابتدای دفتر تا ${formatJalali(range.to ?? todayIso())}`
  const scopeLabel = scope === 'all' ? '' : ` · فقط ${LEGAL_SCOPES.find((s) => s.key === scope)?.label}`

  return (
    <OpsPage
      canvas
      icon={FileSpreadsheet}
      title="دفاتر تجارت الکترونیک"
      description="دفترِ روزنامه‌ی قانونی: هر ردیفِ سند یک ردیف با شماره‌ی ردیفِ پیوسته — آماده‌ی خروجی و چاپ. اسنادِ باطل و معکوسشان هر دو می‌آیند، چون دفترِ قانونی باید اصلاح را هم نشان دهد."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه و دامنه‌ی دفاتر تجارت الکترونیک">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            <div className="jh-field">
              <span className="jh-label">اسناد</span>
              <div className="cc-presets rh-seg" role="group" aria-label="دامنه‌ی اسناد">
                {LEGAL_SCOPES.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    title={s.hint}
                    className={scope === s.key ? 'is-active' : ''}
                    aria-pressed={scope === s.key}
                    onClick={() => setScope(s.key)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('ledgerreport')}>
                    <BookOpenCheck size={14} aria-hidden="true" /> گزارش دفتر
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
      <SectionCard
        icon={FileSpreadsheet}
        title="دفتر روزنامه (قانونی)"
        description={data ? `${rangeText}${scopeLabel} · ${faInt(entries)} سند` : rangeText}
        badge={data ? <CountBadge accent>{faInt(rows.length)} ردیف</CountBadge> : undefined}
        tip="یک ردیف به‌ازای هر ردیفِ سند، به‌ترتیبِ تاریخ و شماره؛ شماره و تاریخِ سند فقط روی ردیفِ اولِ هر سند می‌آیند. روی ردیف کلیک کنید (یا Enter) تا سندش باز شود. با شماره‌ی ردیف (کلیک، Ctrl، Shift) یا Space و Shift+↑↓ چند ردیف را انتخاب کنید تا جمعشان پایین بیاید. خروجی و چاپ کلِ دفتر را می‌برند."
        actions={
          <div className="jg-head-actions">
            <div className={`jg-find${query ? ' has-query' : ''}`} role="search">
              <Search size={14} aria-hidden="true" />
              <input
                ref={findRef}
                type="search"
                value={query}
                placeholder="شماره‌ی سند، حساب یا شرح  (Ctrl+F)"
                aria-label="جست‌وجو در دفتر"
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
            <button type="button" className="ef-btn-secondary" onClick={exportCsv} disabled={rows.length === 0}>
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" onClick={print} disabled={rows.length === 0}>
              <Printer size={14} /> چاپ
            </button>
          </div>
        }
      >
        <AsyncBlock loading={book.loading && !data} error={data ? null : book.error}>
          <div
            ref={gridRef}
            tabIndex={shown.length > 0 ? 0 : -1}
            className={`table-scroll ef-table-wrap rp-scroll lr-scroll${book.loading ? ' is-loading' : ''}`}
            onKeyDown={onKey}
            aria-label="دفتر روزنامه‌ی قانونی — ↑↓ حرکت، Enter سند، Space یا Shift+↑↓ انتخاب، Esc لغوِ انتخاب، Ctrl+F جست‌وجو"
          >
            <table className="ef-table xl-grid cards-on-mobile rp-table lr-ledger eb-sheet">
              <colgroup>
                <col className="lr-c-rowhead" />
                <col className="lr-c-doc" />
                <col className="lr-c-date" />
                <col className="eb-c-code" />
                <col className="lr-c-account" />
                <col />
                <col className="eb-c-amt" />
                <col className="eb-c-amt" />
              </colgroup>
              <thead>
                <tr>
                  <th className="xl-rowhead">ردیف</th>
                  <th>سند</th>
                  <th>تاریخ</th>
                  <th>کدِ حساب</th>
                  <th>نامِ حساب</th>
                  <th>شرح</th>
                  <th className="num lr-pin lr-pin--debit">بدهکار</th>
                  <th className="num lr-pin lr-pin--credit">بستانکار</th>
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 ? (
                  <tr>
                    <td className="card-full rp-status" colSpan={8}>
                      {searching
                        ? 'ردیفی با این جست‌وجو پیدا نشد.'
                        : scope === 'temporary'
                          ? 'در این بازه سندِ موقتی نیست — همه‌ی اسناد دائم شده‌اند.'
                          : 'در این بازه ردیفی ثبت نشده.'}
                    </td>
                  </tr>
                ) : (
                  shown.map((r, i) => {
                    const on = selected.has(String(r.n))
                    return (
                      <tr
                        key={r.n}
                        id={`eb-row-${i}`}
                        className={`acc-row--clickable${r.first ? ' eb-first' : ' eb-cont'}${r.voided ? ' eb-void' : ''}${i === active ? ' is-active' : ''}${on ? ' is-selected' : ''}`}
                        onClick={() => {
                          setActiveRow(i)
                          setEntryId(r.entry_id)
                        }}
                      >
                        <td className="xl-rowhead card-hide">
                          <button
                            type="button"
                            tabIndex={-1}
                            className="xl-rowhead-btn"
                            aria-pressed={on}
                            aria-label={`انتخابِ ردیفِ ${faInt(r.n)}`}
                            onClick={(ev) => {
                              //: شماره‌ی ردیف فقط انتخاب می‌کند؛ کلیکِ بقیه‌ی ردیف سند را باز می‌کند.
                              ev.stopPropagation()
                              setActiveRow(i)
                              click(order, String(r.n), modsOf(ev))
                            }}
                          >
                            {faInt(r.n)}
                          </button>
                        </td>
                        {/* شماره و تاریخ روی ردیف‌های بعدیِ سند هم هستند (کارتِ موبایل و صفحه‌خوان) ولی در گرید پنهان‌اند. */}
                        <td className="card-title">
                          <span className="eb-rep">
                            سند {r.entry_number != null ? fa(r.entry_number) : '—'}
                            {r.voided ? (
                              <span className="lr-badge eb-badge--void">باطل</span>
                            ) : (
                              r.status === 'temporary' && <span className="lr-badge">موقت</span>
                            )}
                          </span>
                        </td>
                        <td data-label="تاریخ">
                          <span className="eb-rep">{formatJalali(r.entry_date)}</span>
                        </td>
                        <td data-label="کدِ حساب">
                          <span className="ltr-cell">{r.account_code}</span>
                        </td>
                        <td data-label="نامِ حساب" title={r.account_name}>
                          {r.account_name}
                        </td>
                        <td className="card-wide" data-label="شرح" title={r.description || undefined}>
                          {r.description || '—'}
                        </td>
                        <td className="num lr-pin lr-pin--debit" data-label="بدهکار">
                          {faAmount(r.debit)}
                        </td>
                        <td className="num lr-pin lr-pin--credit" data-label="بستانکار">
                          {faAmount(r.credit)}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
              <tfoot>
                <tr className="rp-total">
                  <td className="xl-rowhead card-hide" />
                  <td className="card-title" colSpan={5}>
                    {searching ? 'جمعِ ردیف‌های منطبق' : 'جمعِ دفتر'}
                    <small className="lr-foot-note"> {faInt(rows.length)} ردیف</small>
                    {/* با جست‌وجو فقط بخشی از هر سند دیده می‌شود و جمعش به‌تعریف ناتراز است؛ توازن فقط روی کلِ دفتر. */}
                    {!searching && rows.length > 0 && (
                      <CheckChip ok={isBalanced(totals)} okText="تراز است" offText="ناتراز" />
                    )}
                  </td>
                  <td className="num lr-pin lr-pin--debit" data-label="جمعِ بدهکار">
                    {faAmount(totals.debit)}
                  </td>
                  <td className="num lr-pin lr-pin--credit" data-label="جمعِ بستانکار">
                    {faAmount(totals.credit)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          {picked.length > 0 && (
            <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>
              <span>
                بدهکار <b className="num">{faAmount(sums.debit)}</b>
              </span>
              <span>
                بستانکار <b className="num">{faAmount(sums.credit)}</b>
              </span>
              <span>
                خالص <b className="num"><Amount value={sums.net} /></b>
              </span>
            </SelectionBar>
          )}
          {rows.length > shown.length && (
            <div className="daybook-more eb-more">
              <span className="hint">
                نمایشِ {faInt(shown.length)} از {faInt(rows.length)} ردیف — جمع، خروجی و چاپ کلِ دفترند.
              </span>
              <span className="eb-more-btns">
                <button type="button" className="ef-btn-secondary" onClick={() => setLimit((l) => l + CHUNK)}>
                  {faInt(Math.min(CHUNK, rows.length - shown.length))} ردیفِ بعدی
                </button>
                <button type="button" className="ef-btn-secondary" onClick={() => setLimit(Number.POSITIVE_INFINITY)}>
                  نمایشِ همه
                </button>
              </span>
            </div>
          )}
          {shown.length > 0 && (
            <p className="ab-keys lr-keys">
              <kbd>↑</kbd>
              <kbd>↓</kbd> ردیف · <kbd>Enter</kbd> یا کلیک سند · <kbd>Space</kbd> یا <kbd>Shift+↑↓</kbd> یا شماره‌ی ردیف
              انتخاب · <kbd>Esc</kbd> لغوِ انتخاب · <kbd>Ctrl+F</kbd> جست‌وجو
            </p>
          )}
        </AsyncBlock>
      </SectionCard>

      {entryId && <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />}
    </OpsPage>
  )
}
