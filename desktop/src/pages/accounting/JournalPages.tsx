import { useMemo, useState } from 'react'
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
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react'
import {
  fetchCartable,
  fetchJournalEntriesFiltered,
  fetchRenumberPreview,
  finalizeEntries,
  mergeEntries,
  renumberEntries,
  voidJournalEntry,
  type EntrySummary,
  type JournalEntryRecord,
} from '../../api'
import type { AccountCache, OutboxEntry } from '../../electron.d'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JournalEntryForm } from '../../components/JournalEntryForm'
import { JournalEntryWizard } from '../../components/wizard/JournalEntryWizard'
import { OutboxList } from '../../components/OutboxList'
import { Pager, usePagination } from '../../components/Pager'
import { useTheme } from '../../lib/theme'
import { isElectron } from '../../platform'
import { formatJalali } from '../../lib/jalali'
import {
  AsyncBlock,
  Metric,
  Note,
  OpsPage,
  RangeBar,
  StatusChip,
  fa,
  faAmount,
  faInt,
  sourceLabel,
  useAsync,
  useRange,
  type Msg,
} from './kit'

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
  const guided = useTheme().theme.content === 'guided'

  return (
    <OpsPage
      icon={BookOpen}
      title="سند حسابداری"
      description="ثبتِ سندِ دستی. سندِ تازه «موقت» ثبت می‌شود تا در کارتابل بازبینی شود؛ فاکتور و فیش و چک خودشان خودکار سند می‌خورند. دفترِ کاملِ اسناد زیرِ کارتِ «فهرست» است."
    >
      {guided ? (
        <JournalEntryWizard token={token} accounts={accounts} onQueued={onQueued} />
      ) : (
        <JournalEntryForm token={token} accounts={accounts} onQueued={onQueued} />
      )}

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

/** جدولِ اسنادِ دفتر — تکی و مشترک.
 *
 *  پیش‌تر دو نسخه‌ی کمی‌متفاوت داشت: یکی ته صفحه‌ی «سند حسابداری» (با ابطال، بدونِ
 *  شمارِ ردیف) و یکی در صفحه‌ی فهرستِ «اسناد حسابداری» (با شمارِ ردیف، بدونِ ابطال).
 *  حالا یکی است و ستونِ کنش فقط وقتی می‌آید که `onVoid` داده شود. */
function EntryTable({
  entries,
  pageSize = 20,
  onVoid,
}: {
  entries: JournalEntryRecord[]
  pageSize?: number
  onVoid?: (e: JournalEntryRecord) => void
}) {
  const pg = usePagination(entries, pageSize)
  const total = (e: JournalEntryRecord) =>
    e.lines.reduce((sum, l) => sum + Number(l.debit || 0), 0)

  return (
    <div className="table-scroll">
      <table className="cards-on-mobile acc-table">
        <thead>
          <tr>
            <th>شماره</th>
            {/* عطف کنارِ شماره می‌نشیند چون کاربر این دو را با هم می‌خواند: یکی
                جای سند در دفترِ امروز است، دیگری هویتِ ثابتش. */}
            <th>عطف</th>
            <th>فرعی</th>
            <th>تاریخ</th>
            <th>شرح</th>
            <th>منشأ</th>
            <th>وضعیت</th>
            <th>ردیف</th>
            <th>مبلغ</th>
            {onVoid && <th />}
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((e) => (
            <tr key={e.id} className={e.voided_at ? 'acc-row--void' : ''}>
              <td className="card-title" data-label="شماره">
                {fa(e.number ?? 0)}
              </td>
              <td data-label="عطف" className="num">
                {e.atf_number === null ? '—' : faInt(e.atf_number)}
              </td>
              <td data-label="فرعی">{e.sub_number || '—'}</td>
              <td data-label="تاریخ">{formatJalali(e.entry_date)}</td>
              <td data-label="شرح">{e.description || '—'}</td>
              <td data-label="منشأ">{sourceLabel(e.source_type)}</td>
              <td data-label="وضعیت">
                <StatusChip status={e.status} voided={!!e.voided_at} />
              </td>
              <td data-label="ردیف" className="num">
                {faInt(e.lines.length)}
              </td>
              <td data-label="مبلغ" className="num">
                {faAmount(total(e))}
              </td>
              {onVoid && (
                <td className="acc-row-actions card-actions">
                  {/* فقط سندِ دستی: سندِ خودکار با ابطالِ خودِ فاکتور/فیش برمی‌گردد. */}
                  {!e.voided_at && e.source_type === 'manual' && (
                    <button type="button" className="danger" onClick={() => onVoid(e)}>
                      <Trash2 size={13} /> ابطال
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
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
      <Note msg={msg} />

      <SectionCard
        icon={Layers}
        title="دسته‌ها"
        description="معمولاً تصمیم دسته‌ای است: «همه‌ی سندهای فاکتورِ فروشِ این بازه درست‌اند»."
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
        description={
          data
            ? `${faInt(data.entries.length)} سندِ نخست نمایش داده می‌شود`
            : 'در حال بارگذاری…'
        }
        actions={
          picked.size > 0 ? (
            <button
              type="button"
              className="btn-primary"
              onClick={() =>
                finalize({ entry_ids: [...picked] }, `دائم‌کردنِ ${picked.size} سندِ انتخابی.`)
              }
            >
              <Lock size={13} /> دائم‌کردنِ {faInt(picked.size)} سند
            </button>
          ) : undefined
        }
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
    <div className="table-scroll">
      <table className="cards-on-mobile acc-table">
        <thead>
          <tr>
            <th />
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
              <td data-label="انتخاب">
                <input type="checkbox" checked={picked.has(e.id)} onChange={() => onToggle(e.id)} />
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
              <td data-label="منشأ">{sourceLabel(e.source_type)}</td>
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
      <Note msg={msg} />
      <SectionCard
        icon={Lock}
        title="آنچه دائم می‌شود"
        description="پیش از تأیید، دقیقاً همان چیزی را ببینید که قطعی خواهد شد."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={!data || data.total_count === 0}
            onClick={() => void run()}
          >
            <Lock size={14} /> دائم‌کردنِ همه
          </button>
        }
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
    </OpsPage>
  )
}

// ═══════════════ ۴) شماره‌گذاری مجدد اسناد ═══════════════

export function RenumberEntriesPage({ token }: { token: string }) {
  const range = useRange('year')
  const [start, setStart] = useState('1')
  const [msg, setMsg] = useState<Msg>(null)
  const startNumber = Math.max(1, Number(start) || 1)

  const preview = useAsync(
    () => fetchRenumberPreview(token, range.from, range.to, startNumber),
    [token, range.from, range.to, startNumber],
  )

  async function run() {
    if (
      !window.confirm(
        `شماره‌ی ${preview.data?.count ?? 0} سند به‌ترتیبِ تاریخ از ${startNumber} بازنویسی می‌شود.\nادامه می‌دهید؟`,
      )
    )
      return
    try {
      const out = await renumberEntries(token, {
        date_from: range.from,
        date_to: range.to,
        start_number: startNumber,
      })
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
                <NumberInput value={start} onChange={setStart} />
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
      <Note msg={msg} />
      <SectionCard
        icon={Hash}
        title="پیش‌نمایشِ شماره‌ها"
        description="فقط اسنادِ موقت در نقشه می‌آیند؛ سندِ دائم شماره‌ی امضاشده دارد و جابه‌جا نمی‌شود."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={!data || data.changed_count === 0}
            onClick={() => void run()}
          >
            <Hash size={14} /> اعمالِ شماره‌گذاری
          </button>
        }
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
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
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
    if (picked.size < 2) return
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
      <Note msg={msg} />
      <SectionCard
        icon={Combine}
        title="اسنادِ موقتِ دستی"
        description="فقط روزهایی که بیش از یک سند دارند نشان داده می‌شوند؛ ادغام بینِ دو تاریخ معنا ندارد."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={picked.size < 2}
            onClick={() => void run()}
          >
            <Combine size={14} /> ادغامِ {faInt(picked.size)} سند
          </button>
        }
      >
        <label className="acc-inline-field acc-merge-desc">
          شرحِ سندِ ادغامی (اختیاری)
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="خالی بگذارید تا شماره‌ی اسنادِ اصلی نوشته شود"
          />
        </label>

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
          {pickedDate && (
            <p className="hint">
              انتخاب روی تاریخ {formatJalali(pickedDate)} قفل شد؛ برای تاریخِ دیگر اول انتخاب را پاک کنید.
            </p>
          )}
        </AsyncBlock>
      </SectionCard>
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

  const list = useAsync(
    () =>
      fetchJournalEntriesFiltered(token, {
        dateFrom: range.from,
        dateTo: range.to,
        status: status || undefined,
        q: search || undefined,
        limit: 300,
      }),
    [token, range.from, range.to, status, search, reloadKey],
  )
  const rows = list.data ?? []

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

  return (
    <OpsPage
      icon={FileStack}
      title="اسناد حسابداری"
      description="همه‌ی اسنادِ دفتر — دستی و خودکار، موقت و دائم. «عطف» شماره‌ی ثابتِ سند است و با شماره‌گذاری مجدد عوض نمی‌شود؛ «فرعی» ارجاعِ خودِ شماست. سندِ دستی را می‌توان از همین‌جا ابطال کرد."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <label className="acc-inline-field">
                وضعیت
                <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
                  <option value="">همه</option>
                  <option value="temporary">موقت</option>
                  <option value="permanent">دائم</option>
                </select>
              </label>
            }
          />
        </div>
      }
    >
      <SectionCard
        icon={FileStack}
        title="اسناد"
        description={`${faInt(rows.length)} سند`}
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> به‌روزرسانی
          </button>
        }
      >
        <Note msg={msg} />
        <div className="acc-filters">
          <label className="acc-search">
            <Search size={14} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="شماره، عطف، شماره فرعی یا شرحِ سند"
            />
          </label>
        </div>

        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="سندی با این شرایط پیدا نشد."
        >
          <EntryTable entries={rows} onVoid={handleVoid} />
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
