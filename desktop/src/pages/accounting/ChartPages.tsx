import { useMemo, useState } from 'react'
import {
  ArrowLeftRight,
  ChevronLeft,
  FolderTree,
  Layers,
  ListTree,
  Plus,
  Save,
  Search,
  Tag,
  Trash2,
  Wallet,
  X,
} from 'lucide-react'
import {
  createAccount,
  createAnalytic,
  deleteAnalytic,
  fetchAccountBalances,
  fetchAnalytics,
  fetchChartAccounts,
  fetchNextAccountCode,
  reclassifyAccounts,
  updateAnalytic,
  type AnalyticAccount,
  type BalanceRow,
  type ChartAccount,
} from '../../api'
import { AccountTreePanel } from '../../components/AccountTreePanel'
import { SectionCard } from '../../components/SectionCard'
import { Pager, usePagination } from '../../components/Pager'
import {
  AsyncBlock,
  Metric,
  Note,
  OpsPage,
  RangeBar,
  fa,
  faAmount,
  faInt,
  useAsync,
  useRange,
  type Msg,
} from './kit'

/**
 * پنج عملیاتِ *ساختار*: چارت، سرفصلِ تازه، اصلاحِ طبقه‌بندی، تفصیلیِ سایر، و مرورِ حساب‌ها.
 *
 * چهارتای اول ساختار را می‌سازند و پنجمی همان ساختار را با عدد نشان می‌دهد. جدا
 * نگه‌داشتنِ «مرور» از «چارت» عمدی است: چارت ابزارِ *ویرایش* است و مرور ابزارِ
 * *خواندن*؛ یک صفحه‌ی مشترک هر دو کار را بد انجام می‌داد.
 */

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

// ═════════════════════ ۱) درختواره حساب‌ها ═════════════════════

export function ChartOfAccountsPage({ token, onChanged }: { token: string; onChanged?: () => void }) {
  return (
    <OpsPage
      icon={ListTree}
      title="درختواره حساب‌ها"
      description="ساختارِ کاملِ چارت: سرفصل‌ها، حساب‌های سطحِ آخر، کدینگ و قالب‌های آماده‌ی صنفی."
    >
      <AccountTreePanel token={token} onChanged={onChanged} />
    </OpsPage>
  )
}

// ═══════════════════════ ۲) سرفصل جدید ═══════════════════════

export function NewAccountPage({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const accounts = useAsync(() => fetchChartAccounts(token), [token, reloadKey])

  const [form, setForm] = useState({
    code: '',
    name: '',
    type: 'expense',
    is_group: false,
    parent_id: '' as string,
  })

  const groups = useMemo(
    () => (accounts.data ?? []).filter((a) => a.is_group).sort((a, b) => a.code.localeCompare(b.code)),
    [accounts.data],
  )

  /** انتخابِ سرفصلِ مادر، نوع را هم تعیین می‌کند و کدِ آزادِ بعدی را از سرور می‌گیرد.
   *  حدس‌زدنِ کد در مرورگر یعنی دو پیاده‌سازیِ قاعده‌ی کدینگ؛ سرور همان را می‌داند. */
  async function pickParent(parentId: string) {
    const parent = groups.find((g) => g.id === parentId)
    setForm((f) => ({ ...f, parent_id: parentId, type: parent?.type ?? f.type }))
    try {
      const next = await fetchNextAccountCode(token, parentId || null)
      setForm((f) => ({ ...f, parent_id: parentId, type: parent?.type ?? f.type, code: next.code }))
    } catch {
      // نبودنِ پیشنهادِ کد نباید فرم را قفل کند؛ کاربر خودش می‌نویسد.
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    try {
      const created = await createAccount(token, {
        code: form.code.trim(),
        name: form.name.trim(),
        type: form.type,
        is_group: form.is_group,
        parent_id: form.parent_id || null,
      })
      setMsg({ text: `حسابِ «${created.name}» با کد ${created.code} ساخته شد.`, kind: 'ok' })
      setForm({ code: '', name: '', type: form.type, is_group: false, parent_id: form.parent_id })
      setReloadKey((k) => k + 1)
      onChanged?.()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const recent = useMemo(
    () =>
      [...(accounts.data ?? [])]
        .filter((a) => !a.system_role)
        .sort((a, b) => b.code.localeCompare(a.code))
        .slice(0, 12),
    [accounts.data],
  )

  return (
    <OpsPage
      icon={Plus}
      title="سرفصل جدید"
      description="افزودنِ یک حساب یا سرفصلِ تازه به چارت. سرفصل فقط دسته‌بندی می‌کند و سند مستقیم نمی‌گیرد؛ حسابِ سطحِ آخر است که سند می‌خورد."
    >
      <Note msg={msg} />
      <SectionCard
        icon={Plus}
        title="مشخصاتِ حساب"
        description="اول سرفصلِ مادر را انتخاب کنید تا نوع و کدِ پیشنهادی خودکار پر شوند."
      >
        <form className="invoice-form" onSubmit={submit}>
          <label>
            سرفصلِ مادر
            <select value={form.parent_id} onChange={(e) => void pickParent(e.target.value)}>
              <option value="">— بدونِ مادر (ریشه) —</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.code} — {g.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            کدِ حساب
            <input
              type="text"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              dir="ltr"
              required
            />
          </label>
          <label>
            نامِ حساب
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </label>
          <label>
            نوعِ حساب
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {Object.entries(TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="cal-check-inline">
            <input
              type="checkbox"
              checked={form.is_group}
              onChange={(e) => setForm({ ...form, is_group: e.target.checked })}
            />
            سرفصل است (سند مستقیم نمی‌گیرد)
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Save size={14} /> ساختِ حساب
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard icon={ListTree} title="تازه‌ترین حساب‌ها" description="آخرین کدهای چارت.">
        <AsyncBlock
          loading={accounts.loading}
          error={accounts.error}
          empty={recent.length === 0}
          emptyText="هنوز حسابِ سفارشی‌ای ساخته نشده."
        >
          <ul className="acc-groups">
            {recent.map((a) => (
              <li key={a.id}>
                <span className="acc-group-name">
                  <span dir="ltr">{a.code}</span> — {a.name}
                </span>
                <span className="acc-group-count">{TYPE_LABELS[a.type] ?? a.type}</span>
                <span className="acc-group-total">{a.is_group ? 'سرفصل' : 'حساب'}</span>
              </li>
            ))}
          </ul>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ ۳) اصلاح طبقه‌بندی حساب‌ها ═════════════════

export function ReclassifyPage({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [search, setSearch] = useState('')
  const [edits, setEdits] = useState<Record<string, string>>({})
  const accounts = useAsync(() => fetchChartAccounts(token), [token, reloadKey])

  //: آرایه‌ی تازه در هر رندر، وابستگیِ useMemoهای پایین را بی‌فایده می‌کرد.
  const all = useMemo(() => accounts.data ?? [], [accounts.data])
  const byId = useMemo(() => new Map(all.map((a) => [a.id, a])), [all])
  const groups = useMemo(
    () => all.filter((a) => a.is_group).sort((a, b) => a.code.localeCompare(b.code)),
    [all],
  )

  //: حسابِ نقش‌دار عمداً بیرون است — ثبتِ خودکار رویش تکیه دارد و جابه‌جایی‌اش را
  //: سرور هم رد می‌کند. نشان‌دادنش فقط راهِ خطا بود.
  const movable = useMemo(
    () =>
      all
        .filter((a) => !a.system_role)
        .filter((a) => {
          const term = search.trim()
          if (!term) return true
          return a.name.includes(term) || a.code.includes(term)
        })
        .sort((a, b) => a.code.localeCompare(b.code)),
    [all, search],
  )

  const pending = Object.entries(edits).filter(([id, parentId]) => byId.get(id)?.parent_id !== parentId)

  async function apply() {
    if (pending.length === 0) return
    try {
      const out = await reclassifyAccounts(
        token,
        pending.map(([id, parentId]) => ({
          account_id: id,
          parent_id: parentId || null,
          type: byId.get(parentId)?.type ?? byId.get(id)?.type,
        })),
      )
      setMsg({ text: `${faInt(out.count)} حساب جابه‌جا شد.`, kind: 'ok' })
      setEdits({})
      setReloadKey((k) => k + 1)
      onChanged?.()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const pg = usePagination(movable, 20)

  return (
    <OpsPage
      icon={ArrowLeftRight}
      title="اصلاح طبقه‌بندی حساب‌ها"
      description="جابه‌جاییِ دسته‌ایِ حساب‌ها زیرِ سرفصلِ درست. نوعِ حساب از سرفصلِ مقصد گرفته می‌شود تا ترازنامه و سود و زیان یک چیز بگویند."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-search">
              <Search size={14} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="نام یا کدِ حساب"
              />
            </label>
            <button
              type="button"
              className="btn-primary"
              disabled={pending.length === 0}
              onClick={() => void apply()}
            >
              <Save size={14} /> اعمالِ {faInt(pending.length)} تغییر
            </button>
            {pending.length > 0 && (
              <button type="button" onClick={() => setEdits({})}>
                <X size={13} /> انصراف
              </button>
            )}
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <SectionCard
        icon={FolderTree}
        title="حساب‌های قابلِ جابه‌جایی"
        description="حساب‌های دارای نقشِ سیستمی (صندوق، بانک، …) نشان داده نمی‌شوند؛ ثبتِ خودکار به آن‌ها گره خورده."
      >
        <AsyncBlock
          loading={accounts.loading}
          error={accounts.error}
          empty={movable.length === 0}
          emptyText="حسابی با این جست‌وجو پیدا نشد."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>نوعِ فعلی</th>
                  <th>سرفصلِ فعلی</th>
                  <th>سرفصلِ تازه</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((a) => {
                  const chosen = edits[a.id] ?? a.parent_id ?? ''
                  const changed = chosen !== (a.parent_id ?? '')
                  return (
                    <tr key={a.id} className={changed ? 'acc-row--changed' : ''}>
                      <td className="card-title" data-label="کد" dir="ltr">
                        {a.code}
                      </td>
                      <td data-label="نام">{a.name}</td>
                      <td data-label="نوعِ فعلی">{TYPE_LABELS[a.type] ?? a.type}</td>
                      <td data-label="سرفصلِ فعلی">
                        {a.parent_id ? byId.get(a.parent_id)?.name ?? '—' : '— ریشه —'}
                      </td>
                      <td data-label="سرفصلِ تازه">
                        <select
                          value={chosen}
                          onChange={(e) => setEdits({ ...edits, [a.id]: e.target.value })}
                        >
                          <option value="">— ریشه —</option>
                          {groups
                            .filter((g) => g.id !== a.id)
                            .map((g) => (
                              <option key={g.id} value={g.id}>
                                {g.code} — {g.name}
                              </option>
                            ))}
                        </select>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════════ ۴) تفصیلی سایر ═══════════════════════

const EMPTY_ANALYTIC = { code: '', name: '', group_name: '', description: '' }

export function AnalyticsPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [form, setForm] = useState(EMPTY_ANALYTIC)
  const [editing, setEditing] = useState<AnalyticAccount | null>(null)
  const list = useAsync(() => fetchAnalytics(token), [token])

  const rows = useMemo(() => list.data ?? [], [list.data])
  const grouped = useMemo(() => {
    const map = new Map<string, AnalyticAccount[]>()
    for (const row of rows) {
      const key = row.group_name || 'بدونِ دسته'
      map.set(key, [...(map.get(key) ?? []), row])
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [rows])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    try {
      if (editing) {
        await updateAnalytic(token, editing.id, form)
        setMsg({ text: `تفصیلیِ «${form.name}» به‌روز شد.`, kind: 'ok' })
      } else {
        await createAnalytic(token, form)
        setMsg({ text: `تفصیلیِ «${form.name}» ساخته شد.`, kind: 'ok' })
      }
      setForm(EMPTY_ANALYTIC)
      setEditing(null)
      list.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function toggleActive(row: AnalyticAccount) {
    try {
      await updateAnalytic(token, row.id, { is_active: !row.is_active })
      list.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function remove(row: AnalyticAccount) {
    if (!window.confirm(`تفصیلیِ «${row.name}» حذف شود؟`)) return
    try {
      await deleteAnalytic(token, row.id)
      list.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  return (
    <OpsPage
      icon={Tag}
      title="تفصیلی سایر"
      description="بُعدِ تحلیلیِ آزادِ ردیفِ سند — برای هرچه نه طرف‌حساب است نه مرکزِ هزینه: خودرو، قرارداد، دستگاه، پرونده."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Tag size={14} />} label="تفصیلی‌ها" value={faInt(rows.length)} />
            <Metric
              icon={<Layers size={14} />}
              label="دسته‌ها"
              value={faInt(grouped.length)}
            />
            <Metric
              icon={<Wallet size={14} />}
              label="ردیف‌های برچسب‌خورده"
              value={faInt(rows.reduce((s, r) => s + r.line_count, 0))}
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={editing ? Save : Plus}
        title={editing ? `ویرایشِ «${editing.name}»` : 'تفصیلیِ تازه'}
        description="کد یکتاست و در گزارش‌ها به‌جای نام استفاده می‌شود."
        actions={
          editing ? (
            <button
              type="button"
              onClick={() => {
                setEditing(null)
                setForm(EMPTY_ANALYTIC)
              }}
            >
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        <form className="invoice-form" onSubmit={submit}>
          <label>
            کد
            <input
              type="text"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              dir="ltr"
              required
            />
          </label>
          <label>
            نام
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </label>
          <label>
            دسته (اختیاری)
            <input
              type="text"
              value={form.group_name}
              onChange={(e) => setForm({ ...form, group_name: e.target.value })}
              placeholder="مثلاً خودرو"
            />
          </label>
          <label>
            توضیح
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Save size={14} /> {editing ? 'ذخیره' : 'ساخت'}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard icon={Tag} title="فهرستِ تفصیلی‌ها">
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="هنوز تفصیلی‌ای تعریف نشده."
        >
          {grouped.map(([group, items]) => (
            <div className="acc-day" key={group}>
              <h4 className="acc-day-head">
                {group} <span>{faInt(items.length)} مورد</span>
              </h4>
              <div className="table-scroll">
                <table className="cards-on-mobile acc-table">
                  <thead>
                    <tr>
                      <th>کد</th>
                      <th>نام</th>
                      <th>توضیح</th>
                      <th>ردیفِ سند</th>
                      <th>وضعیت</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr key={row.id} className={row.is_active ? '' : 'acc-row--muted'}>
                        <td className="card-title" data-label="کد" dir="ltr">
                          {row.code}
                        </td>
                        <td data-label="نام">{row.name}</td>
                        <td data-label="توضیح">{row.description || '—'}</td>
                        <td data-label="ردیفِ سند" className="num">
                          {faInt(row.line_count)}
                        </td>
                        <td data-label="وضعیت">{row.is_active ? 'فعال' : 'غیرفعال'}</td>
                        <td className="acc-row-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setEditing(row)
                              setForm({
                                code: row.code,
                                name: row.name,
                                group_name: row.group_name,
                                description: row.description,
                              })
                            }}
                          >
                            <Save size={13} /> ویرایش
                          </button>
                          <button type="button" onClick={() => void toggleActive(row)}>
                            {row.is_active ? 'غیرفعال' : 'فعال'}
                          </button>
                          {row.line_count === 0 && (
                            <button type="button" className="danger" onClick={() => void remove(row)}>
                              <Trash2 size={13} />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════════ ۵) مرور حساب‌ها ═══════════════════════

interface BrowseNode {
  account: ChartAccount
  children: BrowseNode[]
  own: BalanceRow | null
  debit: number
  credit: number
}

/** درختِ چارت را با ارقامِ *تجمیعی* می‌سازد: هر سرفصل جمعِ زیرشاخه‌هایش است.
 *  بدونِ رول‌آپ، «مرور» فقط یک تراز آزمایشیِ تخت می‌شد که از قبل داشتیم. */
function buildTree(accounts: ChartAccount[], balances: BalanceRow[]): BrowseNode[] {
  const byAccount = new Map(balances.map((b) => [b.account_id, b]))
  const nodes = new Map<string, BrowseNode>()
  for (const account of accounts) {
    const own = byAccount.get(account.id) ?? null
    nodes.set(account.id, {
      account,
      children: [],
      own,
      debit: own ? Number(own.period_debit) : 0,
      credit: own ? Number(own.period_credit) : 0,
    })
  }
  const roots: BrowseNode[] = []
  for (const node of nodes.values()) {
    const parent = node.account.parent_id ? nodes.get(node.account.parent_id) : null
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  const rollup = (node: BrowseNode): { debit: number; credit: number } => {
    for (const child of node.children) {
      const sums = rollup(child)
      node.debit += sums.debit
      node.credit += sums.credit
    }
    node.children.sort((a, b) => a.account.code.localeCompare(b.account.code))
    return { debit: node.debit, credit: node.credit }
  }
  roots.forEach(rollup)
  return roots.sort((a, b) => a.account.code.localeCompare(b.account.code))
}

export function AccountBrowsePage({ token }: { token: string }) {
  const range = useRange('year')
  const [path, setPath] = useState<string[]>([])
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const balances = useAsync(
    () => fetchAccountBalances(token, range.from, range.to),
    [token, range.from, range.to],
  )

  const tree = useMemo(
    () => buildTree(accounts.data ?? [], balances.data ?? []),
    [accounts.data, balances.data],
  )

  // مسیرِ فعلی: از ریشه تا گرهی که کاربر داخلش رفته.
  const trail = useMemo(() => {
    const out: BrowseNode[] = []
    let level = tree
    for (const id of path) {
      const found = level.find((n) => n.account.id === id)
      if (!found) break
      out.push(found)
      level = found.children
    }
    return out
  }, [tree, path])

  const current = trail.length ? trail[trail.length - 1].children : tree
  const totalDebit = current.reduce((s, n) => s + n.debit, 0)
  const totalCredit = current.reduce((s, n) => s + n.credit, 0)

  return (
    <OpsPage
      icon={Layers}
      title="مرور حساب‌ها"
      description="از سرفصل تا حسابِ سطحِ آخر، سطح‌به‌سطح. رقمِ هر سرفصل جمعِ زیرشاخه‌هایش است."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<Layers size={14} />} label="سطحِ فعلی" value={faInt(current.length)} />
            <Metric icon={<Wallet size={14} />} label="گردشِ بدهکار" value={fa(totalDebit)} tone="in" />
            <Metric icon={<Wallet size={14} />} label="گردشِ بستانکار" value={fa(totalCredit)} tone="out" />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={FolderTree}
        title="مرور"
        description="روی هر سرفصل کلیک کنید تا داخلش بروید."
      >
        <nav className="acc-trail">
          <button type="button" onClick={() => setPath([])} className={path.length ? '' : 'is-active'}>
            کلِ چارت
          </button>
          {trail.map((node, i) => (
            <span key={node.account.id}>
              <ChevronLeft size={13} />
              <button
                type="button"
                className={i === trail.length - 1 ? 'is-active' : ''}
                onClick={() => setPath(path.slice(0, i + 1))}
              >
                {node.account.name}
              </button>
            </span>
          ))}
        </nav>

        <AsyncBlock
          loading={accounts.loading || balances.loading}
          error={accounts.error ?? balances.error}
          empty={current.length === 0}
          emptyText="این حساب زیرمجموعه ندارد — سطحِ آخر است."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>نوع</th>
                  <th>گردشِ بدهکار</th>
                  <th>گردشِ بستانکار</th>
                  <th>مانده</th>
                </tr>
              </thead>
              <tbody>
                {current.map((node) => {
                  const net = node.debit - node.credit
                  return (
                    <tr
                      key={node.account.id}
                      className={node.children.length ? 'acc-row--clickable' : ''}
                      onClick={() =>
                        node.children.length ? setPath([...path, node.account.id]) : undefined
                      }
                    >
                      <td className="card-title" data-label="کد" dir="ltr">
                        {node.account.code}
                      </td>
                      <td data-label="نام">
                        {node.children.length ? <FolderTree size={13} /> : null} {node.account.name}
                      </td>
                      <td data-label="نوع">{TYPE_LABELS[node.account.type] ?? node.account.type}</td>
                      <td data-label="گردشِ بدهکار" className="num">
                        {faAmount(node.debit)}
                      </td>
                      <td data-label="گردشِ بستانکار" className="num">
                        {faAmount(node.credit)}
                      </td>
                      <td data-label="مانده" className="num">
                        {net === 0 ? '—' : `${fa(Math.abs(net))} ${net > 0 ? 'بد' : 'بس'}`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

/** فهرستِ تختِ حساب‌ها — صفحه‌ی «فهرست» ماژول، برای جست‌وجوی سریعِ یک کد. */
export function AccountListPage({ token }: { token: string }) {
  const [search, setSearch] = useState('')
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const rows = useMemo(() => {
    const term = search.trim()
    return (accounts.data ?? [])
      .filter((a) => !term || a.name.includes(term) || a.code.includes(term))
      .sort((a, b) => a.code.localeCompare(b.code))
  }, [accounts.data, search])
  const pg = usePagination(rows, 25)

  return (
    <OpsPage
      icon={ListTree}
      title="فهرست حساب‌ها"
      description="نمای تختِ چارت برای پیداکردنِ سریعِ یک حساب یا کد."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-search">
              <Search size={14} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="نام یا کدِ حساب"
              />
            </label>
          </div>
        </div>
      }
    >
      <SectionCard icon={ListTree} title="حساب‌ها" description={`${faInt(rows.length)} حساب`}>
        <AsyncBlock
          loading={accounts.loading}
          error={accounts.error}
          empty={rows.length === 0}
          emptyText="حسابی پیدا نشد."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>نوع</th>
                  <th>سطح</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((a) => (
                  <tr key={a.id} className={a.is_active ? '' : 'acc-row--muted'}>
                    <td className="card-title" data-label="کد" dir="ltr">
                      {a.code}
                    </td>
                    <td data-label="نام">{a.name}</td>
                    <td data-label="نوع">{TYPE_LABELS[a.type] ?? a.type}</td>
                    <td data-label="سطح">{a.is_group ? 'سرفصل' : 'حساب'}</td>
                    <td data-label="وضعیت">{a.is_active ? 'فعال' : 'غیرفعال'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
