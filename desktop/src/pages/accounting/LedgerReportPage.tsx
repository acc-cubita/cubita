import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { BookOpenCheck, Download, FilePlus2, Landmark, Layers, Library, Scale } from 'lucide-react'

import {
  fetchAllJournalEntries,
  fetchAnalyticLedger,
  fetchAnalytics,
  fetchChartAccounts,
  fetchFiscalYears,
  fetchGeneralLedger,
  fetchJournalEntriesPage,
  fetchJournalEntriesSummary,
  type GeneralLedger,
  type JournalEntryRecord,
  type ReportFilters,
} from '../../api'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { Amount, CheckChip } from '../../components/ReportViews'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { SelectionBar } from '../../components/XlGrid'
import { levelOf } from '../../lib/balanceReport'
import { downloadCsv } from '../../lib/csv'
import { formatJalali } from '../../lib/jalali'
import {
  daybookColumns,
  daybookRows,
  ledgerColumns,
  ledgerCsv,
  ledgerPeriod,
  selectionSums,
} from '../../lib/ledgerReport'
import type { PageKey } from '../../lib/navModel'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { AsyncBlock, OpsPage, RangeCells, StatusChip, fa, faAmount, faInt, sourceText, useAsync, useRange } from './kit'

/** چهار دفترِ حسابداری، به همان ترتیبی که در عمل خوانده می‌شوند. */
type Book = 'journal' | 'general' | 'ledger' | 'analytic'

const BOOKS: { key: Book; label: string; hint: string }[] = [
  { key: 'journal', label: 'روزنامه', hint: 'همه‌ی اسناد به‌ترتیبِ تاریخ، هر سند با ردیف‌هایش' },
  { key: 'general', label: 'کل', hint: 'گردشِ یک حسابِ کل با همه‌ی زیرحساب‌هایش' },
  { key: 'ledger', label: 'معین', hint: 'گردشِ یک حساب با مانده‌ی ردیف‌به‌ردیف' },
  { key: 'analytic', label: 'تفصیلی', hint: 'گردشِ یک تفصیلی در همه‌ی حساب‌ها' },
]

/** اسنادِ هر صفحه‌ی روزنامه. سند با همه‌ی ردیف‌هایش می‌آید، پس ۵۰ سند چند صد ردیف است. */
const DAYBOOK_PAGE = 50
/** جابه‌جاییِ PageUp/PageDown در گریدِ دفترِ حساب. */
const PAGE_STEP = 10

/**
 * «گزارش دفتر» با تمِ اکسلی (الگوی «د» از `cubita-excel-theme`).
 *
 * - **سربرگ** (`jh-bar--report`): دفتر (روزنامه/کل/معین/تفصیلی) و پارامترِ همان دفتر در سطرِ اول — جست‌وجوی سند،
 *   حسابِ کل، حساب یا تفصیلی؛ بعد بازه و سالِ مالی، فیلترهای دفتر، و نماها/میان‌برها.
 * - **روزنامه** یک گرید است نه کارتی به‌ازای هر سند: هر سند یک ردیفِ سرگروه و زیرش ردیف‌هایش؛ «جمعِ بازه» از سرور
 *   در پانویس با نشانِ توازن. کلیک روی سند خودِ سند را باز می‌کند.
 * - **کل، معین و تفصیلی** گریدِ گردشِ «مرور حساب‌ها»اند: «مانده‌ی ابتدای دوره» ردیفِ اول، «جمعِ بازه» و مانده‌ی پایان
 *   در پانویس، ستون‌های مبلغِ میخ‌شده، انتخاب با شماره‌ی ردیف و جمعِ انتخاب، و صفحه‌کلید. صفحه‌بندیِ ۲۰تایی رفت.
 */
export function LedgerReportPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('month')
  const [book, setBook] = useState<Book>('journal')
  const [filters, setFilters] = useState<ReportFilters>({})
  const [accountId, setAccountId] = useState('')
  //: انتخابِ دفترِ کل جداست، وگرنه جابه‌جا شدن بینِ دو دفتر یک شناسه‌ی نامعتبر را
  //: به انتخابگرِ دیگر می‌برد و کاربر یک `select`ِ خالی می‌بیند بی‌آنکه بداند چرا.
  const [generalId, setGeneralId] = useState('')
  const [search, setSearch] = useState('')
  const [entryId, setEntryId] = useState<string | null>(null)

  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const analytics = useAsync(() => fetchAnalytics(token).catch(() => []), [token])
  const postable = useMemo(
    () => (accounts.data ?? []).filter((a) => !a.is_group).sort((a, b) => a.code.localeCompare(b.code)),
    [accounts.data],
  )
  //: حساب‌های سطحِ «کل» — همان `levelOf`ِ گزارش ترازها. سطح از عمقِ درخت می‌آید نه طولِ کد، چون چارت یکدست نیست:
  //: دارایی‌ها ۱ ← ۱۱ ← ۱۱۰۱ دارند و هزینه‌ها ۵ ← ۵۱۰۱.
  const generalAccounts = useMemo(() => {
    const list = accounts.data ?? []
    const byId = new Map(list.map((a) => [a.id, a]))
    return list.filter((a) => levelOf(a, byId) === 2).sort((a, b) => a.code.localeCompare(b.code))
  }, [accounts.data])
  //: بازه و فیلترها یک دامنه‌اند و با هم به سرور می‌روند — همان چیزی که تراز هم می‌فرستد، تا دو گزارش نتوانند از
  //: هم جدا بیفتند.
  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }
  //: ردیفِ سند فقط شناسه‌ی حساب دارد؛ نام از چارت می‌آید تا دفتر خوانا باشد.
  const accountNames = useMemo(
    () => new Map((accounts.data ?? []).map((a) => [a.id, `${a.code} — ${a.name}`])),
    [accounts.data],
  )

  const paramCell =
    book === 'journal' ? (
      //: سرور روی شماره، عطف، شماره‌ی فرعی و شرحِ سند می‌گردد، نه روی حساب. گردشِ یک حساب جایش «معین» است.
      <label className="jh-field lr-param">
        <span className="jh-label">جست‌وجوی سند</span>
        <input
          type="search"
          aria-label="جست‌وجوی سند"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="شماره یا شرحِ سند"
        />
      </label>
    ) : book === 'general' ? (
      <label className="jh-field lr-param">
        <span className="jh-label">حسابِ کل</span>
        <SearchSelect aria-label="حسابِ کل" value={generalId} onChange={(e) => setGeneralId(e.target.value)}>
          <option value="">— انتخابِ حسابِ کل —</option>
          {generalAccounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} — {a.name}
            </option>
          ))}
        </SearchSelect>
      </label>
    ) : book === 'ledger' ? (
      <label className="jh-field lr-param">
        <span className="jh-label">حساب</span>
        <SearchSelect aria-label="حساب" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
          <option value="">— انتخابِ حساب —</option>
          {postable.map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} — {a.name}
            </option>
          ))}
        </SearchSelect>
      </label>
    ) : (
      //: در دفترِ تفصیلی، تفصیلی خودِ موضوعِ دفتر است نه یک فیلتر؛ پس این‌جا می‌نشیند و از نوارِ فیلتر برداشته می‌شود.
      <label className="jh-field lr-param">
        <span className="jh-label">تفصیلی</span>
        <SearchSelect
          aria-label="تفصیلی"
          value={filters.analyticId ?? ''}
          onChange={(e) => setFilters({ ...filters, analyticId: e.target.value || undefined })}
        >
          <option value="">— انتخابِ تفصیلی —</option>
          {(analytics.data ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} — {a.name}
            </option>
          ))}
        </SearchSelect>
      </label>
    )

  return (
    <OpsPage
      canvas
      icon={BookOpenCheck}
      title="گزارش دفتر"
      description="دفترهای حسابداری: روزنامه (همه‌ی اسناد به‌ترتیبِ تاریخ)، کل (گردشِ یک سرفصل با همه‌ی زیرحساب‌هایش)، معین (گردشِ یک حساب با مانده‌ی دوره‌ای) و تفصیلی."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="دفتر، بازه و فیلترهای گزارش دفتر">
          <div className="jh-row lr-row--book">
            <div className="jh-field">
              <span className="jh-label">دفتر</span>
              <div className="cc-presets rh-seg" role="group" aria-label="دفتر">
                {BOOKS.map((b) => (
                  <button
                    key={b.key}
                    type="button"
                    title={b.hint}
                    className={book === b.key ? 'is-active' : ''}
                    aria-pressed={book === b.key}
                    onClick={() => setBook(b.key)}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            </div>
            {paramCell}
          </div>
          <div className="jh-row jh-row--sub rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className={`jh-row jh-row--sub rh-row--filters${book === 'analytic' ? ' lr-filters5' : ''}`}>
            <ReportFilterBar
              token={token}
              filters={filters}
              onChange={setFilters}
              variant="cells"
              showAnalytic={book !== 'analytic'}
            />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            <div className="jh-field rh-views">
              <span className="jh-label">نماهای ذخیره‌شده</span>
              <SavedViewBar token={token} viewKey="accounting.ledger" filters={filters} range={range} setFilters={setFilters} />
            </div>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('journalentry')}>
                    <FilePlus2 size={14} aria-hidden="true" /> ثبت سند جدید
                  </button>
                  <button type="button" onClick={() => onNavigate('balancereport')}>
                    <Scale size={14} aria-hidden="true" /> گزارش ترازها
                  </button>
                  <button type="button" onClick={() => onNavigate('accountbrowse')}>
                    <Layers size={14} aria-hidden="true" /> مرور حساب‌ها
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      }
    >
      {book === 'journal' ? (
        <DaybookGrid token={token} filters={scope} search={search} accountNames={accountNames} onOpenEntry={setEntryId} />
      ) : (
        <LedgerGrid
          //: دفتر یا حسابِ دیگر یعنی گریدِ تازه: انتخاب و ردیفِ فعال از صفر.
          key={`${book}-${book === 'general' ? generalId : book === 'ledger' ? accountId : (filters.analyticId ?? '')}`}
          token={token}
          book={book}
          accountId={book === 'general' ? generalId : book === 'ledger' ? accountId : ''}
          filters={scope}
          entryOpen={entryId !== null}
          onOpenEntry={setEntryId}
        />
      )}

      {entryId && (
        <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />
      )}
    </OpsPage>
  )
}

// ═════════════ روزنامه ═════════════

/**
 * دفتر روزنامه — صفحه‌به‌صفحه از سرور، با جمعِ کلِ دامنه از سرور.
 *
 * پیش از این تا ۲۰۰ سند می‌گرفت و بقیه را **بی‌صدا** نمی‌آورد. در بازه‌ی یک‌ساله یعنی ماه‌های آخر اصلاً دیده
 * نمی‌شدند، و «جمعِ گردشِ بازه» جمعِ همان ۲۰۰ سند بود. حالا صفحه‌ها با کرسرِ سرور می‌آیند و جمع از `/summary` است.
 * عددِ پانویس هرگز از ردیف‌های بارگذاری‌شده ساخته نمی‌شود.
 */
function DaybookGrid({
  token,
  filters,
  search,
  accountNames,
  onOpenEntry,
}: {
  token: string
  filters: ReportFilters
  search: string
  accountNames: Map<string, string>
  onOpenEntry: (id: string) => void
}) {
  //: هر حرفِ جست‌وجو دو درخواست است (صفحه و جمع)، پس با کمی مکث می‌رود.
  const [q, setQ] = useState(search.trim())
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  //: `filters` هر رندر شیءِ تازه است. کلید، دامنه را به‌صورتِ مقدار می‌گوید.
  const scopeKey = JSON.stringify([filters, q])
  const first = useAsync(
    () => fetchJournalEntriesPage(token, filters, { q: q || undefined, limit: DAYBOOK_PAGE }),
    [token, scopeKey],
  )
  const summary = useAsync(() => fetchJournalEntriesSummary(token, filters, q || undefined), [token, scopeKey])

  //: صفحه‌های بعدی مالِ **همین بارِ** این دامنه‌اند، نه مقدارِ دامنه. کلید فقط مقدار را می‌گوید: فیلتر را عوض کنی
  //: و برگردی، کلید همان می‌شود و صفحه‌های قدیمی زنده می‌شدند. در رندرِ اولِ بعد از برگشت، `first.data` هنوز مالِ
  //: دامنه‌ی قبلی بود و کنارِ آن صفحه‌ها سندِ تکراری می‌ساخت. `visit` با هر عوض‌شدنِ کلید شیءِ تازه است، حتی وقتی
  //: کلید به مقدارِ قبلی برگردد.
  const visit = useMemo(() => ({ scopeKey }), [scopeKey])
  const [more, setMore] = useState<{ visit: object | null; entries: JournalEntryRecord[]; cursor: string | null }>({
    visit: null,
    entries: [],
    cursor: null,
  })
  const [moreBusy, setMoreBusy] = useState(false)
  const [moreError, setMoreError] = useState<string | null>(null)
  //: پاسخِ دیررسیده‌ی دامنه‌ی قبلی روی دامنه‌ی تازه نمی‌نشیند.
  const liveVisit = useRef(visit)
  useEffect(() => {
    liveVisit.current = visit
    setMoreError(null)
  }, [visit])

  const extra = more.visit === visit ? more : null
  const entries = [...(first.data?.items ?? []), ...(extra?.entries ?? [])]
  const nextCursor = extra ? extra.cursor : (first.data?.next_cursor ?? null)

  async function loadMore() {
    if (!nextCursor) return
    const mine = visit
    setMoreBusy(true)
    setMoreError(null)
    try {
      const page = await fetchJournalEntriesPage(token, filters, { q: q || undefined, cursor: nextCursor, limit: DAYBOOK_PAGE })
      if (liveVisit.current !== mine) return
      setMore((m) => ({
        visit: mine,
        entries: [...(m.visit === mine ? m.entries : []), ...page.items],
        cursor: page.next_cursor,
      }))
    } catch (err) {
      if (liveVisit.current === mine) setMoreError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setMoreBusy(false)
    }
  }

  const [csvBusy, setCsvBusy] = useState(false)
  const [csvError, setCsvError] = useState<string | null>(null)
  //: خروجی کلِ دامنه است، نه صفحه‌های بارگذاری‌شده. کاربری که «خروجی» می‌زند همه را می‌خواهد.
  async function exportCsv() {
    setCsvBusy(true)
    setCsvError(null)
    try {
      const all = await fetchAllJournalEntries(token, filters, q || undefined)
      downloadCsv(
        `daftar-rooznameh-${filters.dateFrom ?? 'all'}`,
        ['شماره سند', 'تاریخ', 'شرح سند', 'حساب', 'شرح ردیف', 'بدهکار', 'بستانکار'],
        all.flatMap((e) =>
          e.lines.map((l) => [
            e.number ?? '',
            formatJalali(e.entry_date),
            e.description,
            accountNames.get(l.account_id) ?? '',
            l.description,
            Number(l.debit),
            Number(l.credit),
          ]),
        ),
      )
    } catch (err) {
      setCsvError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setCsvBusy(false)
    }
  }

  const total = summary.data
  //: با فیلترِ ردیفی، سند کامل نشان داده می‌شود ولی جمع فقط ردیف‌های منطبق است. برچسب همین را می‌گوید تا کسی جمع را
  //: با ردیف‌های دیده‌شده مقایسه نکند و گیج نشود — و توازن هم سنجیده نمی‌شود، چون بخشی از هر سند است.
  const lineScoped = Boolean(filters.costCenterId || filters.analyticId)
  const cols = daybookColumns(entries)
  const colCount = 4 + (cols.fx ? 1 : 0) + (cols.tracking ? 1 : 0)
  const openKey = (id: string) => (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      onOpenEntry(id)
    }
  }

  return (
    <SectionCard
      icon={BookOpenCheck}
      title="دفتر روزنامه"
      description={
        total
          ? `${faInt(total.entry_count)} سند · ${faInt(total.line_count)} ردیف${lineScoped ? 'ِ منطبق' : ''}`
          : 'هر سند با ردیف‌هایش'
      }
      tip="هر سند یک ردیفِ سرگروه دارد و ردیف‌هایش زیرش می‌آیند؛ روی سند کلیک کنید (یا Enter) تا خودِ سند باز شود. «جمعِ بازه» کلِ دامنه است، نه فقط سندهای بارگذاری‌شده."
      actions={
        <button
          type="button"
          className="ef-btn-secondary"
          onClick={exportCsv}
          disabled={csvBusy || !total || total.entry_count === 0}
        >
          <Download size={14} /> {csvBusy ? 'در حال آماده‌سازی…' : 'خروجی CSV'}
        </button>
      }
    >
      {summary.error && <p className="hint acc-note acc-note--err">جمعِ دفتر نیامد: {summary.error}</p>}
      {csvError && <p className="hint acc-note acc-note--err">خروجی ساخته نشد: {csvError}</p>}
      <AsyncBlock loading={first.loading && !first.data} error={first.data ? null : first.error}>
        <div className={`table-scroll ef-table-wrap rp-scroll${first.loading ? ' is-loading' : ''}`}>
          <table className="ef-table xl-grid cards-on-mobile rp-table lr-daybook">
            <colgroup>
              <col className="lr-c-acct" />
              <col />
              {cols.fx && <col className="lr-c-fx" />}
              {cols.tracking && <col className="lr-c-track" />}
              <col className="lr-c-amt" />
              <col className="lr-c-amt" />
            </colgroup>
            <thead>
              <tr>
                <th>حساب</th>
                <th>شرح ردیف</th>
                {cols.fx && <th className="num">ارز</th>}
                {cols.tracking && <th>پیگیری</th>}
                <th className="num">بدهکار</th>
                <th className="num">بستانکار</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td className="card-full rp-status" colSpan={colCount}>
                    در بازه و فیلترِ انتخاب‌شده سندی یافت نشد.
                  </td>
                </tr>
              ) : (
                daybookRows(entries).map((r) => {
                  const voided = !!r.entry.voided_at
                  if (r.kind === 'entry')
                    return (
                      <tr
                        key={r.entry.id}
                        className={`lr-entry acc-row--clickable${voided ? ' lr-void' : ''}`}
                        tabIndex={0}
                        title="بازکردنِ سند"
                        onClick={() => onOpenEntry(r.entry.id)}
                        onKeyDown={openKey(r.entry.id)}
                      >
                        <td className="card-full" colSpan={colCount}>
                          <b className="lr-entry-no">سند {r.entry.number != null ? fa(r.entry.number) : '—'}</b>
                          <span className="lr-entry-date">{formatJalali(r.entry.entry_date)}</span>
                          <StatusChip status={r.entry.status} voided={voided} />
                          <span className="lr-entry-src">{sourceText(r.entry)}</span>
                          {r.entry.description && <span className="lr-entry-desc">{r.entry.description}</span>}
                        </td>
                      </tr>
                    )
                  const l = r.line
                  return (
                    <tr
                      key={l.id}
                      className={`lr-line acc-row--clickable${voided ? ' lr-void' : ''}`}
                      onClick={() => onOpenEntry(r.entry.id)}
                    >
                      <td className="card-title" title={accountNames.get(l.account_id)}>
                        {accountNames.get(l.account_id) ?? '—'}
                      </td>
                      <td data-label="شرح ردیف" title={l.description || undefined}>
                        {l.description || '—'}
                      </td>
                      {cols.fx && (
                        <td className="num" data-label="ارز">
                          {l.currency_code ? `${fa(l.fx_amount ?? 0)} ${l.currency_code}` : '—'}
                        </td>
                      )}
                      {cols.tracking && (
                        <td data-label="پیگیری">
                          {l.tracking_no ? (
                            <>
                              <span className="ltr-cell">{l.tracking_no}</span>
                              {l.tracking_date ? ` — ${formatJalali(l.tracking_date)}` : ''}
                            </>
                          ) : (
                            '—'
                          )}
                        </td>
                      )}
                      <td className="num" data-label="بدهکار">
                        {faAmount(l.debit)}
                      </td>
                      <td className="num" data-label="بستانکار">
                        {faAmount(l.credit)}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
            <tfoot>
              <tr className="rp-total">
                <td className="card-title" colSpan={colCount - 2}>
                  جمعِ بازه
                  {total && (
                    <small className="lr-foot-note">
                      {lineScoped ? ' ردیف‌های منطبق' : ` همه‌ی ${faInt(total.entry_count)} سند`}
                    </small>
                  )}
                  {total && !lineScoped && total.entry_count > 0 && (
                    <CheckChip
                      ok={Math.abs(Number(total.total_debit) - Number(total.total_credit)) < 0.5}
                      okText="تراز است"
                      offText="ناتراز"
                    />
                  )}
                </td>
                <td className="num" data-label="جمعِ بدهکار">
                  {total ? faAmount(total.total_debit) : '…'}
                </td>
                <td className="num" data-label="جمعِ بستانکار">
                  {total ? faAmount(total.total_credit) : '…'}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        {entries.length > 0 && (
          <div className="daybook-more">
            <span className="hint">
              {total
                ? `نمایشِ ${faInt(entries.length)} از ${faInt(total.entry_count)} سند`
                : `${faInt(entries.length)} سند`}
            </span>
            {nextCursor && (
              <button type="button" className="ef-btn-secondary" onClick={loadMore} disabled={moreBusy}>
                {moreBusy ? 'در حال بارگذاری…' : `${faInt(DAYBOOK_PAGE)} سندِ بعدی`}
              </button>
            )}
          </div>
        )}
        {moreError && <p className="hint acc-note acc-note--err">{moreError}</p>}
      </AsyncBlock>
    </SectionCard>
  )
}

// ═════════════ کل، معین و تفصیلی ═════════════

/**
 * دفترِ یک حساب. «کل» همان حساب به‌علاوه‌ی همه‌ی زیرحساب‌هایش است و «تفصیلی» یک تفصیلی در همه‌ی حساب‌ها؛ سرور هر
 * سه را از یک شکلِ داده می‌دهد، پس یک گرید می‌ماند نه سه — دو نمای یک داده ساخته نمی‌شود.
 */
function LedgerGrid({
  token,
  book,
  accountId,
  filters,
  entryOpen,
  onOpenEntry,
}: {
  token: string
  book: Exclude<Book, 'journal'>
  accountId: string
  filters: ReportFilters
  entryOpen: boolean
  onOpenEntry: (id: string) => void
}) {
  const analytic = book === 'analytic'
  const ready = analytic ? !!filters.analyticId : !!accountId
  const ledger = useAsync<GeneralLedger | null>(
    () =>
      !ready
        ? Promise.resolve(null)
        : analytic
          ? fetchAnalyticLedger(token, filters)
          : fetchGeneralLedger(token, accountId, filters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, accountId, analytic, ready, JSON.stringify(filters)],
  )
  const data = ledger.data
  const lines = useMemo(() => data?.lines ?? [], [data])
  const cols = ledgerColumns(lines, book !== 'ledger')
  const period = data ? ledgerPeriod(data) : null
  const bookName = analytic ? 'دفتر تفصیلی' : book === 'general' ? 'دفتر کل' : 'دفتر معین'
  const Icon = analytic ? Layers : book === 'general' ? Library : Landmark

  // ── انتخاب و صفحه‌کلید ──
  const gridRef = useRef<HTMLDivElement>(null)
  const { selected, click, clear } = useRowSelection()
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, lines.length - 1))
  const order = lines.map((l) => l.line_id)
  const picked = lines.filter((l) => selected.has(l.line_id))
  const sums = selectionSums(picked)
  //: دامنه‌ی دیگر یعنی ردیف‌های دیگر؛ انتخابِ قبلی معنا ندارد.
  const scopeKey = JSON.stringify(filters)
  useEffect(() => {
    clear()
    setActiveRow(0)
  }, [scopeKey, clear])
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`lr-line-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(lines.length - 1, i)))
  }
  /** Shift+↑↓: انتخاب از ردیفِ فعلی تا مقصد — اگر لنگری نیست، همین ردیف لنگر می‌شود. */
  const extendTo = (to: number) => {
    if (selected.size === 0) click(order, order[active], { shift: false, ctrl: true })
    click(order, order[to], { shift: true, ctrl: false })
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    //: کشوی سند کیبوردِ خودش را دارد (Esc)؛ این‌جا نباید همان کلید را دوباره بخورد.
    if (entryOpen || lines.length === 0) return
    const last = lines.length - 1
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
        onOpenEntry(lines[active].entry_id)
        break
      case 'Escape':
        if (selected.size > 0) {
          e.preventDefault()
          clear()
        }
        break
    }
  }

  if (!ready)
    return (
      <SectionCard icon={Icon} title={bookName}>
        <p className="hint">
          {analytic
            ? 'یک تفصیلی از سربرگ انتخاب کنید؛ گردشش در همه‌ی حساب‌ها می‌آید.'
            : book === 'general'
              ? 'یک حسابِ کل از سربرگ انتخاب کنید؛ گردشِ همه‌ی زیرحساب‌هایش با هم می‌آید.'
              : 'یک حساب از سربرگ انتخاب کنید تا گردش و مانده‌اش بیاید.'}
        </p>
      </SectionCard>
    )

  const title = data?.account_code ? `${data.account_code} — ${data.account_name}` : bookName
  const optional = (cols.account ? 1 : 0) + (cols.fx ? 1 : 0) + (cols.tracking ? 1 : 0)
  //: ستون‌های متنی (بی شماره‌ی ردیف و سه ستونِ مبلغ) — برچسبِ ردیفِ بالا و پایین رویشان پهن می‌شود.
  const labelSpan = 3 + optional
  const exportCsv = () => {
    if (!data) return
    const { headers, rows } = ledgerCsv(data, cols, formatJalali)
    downloadCsv(`${analytic ? 'daftar-tafsili' : book === 'general' ? 'daftar-kol' : 'daftar-moein'}-${data.account_code ?? 'all'}`, headers, rows)
  }

  return (
    <SectionCard
      icon={Icon}
      title={title}
      description={
        data
          ? `${bookName} · ${filters.dateFrom ? formatJalali(filters.dateFrom) : 'از ابتدا'} تا ${filters.dateTo ? formatJalali(filters.dateTo) : 'امروز'}` +
            (data.fx_totals.length ? ` · ${data.fx_totals.map((t) => `${fa(t.amount)} ${t.currency_code}`).join(' · ')}` : '')
          : bookName
      }
      tip="روی هر ردیف کلیک کنید (یا Enter) تا سندش باز شود. با شماره‌ی ردیف (کلیک، Ctrl، Shift) یا Space و Shift+↑↓ چند ردیف را انتخاب کنید تا جمعشان پایین بیاید."
      actions={
        <button type="button" className="ef-btn-secondary" disabled={!data || data.lines.length === 0} onClick={exportCsv}>
          <Download size={14} /> خروجی CSV
        </button>
      }
    >
      <AsyncBlock loading={ledger.loading && !data} error={data ? null : ledger.error}>
        {data && period && (
          <>
            <div
              ref={gridRef}
              tabIndex={lines.length > 0 ? 0 : -1}
              className={`table-scroll ef-table-wrap rp-scroll lr-scroll${ledger.loading ? ' is-loading' : ''}`}
              onKeyDown={onKey}
              aria-label={`${bookName} — ↑↓ حرکت، Enter سند، Space یا Shift+↑↓ انتخاب، Esc لغوِ انتخاب`}
            >
              {/* کفِ عرض با هر ستونِ اختیاری بزرگ می‌شود تا «شرح» له نشود؛ جا نشد، ستون‌های متنی زیرِ مبلغ‌های میخ‌شده می‌لغزند. */}
              <table
                className="ef-table xl-grid cards-on-mobile rp-table lr-ledger"
                style={{ '--lr-opt': optional } as CSSProperties}
              >
                <colgroup>
                  <col className="lr-c-rowhead" />
                  <col className="lr-c-doc" />
                  <col className="lr-c-date" />
                  {cols.account && <col className="lr-c-account" />}
                  <col />
                  {cols.fx && <col className="lr-c-fx" />}
                  {cols.tracking && <col className="lr-c-track" />}
                  <col className="lr-c-dc" />
                  <col className="lr-c-dc" />
                  <col className="lr-c-bal" />
                </colgroup>
                <thead>
                  <tr>
                    <th className="xl-rowhead" aria-label="انتخاب" />
                    <th>سند</th>
                    <th>تاریخ</th>
                    {cols.account && <th>حساب</th>}
                    <th>شرح</th>
                    {cols.fx && <th className="num">ارز</th>}
                    {cols.tracking && <th>پیگیری</th>}
                    <th className="num lr-pin lr-pin--debit">بدهکار</th>
                    <th className="num lr-pin lr-pin--credit">بستانکار</th>
                    <th className="num lr-pin lr-pin--bal">مانده</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="lr-carry">
                    <td className="xl-rowhead card-hide" />
                    <td className="card-title" colSpan={labelSpan}>
                      مانده‌ی ابتدای دوره
                    </td>
                    <td className="card-hide lr-pin lr-pin--debit" />
                    <td className="card-hide lr-pin lr-pin--credit" />
                    <td className="num lr-pin lr-pin--bal" data-label="مانده">
                      <Amount value={data.opening_balance} />
                    </td>
                  </tr>
                  {lines.length === 0 ? (
                    <tr>
                      <td className="card-full rp-status" colSpan={labelSpan + 4}>
                        {analytic
                          ? 'این تفصیلی در این دامنه هیچ گردشی ندارد.'
                          : book === 'general'
                            ? 'هیچ‌کدام از زیرحساب‌های این سرفصل در این دامنه گردشی ندارند.'
                            : 'این حساب در این دامنه گردشی ندارد.'}
                      </td>
                    </tr>
                  ) : (
                    lines.map((l, i) => {
                      const on = selected.has(l.line_id)
                      return (
                        <tr
                          key={l.line_id}
                          id={`lr-line-${i}`}
                          className={`acc-row--clickable${i === active ? ' is-active' : ''}${on ? ' is-selected' : ''}`}
                          onClick={() => {
                            setActiveRow(i)
                            onOpenEntry(l.entry_id)
                          }}
                        >
                          <td className="xl-rowhead card-hide">
                            <button
                              type="button"
                              tabIndex={-1}
                              className="xl-rowhead-btn"
                              aria-pressed={on}
                              aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}
                              onClick={(ev) => {
                                //: شماره‌ی ردیف فقط انتخاب می‌کند؛ کلیکِ بقیه‌ی ردیف سند را باز می‌کند.
                                ev.stopPropagation()
                                setActiveRow(i)
                                click(order, l.line_id, modsOf(ev))
                              }}
                            >
                              {faInt(i + 1)}
                            </button>
                          </td>
                          <td className="card-title" data-label="سند">
                            {l.entry_number != null ? fa(l.entry_number) : '—'}
                            {l.entry_status === 'temporary' && <span className="lr-badge">موقت</span>}
                          </td>
                          <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                          {cols.account && (
                            <td data-label="حساب" title={`${l.account_code} — ${l.account_name}`}>
                              <span className="ltr-cell">{l.account_code}</span> {l.account_name}
                            </td>
                          )}
                          <td className="card-wide" data-label="شرح" title={l.description || undefined}>
                            {l.description || '—'}
                          </td>
                          {cols.fx && (
                            <td className="num" data-label="ارز">
                              {l.currency_code ? `${fa(l.fx_amount ?? 0)} ${l.currency_code}` : '—'}
                            </td>
                          )}
                          {cols.tracking && (
                            <td data-label="پیگیری">
                              {l.tracking_no ? (
                                <>
                                  <span className="ltr-cell">{l.tracking_no}</span>
                                  {l.tracking_date ? ` — ${formatJalali(l.tracking_date)}` : ''}
                                </>
                              ) : (
                                '—'
                              )}
                            </td>
                          )}
                          <td className="num lr-pin lr-pin--debit" data-label="بدهکار">
                            {faAmount(l.debit)}
                          </td>
                          <td className="num lr-pin lr-pin--credit" data-label="بستانکار">
                            {faAmount(l.credit)}
                          </td>
                          <td className="num lr-pin lr-pin--bal" data-label="مانده">
                            <Amount value={l.balance} />
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
                <tfoot>
                  <tr className="rp-total">
                    <td className="xl-rowhead card-hide" />
                    <td className="card-title" colSpan={labelSpan}>
                      جمعِ بازه و مانده‌ی پایان
                      <small className="lr-foot-note"> {faInt(data.total_lines ?? lines.length)} ردیف</small>
                    </td>
                    <td className="num lr-pin lr-pin--debit" data-label="جمعِ بدهکار">
                      {faAmount(period.debit)}
                    </td>
                    <td className="num lr-pin lr-pin--credit" data-label="جمعِ بستانکار">
                      {faAmount(period.credit)}
                    </td>
                    <td className="num lr-pin lr-pin--bal" data-label="مانده‌ی پایان">
                      <Amount value={data.closing_balance} />
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
            {lines.length > 0 && (
              <p className="ab-keys lr-keys">
                <kbd>↑</kbd>
                <kbd>↓</kbd> ردیف · <kbd>Enter</kbd> یا کلیک سند · <kbd>Space</kbd> یا <kbd>Shift+↑↓</kbd> یا شماره‌ی ردیف
                انتخاب · <kbd>Esc</kbd> لغوِ انتخاب
              </p>
            )}
          </>
        )}
      </AsyncBlock>
    </SectionCard>
  )
}

