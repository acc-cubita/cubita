import { useMemo, useState } from 'react'
import {
  ArrowLeftRight,
  FolderTree,
  Layers,
  ListTree,
  Check,
  Pencil,
  Plus,
  Power,
  Tag,
  Trash2,
  Wallet,
  X,
} from 'lucide-react'
import {
  createAccount,
  createAnalytic,
  deleteAnalytic,
  fetchAnalytics,
  fetchChartAccounts,
  fetchNextAccountCode,
  reclassifyAccounts,
  updateAnalytic,
  type AnalyticAccount,
} from '../../api'
import { AccountTreePanel } from '../../components/AccountTreePanel'
import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import { Pager, usePagination } from '../../components/Pager'
import {
  ActionBar,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  ListToolbar,
  RowAction,
  SearchField,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import {
  AsyncBlock,
  Metric,
  OpsPage,
  faInt,
  useAsync,
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
      canvas
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
    const missing = firstMissing([
      [form.code, 'acc-code', 'کدِ حساب را وارد کنید.'],
      [form.name, 'acc-name', 'نامِ حساب را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      canvas
      icon={Plus}
      title="سرفصل جدید"
      description="افزودنِ یک حساب یا سرفصلِ تازه به چارت. سرفصل فقط دسته‌بندی می‌کند و سند مستقیم نمی‌گیرد؛ حسابِ سطحِ آخر است که سند می‌خورد."
    >
      <form noValidate onSubmit={submit}>
        <SectionCard
          icon={Plus}
          title="مشخصاتِ حساب"
          tip="اول سرفصلِ مادر را انتخاب کنید تا نوعِ حساب و کدِ پیشنهادیِ بعدی خودکار پر شوند."
        >
          <FormGrid>
            <FormField label="سرفصلِ مادر" tip="نوعِ حساب از مادر گرفته می‌شود تا ترازنامه و سود و زیان یک چیز بگویند.">
              {(id) => (
                <SearchSelect id={id} value={form.parent_id} onChange={(e) => void pickParent(e.target.value)}>
                  <option value="">— بدونِ مادر (ریشه) —</option>
                  {groups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.code} — {g.name}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField id="acc-code" label="کدِ حساب" required>
              {(id) => (
                <input
                  id={id}
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  dir="ltr"
                />
              )}
            </FormField>
            <FormField id="acc-name" label="نامِ حساب" required>
              {(id) => (
                <input id={id} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              )}
            </FormField>
            <FormField label="نوعِ حساب" required>
              {(id) => (
                <SearchSelect id={id} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  {Object.entries(TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <div className="ef-checks">
              <label className="ef-check-tip">
                <input
                  type="checkbox"
                  checked={form.is_group}
                  onChange={(e) => setForm({ ...form, is_group: e.target.checked })}
                />
                سرفصل است (سند مستقیم نمی‌گیرد)
              </label>
            </div>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg} />}>
          <button type="submit" className="btn-primary">
            <Check size={16} /> ساختِ حساب
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={ListTree}
        title="تازه‌ترین حساب‌ها"
        description="آخرین کدهایی که به چارت اضافه شده‌اند."
        badge={<CountBadge>{faInt(recent.length)} حساب</CountBadge>}
      >
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
      title="جابه‌جایی حساب در درختواره"
      description="جابه‌جاییِ دسته‌ایِ حساب‌ها زیرِ سرفصلِ درست. نوعِ حساب از سرفصلِ مقصد گرفته می‌شود تا ترازنامه و سود و زیان یک چیز بگویند. ⚠️ این کار مانده را جابه‌جا نمی‌کند و چون ساختارِ حساب را عوض می‌کند، گزارش‌های گذشته هم از این پس با طبقه‌بندیِ تازه دیده می‌شوند — برای بردنِ مانده به حسابِ درست، «اصلاح طبقه‌بندی مانده» را باز کنید."
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
    const missing = firstMissing([
      [form.code, 'an-code', 'کدِ تفصیلی را وارد کنید.'],
      [form.name, 'an-name', 'نامِ تفصیلی را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      canvas
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
      <form noValidate onSubmit={submit}>
        <SectionCard
          icon={editing ? Pencil : Plus}
          title={editing ? `ویرایشِ «${editing.name}»` : 'تفصیلیِ تازه'}
          tip="کد یکتاست و در گزارش‌ها به‌جای نام استفاده می‌شود."
        >
          <FormGrid>
            <FormField id="an-code" label="کد" required>
              {(id) => (
                <input
                  id={id}
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  dir="ltr"
                />
              )}
            </FormField>
            <FormField id="an-name" label="نام" required>
              {(id) => (
                <input id={id} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              )}
            </FormField>
            <FormField label="دسته" optional tip="تفصیلی‌های هم‌دسته در فهرست زیرِ یک عنوان جمع می‌شوند.">
              {(id) => (
                <input
                  id={id}
                  value={form.group_name}
                  onChange={(e) => setForm({ ...form, group_name: e.target.value })}
                  placeholder="مثلاً خودرو"
                />
              )}
            </FormField>
            <FormField label="توضیح" optional span="full">
              {(id) => (
                <input
                  id={id}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              )}
            </FormField>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg} />}>
          {editing && (
            <button
              type="button"
              className="ef-btn-secondary"
              onClick={() => {
                setEditing(null)
                setForm(EMPTY_ANALYTIC)
              }}
            >
              <X size={15} /> انصراف
            </button>
          )}
          <button type="submit" className="btn-primary">
            <Check size={16} /> {editing ? 'ذخیرهٔ تغییرات' : 'ثبت تفصیلی'}
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={Tag}
        title="فهرستِ تفصیلی‌ها"
        badge={<CountBadge accent>{faInt(rows.length)} تفصیلی</CountBadge>}
        description="تفصیلی‌ها به تفکیکِ دسته. تفصیلیِ استفاده‌شده حذف نمی‌شود؛ غیرفعالش کنید."
      >
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
              <div className="table-scroll ef-table-wrap">
                <table className="cards-on-mobile acc-table ef-table">
                  <thead>
                    <tr>
                      <th>کد</th>
                      <th>نام</th>
                      <th>توضیح</th>
                      <th>ردیفِ سند</th>
                      <th>وضعیت</th>
                      <th className="ef-col-min">عملیات</th>
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
                          <CountBadge>{faInt(row.line_count)} ردیف</CountBadge>
                        </td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${row.is_active ? 'tone-success' : 'tone-muted'}`}>
                            {row.is_active ? 'فعال' : 'غیرفعال'}
                          </span>
                        </td>
                        <td className="card-actions ef-col-min">
                          <div className="row-actions ef-row-actions">
                            <RowAction
                              icon={Pencil}
                              label="ویرایش"
                              onClick={() => {
                                setEditing(row)
                                setForm({
                                  code: row.code,
                                  name: row.name,
                                  group_name: row.group_name,
                                  description: row.description,
                                })
                                document.getElementById('an-code')?.focus()
                              }}
                            />
                            <RowAction
                              icon={Power}
                              label={row.is_active ? 'غیرفعال‌کردن' : 'فعال‌کردن'}
                              onClick={() => void toggleActive(row)}
                            />
                            <RowAction
                              icon={Trash2}
                              label="حذف"
                              danger
                              onClick={() => void remove(row)}
                              disabled={row.line_count > 0}
                              title={
                                row.line_count > 0
                                  ? 'ردیف‌های سند به این تفصیلی اشاره کرده‌اند؛ به‌جای حذف غیرفعالش کنید.'
                                  : undefined
                              }
                            />
                          </div>
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
//: کاوشگرِ حرفه‌ای (UI-02) فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ
//: ورودِ صفحه عوض نشود.
export { AccountBrowsePage } from './AccountBrowser'

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
      canvas
      icon={ListTree}
      title="فهرست حساب‌ها"
      description="نمای تختِ چارت برای پیداکردنِ سریعِ یک حساب یا کد."
    >
      <SectionCard
        icon={ListTree}
        title="حساب‌ها"
        badge={accounts.data ? <CountBadge accent>{faInt(rows.length)} حساب</CountBadge> : undefined}
        description="نمای تختِ چارت — سرفصل‌ها و حساب‌های سطحِ آخر کنارِ هم."
      >
        <ListToolbar>
          <SearchField value={search} onChange={setSearch} placeholder="نام یا کدِ حساب" label="جست‌وجوی حساب" />
        </ListToolbar>
        <AsyncBlock
          loading={accounts.loading}
          error={accounts.error}
          empty={rows.length === 0}
          emptyText="حسابی پیدا نشد."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile acc-table ef-table">
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
                    <td data-label="وضعیت">
                      <span className={`status-badge ${a.is_active ? 'tone-success' : 'tone-muted'}`}>
                        {a.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
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
