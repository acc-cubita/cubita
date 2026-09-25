import { useMemo, useState } from 'react'
import { ArrowLeftRight, FolderTree, ListTree, Check, X } from 'lucide-react'
import { fetchChartAccounts, reclassifyAccounts } from '../../api'
import { AccountTreePanel } from '../../components/AccountTreePanel'
import { useNavSection } from '../../components/navContext'
import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import { Pager, usePagination } from '../../components/Pager'
import {
  ActionBar,
  CountBadge,
  FormStatus,
  ListToolbar,
  SearchField,
} from '../../components/form/FormKit'
import {
  AsyncBlock,
  OpsPage,
  faInt,
  useAsync,
  type Msg,
} from './kit'

/**
 * چهار عملیاتِ *ساختار*: درختواره، انتقالِ حساب به سرفصلِ دیگر، تفصیلیِ سایر، و مرورِ حساب‌ها.
 *
 * سه‌تای اول ساختار را می‌سازند و چهارمی همان ساختار را با عدد نشان می‌دهد. جدا
 * نگه‌داشتنِ «مرور» از «درختواره» عمدی است: درختواره ابزارِ *ویرایش* است و مرور ابزارِ
 * *خواندن*؛ یک صفحه‌ی مشترک هر دو کار را بد انجام می‌داد.
 *
 * «سرفصل جدید» و «فهرست حساب‌ها» (بازچینیِ ۱۴۰۵/۰۷/۰۳) صفحه‌ی جدا نیستند: افزودن و نمای تخت
 * هر دو درونِ درختواره‌اند — دو صفحه برای یک داده یعنی حسابدار حدس بزند کدام را باز کند.
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
  const nav = useNavSection()
  return (
    <OpsPage
      canvas
      icon={ListTree}
      title="درختواره حساب‌ها"
      description="ساختارِ کاملِ چارت با مانده‌ی هر حساب: افزودن، ویرایش، غیرفعال‌کردن و جست‌وجو — درختی یا تخت. قالب‌های صنفی و حذفِ حساب در تنظیمات ← کدینگ است."
    >
      {/* «سرفصل جدید» و «فهرست حساب‌ها»ی قدیمی با بخشِ `new`/`flat` به همین‌جا می‌رسند. */}
      <AccountTreePanel
        token={token}
        onChanged={onChanged}
        startAdding={nav?.activePage === 'acctchart' && nav.section === 'new'}
        startFlat={nav?.activePage === 'acctchart' && nav.section === 'flat'}
      />
    </OpsPage>
  )
}

// ═════════════════ ۲) انتقال حساب به سرفصل دیگر ═════════════════

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
    if (pending.length === 0) {
      setMsg({ text: 'هیچ حسابی سرفصلِ تازه نگرفته است.', kind: 'err' })
      return
    }
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
      canvas
      icon={ArrowLeftRight}
      title="انتقال حساب به سرفصل دیگر"
      description="خودِ حساب‌ها را دسته‌ای زیرِ سرفصلِ درست می‌برد. نوعِ حساب از سرفصلِ مقصد گرفته می‌شود تا ترازنامه و سود و زیان یک چیز بگویند. ⚠️ سندی صادر نمی‌شود و چون ساختار عوض می‌شود، گزارش‌های گذشته هم از این پس با طبقه‌بندیِ تازه دیده می‌شوند — برای بردنِ *مانده* به حسابِ دیگر، «انتقال مانده به حساب دیگر» را باز کنید."
    >
      <SectionCard
        icon={FolderTree}
        title="حساب‌های قابلِ جابه‌جایی"
        tip="حساب‌های دارای نقشِ سیستمی (صندوق، بانک، …) نشان داده نمی‌شوند؛ ثبتِ خودکار به آن‌ها گره خورده."
        badge={<CountBadge>{faInt(movable.length)} حساب</CountBadge>}
      >
        <ListToolbar>
          <SearchField value={search} onChange={setSearch} placeholder="نام یا کدِ حساب" label="جست‌وجوی حساب" />
        </ListToolbar>
        <AsyncBlock
          loading={accounts.loading}
          error={accounts.error}
          empty={movable.length === 0}
          emptyText="حسابی با این جست‌وجو پیدا نشد."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
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
                      <td className="card-wide ef-col-wide" data-label="سرفصلِ تازه">
                        <SearchSelect
                          aria-label={`سرفصلِ تازه‌ی حسابِ ${a.name}`}
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
                        </SearchSelect>
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
      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              pending.length > 0
                ? `${faInt(pending.length)} حساب سرفصلِ تازه گرفته است.`
                : 'برای هر حساب، سرفصلِ تازه‌اش را از ستونِ آخر انتخاب کنید.'
            }
          />
        }
      >
        {pending.length > 0 && (
          <button type="button" className="ef-btn-secondary" onClick={() => setEdits({})}>
            <X size={15} /> انصراف
          </button>
        )}
        <button type="button" className="btn-primary" onClick={() => void apply()}>
          <Check size={16} /> {pending.length > 0 ? `اعمالِ ${faInt(pending.length)} تغییر` : 'اعمالِ تغییرها'}
        </button>
      </ActionBar>
    </OpsPage>
  )
}

// ═══════════════════════ ۴) تفصیلی سایر ═══════════════════════
//: برگه‌ی اکسلیِ ویرایشِ درجا فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { AnalyticsPage } from './AnalyticsPage'

// ═══════════════════════ ۵) مرور حساب‌ها ═══════════════════════
//: کاوشگرِ حرفه‌ای (UI-02) فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ
//: ورودِ صفحه عوض نشود.
export { AccountBrowsePage } from './AccountBrowser'
