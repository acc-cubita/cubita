import { useMemo, useState } from 'react'
import {
  BookOpenCheck,
  Download,
  FileSpreadsheet,
  Landmark,
  Percent,
  Printer,
  Scale,
  Search,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import {
  fetchAccountBalances,
  fetchChartAccounts,
  fetchGeneralLedger,
  fetchJournalEntriesFiltered,
  fetchLegalBook,
  fetchVatReport,
  type BalanceRow,
  type ChartAccount,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { Pager, usePagination } from '../../components/Pager'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, isoToJalali, jalaaliMonthLength, jalaliToIso, todayIso } from '../../lib/jalali'
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
  sourceLabel,
  useAsync,
  useRange,
} from './kit'

/**
 * چهار گزارشِ پایه‌ی دفترداری.
 *
 * سه‌تای اولش نمایشِ همان یک دادهٔ گردش‌اند در سه سطحِ ریزشدن — تراز (خلاصه)، دفتر
 * (سندبه‌سند)، دفاترِ قانونی (ردیف‌به‌ردیف با چیدمانِ رسمی). چهارمی مالیات است که
 * دادهٔ خودش را دارد. هر چهار تا خروجیِ CSV می‌دهند چون هر کدامشان دیر یا زود باید
 * جایی بیرون از برنامه تحویل شوند.
 */

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

/** سطحِ حساب در چارت: ۱ = گروه، ۲ = کل، ۳ = معین، ۴+ = تفصیلی. */
function levelOf(account: ChartAccount, byId: Map<string, ChartAccount>): number {
  let level = 1
  let node = account
  const seen = new Set<string>()
  while (node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    node = parent
    level += 1
  }
  return level
}

/** جدِ حساب در سطحِ داده‌شده — پایه‌ی تجمیعِ تراز در سطحِ کل/معین. */
function ancestorAtLevel(
  account: ChartAccount,
  byId: Map<string, ChartAccount>,
  level: number,
): ChartAccount {
  let node = account
  const seen = new Set<string>()
  while (levelOf(node, byId) > level && node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    node = parent
  }
  return node
}

// ═══════════════════════ ۱) گزارش ترازها ═══════════════════════

type Columns = 2 | 4 | 6 | 8

const COLUMN_OPTIONS: { value: Columns; label: string; hint: string }[] = [
  { value: 2, label: 'دو ستونی', hint: 'فقط مانده‌ی پایانِ دوره' },
  { value: 4, label: 'چهار ستونی', hint: 'گردش و مانده‌ی دوره' },
  { value: 6, label: 'شش ستونی', hint: 'افتتاحیه، گردش، مانده' },
  { value: 8, label: 'هشت ستونی', hint: 'افتتاحیه، گردش، جمع، مانده' },
]

const LEVEL_OPTIONS = [
  { value: 2, label: 'کل' },
  { value: 3, label: 'معین' },
  { value: 0, label: 'تفصیلی (سطحِ آخر)' },
]

export function BalanceReportPage({ token }: { token: string }) {
  const range = useRange('year')
  const [columns, setColumns] = useState<Columns>(6)
  const [level, setLevel] = useState(0)
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const balances = useAsync(
    () => fetchAccountBalances(token, range.from, range.to),
    [token, range.from, range.to],
  )

  /** تراز در هر سطحی، جمعِ همان ردیف‌های سطحِ آخر است — پس تجمیع اینجا انجام می‌شود
   *  نه با کوئریِ جدا. یک منبعِ عدد برای هر چهار حالتِ ستونی. */
  const rows = useMemo(() => {
    const list = accounts.data ?? []
    const byId = new Map(list.map((a) => [a.id, a]))
    const source = balances.data ?? []
    if (level === 0) return source
    const totals = new Map<string, BalanceRow>()
    for (const row of source) {
      const leaf = byId.get(row.account_id)
      if (!leaf) continue
      const target = ancestorAtLevel(leaf, byId, level)
      const bucket = totals.get(target.id)
      if (!bucket) {
        totals.set(target.id, {
          ...row,
          account_id: target.id,
          account_code: target.code,
          account_name: target.name,
          account_type: target.type,
          parent_id: target.parent_id,
        })
      } else {
        bucket.opening_debit = String(Number(bucket.opening_debit) + Number(row.opening_debit))
        bucket.opening_credit = String(Number(bucket.opening_credit) + Number(row.opening_credit))
        bucket.period_debit = String(Number(bucket.period_debit) + Number(row.period_debit))
        bucket.period_credit = String(Number(bucket.period_credit) + Number(row.period_credit))
        bucket.closing_debit = String(Number(bucket.closing_debit) + Number(row.closing_debit))
        bucket.closing_credit = String(Number(bucket.closing_credit) + Number(row.closing_credit))
      }
    }
    // مانده‌ی تجمیع‌شده باید *خالص* بشود، وگرنه یک سرفصل هم بدهکار و هم بستانکار
    // نشان می‌داد و جمعِ ستونِ مانده دو برابرِ واقعیت می‌شد.
    return [...totals.values()]
      .map((r) => {
        const net = Number(r.closing_debit) - Number(r.closing_credit)
        const openNet = Number(r.opening_debit) - Number(r.opening_credit)
        return {
          ...r,
          opening_debit: String(openNet > 0 ? openNet : 0),
          opening_credit: String(openNet < 0 ? -openNet : 0),
          closing_debit: String(net > 0 ? net : 0),
          closing_credit: String(net < 0 ? -net : 0),
        }
      })
      .sort((a, b) => a.account_code.localeCompare(b.account_code))
  }, [accounts.data, balances.data, level])

  const sum = (key: keyof BalanceRow) => rows.reduce((s, r) => s + Number(r[key] as string), 0)
  const periodDebit = sum('period_debit')
  const periodCredit = sum('period_credit')

  function exportCsv() {
    const headers = ['کد', 'نام حساب', 'نوع']
    if (columns >= 6) headers.push('افتتاحیه بدهکار', 'افتتاحیه بستانکار')
    if (columns >= 4) headers.push('گردش بدهکار', 'گردش بستانکار')
    if (columns >= 8) headers.push('جمع بدهکار', 'جمع بستانکار')
    headers.push('مانده بدهکار', 'مانده بستانکار')
    downloadCsv(
      `tarazha-${range.from ?? 'all'}`,
      headers,
      rows.map((r) => {
        const cells: (string | number)[] = [r.account_code, r.account_name, TYPE_LABELS[r.account_type] ?? r.account_type]
        if (columns >= 6) cells.push(Number(r.opening_debit), Number(r.opening_credit))
        if (columns >= 4) cells.push(Number(r.period_debit), Number(r.period_credit))
        if (columns >= 8)
          cells.push(
            Number(r.opening_debit) + Number(r.period_debit),
            Number(r.opening_credit) + Number(r.period_credit),
          )
        cells.push(Number(r.closing_debit), Number(r.closing_credit))
        return cells
      }),
    )
  }

  const pg = usePagination(rows, 25)

  return (
    <OpsPage
      icon={Scale}
      title="گزارش ترازها"
      description="تراز آزمایشی در چهار قالبِ استاندارد و سه سطحِ حساب. همان یک داده است؛ ستون‌ها تعیین می‌کنند چقدرش را ببینید."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <>
                <label className="acc-inline-field">
                  ستون‌ها
                  <select
                    value={columns}
                    onChange={(e) => setColumns(Number(e.target.value) as Columns)}
                  >
                    {COLUMN_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label} — {o.hint}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="acc-inline-field">
                  سطح
                  <select value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                    {LEVEL_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            }
          />
          <div className="cc-summary">
            <Metric icon={<Scale size={14} />} label="ردیف" value={faInt(rows.length)} />
            <Metric icon={<Wallet size={14} />} label="گردشِ بدهکار" value={fa(periodDebit)} tone="in" />
            <Metric icon={<Wallet size={14} />} label="گردشِ بستانکار" value={fa(periodCredit)} tone="out" />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Scale}
        title="تراز"
        description={
          range.from
            ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())}`
            : 'از ابتدای دفتر'
        }
        actions={
          <>
            <button type="button" onClick={exportCsv} disabled={rows.length === 0}>
              <Download size={13} /> خروجی CSV
            </button>
            <button type="button" onClick={() => window.print()}>
              <Printer size={13} /> چاپ
            </button>
          </>
        }
      >
        <AsyncBlock
          loading={accounts.loading || balances.loading}
          error={accounts.error ?? balances.error}
          empty={rows.length === 0}
          emptyText="در این بازه گردشی ثبت نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table acc-table--wide">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نامِ حساب</th>
                  {columns >= 6 && (
                    <>
                      <th>افتتاحیه بد</th>
                      <th>افتتاحیه بس</th>
                    </>
                  )}
                  {columns >= 4 && (
                    <>
                      <th>گردش بد</th>
                      <th>گردش بس</th>
                    </>
                  )}
                  {columns >= 8 && (
                    <>
                      <th>جمع بد</th>
                      <th>جمع بس</th>
                    </>
                  )}
                  <th>مانده بد</th>
                  <th>مانده بس</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.account_id}>
                    <td className="card-title" data-label="کد" dir="ltr">
                      {r.account_code}
                    </td>
                    <td data-label="نامِ حساب">{r.account_name}</td>
                    {columns >= 6 && (
                      <>
                        <td data-label="افتتاحیه بد" className="num">{faAmount(r.opening_debit)}</td>
                        <td data-label="افتتاحیه بس" className="num">{faAmount(r.opening_credit)}</td>
                      </>
                    )}
                    {columns >= 4 && (
                      <>
                        <td data-label="گردش بد" className="num">{faAmount(r.period_debit)}</td>
                        <td data-label="گردش بس" className="num">{faAmount(r.period_credit)}</td>
                      </>
                    )}
                    {columns >= 8 && (
                      <>
                        <td data-label="جمع بد" className="num">
                          {faAmount(Number(r.opening_debit) + Number(r.period_debit))}
                        </td>
                        <td data-label="جمع بس" className="num">
                          {faAmount(Number(r.opening_credit) + Number(r.period_credit))}
                        </td>
                      </>
                    )}
                    <td data-label="مانده بد" className="num">{faAmount(r.closing_debit)}</td>
                    <td data-label="مانده بس" className="num">{faAmount(r.closing_credit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
          <BalanceFooter debit={periodDebit} credit={periodCredit} />
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════════ ۲) گزارش دفتر ═══════════════════════

type Book = 'journal' | 'ledger'

export function LedgerReportPage({ token }: { token: string }) {
  const range = useRange('month')
  const [book, setBook] = useState<Book>('journal')
  const [accountId, setAccountId] = useState('')
  const [search, setSearch] = useState('')

  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const postable = useMemo(
    () =>
      (accounts.data ?? [])
        .filter((a) => !a.is_group)
        .sort((a, b) => a.code.localeCompare(b.code)),
    [accounts.data],
  )
  //: ردیفِ سند فقط شناسه‌ی حساب دارد؛ نام از چارت می‌آید تا دفتر خوانا باشد.
  const accountNames = useMemo(
    () => new Map((accounts.data ?? []).map((a) => [a.id, `${a.code} — ${a.name}`])),
    [accounts.data],
  )

  return (
    <OpsPage
      icon={BookOpenCheck}
      title="گزارش دفتر"
      description="دفترِ روزنامه (همه‌ی اسناد به‌ترتیبِ تاریخ) و دفترِ معین (گردشِ یک حساب با مانده‌ی دوره‌ای)."
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
              className={book === 'ledger' ? 'is-active' : ''}
              onClick={() => setBook('ledger')}
            >
              <Landmark size={14} /> دفتر معین
            </button>
          </div>
          <RangeBar
            range={range}
            extra={
              book === 'journal' ? (
                <label className="acc-search">
                  <Search size={14} />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="شماره یا شرحِ سند"
                  />
                </label>
              ) : (
                <label className="acc-inline-field">
                  حساب
                  <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                    <option value="">— انتخابِ حساب —</option>
                    {postable.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </option>
                    ))}
                  </select>
                </label>
              )
            }
          />
        </div>
      }
    >
      {book === 'journal' ? (
        <DaybookCard
          token={token}
          from={range.from}
          to={range.to}
          search={search}
          accountNames={accountNames}
        />
      ) : (
        <SubsidiaryCard token={token} accountId={accountId} from={range.from} to={range.to} />
      )}
    </OpsPage>
  )
}

function DaybookCard({
  token,
  from,
  to,
  search,
  accountNames,
}: {
  token: string
  from?: string
  to?: string
  search: string
  accountNames: Map<string, string>
}) {
  const list = useAsync(
    () =>
      fetchJournalEntriesFiltered(token, {
        dateFrom: from,
        dateTo: to,
        q: search || undefined,
        limit: 200,
      }),
    [token, from, to, search],
  )
  const entries = list.data ?? []
  const pg = usePagination(entries, 12)

  function exportCsv() {
    downloadCsv(
      `daftar-rooznameh-${from ?? 'all'}`,
      ['شماره سند', 'تاریخ', 'شرح سند', 'حساب', 'شرح ردیف', 'بدهکار', 'بستانکار'],
      entries.flatMap((e) =>
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
  }

  const debit = entries.reduce(
    (s, e) => s + e.lines.reduce((t, l) => t + Number(l.debit), 0),
    0,
  )

  return (
    <SectionCard
      icon={BookOpenCheck}
      title="دفتر روزنامه"
      description={`${faInt(entries.length)} سند — هر سند با ردیف‌هایش`}
      actions={
        <button type="button" onClick={exportCsv} disabled={entries.length === 0}>
          <Download size={13} /> خروجی CSV
        </button>
      }
    >
      <AsyncBlock
        loading={list.loading}
        error={list.error}
        empty={entries.length === 0}
        emptyText="در این بازه سندی نیست."
      >
        {pg.pageItems.map((e) => (
          <div className="acc-day" key={e.id}>
            <h4 className="acc-day-head">
              سند {fa(e.number ?? 0)} — {formatJalali(e.entry_date)}
              <span>
                <StatusChip status={e.status} voided={!!e.voided_at} /> {sourceLabel(e.source_type)}
              </span>
            </h4>
            {e.description && <p className="hint">{e.description}</p>}
            <div className="table-scroll">
              <table className="cards-on-mobile acc-table">
                <thead>
                  <tr>
                    <th>حساب</th>
                    <th>شرح ردیف</th>
                    <th>بدهکار</th>
                    <th>بستانکار</th>
                  </tr>
                </thead>
                <tbody>
                  {e.lines.map((l) => (
                    <tr key={l.id}>
                      <td className="card-title" data-label="حساب">
                        {accountNames.get(l.account_id) ?? '—'}
                      </td>
                      <td data-label="شرح ردیف">{l.description || '—'}</td>
                      <td data-label="بدهکار" className="num">
                        {faAmount(l.debit)}
                      </td>
                      <td data-label="بستانکار" className="num">
                        {faAmount(l.credit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        <p className="hint">جمعِ گردشِ بازه: {fa(debit)}</p>
      </AsyncBlock>
    </SectionCard>
  )
}

function SubsidiaryCard({
  token,
  accountId,
  from,
  to,
}: {
  token: string
  accountId: string
  from?: string
  to?: string
}) {
  const ledger = useAsync(
    () => (accountId ? fetchGeneralLedger(token, accountId, from, to) : Promise.resolve(null)),
    [token, accountId, from, to],
  )
  const data = ledger.data
  const pg = usePagination(data?.lines ?? [], 20)

  if (!accountId)
    return (
      <SectionCard icon={Landmark} title="دفتر معین">
        <p className="hint">برای دیدنِ دفترِ معین، یک حساب انتخاب کنید.</p>
      </SectionCard>
    )

  return (
    <SectionCard
      icon={Landmark}
      title={data ? `${data.account_code} — ${data.account_name}` : 'دفتر معین'}
      description={
        data
          ? `مانده‌ی ابتدای دوره ${fa(data.opening_balance)} · مانده‌ی پایان ${fa(data.closing_balance)}`
          : undefined
      }
      actions={
        <button
          type="button"
          disabled={!data || data.lines.length === 0}
          onClick={() =>
            data &&
            downloadCsv(
              `daftar-moein-${data.account_code}`,
              ['شماره سند', 'تاریخ', 'شرح', 'بدهکار', 'بستانکار', 'مانده'],
              data.lines.map((l) => [
                l.entry_number ?? '',
                formatJalali(l.entry_date),
                l.description,
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
        emptyText="این حساب در بازه‌ی انتخابی گردشی ندارد."
      >
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>سند</th>
                <th>تاریخ</th>
                <th>شرح</th>
                <th>بدهکار</th>
                <th>بستانکار</th>
                <th>مانده</th>
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((l, i) => (
                <tr key={`${l.entry_id}-${i}`}>
                  <td className="card-title" data-label="سند">
                    {fa(l.entry_number ?? 0)}
                  </td>
                  <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                  <td data-label="شرح">{l.description || '—'}</td>
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
    </SectionCard>
  )
}

// ═════════════ ۳) مالیات بر ارزش افزوده ═════════════

const QUARTERS = [
  { value: 1, label: 'بهار (فروردین—خرداد)' },
  { value: 2, label: 'تابستان (تیر—شهریور)' },
  { value: 3, label: 'پاییز (مهر—آذر)' },
  { value: 4, label: 'زمستان (دی—اسفند)' },
]

export function VatPage({ token }: { token: string }) {
  const now = isoToJalali(todayIso())
  const [year, setYear] = useState(now.jy)
  const [quarter, setQuarter] = useState(Math.ceil(now.jm / 3))

  // بازه‌ی فصل به تقویمِ شمسی — اظهارنامه فصلی است، نه سه‌ماهه‌ی میلادی.
  const { from, to } = useMemo(() => {
    const startMonth = (quarter - 1) * 3 + 1
    const endMonth = startMonth + 2
    return {
      from: jalaliToIso(year, startMonth, 1),
      to: jalaliToIso(year, endMonth, jalaaliMonthLength(year, endMonth)),
    }
  }, [year, quarter])

  const report = useAsync(() => fetchVatReport(token, from, to), [token, from, to])
  const data = report.data
  const net = Number(data?.net_vat ?? 0)

  const rows = data
    ? [
        { label: 'فروشِ مشمول', net: data.sales_net, vat: data.output_vat, sign: 1 },
        { label: 'برگشت از فروش', net: data.sales_returns_net, vat: data.sales_returns_vat, sign: -1 },
        { label: 'خریدِ مشمول', net: data.purchase_net, vat: data.input_vat, sign: -1 },
        {
          label: 'برگشت از خرید',
          net: data.purchase_returns_net,
          vat: data.purchase_returns_vat,
          sign: 1,
        },
      ]
    : []

  return (
    <OpsPage
      icon={Percent}
      title="مالیات بر ارزش افزوده"
      description="مالیاتِ فروش منهای اعتبارِ مالیاتیِ خرید در یک فصل — همان عددی که در اظهارنامه‌ی فصلی می‌رود."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              سالِ مالی
              <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
                {[now.jy + 1, now.jy, now.jy - 1, now.jy - 2].map((y) => (
                  <option key={y} value={y}>
                    {fa(y)}
                  </option>
                ))}
              </select>
            </label>
            <label className="acc-inline-field">
              فصل
              <select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
                {QUARTERS.map((q) => (
                  <option key={q.value} value={q.value}>
                    {q.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="cc-summary">
            <Metric
              icon={<TrendingUp size={14} />}
              label="مالیاتِ فروش"
              value={data ? fa(data.output_vat) : '—'}
              tone="in"
            />
            <Metric
              icon={<TrendingDown size={14} />}
              label="اعتبارِ خرید"
              value={data ? fa(data.input_vat) : '—'}
              tone="out"
            />
            <Metric
              icon={<Percent size={14} />}
              label={net >= 0 ? 'قابلِ پرداخت' : 'قابلِ استرداد'}
              value={data ? fa(Math.abs(net)) : '—'}
              tone={net >= 0 ? 'out' : 'in'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Percent}
        title="ریزِ محاسبه"
        description={`${formatJalali(from)} تا ${formatJalali(to)}`}
        actions={
          <button
            type="button"
            disabled={!data}
            onClick={() =>
              data &&
              downloadCsv(
                `vat-${year}-q${quarter}`,
                ['شرح', 'مبلغ خالص', 'مالیات'],
                rows.map((r) => [r.label, Number(r.net), Number(r.vat)]),
              )
            }
          >
            <Download size={13} /> خروجی CSV
          </button>
        }
      >
        <AsyncBlock loading={report.loading} error={report.error}>
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شرح</th>
                  <th>مبلغِ خالص</th>
                  <th>مالیات</th>
                  <th>اثر</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label}>
                    <td className="card-title" data-label="شرح">
                      {r.label}
                    </td>
                    <td data-label="مبلغِ خالص" className="num">
                      {faAmount(r.net)}
                    </td>
                    <td data-label="مالیات" className="num">
                      {faAmount(r.vat)}
                    </td>
                    <td data-label="اثر" className={r.sign > 0 ? 'pos-out' : 'pos-in'}>
                      {r.sign > 0 ? 'افزاینده‌ی بدهی' : 'کاهنده‌ی بدهی'}
                    </td>
                  </tr>
                ))}
                <tr className="acc-row--total">
                  <td className="card-title" data-label="شرح">مالیاتِ خالصِ فصل</td>
                  <td className="num" data-label="مبلغِ خالص">—</td>
                  <td className="num" data-label="مالیات">{fa(net)}</td>
                  <td data-label="اثر">{net >= 0 ? 'پرداختنی' : 'استردادی'}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

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
            <button type="button" onClick={exportCsv} disabled={rows.length === 0}>
              <Download size={13} /> خروجی CSV
            </button>
            <button type="button" onClick={() => window.print()}>
              <Printer size={13} /> چاپ
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
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table acc-table--wide">
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
