import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  Combine,
  FileStack,
  Hash,
  Inbox,
  Layers,
  ListChecks,
  Lock,
  Printer,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import {
  fetchCartable,
  fetchJournalEntriesFiltered,
  fetchRenumberPreview,
  finalizeEntries,
  mergeEntries,
  printJournalEntry,
  renumberEntries,
  setEntrySubNumber,
  voidJournalEntry,
  type EntrySummary,
  type JournalEntryRecord,
} from '../../api'
import type { AccountCache, OutboxEntry } from '../../electron.d'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JournalEntryForm } from '../../components/JournalEntryForm'
import {
  ActionBar,
  CountBadge,
  FormField,
  FormStatus,
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
  Metric,
  Note,
  OpsPage,
  RangeBar,
  SOURCE_LABELS,
  StatusChip,
  fa,
  faAmount,
  faInt,
  sourceLabel,
  sourceText,
  useAsync,
  useRange,
  type Msg,
} from './kit'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * پنج عملیاتی که مستقیماً روی *سند* کار می‌کنند.
 *
 * تقسیم‌بندی عمدی است و از خودِ کارِ دفترداری می‌آید:
 *  - **سند حسابداری** جایی است که سند *ساخته* می‌شود.
 *  - **کارتابل** جایی است که سند *بازبینی* می‌شود (صفِ موقت‌ها).
 *  - **تبدیل به دائم** همان بازبینی است ولی *دسته‌ای*، برای پایانِ ماه.
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

//: عرضِ پیش‌فرضِ ستون‌ها برای وقتی کاربر یکی را کشید (`useColumnWidths`).
const LIST_COL_FALLBACK: Record<string, number> = {
  rowhead: 44,
  number: 70,
  atf: 70,
  sub: 90,
  date: 96,
  desc: 240,
  source: 130,
  status: 80,
  lines: 50,
  amount: 130,
  actions: 96,
}

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
  const cw = useColumnWidths('cubita.grid.journalList', LIST_COL_FALLBACK)
  const { selected, click, clear } = useRowSelection()
  //: فیلترِ تازه یعنی فهرستِ دیگری؛ انتخابِ قبلی دیگر معنا ندارد.
  useEffect(() => clear(), [entries, clear])
  const order = pg.pageItems.map((e) => e.id)
  const chosen = entries.filter((e) => selected.has(e.id))
  const withActions = Boolean(onVoid || onPrint)
  const colIds = ['rowhead', 'number', 'atf', 'sub', 'date', 'desc', 'source', 'status', 'lines', 'amount', ...(withActions ? ['actions'] : [])]

  const head = (id: string, label: ReactNode) => (
    <th data-col={id}>
      {label}
      <ColResizer onBegin={(ev) => cw.begin(ev, id)} onReset={cw.reset} />
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
      <table className="cards-on-mobile acc-table ef-table xl-grid xl-grid--list" style={cw.table(colIds)}>
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

// ═══════════════════ ۲) کارتابل صدور سند ═══════════════════

export function EntryCartablePage({ token }: { token: string }) {
  const range = useRange('all')
  const [msg, setMsg] = useState<Msg>(null)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const cartable = useAsync(
    () => fetchCartable(token, range.from, range.to),
    [token, range.from, range.to],
  )

  const toggle = (id: string) =>
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  async function finalize(payload: Parameters<typeof finalizeEntries>[1], label: string) {
    if ('entry_ids' in payload && (payload.entry_ids?.length ?? 0) === 0) {
      setMsg({ text: 'اول از جدولِ «اسنادِ در انتظار» سندی را علامت بزنید.', kind: 'err' })
      return
    }
    if (!window.confirm(`${label}\nسندِ دائم دیگر ادغام یا بازشماره‌گذاری نمی‌شود. ادامه؟`)) return
    try {
      const out = await finalizeEntries(token, payload)
      setMsg({ text: `${faInt(out.count)} سند دائم شد.`, kind: 'ok' })
      setPicked(new Set())
      cartable.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = cartable.data
  return (
    <OpsPage
      canvas
      icon={ClipboardCheck}
      title="کارتابل صدور سند حسابداری"
      description="صفِ اسنادِ موقت — هرچه ثبت شده ولی هنوز بازبینی نشده. سند را ببینید، بعد دائمش کنید."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric
              icon={<Inbox size={14} />}
              label="سندِ در انتظار"
              value={data ? faInt(data.total_count) : '—'}
              tone={data && data.total_count > 0 ? 'out' : 'in'}
            />
            <Metric
              icon={<Layers size={14} />}
              label="منشأهای مختلف"
              value={data ? faInt(data.groups.length) : '—'}
            />
            <Metric
              icon={<CheckCircle2 size={14} />}
              label="مبلغِ در انتظار"
              value={data ? fa(data.groups.reduce((s, g) => s + Number(g.total), 0)) : '—'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Layers}
        title="دسته‌ها"
        tip="معمولاً تصمیم دسته‌ای است: «همه‌ی سندهای فاکتورِ فروشِ این بازه درست‌اند»."
        badge={data ? <CountBadge accent>{faInt(data.groups.length)} منشأ</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={cartable.loading}
          error={cartable.error}
          empty={(data?.groups.length ?? 0) === 0}
          emptyText="هیچ سندِ موقتی در این بازه نیست — کارتابل خالی است."
        >
          <ul className="acc-groups">
            {(data?.groups ?? []).map((g) => (
              <li key={g.source_type}>
                <span className="acc-group-name">{sourceLabel(g.source_type)}</span>
                <span className="acc-group-count">{faInt(g.count)} سند</span>
                <span className="acc-group-total">{fa(g.total)}</span>
                <button
                  type="button"
                  className="ef-btn-secondary"
                  onClick={() =>
                    finalize(
                      { date_from: range.from, date_to: range.to, source_type: g.source_type },
                      `دائم‌کردنِ ${g.count} سندِ «${sourceLabel(g.source_type)}».`,
                    )
                  }
                >
                  <Lock size={13} /> دائم کن
                </button>
              </li>
            ))}
          </ul>
        </AsyncBlock>
      </SectionCard>

      <SectionCard
        icon={ListChecks}
        title="اسنادِ در انتظار"
        badge={data ? <CountBadge accent>{faInt(data.entries.length)} سند</CountBadge> : undefined}
        description="سندهایی را که بازبینی کرده‌اید علامت بزنید و از نوارِ پایین دائم کنید."
      >
        <AsyncBlock
          loading={cartable.loading}
          error={cartable.error}
          empty={(data?.entries.length ?? 0) === 0}
          emptyText="سندی در انتظار نیست."
        >
          <CartableTable entries={data?.entries ?? []} picked={picked} onToggle={toggle} />
        </AsyncBlock>
      </SectionCard>
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={picked.size > 0 ? `${faInt(picked.size)} سند انتخاب شده است.` : 'سندی انتخاب نشده است.'}
          />
        }
      >
        <button
          type="button"
          className="btn-primary"
          onClick={() => finalize({ entry_ids: [...picked] }, `دائم‌کردنِ ${picked.size} سندِ انتخابی.`)}
        >
          <Lock size={15} /> دائم‌کردنِ {picked.size > 0 ? `${faInt(picked.size)} سند` : 'انتخاب‌شده‌ها'}
        </button>
      </ActionBar>
    </OpsPage>
  )
}

function CartableTable({
  entries,
  picked,
  onToggle,
}: {
  entries: EntrySummary[]
  picked: Set<string>
  onToggle: (id: string) => void
}) {
  const pg = usePagination(entries, 15)
  return (
    <div className="table-scroll ef-table-wrap">
      <table className="cards-on-mobile acc-table ef-table">
        <thead>
          <tr>
            <th className="ef-col-min" aria-label="انتخاب" />
            <th>شماره</th>
            <th>عطف</th>
            <th>فرعی</th>
            <th>تاریخ</th>
            <th>شرح</th>
            <th>منشأ</th>
            <th>حساب‌ها</th>
            <th>مبلغ</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((e) => (
            <tr key={e.id}>
              <td className="ef-col-min" data-label="انتخاب">
                <input
                  type="checkbox"
                  aria-label={`انتخابِ سندِ ${fa(e.number ?? 0)}`}
                  checked={picked.has(e.id)}
                  onChange={() => onToggle(e.id)}
                />
              </td>
              <td className="card-title" data-label="شماره">
                {fa(e.number ?? 0)}
              </td>
              <td data-label="عطف" className="num">
                {e.atf_number === null ? '—' : faInt(e.atf_number)}
              </td>
              <td data-label="فرعی">{e.sub_number || '—'}</td>
              <td data-label="تاریخ">{formatJalali(e.entry_date)}</td>
              <td data-label="شرح">{e.description || '—'}</td>
              <td data-label="منشأ">{sourceText(e)}</td>
              <td data-label="حساب‌ها" className="acc-accounts">
                {e.accounts.slice(0, 3).join('، ')}
                {e.accounts.length > 3 ? ' …' : ''}
              </td>
              <td data-label="مبلغ" className="num">
                {fa(e.total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

// ═══════════════ ۳) تبدیل اسناد موقت به دائم ═══════════════

export function FinalizeEntriesPage({ token }: { token: string }) {
  const range = useRange('month')
  const [msg, setMsg] = useState<Msg>(null)
  const preview = useAsync(
    () => fetchCartable(token, range.from, range.to),
    [token, range.from, range.to],
  )

  async function run() {
    const count = preview.data?.total_count ?? 0
    if (count === 0) {
      setMsg({ text: 'در این بازه سندِ موقتی نیست؛ بازه را عوض کنید.', kind: 'err' })
      return
    }
    if (
      !window.confirm(
        `${count} سندِ موقتِ این بازه دائم می‌شوند.\nاین کار برگشت‌پذیر نیست. ادامه می‌دهید؟`,
      )
    )
      return
    try {
      const out = await finalizeEntries(token, { date_from: range.from, date_to: range.to })
      setMsg({
        text: `${faInt(out.count)} سند از ${formatJalali(out.first_date)} تا ${formatJalali(out.last_date)} دائم شد.`,
        kind: 'ok',
      })
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = preview.data
  return (
    <OpsPage
      canvas
      icon={Lock}
      title="تبدیل اسناد موقت به دائم"
      description="عملیاتِ پایانِ ماه: همه‌ی اسنادِ موقتِ یک بازه یک‌جا قطعی می‌شوند. اثرِ مالی ندارد — فقط سند را از دسترسِ ادغام و بازشماره‌گذاری بیرون می‌برد."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric
              icon={<Inbox size={14} />}
              label="موقت در این بازه"
              value={data ? faInt(data.total_count) : '—'}
              tone={data && data.total_count > 0 ? 'out' : 'in'}
            />
            <Metric
              icon={<Layers size={14} />}
              label="منشأها"
              value={data ? faInt(data.groups.length) : '—'}
            />
            <Metric
              icon={<CheckCircle2 size={14} />}
              label="مبلغِ کل"
              value={data ? fa(data.groups.reduce((s, g) => s + Number(g.total), 0)) : '—'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Lock}
        title="آنچه دائم می‌شود"
        description="پیش از تأیید، دقیقاً همان چیزی را ببینید که قطعی خواهد شد."
        badge={data ? <CountBadge accent>{faInt(data.total_count)} سند</CountBadge> : undefined}
      >
        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={(data?.total_count ?? 0) === 0}
          emptyText="در این بازه سندِ موقتی نیست."
        >
          <ul className="acc-groups">
            {(data?.groups ?? []).map((g) => (
              <li key={g.source_type}>
                <span className="acc-group-name">{sourceLabel(g.source_type)}</span>
                <span className="acc-group-count">{faInt(g.count)} سند</span>
                <span className="acc-group-total">{fa(g.total)}</span>
              </li>
            ))}
          </ul>
        </AsyncBlock>
      </SectionCard>
      <ActionBar status={<FormStatus msg={msg} idle="اثرِ مالی ندارد، ولی برگشت‌پذیر هم نیست." />}>
        <button type="button" className="btn-primary" disabled={preview.loading} onClick={() => void run()}>
          <Lock size={15} /> دائم‌کردنِ همه
        </button>
      </ActionBar>
    </OpsPage>
  )
}

// ═══════════════ ۴) شماره‌گذاری مجدد اسناد ═══════════════

export function RenumberEntriesPage({ token }: { token: string }) {
  const range = useRange('year')
  const [start, setStart] = useState('1')
  const [msg, setMsg] = useState<Msg>(null)
  const startNumber = Math.max(1, Number(start) || 1)

  //: انتخابِ دستی. خالی یعنی «کلِ بازه» — همان رفتارِ قبلی، دست‌نخورده.
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const togglePick = (id: string) =>
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const preview = useAsync(
    () => fetchRenumberPreview(token, range.from, range.to, startNumber),
    [token, range.from, range.to, startNumber],
  )

  //: با عوض‌شدنِ بازه انتخاب پاک می‌شود. وگرنه شناسه‌هایی که دیگر در پیش‌نمایش
  //: نیستند در انتخاب می‌ماندند و کاربر روی چیزی اعمال می‌کرد که نمی‌دید.
  useEffect(() => setPicked(new Set()), [range.from, range.to])

  async function run() {
    const manual = picked.size > 0
    if (!manual && (preview.data?.changed_count ?? 0) === 0) {
      setMsg({ text: 'شماره‌ی هیچ سندی عوض نمی‌شود؛ بازه یا شماره‌ی شروع را عوض کنید.', kind: 'err' })
      return
    }
    if (
      !window.confirm(
        `شماره‌ی ${manual ? picked.size : (preview.data?.count ?? 0)} سند به‌ترتیبِ تاریخ از ${startNumber} بازنویسی می‌شود.\nادامه می‌دهید؟`,
      )
    )
      return
    try {
      //: انتخابِ دستی **جای** بازه می‌نشیند نه کنارش — سرور هم همین‌طور رفتار
      //: می‌کند، پس فرستادنِ هر دو یعنی کاربر باید حدس بزند کدام برنده است.
      const out = await renumberEntries(token, {
        date_from: manual ? null : range.from,
        date_to: manual ? null : range.to,
        entry_ids: manual ? [...picked] : null,
        start_number: startNumber,
      })
      setPicked(new Set())
      setMsg({
        text: `${faInt(out.changed_count)} سند شماره‌ی تازه گرفت (${fa(out.first_number)} تا ${fa(out.last_number)}).`,
        kind: 'ok',
      })
      preview.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const data = preview.data
  return (
    <OpsPage
      canvas
      icon={Hash}
      title="شماره‌گذاری مجدد اسناد"
      description="شماره‌ی اسناد را به‌ترتیبِ تاریخ از نو می‌دهد. فقط روی اسنادِ موقت — سندِ دائم شماره‌ی امضاشده دارد و جابه‌جا نمی‌شود."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <label className="acc-inline-field">
                شروع از شماره
                <NumberInput value={start} onChange={setStart} group={false} />
              </label>
            }
          />
          <div className="cc-summary">
            <Metric
              icon={<FileStack size={14} />}
              label="سندِ موقتِ بازه"
              value={data ? faInt(data.count) : '—'}
              hint={
                data && data.skipped_permanent > 0
                  ? `${faInt(data.skipped_permanent)} سندِ دائم دست نمی‌خورد`
                  : undefined
              }
            />
            <Metric
              icon={<Hash size={14} />}
              label="شماره عوض می‌شود"
              value={data ? faInt(data.changed_count) : '—'}
              tone={data && data.changed_count > 0 ? 'out' : 'in'}
            />
            <Metric
              icon={<CheckCircle2 size={14} />}
              label="بازه‌ی شماره"
              value={data && data.count > 0 ? `${fa(startNumber)} — ${fa(startNumber + data.count - 1)}` : '—'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Hash}
        title="پیش‌نمایشِ شماره‌ها"
        tip="فقط اسنادِ موقت در نقشه می‌آیند؛ سندِ دائم شماره‌ی امضاشده دارد و جابه‌جا نمی‌شود. اگر ردیفی را علامت بزنید، فقط همان‌ها بازشماره می‌شوند."
      >
        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={(data?.count ?? 0) === 0}
          emptyText="در این بازه سندِ موقتی نیست."
        >
          {data?.truncated && (
            <p className="hint">فقط {faInt(data.rows.length)} ردیفِ نخست نمایش داده می‌شود؛ اعمال روی همه انجام می‌شود.</p>
          )}
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
              <thead>
                <tr>
                  <th className="ef-col-min" aria-label="انتخاب" />
                  <th>تاریخ</th>
                  <th>شرح</th>
                  <th>وضعیت</th>
                  {/* عطف اینجاست تا کاربر پیش از زدنِ دکمه ببیند چه چیزی *تغییر
                      نمی‌کند* — تضمینی که کلِ دلیلِ وجودِ این ستون است. */}
                  <th>عطف (ثابت)</th>
                  <th>شماره‌ی فعلی</th>
                  <th>شماره‌ی تازه</th>
                </tr>
              </thead>
              <tbody>
                {(data?.rows ?? []).map((r) => (
                  <tr key={r.id} className={r.changed ? 'acc-row--changed' : ''}>
                    <td className="ef-col-min" data-label="انتخاب">
                      <input
                        type="checkbox"
                        aria-label="انتخابِ سند"
                        checked={picked.has(r.id)}
                        onChange={() => togglePick(r.id)}
                      />
                    </td>
                    <td className="card-title" data-label="تاریخ">
                      {formatJalali(r.entry_date)}
                    </td>
                    <td data-label="شرح">{r.description || sourceLabel(r.source_type)}</td>
                    <td data-label="وضعیت">
                      <StatusChip status={r.status} />
                    </td>
                    <td data-label="عطف (ثابت)" className="num">
                      {r.atf_number == null ? '—' : fa(r.atf_number)}
                    </td>
                    <td data-label="شماره‌ی فعلی" className="num">
                      {r.old_number == null ? '—' : fa(r.old_number)}
                    </td>
                    <td data-label="شماره‌ی تازه" className="num">
                      {fa(r.new_number)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              picked.size > 0
                ? `فقط ${faInt(picked.size)} سندِ علامت‌خورده بازشماره می‌شوند.`
                : 'همه‌ی اسنادِ موقتِ این بازه بازشماره می‌شوند.'
            }
          />
        }
      >
        <button type="button" className="btn-primary" disabled={preview.loading} onClick={() => void run()}>
          <Hash size={15} /> اعمالِ شماره‌گذاری
        </button>
      </ActionBar>
    </OpsPage>
  )
}

// ═══════════════════════ ۵) ادغام اسناد ═══════════════════════

export function MergeEntriesPage({ token }: { token: string }) {
  const range = useRange('month')
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [description, setDescription] = useState('')
  const [msg, setMsg] = useState<Msg>(null)

  const list = useAsync(
    () =>
      fetchJournalEntriesFiltered(token, {
        dateFrom: range.from,
        dateTo: range.to,
        status: 'temporary',
        sourceType: 'manual',
        limit: 200,
      }),
    [token, range.from, range.to],
  )

  const entries = useMemo(
    () => (list.data ?? []).filter((e) => !e.voided_at),
    [list.data],
  )

  // ادغام فقط بینِ هم‌تاریخ‌هاست، پس گروه‌بندیِ صفحه هم بر اساسِ تاریخ است — وگرنه
  // کاربر انتخاب می‌کرد و سرور رد می‌کرد، که بدترین ترتیبِ فهمیدنِ یک قاعده است.
  const byDate = useMemo(() => {
    const map = new Map<string, JournalEntryRecord[]>()
    for (const e of entries) {
      const bucket = map.get(e.entry_date) ?? []
      bucket.push(e)
      map.set(e.entry_date, bucket)
    }
    return [...map.entries()]
      .filter(([, rows]) => rows.length > 1)
      .sort((a, b) => (a[0] < b[0] ? 1 : -1))
  }, [entries])

  const pickedDate = useMemo(() => {
    const first = entries.find((e) => picked.has(e.id))
    return first?.entry_date ?? null
  }, [entries, picked])

  function toggle(entry: JournalEntryRecord) {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(entry.id)) next.delete(entry.id)
      else next.add(entry.id)
      return next
    })
  }

  async function run() {
    if (picked.size < 2) {
      setMsg({ text: 'دست‌کم دو سندِ هم‌تاریخ را برای ادغام علامت بزنید.', kind: 'err' })
      return
    }
    if (!window.confirm(`${picked.size} سند در یک سند ادغام می‌شوند و اصل‌ها حذف خواهند شد. ادامه؟`))
      return
    try {
      const out = await mergeEntries(token, [...picked], description)
      setMsg({
        text: `سندِ ادغامی با شماره ${fa(out.number ?? 0)} و ${faInt(out.line_count)} ردیف ساخته شد.`,
        kind: 'ok',
      })
      setPicked(new Set())
      setDescription('')
      list.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  return (
    <OpsPage
      canvas
      icon={Combine}
      title="ادغام اسناد"
      description="چند سندِ موقتِ دستیِ هم‌تاریخ را در یک سند جمع می‌کند. مانده‌ی هیچ حسابی تکان نمی‌خورد — فقط تعدادِ اسناد کم می‌شود."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric
              icon={<FileStack size={14} />}
              label="سندِ قابلِ ادغام"
              value={list.data ? faInt(entries.length) : '—'}
            />
            <Metric icon={<Layers size={14} />} label="روزهای دارای چند سند" value={faInt(byDate.length)} />
            <Metric
              icon={<Combine size={14} />}
              label="انتخاب‌شده"
              value={faInt(picked.size)}
              tone={picked.size > 1 ? 'in' : 'plain'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Combine}
        title="اسنادِ موقتِ دستی"
        tip="فقط روزهایی که بیش از یک سند دارند نشان داده می‌شوند؛ ادغام بینِ دو تاریخ معنا ندارد."
      >
        <div className="ef-block-top">
          <FormField label="شرحِ سندِ ادغامی" optional tip="خالی بگذارید تا شماره‌ی اسنادِ اصلی نوشته شود.">
            {(id) => (
              <input
                id={id}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="مثلاً: هزینه‌های تنخواهِ هفته‌ی اول"
              />
            )}
          </FormField>
        </div>

        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={byDate.length === 0}
          emptyText="هیچ روزی در این بازه بیش از یک سندِ موقتِ دستی ندارد."
        >
          {byDate.map(([day, rows]) => (
            <div className="acc-day" key={day}>
              <h4 className="acc-day-head">
                {formatJalali(day)} <span>{faInt(rows.length)} سند</span>
              </h4>
              <ul className="acc-picklist">
                {rows.map((e) => {
                  const total = e.lines.reduce((s, l) => s + Number(l.debit || 0), 0)
                  const blocked = pickedDate !== null && pickedDate !== e.entry_date
                  return (
                    <li key={e.id} className={blocked ? 'is-blocked' : ''}>
                      <label>
                        <input
                          type="checkbox"
                          checked={picked.has(e.id)}
                          disabled={blocked}
                          onChange={() => toggle(e)}
                        />
                        <span className="acc-pick-title">سند {fa(e.number ?? 0)}</span>
                        <span className="acc-pick-sub">{e.description || '—'}</span>
                        <span className="acc-pick-meta">{fa(total)}</span>
                      </label>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </AsyncBlock>
      </SectionCard>
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              pickedDate
                ? `${faInt(picked.size)} سندِ ${formatJalali(pickedDate)} علامت خورده؛ برای تاریخِ دیگر اول انتخاب را پاک کنید.`
                : 'دست‌کم دو سندِ هم‌تاریخ را علامت بزنید.'
            }
          />
        }
      >
        <button type="button" className="btn-primary" onClick={() => void run()}>
          <Combine size={15} /> {picked.size > 1 ? `ادغامِ ${faInt(picked.size)} سند` : 'ادغامِ اسناد'}
        </button>
      </ActionBar>
    </OpsPage>
  )
}

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
