import { useEffect, useState, type ReactNode } from 'react'
import {
  BookOpen,
  FileStack,
  Inbox,
  Printer,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import {
  fetchJournalEntriesFiltered,
  printJournalEntry,
  setEntrySubNumber,
  voidJournalEntry,
  type JournalEntryRecord,
} from '../../api'
import type { AccountCache, OutboxEntry } from '../../electron.d'
import { SectionCard } from '../../components/SectionCard'
import { JournalEntryForm } from '../../components/JournalEntryForm'
import {
  CountBadge,
  ListToolbar,
  RowAction,
  SearchField,
} from '../../components/form/FormKit'
import { OutboxList } from '../../components/OutboxList'
import { Pager, usePagination } from '../../components/Pager'
import { isElectron } from '../../platform'
import { formatJalali } from '../../lib/jalali'
import { normalizeFa } from '../../lib/faText'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useDebounced } from '../../lib/useDebounced'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import {
  AsyncBlock,
  Note,
  OpsPage,
  RangeBar,
  SOURCE_LABELS,
  StatusChip,
  fa,
  faAmount,
  faInt,
  sourceText,
  useAsync,
  useRange,
  type Msg,
} from './kit'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * چهار عملیاتی که مستقیماً روی *سند* کار می‌کنند.
 *
 * تقسیم‌بندی عمدی است و از خودِ کارِ دفترداری می‌آید:
 *  - **سند حسابداری** جایی است که سند *ساخته* می‌شود.
 *  - **کارتابل اسناد موقت** جایی است که سند *بازبینی* و دائم می‌شود — تکی، دسته‌ای به منشأ، یا کلِ
 *    یک بازه برای پایانِ ماه. منوی جدای «تبدیل اسناد موقت به دائم» همین کارِ آخر را روی همین داده
 *    می‌کرد و در بازچینیِ ۱۴۰۵/۰۷/۰۳ در کارتابل ادغام شد.
 *  - **شماره‌گذاری مجدد** و **ادغام** دو ابزارِ مرتب‌کردنِ دفترِ به‌هم‌ریخته‌اند و
 *    هر دو عمداً فقط روی اسنادِ موقت کار می‌کنند.
 */

// ═══════════════════════ ۱) سند حسابداری ═══════════════════════

export function JournalEntryPage({
  token,
  accounts,
  outbox,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
}) {
  return (
    <OpsPage
      canvas
      icon={BookOpen}
      title="سند حسابداری"
      description="ثبتِ سندِ دستی. سندِ تازه «موقت» ثبت می‌شود تا در کارتابل بازبینی شود؛ فاکتور و فیش و چک خودشان خودکار سند می‌خورند. دفترِ کاملِ اسناد زیرِ کارتِ «فهرست» است."
    >
      <JournalEntryForm token={token} accounts={accounts} onQueued={onQueued} />

      {isElectron && (
        <SectionCard
          icon={Inbox}
          title="صف اسناد ارسال‌نشده"
          description="سندهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
        >
          <OutboxList entries={outbox} emptyHint="سندی در صف نیست." />
        </SectionCard>
      )}
    </OpsPage>
  )
}

/** فیلترهای سرستونِ فهرستِ اسناد — متنِ خامِ کادرها؛ تبدیل به پارامترِ سرور در صفحه. */
interface ColumnFilters {
  number: string
  atf: string
  sub: string
  desc: string
  source: string
}
const NO_COLUMN_FILTERS: ColumnFilters = { number: '', atf: '', sub: '', desc: '', source: '' }

//: ستون‌بندیِ «جا در قاب»: شماره‌ی ردیف و آیکون‌های کنش ثابت، «شرح» باقی را می‌گیرد.
const LIST_LAYOUT = { fixed: ['rowhead', 'actions'], auto: 'desc' } as const

/** جدولِ اسنادِ دفتر — تکی و مشترک.
 *
 *  پیش‌تر دو نسخه‌ی کمی‌متفاوت داشت: یکی ته صفحه‌ی «سند حسابداری» (با ابطال، بدونِ
 *  شمارِ ردیف) و یکی در صفحه‌ی فهرستِ «اسناد حسابداری» (با شمارِ ردیف، بدونِ ابطال).
 *  حالا یکی است و ستونِ کنش فقط وقتی می‌آید که `onVoid` داده شود.
 *
 *  **جدولِ اکسل‌مانند** (`.xl-grid`): سرستونِ خاکستری و خطوطِ ظریفِ افقی و عمودی، ردیفِ هر سند
 *  با رنگِ ملایمِ وضعیتش (موقت کهربایی، دائم سبز، باطل خط‌خورده)، ستون‌های کشیدنی، و انتخابِ
 *  ردیف با سرستونِ ردیف (کلیک / Ctrl / Shift) که جمعِ مبلغِ انتخاب‌شده‌ها را مثلِ نوارِ وضعیتِ
 *  اکسل می‌گوید. `filters` ردیفِ فیلترِ زیرِ سرستون‌ها را می‌سازد — مقدارها سمتِ سرور اعمال
 *  می‌شوند، نه روی صفحه‌ی بارشده. */
function EntryTable({
  entries,
  pageSize = 20,
  onVoid,
  onPrint,
  onEditSub,
  filters,
}: {
  entries: JournalEntryRecord[]
  pageSize?: number
  onVoid?: (e: JournalEntryRecord) => void
  /** برگه‌ی چاپیِ سند. برخلافِ ابطال برای **هر** سندی می‌آید — خودکار و باطل هم —
   *  چون چاپ خواندن است و سندِ باطل هم باید بتواند با نشانِ ابطالش چاپ شود. */
  onPrint?: (e: JournalEntryRecord) => void
  /** اصلاحِ شماره فرعی. فقط سندِ موقت؛ روی دائم دکمه نمی‌آید. */
  onEditSub?: (e: JournalEntryRecord) => void
  filters?: {
    values: ColumnFilters
    onChange: (key: keyof ColumnFilters, value: string) => void
    status: '' | 'temporary' | 'permanent'
    onStatus: (s: '' | 'temporary' | 'permanent') => void
  }
}) {
  const pg = usePagination(entries, pageSize)
  const total = (e: JournalEntryRecord) =>
    e.lines.reduce((sum, l) => sum + Number(l.debit || 0), 0)
  const withActions = Boolean(onVoid || onPrint)
  const cw = useColumnWidths('cubita.grid.journalList.shares', LIST_LAYOUT)
  const { selected, click, clear } = useRowSelection()
  //: فیلترِ تازه یعنی فهرستِ دیگری؛ انتخابِ قبلی دیگر معنا ندارد.
  useEffect(() => clear(), [entries, clear])
  const order = pg.pageItems.map((e) => e.id)
  const chosen = entries.filter((e) => selected.has(e.id))
  const colIds = ['rowhead', 'number', 'atf', 'sub', 'date', 'desc', 'source', 'status', 'lines', 'amount', ...(withActions ? ['actions'] : [])]

  const head = (id: string, label: ReactNode) => (
    <th data-col={id}>
      {label}
      {/* لبه‌ی کنارِ ستونِ ثابت (آیکون‌ها) کشیدنی نیست. */}
      {cw.canResize(id, colIds[colIds.indexOf(id) + 1]) && (
        <ColResizer onBegin={(ev) => cw.begin(ev, id)} onReset={cw.reset} />
      )}
    </th>
  )
  const textFilter = (key: keyof ColumnFilters, label: string, numeric = false) =>
    filters && (
      <input
        type="search"
        inputMode={numeric ? 'numeric' : undefined}
        value={filters.values[key]}
        onChange={(ev) => filters.onChange(key, ev.target.value)}
        placeholder="فیلتر…"
        aria-label={`فیلترِ ${label}`}
      />
    )

  return (
    <div className="table-scroll ef-table-wrap">
      <table ref={cw.frame} className="cards-on-mobile acc-table ef-table xl-grid xl-grid--list">
        <colgroup>
          {colIds.map((id) => (
            <col key={id} className={`xl-c-${id}`} style={cw.col(id)} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th className="xl-rowhead" data-col="rowhead" aria-label="انتخاب" />
            {head('number', 'شماره')}
            {/* عطف کنارِ شماره می‌نشیند چون کاربر این دو را با هم می‌خواند: یکی
                جای سند در دفترِ امروز است، دیگری هویتِ ثابتش. */}
            {head('atf', 'عطف')}
            {head('sub', 'فرعی')}
            {head('date', 'تاریخ')}
            {head('desc', 'شرح')}
            {head('source', 'منشأ')}
            {head('status', 'وضعیت')}
            {head('lines', 'ردیف')}
            {head('amount', 'مبلغ')}
            {withActions && <th className="ef-col-min" data-col="actions">عملیات</th>}
          </tr>
          {filters && (
            <tr className="xl-filter-row">
              <th className="xl-rowhead" aria-hidden="true" />
              <th>{textFilter('number', 'شماره', true)}</th>
              <th>{textFilter('atf', 'عطف', true)}</th>
              <th>{textFilter('sub', 'فرعی')}</th>
              {/* تاریخ فیلترِ خودش را دارد: بازه‌ی بالای صفحه. */}
              <th />
              <th>{textFilter('desc', 'شرح')}</th>
              <th>
                <SearchSelect
                  value={filters.values.source}
                  onChange={(ev) => filters.onChange('source', ev.target.value)}
                  aria-label="فیلترِ منشأ"
                >
                  <option value="">همه</option>
                  {Object.entries(SOURCE_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </SearchSelect>
              </th>
              <th>
                <SearchSelect
                  value={filters.status}
                  onChange={(ev) => filters.onStatus(ev.target.value as '' | 'temporary' | 'permanent')}
                  aria-label="فیلترِ وضعیت"
                >
                  <option value="">همه</option>
                  <option value="temporary">موقت</option>
                  <option value="permanent">دائم</option>
                </SearchSelect>
              </th>
              <th />
              <th />
              {withActions && <th />}
            </tr>
          )}
        </thead>
        <tbody>
          {pg.pageItems.map((e, idx) => {
            const on = selected.has(e.id)
            const tone = e.voided_at ? 'acc-row--void' : e.status === 'permanent' ? 'xl-row--perm' : 'xl-row--temp'
            return (
            <tr key={e.id} className={`${tone}${on ? ' is-selected' : ''}`}>
              <td className="xl-rowhead card-hide">
                <button
                  type="button"
                  className="xl-rowhead-btn"
                  aria-pressed={on}
                  aria-label={`انتخابِ سندِ ${fa(e.number ?? 0)}`}
                  onClick={(ev) => click(order, e.id, modsOf(ev))}
                >
                  {/* `pg.page` از صفر است. */}
                  {fa(pg.page * pageSize + idx + 1)}
                </button>
              </td>
              <td className="card-title" data-label="شماره">
                {fa(e.number ?? 0)}
              </td>
              <td data-label="عطف" className="num">
                {e.atf_number === null ? '—' : faInt(e.atf_number)}
              </td>
              <td data-label="فرعی">
                {/* عطف تغییرناپذیر است، ولی فرعی ارجاعِ کاربر است و غلطِ تایپی
                    باید اصلاح شود — تا وقتی سند موقت است. */}
                {onEditSub && !e.voided_at && e.status === 'temporary' ? (
                  <button type="button" className="link-btn" onClick={() => onEditSub(e)}>
                    {e.sub_number || '＋ افزودن'}
                  </button>
                ) : (
                  e.sub_number || '—'
                )}
              </td>
              <td data-label="تاریخ">{formatJalali(e.entry_date)}</td>
              <td data-label="شرح" className="xl-ellipsis" title={e.description || undefined}>
                {e.description || '—'}
              </td>
              <td data-label="منشأ" className="xl-ellipsis">{sourceText(e)}</td>
              <td data-label="وضعیت">
                <StatusChip status={e.status} voided={!!e.voided_at} />
              </td>
              <td data-label="ردیف" className="num">
                {faInt(e.lines.length)}
              </td>
              <td data-label="مبلغ" className="num">
                {faAmount(total(e))}
              </td>
              {withActions && (
                <td className="card-actions ef-col-min">
                  <div className="row-actions ef-row-actions">
                    {onPrint && <RowAction icon={Printer} label="چاپ" onClick={() => onPrint(e)} />}
                    {/* فقط سندِ دستی: سندِ خودکار با ابطالِ خودِ فاکتور/فیش برمی‌گردد. */}
                    {onVoid && (
                      <RowAction
                        icon={Trash2}
                        label="ابطال"
                        danger
                        onClick={() => onVoid(e)}
                        disabled={!!e.voided_at || e.source_type !== 'manual'}
                        title={
                          e.voided_at
                            ? 'این سند قبلاً باطل شده است.'
                            : e.source_type !== 'manual'
                              ? 'سندِ خودکار با ابطالِ فاکتور، فیش یا عملیاتِ منشأ برمی‌گردد.'
                              : undefined
                        }
                      />
                    )}
                  </div>
                </td>
              )}
            </tr>
            )
          })}
        </tbody>
      </table>
      {chosen.length > 0 && (
        <SelectionBar count={chosen.length} unit="سند" onClear={clear}>
          <span>
            جمع مبلغ <b className="num">{faAmount(chosen.reduce((s, e) => s + total(e), 0))}</b>
          </span>
          <span>
            ردیف‌ها <b className="num">{faInt(chosen.reduce((s, e) => s + e.lines.length, 0))}</b>
          </span>
        </SelectionBar>
      )}
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

// ═══════════════════ ۲) کارتابل اسناد موقت ═══════════════════
//: برگه‌ی اکسلیِ کارتابل فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { EntryCartablePage } from './EntryCartablePage'

// ═══════════════ ۳) شماره‌گذاری مجدد اسناد ═══════════════
//: برگه‌ی اکسلیِ نقشه‌ی شماره‌ها فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { RenumberEntriesPage } from './RenumberEntriesPage'

// ═══════════════════════ ۴) ادغام اسناد ═══════════════════════
//: برگه‌ی اکسلیِ ادغام فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { MergeEntriesPage } from './MergeEntriesPage'

/** فهرستِ اسنادِ حسابداری — صفحه‌ی «فهرست» ماژول. */
/**
 * «اسناد حسابداری» — دفترِ کاملِ اسناد، تنها جایی که فهرستِ اسناد دیده می‌شود.
 *
 * پیش‌تر ته صفحه‌ی «سند حسابداری» هم یک فهرستِ دوم بود با فیلترهای دیگر (جست‌وجوی
 * متنی، بدونِ بازه) و کنشِ ابطال. دو فهرست از یک داده یعنی کاربر باید حدس می‌زد کدام
 * را باز کند؛ حالا یکی است و هر دو فیلتر و کنشِ ابطال را دارد.
 */
export function EntryListPage({ token }: { token: string }) {
  const range = useRange('year')
  const [status, setStatus] = useState<'' | 'temporary' | 'permanent'>('')
  const [search, setSearch] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [msg, setMsg] = useState<Msg>(null)
  //: فیلترهای سرستون — همه سمتِ سرور (`/api/journal-entries`)، نه روی ۳۰۰ سندِ بارشده. متن‌ها با
  //: مکث می‌روند تا هر حرف یک درخواست نشود.
  const [cols, setCols] = useState<ColumnFilters>(NO_COLUMN_FILTERS)
  const colsQ = useDebounced(cols, 350)
  const num = (v: string) => {
    const d = normalizeFa(v).replace(/\D/g, '')
    return d ? Number(d) : undefined
  }

  const list = useAsync(
    () =>
      fetchJournalEntriesFiltered(token, {
        dateFrom: range.from,
        dateTo: range.to,
        status: status || undefined,
        q: search || undefined,
        limit: 300,
        entryFrom: num(colsQ.number),
        entryTo: num(colsQ.number),
        atf: num(colsQ.atf),
        sub: colsQ.sub.trim() || undefined,
        desc: colsQ.desc.trim() || undefined,
        sourceType: colsQ.source || undefined,
      }),
    [token, range.from, range.to, status, search, reloadKey, colsQ],
  )
  const rows = list.data ?? []

  async function handleEditSub(entry: JournalEntryRecord) {
    const next = window.prompt(
      `شماره فرعیِ سندِ ${entry.number ?? ''} — ارجاعِ خودتان (شماره‌ی پرونده، سندِ سیستمِ قبلی، کدِ دسته).
خالی بگذارید تا پاک شود:`,
      entry.sub_number ?? '',
    )
    if (next === null) return
    try {
      await setEntrySubNumber(token, entry.id, next.trim() || null)
      setMsg({ text: 'شماره فرعی ثبت شد.', kind: 'ok' })
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function handleVoid(entry: JournalEntryRecord) {
    const reason = window.prompt(
      `ابطالِ سندِ ${entry.number ?? ''} یک سندِ معکوس ثبت می‌کند و اصل سرِ جایش می‌ماند.\nعلتِ ابطال:`,
    )
    if (reason === null) return
    try {
      const out = await voidJournalEntry(token, entry.id, reason)
      setMsg({ text: `سندِ معکوس با شماره ${fa(out.reversal_entry_number ?? 0)} ثبت شد.`, kind: 'ok' })
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function handlePrint(entry: JournalEntryRecord) {
    try {
      await printJournalEntry(token, entry.id)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  return (
    <OpsPage
      canvas
      icon={FileStack}
      title="اسناد حسابداری"
      description="همه‌ی اسنادِ دفتر — دستی و خودکار، موقت و دائم. «عطف» شماره‌ی ثابتِ سند است و با شماره‌گذاری مجدد عوض نمی‌شود؛ «فرعی» ارجاعِ خودِ شماست. سندِ دستی را می‌توان از همین‌جا ابطال کرد."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              //: روی دسکتاپ «وضعیت» فیلترِ سرستونِ جدول است؛ این یکی فقط برای موبایل می‌ماند، جایی که
              //: جدول کارت می‌شود و سرستون‌ها (و فیلترهایشان) پنهان‌اند.
              <label className="acc-inline-field xl-narrow-only">
                وضعیت
                <SearchSelect value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
                  <option value="">همه</option>
                  <option value="temporary">موقت</option>
                  <option value="permanent">دائم</option>
                </SearchSelect>
              </label>
            }
          />
        </div>
      }
    >
      <SectionCard
        icon={FileStack}
        title="اسناد"
        badge={list.data ? <CountBadge accent>{faInt(rows.length)} سند</CountBadge> : undefined}
        description="دفترِ کاملِ اسناد — دستی و خودکار، موقت و دائم."
      >
        <ListToolbar>
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="شماره، عطف، شماره فرعی یا شرحِ سند"
            label="جست‌وجو در اسناد"
          />
          <button type="button" className="ef-btn-secondary" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={14} /> به‌روزرسانی
          </button>
        </ListToolbar>
        <Note msg={msg} />

        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="سندی با این شرایط پیدا نشد."
        >
          <EntryTable
            entries={rows}
            onVoid={handleVoid}
            onPrint={handlePrint}
            onEditSub={handleEditSub}
            filters={{ values: cols, onChange: (k, v) => setCols((c) => ({ ...c, [k]: v })), status, onStatus: setStatus }}
          />
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
