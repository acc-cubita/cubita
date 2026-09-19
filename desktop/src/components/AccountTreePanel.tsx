import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronDown,
  FolderTree,
  ListTree,
  Minus,
  Pencil,
  Plus,
  RefreshCw,
  Save,
} from 'lucide-react'
import {
  ACCOUNT_NATURE_LABELS,
  ACCOUNT_TRAIT_META,
  createAccount,
  fetchChartAccounts,
  fetchNextAccountCode,
  fetchTrialBalance,
  updateAccount,
  type AccountTraits,
  type ChartAccount,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { AccountLedgerDrawer } from './AccountLedgerDrawer'
import { AccountEditDrawer } from './AccountEditDrawer'
import { SearchSelect } from '../components/SearchSelect'

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
 *  ۴. قالب‌های صنفی، قاعده‌ی کدینگ و **حذفِ حساب** این‌جا نیستند — تنظیمات ← کدینگ.
 *     حذف عمداً برداشته شد: دکمه‌ی ویرانگر کنارِ دکمه‌ای که روزی صد بار زده
 *     می‌شود، دیر یا زود اشتباه زده می‌شود. غیرفعال‌سازی این‌جا می‌ماند چون
 *     برگشت‌پذیر است.
 *     یک‌بار تنظیم می‌شوند؛ نشستنشان بالای درختواره باعث می‌شد کاربر ناخواسته
 *     چند قالب را پشتِ هم درج کند و چارتش پر از حسابِ بی‌ربط شود.
 *  ۵. **ماهیتِ حساب** (بدهکار/بستانکار/مهم نیست) — فقط معیارِ گزارش، نه گاردِ ثبت.
 *  ۶. **عنوانِ دوم** برای گزارشِ دوزبانه، و **عنوانِ کامل** (مسیر از ریشه) در راهنمای سطر.
 *  ۷. **ویژگی‌های حساب** (شش پرچم) در کشوی ویرایش — جانشینِ `window.prompt`های
 *     نام و کد، که دیگر جواب نمی‌دادند وقتی دو تیک به هم وابسته شدند.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const money = (n: number) => Math.round(n).toLocaleString('fa-IR')

/** واژگانِ سطحِ حساب در حسابداریِ ایران، بر پایه‌ی عمق در درخت. */
const LEVEL_LABELS = ['گروه', 'کل', 'معین', 'تفصیلی']
const levelOf = (depth: number) => LEVEL_LABELS[Math.min(depth, LEVEL_LABELS.length - 1)]
//: رنگِ هر سطح — قراردادِ جاافتاده‌ی نرم‌افزارهای حسابداریِ ایرانی (سبز/آبی/زرد).
//: کلاسِ CSS است نه رنگِ درون‌خطی، تا در پوسته‌ی روشن و تیره هر دو بخواند.
const levelToneOf = (depth: number) => `tree-level--l${Math.min(depth, LEVEL_LABELS.length - 1)}`

/**
 * پرچم‌هایی که روی سطرِ درخت نشانه می‌گیرند، با برچسبِ کوتاه.
 *
 * «نمایش در گزارشات مدیریتی» عمداً این‌جا نیست: پیش‌فرضش روشن است، پس نشانه‌اش روی
 * تقریباً همه‌ی سطرها می‌آمد و چیزی نمی‌گفت. حالتِ *خاموشش* جداگانه نشان داده می‌شود.
 */
const TRAIT_TAGS = ACCOUNT_TRAIT_META.filter((t) => t.key !== 'in_management_reports').map((t) => ({
  key: t.key,
  tag: t.key === 'nature_control' ? 'کنترلِ ماهیت' : t.label,
  title: t.hint,
}))

/** پیش‌فرضِ ویژگی‌های حسابِ تازه — عیناً همان پیش‌فرضِ ستون‌ها در مهاجرتِ ۰۰۸۸. */
const NEW_ACCOUNT_TRAITS: AccountTraits = {
  nature_control: false,
  is_fx: false,
  fx_revaluable: false,
  accepts_tafsili: false,
  has_tracking: false,
  in_management_reports: true,
}

interface Node extends ChartAccount {
  depth: number
  children: Node[]
  /** «عنوانِ کامل» — مسیرِ حساب از ریشه، مثلِ «دارایی‌ها › دارایی‌های جاری › صندوق». */
  fullName: string
  /** مانده‌ی خودِ حساب (برگ) یا جمعِ زیرمجموعه (سرفصل). */
  balance: number
}

/** فهرستِ تخت را به درخت تبدیل می‌کند و مانده‌ها را پایین‌به‌بالا جمع می‌زند. */
function buildTree(accounts: ChartAccount[], balances: Map<string, number>): Node[] {
  const nodes = new Map<string, Node>()
  for (const a of accounts)
    nodes.set(a.id, { ...a, depth: 0, children: [], balance: balances.get(a.id) ?? 0, fullName: a.name })

  const roots: Node[] = []
  for (const node of nodes.values()) {
    const parent = node.parent_id ? nodes.get(node.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }

  const byCode = (a: Node, b: Node) => a.code.localeCompare(b.code, 'en', { numeric: true })
  const walk = (list: Node[], depth: number, prefix: string): number => {
    list.sort(byCode)
    let sum = 0
    for (const node of list) {
      node.depth = depth
      node.fullName = prefix ? `${prefix} › ${node.name}` : node.name
      const childSum = walk(node.children, depth + 1, node.fullName)
      //: مانده‌ی گره = مانده‌ی خودش + جمعِ فرزندان. سرفصل مانده‌ی مستقیم ندارد پس
      //: صفر است و این می‌شود همان جمعِ فرزندان؛ ولی حسابِ معینی که تفصیلی گرفته
      //: ممکن است ردیفِ مستقیمِ قدیمی هم داشته باشد و جای‌گذاریِ ساده پنهانش می‌کرد.
      node.balance += childSum
      sum += node.balance
    }
    return sum
  }
  walk(roots, 0, '')
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
  /** حسابی که کشوی ویرایش رویش باز است — همان فرمِ کاملِ «ویژگی‌های حساب». */
  const [editing, setEditing] = useState<Node | null>(null)
  /** منوی راست‌کلیک: گره و مختصاتِ صفحه. null = بسته. */
  const [menu, setMenu] = useState<{ node: Node; x: number; y: number } | null>(null)
  const [busy, setBusy] = useState(false)
  /** سرفصلی که فرمِ «افزودن زیرحساب» زیرش باز است. */
  const [addUnder, setAddUnder] = useState<Node | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')
  const [newName2, setNewName2] = useState('')
  //: '' یعنی «مشتق از نوعِ حساب» — همان چیزی که بک‌اند با null می‌فهمد.
  const [newNature, setNewNature] = useState('')
  const [newIsGroup, setNewIsGroup] = useState(false)
  const [newCodeHint, setNewCodeHint] = useState('')
  //: ویژگی‌های حسابِ تازه. پیش‌فرض‌ها همان پیش‌فرضِ سرورند تا فرم و پایگاه‌داده
  //: یک چیز بگویند؛ «نمایش در گزارشات مدیریتی» تنها موردِ روشن است.
  const [newTraits, setNewTraits] = useState<AccountTraits>(NEW_ACCOUNT_TRAITS)

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
  }, [refresh])

  const roots = useMemo(() => buildTree(accounts ?? [], balances), [accounts, balances])

  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenu(null) }
    //: `capture` لازم است تا کلیک روی خودِ آیتم‌های منو هم اول منو را ببندد و بعد
    //: کارش را بکند؛ وگرنه منو باز می‌ماند و روی کشویی که باز می‌شود می‌نشیند.
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('keydown', onKey)
    }
  }, [menu])

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
    setNewName2('')
    setNewNature('')
    setNewIsGroup(false)
    setNewTraits(NEW_ACCOUNT_TRAITS)
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
        name2: newName2.trim(),
        nature: newNature || null,
        type: parent.type,
        is_group: newIsGroup,
        parent_id: parent.id,
        ...newTraits,
      })
      setAddUnder(null)
      return `حساب «${newName.trim()}» زیرِ «${parent.name}» ساخته شد.`
    })
  }

  function setNewTrait(key: keyof AccountTraits, value: boolean) {
    setNewTraits((t) => {
      const next = { ...t, [key]: value }
      if (key === 'is_fx' && !value) next.fx_revaluable = false
      return next
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
        <tr
          key={node.id}
          className={node.is_group ? 'group-row' : ''}
          //: راست‌کلیک همان سه کارِ دکمه‌های سطر را می‌کند. **افزوده است، نه
          //: جایگزین**: روی موبایل و در نسخه‌ی وب راست‌کلیک وجود ندارد یا کشف
          //: نمی‌شود، پس دکمه‌ها باید سرِ جایشان بمانند.
          onContextMenu={(e) => {
            e.preventDefault()
            setMenu({ node, x: e.clientX, y: e.clientY })
          }}
        >
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
              <span className={node.is_group ? 'chart-group-name' : 'entity-name'} title={node.fullName}>
                {node.name}
              </span>
              {node.name2 && <span className="chart-name2" dir="ltr">{node.name2}</span>}
              {node.system_role && <span className="chart-sys-tag">سیستمی</span>}
              {!node.is_active && <span className="fy-badge fy-badge--closed">غیرفعال</span>}
              {/* نشانه‌های ویژگی روی خودِ سطر: بدونِ اینها کاربر باید هر حساب را باز
                  کند تا بفهمد ارزی یا پیگیری‌دار هست یا نه. فقط پرچم‌های *روشن*
                  نشان داده می‌شوند؛ نمایشِ همه‌شان ردیف را به دیوارِ برچسب تبدیل
                  می‌کرد. «نمایش در گزارشات» برعکس است — چون پیش‌فرض روشن است،
                  دیده‌شدنش وقتی ارزش دارد که کاربر خاموشش کرده باشد. */}
              {TRAIT_TAGS.map(({ key, tag, title }) =>
                node[key] ? (
                  <span key={key} className="chart-trait-tag" title={title}>{tag}</span>
                ) : null,
              )}
              {!node.in_management_reports && (
                <span className="chart-trait-tag chart-trait-tag--off" title="از گزارش‌های مدیریتی کنار گذاشته شده">
                  بدونِ گزارشِ مدیریتی
                </span>
              )}
            </div>
          </td>
          <td data-label="سطح">
            <span className={`tree-level ${levelToneOf(node.depth)}`}>{levelOf(node.depth)}</span>
          </td>
          <td data-label="ماهیت">
            {node.is_group ? (
              <span className="tree-level">—</span>
            ) : (
              <span
                className={`nature-badge nature-badge--${node.effective_nature}`}
                //: تفاوتِ «خودم گذاشتم» و «پیش‌فرض» مهم است — کاربر باید بداند کدام را
                //: خودش تعیین کرده و کدام از نوعِ حساب آمده.
                title={node.nature ? 'ماهیتِ تعیین‌شده توسطِ شما' : 'پیش‌فرض، مشتق از نوعِ حساب'}
              >
                {ACCOUNT_NATURE_LABELS[node.effective_nature] ?? node.effective_nature}
                {!node.nature && <span className="nature-badge__auto">خودکار</span>}
              </span>
            )}
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
            <button
              type="button"
              onClick={() => openAdd(node)}
              disabled={busy}
              //: روی معین هم هست، چون تفصیلی زیرِ معین می‌نشیند. اگر آن حساب سندِ
              //: مستقیم خورده باشد سرور با پیامِ روشن ردش می‌کند — بهتر از پنهان
              //: کردنِ دکمه، که کاربر نمی‌فهمد چرا نمی‌تواند. به همان دلیل، حسابِ
              //: تفصیلی‌ناپذیر هم دکمه دارد ولی راهنمایش می‌گوید اول چه باید کرد.
              title={
                node.is_group
                  ? 'افزودنِ زیرحساب'
                  : node.accepts_tafsili || node.children.length > 0
                    ? 'افزودنِ تفصیلی زیرِ این حساب'
                    : 'برای افزودنِ تفصیلی، اول در ویرایشِ حساب «تفصیلی پذیر» را روشن کنید'
              }
            >
              <Plus size={13} />
            </button>
            {!node.is_group && (
              <button
                type="button"
                onClick={() => setLedger({ id: node.id, code: node.code, name: node.name })}
                title="کارتِ حساب"
              >
                <BookOpen size={13} />
              </button>
            )}
            <button
              type="button"
              onClick={() => setEditing(node)}
              disabled={busy}
              //: یک دکمه به‌جای دو پرامپتِ قبلی (نام و کد): ویژگی‌های حساب شش تیک
              //: است و دوتاشان به هم وابسته‌اند — در پرسشِ تک‌خطی نمی‌گنجد.
              title="ویرایشِ حساب و ویژگی‌هایش"
            >
              <Pencil size={13} />
            </button>
            <button
              type="button"
              disabled={busy}
              //: روی حسابِ سیستمی هم هست. غیرفعال یعنی «از فهرست‌های انتخاب پنهان شو»؛
              //: ثبتِ خودکار حساب را با نقشش پیدا می‌کند و is_active را نگاه نمی‌کند،
              //: پس چیزی نمی‌شکند.
              title={node.is_active ? 'از فهرست‌های انتخاب پنهان شود' : 'دوباره در فهرست‌ها دیده شود'}
              onClick={() =>
                void run(async () => {
                  await updateAccount(token, node.id, { is_active: !node.is_active })
                  return node.is_active ? 'حساب غیرفعال شد.' : 'حساب فعال شد.'
                })
              }
            >
              {node.is_active ? 'غیرفعال' : 'فعال'}
            </button>

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
                <input
                  value={newName2}
                  onChange={(e) => setNewName2(e.target.value)}
                  placeholder="عنوان دوم (اختیاری)"
                  dir="ltr"
                />
                <SearchSelect value={newNature} onChange={(e) => setNewNature(e.target.value)} title="ماهیتِ حساب">
                  <option value="">ماهیت: پیش‌فرضِ نوعِ حساب</option>
                  <option value="debit">بدهکار</option>
                  <option value="credit">بستانکار</option>
                  <option value="any">مهم نیست</option>
                </SearchSelect>
                <label className="fy-check">
                  <input type="checkbox" checked={newIsGroup} onChange={(e) => setNewIsGroup(e.target.checked)} />
                  سرفصل است
                </label>
                {/* همان شش ویژگیِ کشوی ویرایش، این‌بار موقعِ ساخت — تا کاربر مجبور
                    نباشد حساب را بسازد و بلافاصله بازش کند تا تیک بزند. */}
                {ACCOUNT_TRAIT_META.map((trait) => {
                  const locked = trait.key === 'fx_revaluable' && !newTraits.is_fx
                  return (
                    <label key={trait.key} className="fy-check" title={locked ? 'اول «ارزی» را روشن کنید.' : trait.hint}>
                      <input
                        type="checkbox"
                        checked={newTraits[trait.key]}
                        disabled={locked}
                        onChange={(e) => setNewTrait(trait.key, e.target.checked)}
                      />
                      {trait.label}
                    </label>
                  )
                })}
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
            <SearchSelect value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">همه‌ی انواع</option>
              {Object.entries(ACCOUNT_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </SearchSelect>
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
          <EmptyState
            icon={ListTree}
            //: کاربرِ تازه نمی‌داند قالب‌های آماده وجود دارند. «حسابی وجود ندارد»
            //: بن‌بست بود؛ این جمله راه را نشان می‌دهد.
            text="حسابی وجود ندارد. برای شروع، از تنظیمات ← کدینگ یکی از قالب‌های آماده را درج کنید."
          />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table chart-table tree-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>حساب</th>
                    <th>سطح</th>
                    <th>ماهیت</th>
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

      {menu && (
        <div
          className="tree-menu"
          //: مختصاتِ صفحه است، پس `position: fixed`. جهتِ RTL با `insetInlineStart`
          //: خودش برعکس می‌شود، پس `left` مستقیم داده می‌شود.
          style={{ left: menu.x, top: menu.y }}
          role="menu"
        >
          <div className="tree-menu-head">{menu.node.code} — {menu.node.name}</div>
          <button type="button" onClick={() => openAdd(menu.node)}>
            <Plus size={13} /> {menu.node.is_group ? 'زیرحسابِ جدید' : 'تفصیلیِ جدید'}
          </button>
          <button type="button" onClick={() => setEditing(menu.node)}>
            <Pencil size={13} /> ویرایش
          </button>
          {!menu.node.is_group && (
            <button
              type="button"
              onClick={() =>
                setLedger({ id: menu.node.id, code: menu.node.code, name: menu.node.name })
              }
            >
              <BookOpen size={13} /> کارتِ حساب
            </button>
          )}
          {/* «حذف» عمداً این‌جا نیست — تنظیمات ← کدینگ. دکمه‌ی ویرانگر در منویی که
              با یک راست‌کلیکِ ناخواسته باز می‌شود، دیر یا زود اشتباه زده می‌شود. */}
        </div>
      )}

      {ledger && <AccountLedgerDrawer token={token} account={ledger} onClose={() => setLedger(null)} />}

      {editing && (
        <AccountEditDrawer
          token={token}
          account={editing}
          levelLabel={levelOf(editing.depth)}
          //: مسیرِ کامل منهای خودِ حساب — همان «حساب سرشاخه»ی فرمِ سپیدار، ولی با
          //: کلِ مسیر تا کاربر بداند این معین زیرِ کدام گروه است.
          parentName={editing.fullName.split(' › ').slice(0, -1).join(' › ')}
          typeLabel={ACCOUNT_TYPE_LABELS[editing.type] ?? editing.type}
          onClose={() => setEditing(null)}
          onSaved={(text) => {
            setEditing(null)
            void run(async () => text)
          }}
        />
      )}
    </>
  )
}
