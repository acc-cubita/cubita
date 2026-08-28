import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronDown,
  FolderTree,
  Hash,
  ListTree,
  Minus,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react'
import {
  applyChartTemplate,
  changeAccountCode,
  createAccount,
  deleteAccount,
  fetchChartAccounts,
  fetchChartTemplates,
  fetchNextAccountCode,
  fetchTrialBalance,
  updateAccount,
  type ChartAccount,
  type ChartTemplate,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { AccountLedgerDrawer } from './AccountLedgerDrawer'

export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی', liability: 'بدهی', equity: 'سرمایه', income: 'درآمد', expense: 'هزینه',
}
const TYPE_TONE: Record<string, string> = {
  asset: 'success', liability: 'warning', equity: 'default', income: 'success', expense: 'danger',
}

/**
 * درختواره‌ی حساب‌ها — کدینگِ حسابداری.
 *
 * جانشینِ جدولِ تختِ صفحه‌بندی‌شده‌ی قبلی. چارتِ حساب ذاتاً درخت است و نمایشِ تختِ ۱۰تایی
 * دقیقاً همان چیزی را پنهان می‌کرد که مهم است: **رابطه‌ی پدر و فرزند**. با ۶۰-۷۰ حساب،
 * حسابدار باید بتواند یک سرفصل را باز کند و زیرمجموعه‌اش را ببیند، نه بین ۷ صفحه بگردد.
 *
 * چهار چیز به آن اضافه شده که کدینگ را کامل می‌کند:
 *  ۱. **سطحِ حساب** (گروه/کل/معین/تفصیلی) از عمقِ درخت — واژگانِ حسابداریِ ایران.
 *  ۲. **مانده‌ی هر حساب** و جمعِ سرفصل‌ها، که از تراز آزمایشی می‌آید و پایین‌به‌بالا جمع می‌شود.
 *  ۳. **تغییرِ کدِ حساب**؛ امن است چون ثبتِ خودکار حساب را با `system_role` پیدا می‌کند نه با کد.
 *  ۴. **قالب‌های آماده‌ی صنفی** برای درجِ یک‌جای ده‌ها حسابِ استاندارد.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const money = (n: number) => Math.round(n).toLocaleString('fa-IR')

/** واژگانِ سطحِ حساب در حسابداریِ ایران، بر پایه‌ی عمق در درخت. */
const LEVEL_LABELS = ['گروه', 'کل', 'معین', 'تفصیلی']
const levelOf = (depth: number) => LEVEL_LABELS[Math.min(depth, LEVEL_LABELS.length - 1)]

interface Node extends ChartAccount {
  depth: number
  children: Node[]
  /** مانده‌ی خودِ حساب (برگ) یا جمعِ زیرمجموعه (سرفصل). */
  balance: number
}

/** فهرستِ تخت را به درخت تبدیل می‌کند و مانده‌ها را پایین‌به‌بالا جمع می‌زند. */
function buildTree(accounts: ChartAccount[], balances: Map<string, number>): Node[] {
  const nodes = new Map<string, Node>()
  for (const a of accounts) nodes.set(a.id, { ...a, depth: 0, children: [], balance: balances.get(a.id) ?? 0 })

  const roots: Node[] = []
  for (const node of nodes.values()) {
    const parent = node.parent_id ? nodes.get(node.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }

  const byCode = (a: Node, b: Node) => a.code.localeCompare(b.code, 'en', { numeric: true })
  const walk = (list: Node[], depth: number): number => {
    list.sort(byCode)
    let sum = 0
    for (const node of list) {
      node.depth = depth
      const childSum = walk(node.children, depth + 1)
      // سرفصل مانده‌ی مستقیم ندارد؛ مانده‌اش جمعِ فرزندان است.
      if (node.children.length > 0) node.balance = childSum
      sum += node.balance
    }
    return sum
  }
  walk(roots, 0)
  return roots
}

/** گره‌هایی که با جست‌وجو می‌مانند — به‌همراه همه‌ی نیاکانشان، تا مسیر گم نشود. */
function matchingIds(roots: Node[], query: string): Set<string> | null {
  const q = query.trim()
  if (!q) return null
  const keep = new Set<string>()
  const visit = (node: Node, ancestors: string[]): boolean => {
    const hit = node.name.includes(q) || node.code.includes(q)
    let childHit = false
    for (const child of node.children) childHit = visit(child, [...ancestors, node.id]) || childHit
    if (hit || childHit) {
      keep.add(node.id)
      for (const id of ancestors) keep.add(id)
      return true
    }
    return false
  }
  for (const root of roots) visit(root, [])
  return keep
}

export function AccountTreePanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [accounts, setAccounts] = useState<ChartAccount[] | null>(null)
  const [balances, setBalances] = useState<Map<string, number>>(new Map())
  const [templates, setTemplates] = useState<ChartTemplate[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showInactive, setShowInactive] = useState(true)
  // درخت پیش‌فرض **بسته** است: با ۶۰+ حساب، بازبودنِ همه یعنی دیواری از ردیف که
  // هیچ ساختاری نشان نمی‌دهد. کاربر هر سرفصلی را که لازم دارد باز می‌کند.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  //: فقط بارِ اول جمع می‌شود؛ به‌روزرسانی‌های بعدی نباید آنچه کاربر باز کرده را ببندند.
  const didCollapseRef = useRef(false)
  const [ledger, setLedger] = useState<{ id: string; code: string; name: string } | null>(null)
  const [busy, setBusy] = useState(false)
  /** سرفصلی که فرمِ «افزودن زیرحساب» زیرش باز است. */
  const [addUnder, setAddUnder] = useState<Node | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')
  const [newIsGroup, setNewIsGroup] = useState(false)
  const [newCodeHint, setNewCodeHint] = useState('')

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [list, tb] = await Promise.all([
        fetchChartAccounts(token),
        // مانده‌ها اختیاری‌اند: اگر نیامدند، درخت بدونِ ستونِ مانده کار می‌کند.
        fetchTrialBalance(token).catch(() => []),
      ])
      setAccounts(list)
      setBalances(new Map(tb.map((r) => [r.account_id, Number(r.balance) || 0])))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => {
    void refresh()
    void fetchChartTemplates(token).then(setTemplates).catch(() => {})
  }, [refresh, token])

  const roots = useMemo(() => buildTree(accounts ?? [], balances), [accounts, balances])

  useEffect(() => {
    if (didCollapseRef.current || roots.length === 0) return
    didCollapseRef.current = true
    const ids: string[] = []
    const walk = (list: Node[]) =>
      list.forEach((n) => {
        if (n.children.length) {
          ids.push(n.id)
          walk(n.children)
        }
      })
    walk(roots)
    setCollapsed(new Set(ids))
  }, [roots])
  const visibleIds = useMemo(() => matchingIds(roots, search), [roots, search])

  async function run(action: () => Promise<string>) {
    setBusy(true)
    setMsg(null)
    try {
      setMsg({ text: await action(), kind: 'ok' })
      await refresh()
      onChanged?.()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  function toggle(id: string) {
    setCollapsed((c) => {
      const next = new Set(c)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allGroupIds = useMemo(() => {
    const ids: string[] = []
    const walk = (list: Node[]) => list.forEach((n) => { if (n.children.length) { ids.push(n.id); walk(n.children) } })
    walk(roots)
    return ids
  }, [roots])

  /**
   * کدِ پیشنهادی از سرور می‌آید نه از حدسِ محلی، چون قاعده‌ی کدینگ (رقمِ هر سطح)
   * آن‌جا تعریف شده و همان‌جا هم اعمال می‌شود. حدس‌زدنِ محلی یعنی فرم کدی پیشنهاد
   * بدهد که سرور ردش کند.
   */
  function openAdd(parent: Node) {
    setAddUnder(parent)
    setNewName('')
    setNewIsGroup(false)
    setNewCode('')
    setNewCodeHint('')
    void fetchNextAccountCode(token, parent.id)
      .then((r) => {
        setNewCode(r.code)
        setNewCodeHint(`سطحِ ${r.level} — ${r.digits.toLocaleString('fa-IR')} رقمِ افزوده`)
      })
      .catch(() => setNewCodeHint('کدِ پیشنهادی خوانده نشد؛ کد را دستی وارد کنید.'))
  }

  function submitAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!addUnder) return
    const parent = addUnder
    void run(async () => {
      await createAccount(token, {
        code: newCode.trim(),
        name: newName.trim(),
        type: parent.type,
        is_group: newIsGroup,
        parent_id: parent.id,
      })
      setAddUnder(null)
      return `حساب «${newName.trim()}» زیرِ «${parent.name}» ساخته شد.`
    })
  }

  function rename(a: Node) {
    const next = window.prompt(`نامِ تازه برای «${a.name}»:`, a.name)
    if (next === null || !next.trim() || next.trim() === a.name) return
    void run(async () => {
      await updateAccount(token, a.id, { name: next.trim() })
      return 'نامِ حساب تغییر کرد.'
    })
  }

  function recode(a: Node) {
    const next = window.prompt(
      `کدِ تازه برای «${a.name}»:\n\nتغییرِ کد امن است — منطقِ ثبتِ خودکار حساب را با نقشش می‌شناسد نه با کدش.`,
      a.code,
    )
    if (next === null || !next.trim() || next.trim() === a.code) return
    void run(async () => {
      await changeAccountCode(token, a.id, next.trim())
      return `کدِ «${a.name}» به ${next.trim()} تغییر کرد.`
    })
  }

  function applyTemplate(t: ChartTemplate) {
    if (
      !window.confirm(
        `«${t.label}» اعمال شود؟\n\n${fa(t.missing)} حسابِ نبود ساخته می‌شود. حساب‌های موجود دست نمی‌خورند و اجرای دوباره بی‌اثر است.`,
      )
    )
      return
    void run(async () => {
      const res = await applyChartTemplate(token, t.key)
      const fresh = await fetchChartTemplates(token)
      setTemplates(fresh)
      return res.created === 0
        ? `همه‌ی حساب‌های «${t.label}» از قبل وجود داشتند؛ چیزی اضافه نشد.`
        : `${fa(res.created)} حساب از «${t.label}» اضافه شد.`
    })
  }

  const counts = useMemo(() => {
    const list = accounts ?? []
    return {
      total: list.length,
      groups: list.filter((a) => a.is_group).length,
      leaves: list.filter((a) => !a.is_group).length,
      inactive: list.filter((a) => !a.is_active).length,
    }
  }, [accounts])

  function renderRows(list: Node[]): React.ReactNode[] {
    const out: React.ReactNode[] = []
    for (const node of list) {
      if (visibleIds && !visibleIds.has(node.id)) continue
      if (typeFilter && node.type !== typeFilter) continue
      if (!showInactive && !node.is_active && !node.is_group) continue

      const hasChildren = node.children.length > 0
      // در حالتِ جست‌وجو همه‌چیز باز است، وگرنه مسیرِ نتیجه پنهان می‌ماند.
      const isCollapsed = !search && collapsed.has(node.id)

      out.push(
        <tr key={node.id} className={node.is_group ? 'group-row' : ''}>
          <td data-label="حساب">
            <div className="tree-cell" style={{ paddingInlineStart: `${node.depth * 18}px` }}>
              {hasChildren ? (
                <button type="button" className="tree-toggle" onClick={() => toggle(node.id)}>
                  {isCollapsed ? <ChevronLeft size={14} /> : <ChevronDown size={14} />}
                </button>
              ) : (
                <span className="tree-toggle tree-toggle--leaf">
                  <Minus size={10} />
                </span>
              )}
              <span className="tree-code">{node.code}</span>
              {node.is_group && <FolderTree size={13} className="chart-group-icon" />}
              <span className={node.is_group ? 'chart-group-name' : 'entity-name'}>{node.name}</span>
              {node.system_role && <span className="chart-sys-tag">سیستمی</span>}
              {!node.is_active && <span className="fy-badge fy-badge--closed">غیرفعال</span>}
            </div>
          </td>
          <td data-label="سطح">
            <span className="tree-level">{levelOf(node.depth)}</span>
          </td>
          <td data-label="نوع">
            <span className={`status-badge tone-${TYPE_TONE[node.type] ?? 'default'}`}>
              {ACCOUNT_TYPE_LABELS[node.type] ?? node.type}
            </span>
          </td>
          <td data-label="مانده" className="tree-balance">
            {node.balance === 0 ? '—' : money(node.balance)}
          </td>
          <td className="check-actions card-actions">
            {node.is_group && (
              <button type="button" onClick={() => openAdd(node)} disabled={busy} title="افزودنِ زیرحساب">
                <Plus size={13} />
              </button>
            )}
            {!node.is_group && (
              <button
                type="button"
                onClick={() => setLedger({ id: node.id, code: node.code, name: node.name })}
                title="کارتِ حساب"
              >
                <BookOpen size={13} />
              </button>
            )}
            <button type="button" onClick={() => rename(node)} disabled={busy} title="تغییرِ نام">
              <Pencil size={13} />
            </button>
            <button type="button" onClick={() => recode(node)} disabled={busy} title="تغییرِ کد">
              <Hash size={13} />
            </button>
            {!node.system_role && (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await updateAccount(token, node.id, { is_active: !node.is_active })
                    return node.is_active ? 'حساب غیرفعال شد.' : 'حساب فعال شد.'
                  })
                }
              >
                {node.is_active ? 'غیرفعال' : 'فعال'}
              </button>
            )}
            {!node.system_role && !node.children.length && (
              <button
                type="button"
                className="icon-btn-danger"
                disabled={busy}
                aria-label="حذف حساب"
                onClick={() => {
                  if (!window.confirm(`حسابِ «${node.name}» حذف شود؟ (فقط حسابِ بی‌سند حذف می‌شود)`)) return
                  void run(async () => {
                    await deleteAccount(token, node.id)
                    return 'حساب حذف شد.'
                  })
                }}
              >
                <Trash2 size={13} />
              </button>
            )}
          </td>
        </tr>,
      )

      if (addUnder?.id === node.id) {
        out.push(
          <tr key={`${node.id}-add`} className="tree-add-row">
            <td colSpan={5}>
              <form className="tree-add" onSubmit={submitAdd}>
                <span className="tree-add-label">زیرِ «{node.name}»:</span>
                <input
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  placeholder="کد"
                  title={newCodeHint}
                  required
                />
                <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="نام حساب" required />
                <label className="fy-check">
                  <input type="checkbox" checked={newIsGroup} onChange={(e) => setNewIsGroup(e.target.checked)} />
                  سرفصل است
                </label>
                <button type="submit" className="btn-primary" disabled={busy}>
                  <Save size={13} /> ثبت
                </button>
                <button type="button" onClick={() => setAddUnder(null)}>انصراف</button>
                {newCodeHint && <span className="bk-hint">{newCodeHint}</span>}
              </form>
            </td>
          </tr>,
        )
      }

      if (hasChildren && !isCollapsed) out.push(...renderRows(node.children))
    }
    return out
  }

  return (
    <>
      <SectionCard
        icon={Sparkles}
        title="درج حساب‌های پیش‌فرض"
        description="حساب‌های استانداردِ صنفتان را یک‌جا اضافه کنید. هر قالب = حساب‌های عمومی + حساب‌های تخصصیِ همان صنف."
      >
        {templates.length === 0 ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <div className="tpl-grid">
            {templates.map((t) => (
              <button
                key={t.key}
                type="button"
                className={`tpl-card${t.missing === 0 ? ' done' : ''}`}
                onClick={() => applyTemplate(t)}
                disabled={busy || t.missing === 0}
              >
                <span className="tpl-title">{t.label}</span>
                <span className="tpl-hint">{t.hint}</span>
                <span className="tpl-meta">
                  {t.missing === 0
                    ? 'همه‌ی حساب‌ها موجود است'
                    : `${fa(t.missing)} حساب از ${fa(t.total)} اضافه می‌شود`}
                </span>
              </button>
            ))}
          </div>
        )}
        <p className="bk-hint">
          حسابِ موجود هرگز دست نمی‌خورد و اجرای دوباره چیزی اضافه نمی‌کند. می‌توانید بیش از یک قالب را
          اعمال کنید — مثلاً کسب‌وکاری که هم تولید دارد هم بازرگانی.
        </p>
      </SectionCard>

      <SectionCard
        icon={ListTree}
        title="درختواره‌ی حساب‌ها"
        description={
          accounts
            ? `${fa(counts.total)} حساب — ${fa(counts.groups)} سرفصل، ${fa(counts.leaves)} حسابِ قابلِ ثبت${counts.inactive ? `، ${fa(counts.inactive)} غیرفعال` : ''}`
            : ''
        }
        actions={
          <div className="check-actions">
            <input
              type="text"
              placeholder="جستجو نام یا کد…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">همه‌ی انواع</option>
              {Object.entries(ACCOUNT_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <button type="button" onClick={() => setCollapsed(new Set())}>بازکردن همه</button>
            <button type="button" onClick={() => setCollapsed(new Set(allGroupIds))}>بستن همه</button>
            <button type="button" onClick={() => void refresh()} title="به‌روزرسانی">
              <RefreshCw size={13} />
            </button>
          </div>
        }
      >
        {error && <div className="fy-note fy-note--err"><AlertTriangle size={16} /><div>{error}</div></div>}
        {msg && (
          <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
            {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            <div>{msg.text}</div>
          </div>
        )}

        <label className="fy-check tree-inactive">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          نمایشِ حساب‌های غیرفعال
        </label>

        {accounts == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : roots.length === 0 ? (
          <EmptyState icon={ListTree} text="حسابی وجود ندارد." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table chart-table tree-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>حساب</th>
                    <th>سطح</th>
                    <th>نوع</th>
                    <th>مانده</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>{renderRows(roots)}</tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>

      {ledger && <AccountLedgerDrawer token={token} account={ledger} onClose={() => setLedger(null)} />}
    </>
  )
}
