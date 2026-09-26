import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpenCheck,
  Download,
  FileSpreadsheet,
  Landmark,
  Layers,
  Library,
  Printer,
  Wallet,
} from 'lucide-react'
import {
  fetchChartAccounts,
  fetchAnalyticLedger,
  fetchGeneralLedger,
  fetchAllJournalEntries,
  fetchJournalEntriesPage,
  fetchJournalEntriesSummary,
  fetchLegalBook,
  type GeneralLedger,
  type JournalEntryRecord,
  type ReportFilters,
} from '../../api'
import { EntryCard } from '../../components/EntryCard'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SectionCard } from '../../components/SectionCard'
import { SearchField } from '../../components/form/FormKit'
import { Pager, usePagination } from '../../components/Pager'
import { levelOf } from '../../lib/balanceReport'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  AsyncBlock,
  BalanceFooter,
  Metric,
  OpsPage,
  RangeBar,
  StatusChip,
  fa,
  faAmount,
  faInt,
  useAsync,
  useRange,
} from './kit'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * چهار گزارشِ پایه‌ی دفترداری.
 *
 * سه‌تای اولش نمایشِ همان یک دادهٔ گردش‌اند در سه سطحِ ریزشدن — تراز (خلاصه)، دفتر
 * (سندبه‌سند)، دفاترِ قانونی (ردیف‌به‌ردیف با چیدمانِ رسمی). چهارمی مالیات است که
 * دادهٔ خودش را دارد. هر چهار تا خروجیِ CSV می‌دهند چون هر کدامشان دیر یا زود باید
 * جایی بیرون از برنامه تحویل شوند.
 */

/** «گزارش ترازها» فایلِ خودش را دارد (تمِ اکسلی)؛ از این‌جا هم صادر می‌شود تا واردکننده‌ها دست نخورند. */
export { BalanceReportPage } from './BalanceReportPage'

// ═══════════════════════ ۲) گزارش دفتر ═══════════════════════

/** سه دفترِ حسابداری، به همان ترتیبی که در عمل خوانده می‌شوند. */
type Book = 'journal' | 'general' | 'ledger' | 'analytic'

export function LedgerReportPage({ token }: { token: string }) {
  const range = useRange('month')
  const [book, setBook] = useState<Book>('journal')
  const [filters, setFilters] = useState<ReportFilters>({})
  const [accountId, setAccountId] = useState('')
  //: انتخابِ دفترِ کل جداست، وگرنه جابه‌جا شدن بینِ دو تب یک شناسه‌ی نامعتبر را
  //: به انتخابگرِ دیگر می‌برد و کاربر یک `select`ِ خالی می‌بیند بی‌آنکه بداند چرا.
  const [generalId, setGeneralId] = useState('')
  const [search, setSearch] = useState('')

  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const postable = useMemo(
    () =>
      (accounts.data ?? [])
        .filter((a) => !a.is_group)
        .sort((a, b) => a.code.localeCompare(b.code)),
    [accounts.data],
  )
  //: حساب‌های سطحِ «کل» — همان عددی که `LEVEL_OPTIONS`ِ گزارش ترازها به کار می‌برد،
  //: با همان `levelOf`. سطح از عمقِ درخت می‌آید نه طولِ کد، چون چارت یکدست نیست:
  //: دارایی‌ها ۱ ← ۱۱ ← ۱۱۰۱ دارند و هزینه‌ها ۵ ← ۵۱۰۱.
  const generalAccounts = useMemo(() => {
    const list = accounts.data ?? []
    const byId = new Map(list.map((a) => [a.id, a]))
    return list
      .filter((a) => levelOf(a, byId) === 2)
      .sort((a, b) => a.code.localeCompare(b.code))
  }, [accounts.data])
  //: بازه و فیلترها یک دامنه‌اند و با هم به سرور می‌روند — همان چیزی که تراز هم
  //: می‌فرستد، تا دو گزارش نتوانند از هم جدا بیفتند.
  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }

  //: ردیفِ سند فقط شناسه‌ی حساب دارد؛ نام از چارت می‌آید تا دفتر خوانا باشد.
  const accountNames = useMemo(
    () => new Map((accounts.data ?? []).map((a) => [a.id, `${a.code} — ${a.name}`])),
    [accounts.data],
  )

  return (
    <OpsPage
      canvas
      icon={BookOpenCheck}
      title="گزارش دفتر"
      description="سه دفترِ حسابداری: روزنامه (همه‌ی اسناد به‌ترتیبِ تاریخ)، کل (گردشِ یک سرفصل با همه‌ی زیرحساب‌هایش) و معین (گردشِ یک حساب با مانده‌ی دوره‌ای)."
      head={
        <div className="cc-head">
          <div className="cc-tabs">
            <button
              type="button"
              className={book === 'journal' ? 'is-active' : ''}
              onClick={() => setBook('journal')}
            >
              <BookOpenCheck size={14} /> دفتر روزنامه
            </button>
            <button
              type="button"
              className={book === 'general' ? 'is-active' : ''}
              onClick={() => setBook('general')}
            >
              <Library size={14} /> دفتر کل
            </button>
            <button
              type="button"
              className={book === 'ledger' ? 'is-active' : ''}
              onClick={() => setBook('ledger')}
            >
              <Landmark size={14} /> دفتر معین
            </button>
            <button
              type="button"
              className={book === 'analytic' ? 'is-active' : ''}
              onClick={() => setBook('analytic')}
            >
              <Layers size={14} /> دفتر تفصیلی
            </button>
          </div>
          <RangeBar
            range={range}
            extra={
              book === 'journal' ? (
                <>
                  {/* سرور روی شماره، عطف، شماره‌ی فرعی و شرحِ سند می‌گردد، نه روی حساب.
                      برچسبِ قبلی «نام یا کدِ حساب» بود و جست‌وجوی حساب بی‌صدا چیزی پیدا
                      نمی‌کرد. گردشِ یک حساب جایش «دفتر معین» است. */}
                  <SearchField
                    value={search}
                    onChange={setSearch}
                    placeholder="شماره یا شرحِ سند"
                    label="جست‌وجوی سند"
                  />
                  <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
                </>
              ) : book === 'general' ? (
                <>
                  <label className="acc-inline-field">
                    حسابِ کل
                    <SearchSelect value={generalId} onChange={(e) => setGeneralId(e.target.value)}>
                      <option value="">— انتخابِ حسابِ کل —</option>
                      {generalAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </SearchSelect>
                  </label>
                  <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
                </>
              ) : book === 'ledger' ? (
                <>
                  <label className="acc-inline-field">
                    حساب
                    <SearchSelect value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                      <option value="">— انتخابِ حساب —</option>
                      {postable.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </SearchSelect>
                  </label>
                  <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
                </>
              ) : (
                <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
              )
            }
          />
          <SavedViewBar
            token={token}
            viewKey="accounting.ledger"
            filters={filters}
            range={range}
            setFilters={setFilters}
          />
        </div>
      }
    >
      {book === 'journal' ? (
        <DaybookCard token={token} filters={scope} search={search} accountNames={accountNames} />
      ) : book === 'general' ? (
        <SubsidiaryCard token={token} accountId={generalId} filters={scope} rollup />
      ) : book === 'analytic' ? (
        <SubsidiaryCard token={token} accountId="" filters={scope} analytic />
      ) : (
        <SubsidiaryCard token={token} accountId={accountId} filters={scope} />
      )}
    </OpsPage>
  )
}

/** اسنادِ هر صفحه‌ی روزنامه. سند با همه‌ی ردیف‌هایش می‌آید، پس ۵۰ سند چند صد ردیف است. */
const DAYBOOK_PAGE = 50

/**
 * دفتر روزنامه — صفحه‌به‌صفحه از سرور، با جمعِ کلِ دامنه از سرور.
 *
 * پیش از این تا ۲۰۰ سند می‌گرفت و بقیه را **بی‌صدا** نمی‌آورد. در بازه‌ی یک‌ساله یعنی
 * ماه‌های آخر اصلاً دیده نمی‌شدند، و «جمعِ گردشِ بازه» جمعِ همان ۲۰۰ سند بود. حالا
 * صفحه‌ها با کرسرِ سرور می‌آیند و جمع از `/summary` است. عددِ بالای کارت هرگز از
 * ردیف‌های بارگذاری‌شده ساخته نمی‌شود.
 */
function DaybookCard({
  token,
  filters,
  search,
  accountNames,
}: {
  token: string
  filters: ReportFilters
  search: string
  accountNames: Map<string, string>
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

  //: صفحه‌های بعدی مالِ **همین بارِ** این دامنه‌اند، نه مقدارِ دامنه. کلید فقط مقدار را
  //: می‌گوید: فیلتر را عوض کنی و برگردی، کلید همان می‌شود و صفحه‌های قدیمی زنده
  //: می‌شدند. در رندرِ اولِ بعد از برگشت، `first.data` هنوز مالِ دامنه‌ی قبلی بود و
  //: کنارِ آن صفحه‌ها سندِ تکراری می‌ساخت. مرورگرِ واقعی همین را گرفت. `visit` با هر
  //: عوض‌شدنِ کلید شیءِ تازه است، حتی وقتی کلید به مقدارِ قبلی برگردد.
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
      const page = await fetchJournalEntriesPage(token, filters, {
        q: q || undefined,
        cursor: nextCursor,
        limit: DAYBOOK_PAGE,
      })
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
  //: با فیلترِ ردیفی، سند کامل نشان داده می‌شود ولی جمع فقط ردیف‌های منطبق است. برچسب
  //: همین را می‌گوید تا کسی جمع را با ردیف‌های دیده‌شده مقایسه نکند و گیج نشود.
  const lineScoped = Boolean(filters.costCenterId || filters.analyticId)

  return (
    <SectionCard
      icon={BookOpenCheck}
      title="دفتر روزنامه"
      description={
        total
          ? `${faInt(total.entry_count)} سند · ${faInt(total.line_count)} ردیف${lineScoped ? 'ِ منطبق' : ''}`
          : 'هر سند با ردیف‌هایش'
      }
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
      {total && (
        <div className="cc-summary daybook-summary">
          <Metric
            icon={<Wallet size={14} />}
            label={lineScoped ? 'بدهکارِ ردیف‌های منطبق' : 'جمعِ بدهکار'}
            value={fa(Number(total.total_debit))}
            tone="in"
          />
          <Metric
            icon={<Wallet size={14} />}
            label={lineScoped ? 'بستانکارِ ردیف‌های منطبق' : 'جمعِ بستانکار'}
            value={fa(Number(total.total_credit))}
            tone="out"
          />
        </div>
      )}
      {summary.error && <p className="hint acc-note acc-note--err">جمعِ دفتر نیامد: {summary.error}</p>}
      {csvError && <p className="hint acc-note acc-note--err">خروجی ساخته نشد: {csvError}</p>}
      <AsyncBlock
        loading={first.loading}
        error={first.error}
        empty={entries.length === 0}
        emptyText="در بازه و فیلترِ انتخاب‌شده سندی یافت نشد."
      >
        {/* همان `EntryCard`ی که درایوِ drill-down رندر می‌کند — یک نمای یک داده.
            پیش از این این جدول فقط این‌جا بود و وقتی «ردیفِ دفتر → سند» لازم شد،
            وسوسه‌ی نوشتنِ نسخه‌ی دومش پیش آمد. */}
        {entries.map((e) => (
          <EntryCard key={e.id} entry={e} accountNames={accountNames} />
        ))}
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
        {moreError && <p className="hint acc-note acc-note--err">{moreError}</p>}
      </AsyncBlock>
    </SectionCard>
  )
}

/**
 * دفترِ یک حساب. با `rollup` همان حساب به‌علاوه‌ی همه‌ی زیرحساب‌هایش را می‌آورد —
 * یعنی «دفتر کل». سرور هر دو حالت را از یک نقطه می‌دهد، پس این‌جا هم یک کارت
 * می‌ماند نه دو: دو نمای یک داده ساخته نمی‌شود.
 */
function SubsidiaryCard({
  token,
  accountId,
  filters,
  rollup = false,
  analytic = false,
}: {
  token: string
  accountId: string
  filters: ReportFilters
  rollup?: boolean
  /** دفترِ تفصیلی: حساب اختیاری است و دامنه را `filters.analyticId` تعیین می‌کند. */
  analytic?: boolean
}) {
  const [entryId, setEntryId] = useState<string | null>(null)
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
  const pg = usePagination(data?.lines ?? [], 20)
  const bookName = analytic ? 'دفتر تفصیلی' : rollup ? 'دفتر کل' : 'دفتر معین'
  const Icon = analytic ? Layers : rollup ? Library : Landmark

  //: ستون فقط وقتی می‌آید که ردیفی مقدار داشته باشد — جدولِ همیشه‌هشت‌ستونه‌ای که
  //: نیمش خط تیره است، خواندن را سخت می‌کند نه آسان.
  const hasFx = (data?.lines ?? []).some((l) => l.currency_code)
  const hasTracking = (data?.lines ?? []).some((l) => l.tracking_no)
  //: در دفترِ تفصیلی ردیف‌ها از حساب‌های مختلف‌اند، پس ستونِ حساب لازم است.
  const showAccount = rollup || analytic

  if (!ready)
    return (
      <SectionCard icon={Icon} title={bookName}>
        <p className="hint">
          {analytic
            ? 'برای دیدنِ دفترِ تفصیلی، از نوارِ فیلتر یک تفصیلی انتخاب کنید؛ گردشش در همه‌ی حساب‌ها می‌آید.'
            : rollup
              ? 'برای دیدنِ دفترِ کل، یک حسابِ کل انتخاب کنید؛ گردشِ همه‌ی زیرحساب‌هایش با هم می‌آید.'
              : 'برای دیدنِ دفترِ معین، یک حساب انتخاب کنید.'}
        </p>
      </SectionCard>
    )

  const title = data?.account_code ? `${data.account_code} — ${data.account_name}` : bookName

  return (
    <SectionCard
      icon={Icon}
      title={title}
      description={
        data
          ? `مانده‌ی ابتدای دوره ${fa(data.opening_balance)} · مانده‌ی پایان ${fa(data.closing_balance)}` +
            (data.fx_totals.length
              ? ` · ${data.fx_totals.map((t) => `${fa(t.amount)} ${t.currency_code}`).join(' · ')}`
              : '')
          : undefined
      }
      actions={
        <button
          type="button"
          className="ef-btn-secondary"
          disabled={!data || data.lines.length === 0}
          onClick={() =>
            data &&
            downloadCsv(
              `${analytic ? 'daftar-tafsili' : rollup ? 'daftar-kol' : 'daftar-moein'}-${data.account_code ?? 'all'}`,
              [
                'شماره سند',
                'تاریخ',
                ...(showAccount ? ['حساب'] : []),
                'شرح',
                ...(hasFx ? ['ارز', 'مبلغ ارزی'] : []),
                ...(hasTracking ? ['شماره پیگیری', 'تاریخ پیگیری'] : []),
                'بدهکار',
                'بستانکار',
                'مانده',
              ],
              data.lines.map((l) => [
                l.entry_number ?? '',
                formatJalali(l.entry_date),
                ...(showAccount ? [`${l.account_code} — ${l.account_name}`] : []),
                l.description,
                ...(hasFx ? [l.currency_code ?? '', l.fx_amount ? Number(l.fx_amount) : ''] : []),
                ...(hasTracking
                  ? [l.tracking_no ?? '', l.tracking_date ? formatJalali(l.tracking_date) : '']
                  : []),
                Number(l.debit),
                Number(l.credit),
                Number(l.balance),
              ]),
            )
          }
        >
          <Download size={13} /> خروجی CSV
        </button>
      }
    >
      <AsyncBlock
        loading={ledger.loading}
        error={ledger.error}
        empty={(data?.lines.length ?? 0) === 0}
        emptyText={
          analytic
            ? 'این تفصیلی در این دامنه هیچ گردشی ندارد.'
            : rollup
              ? 'هیچ‌کدام از زیرحساب‌های این سرفصل در بازه‌ی انتخابی گردشی ندارند.'
              : 'این حساب در بازه‌ی انتخابی گردشی ندارد.'
        }
      >
        <p className="hint">روی هر ردیف کلیک کنید تا سندش باز شود.</p>
        <div className="table-scroll ef-table-wrap">
          <table className="ef-table cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>سند</th>
                <th>تاریخ</th>
                {/* در دفترِ معین همه‌ی ردیف‌ها یک حساب‌اند و این ستون فقط تکرار است. */}
                {showAccount && <th>حساب</th>}
                <th>شرح</th>
                {hasFx && <th>ارز</th>}
                {hasTracking && <th>پیگیری</th>}
                <th>بدهکار</th>
                <th>بستانکار</th>
                <th>مانده</th>
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((l) => (
                <tr
                  key={l.line_id}
                  className="acc-row--clickable"
                  onClick={() => setEntryId(l.entry_id)}
                >
                  <td className="card-title" data-label="سند">
                    {fa(l.entry_number ?? 0)}
                  </td>
                  <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                  {showAccount && (
                    <td data-label="حساب">
                      <span dir="ltr">{l.account_code}</span> — {l.account_name}
                    </td>
                  )}
                  <td data-label="شرح">{l.description || '—'}</td>
                  {hasFx && (
                    <td data-label="ارز" className="num">
                      {l.currency_code ? `${fa(l.fx_amount ?? 0)} ${l.currency_code}` : '—'}
                    </td>
                  )}
                  {hasTracking && (
                    <td data-label="پیگیری">
                      {l.tracking_no ? (
                        <>
                          <span dir="ltr">{l.tracking_no}</span>
                          {l.tracking_date ? ` — ${formatJalali(l.tracking_date)}` : ''}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                  )}
                  <td data-label="بدهکار" className="num">
                    {faAmount(l.debit)}
                  </td>
                  <td data-label="بستانکار" className="num">
                    {faAmount(l.credit)}
                  </td>
                  <td data-label="مانده" className="num">
                    {fa(l.balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      </AsyncBlock>

      {entryId && (
        <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />
      )}
    </SectionCard>
  )
}

// ═════════════ ۳) مالیات بر ارزش افزوده ═════════════

/** «مالیات بر ارزش افزوده» فایلِ خودش را دارد (تمِ اکسلی)؛ از این‌جا هم صادر می‌شود تا واردکننده‌ها دست نخورند. */
export { VatPage } from './VatPage'

// ═════════════ ۴) دفاتر تجارت الکترونیک ═════════════

export function LegalBooksPage({ token }: { token: string }) {
  const range = useRange('year')
  const book = useAsync(
    () =>
      range.from && range.to
        ? fetchLegalBook(token, range.from, range.to)
        : fetchLegalBook(token, '1900-01-01', todayIso()),
    [token, range.from, range.to],
  )
  const data = book.data
  const rows = data?.rows ?? []
  const pg = usePagination(rows, 40)

  function exportCsv() {
    downloadCsv(
      `dafater-${range.from ?? 'all'}`,
      ['ردیف', 'شماره سند', 'تاریخ', 'کد حساب', 'نام حساب', 'شرح', 'بدهکار', 'بستانکار', 'وضعیت'],
      rows.map((r, i) => [
        i + 1,
        r.entry_number ?? '',
        formatJalali(r.entry_date),
        r.account_code,
        r.account_name,
        r.description,
        Number(r.debit),
        Number(r.credit),
        r.voided ? 'باطل' : r.status === 'permanent' ? 'دائم' : 'موقت',
      ]),
    )
  }

  return (
    <OpsPage
      canvas
      icon={FileSpreadsheet}
      title="دفاتر تجارت الکترونیک"
      description="ردیف‌های دفترِ روزنامه با چیدمانِ دفاترِ قانونی — آماده‌ی خروجی و بارگذاری در سامانه. اسنادِ باطل و معکوسشان هر دو می‌آیند، چون دفترِ قانونی باید اصلاح را هم نشان دهد."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<FileSpreadsheet size={14} />} label="ردیفِ دفتر" value={faInt(rows.length)} />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ بدهکار"
              value={data ? fa(data.total_debit) : '—'}
              tone="in"
            />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ بستانکار"
              value={data ? fa(data.total_credit) : '—'}
              tone="out"
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={FileSpreadsheet}
        title="دفترِ روزنامه (قانونی)"
        description="یک ردیف به‌ازای هر ردیفِ سند، به‌ترتیبِ تاریخ و شماره."
        actions={
          <>
            <button type="button" className="ef-btn-secondary" onClick={exportCsv} disabled={rows.length === 0}>
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" onClick={() => window.print()}>
              <Printer size={14} /> چاپ
            </button>
          </>
        }
      >
        <AsyncBlock
          loading={book.loading}
          error={book.error}
          empty={rows.length === 0}
          emptyText="در این بازه ردیفی ثبت نشده."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="ef-table cards-on-mobile acc-table acc-table--wide">
              <thead>
                <tr>
                  <th>سند</th>
                  <th>تاریخ</th>
                  <th>کدِ حساب</th>
                  <th>نامِ حساب</th>
                  <th>شرح</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r, i) => (
                  <tr key={`${r.entry_id}-${i}`} className={r.voided ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="سند">
                      {fa(r.entry_number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(r.entry_date)}</td>
                    <td data-label="کدِ حساب" dir="ltr">
                      {r.account_code}
                    </td>
                    <td data-label="نامِ حساب">{r.account_name}</td>
                    <td data-label="شرح">{r.description || '—'}</td>
                    <td data-label="بدهکار" className="num">
                      {faAmount(r.debit)}
                    </td>
                    <td data-label="بستانکار" className="num">
                      {faAmount(r.credit)}
                    </td>
                    <td data-label="وضعیت">
                      <StatusChip status={r.status} voided={r.voided} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
          {data && (
            <BalanceFooter debit={Number(data.total_debit)} credit={Number(data.total_credit)} />
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
