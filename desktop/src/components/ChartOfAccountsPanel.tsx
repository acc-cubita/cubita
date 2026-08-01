import { useCallback, useEffect, useMemo, useState } from 'react'
import { ListTree, Plus, Save, Pencil, Trash2, BookOpen, RefreshCw, FolderTree } from 'lucide-react'
import {
  fetchChartAccounts, createAccount, updateAccount, deleteAccount, type ChartAccount,
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
 * مدیریتِ چارتِ حساب‌ها — تا پیش از این فقط خواندنی بود. حالا: ساختِ زیرحساب/سرفصل،
 * تغییرِ نام، فعال/غیرفعال‌سازی، حذفِ حسابِ بی‌استفاده، و «کارتِ حساب» (دفتر کل) درجا.
 * حسابِ سیستمی (نقش‌دار) محافظت می‌شود: نه غیرفعال می‌شود نه حذف.
 */
export function ChartOfAccountsPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [accounts, setAccounts] = useState<ChartAccount[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [ledger, setLedger] = useState<{ id: string; code: string; name: string } | null>(null)

  // فرمِ افزودن
  const [showAdd, setShowAdd] = useState(false)
  const [parentId, setParentId] = useState('')
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [isGroup, setIsGroup] = useState(false)
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setAccounts(await fetchChartAccounts(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  const groups = useMemo(() => (accounts ?? []).filter((a) => a.is_group), [accounts])
  const parentType = useMemo(() => groups.find((g) => g.id === parentId)?.type ?? '', [groups, parentId])

  const filtered = useMemo(() => {
    const list = accounts ?? []
    const q = search.trim()
    if (!q) return list
    return list.filter((a) => a.name.includes(q) || a.code.includes(q))
  }, [accounts, search])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null); setError(null)
    if (!parentId) { setMessage('سرفصلِ والد را انتخاب کنید.'); return }
    if (!code.trim() || !name.trim()) { setMessage('کد و نام الزامی است.'); return }
    setSaving(true)
    try {
      await createAccount(token, { code: code.trim(), name: name.trim(), type: parentType, is_group: isGroup, parent_id: parentId })
      setMessage(`حساب «${name.trim()}» ساخته شد.`)
      setCode(''); setName(''); setIsGroup(false)
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  async function rename(a: ChartAccount) {
    const next = window.prompt(`نامِ تازه برای «${a.name}»:`, a.name)
    if (next === null || !next.trim() || next.trim() === a.name) return
    try {
      await updateAccount(token, a.id, { name: next.trim() })
      await refresh(); onChanged?.()
    } catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  async function toggleActive(a: ChartAccount) {
    try {
      await updateAccount(token, a.id, { is_active: !a.is_active })
      await refresh(); onChanged?.()
    } catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  async function remove(a: ChartAccount) {
    if (!window.confirm(`حسابِ «${a.name}» حذف شود؟ (فقط حسابِ بی‌سند و بی‌زیرحساب حذف می‌شود)`)) return
    try {
      await deleteAccount(token, a.id)
      await refresh(); onChanged?.()
    } catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={Plus}
        title="افزودن حساب"
        description="زیرِ یک سرفصل، حسابِ تازه یا سرفصلِ فرعی بسازید."
        actions={<button onClick={() => setShowAdd((s) => !s)}>{showAdd ? 'بستن' : 'افزودن'}</button>}
      >
        {showAdd ? (
          <form className="invoice-form form-full" onSubmit={handleCreate}>
            <label>
              سرفصلِ والد
              <select value={parentId} onChange={(e) => setParentId(e.target.value)}>
                <option value="">— انتخابِ سرفصل —</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.code} · {g.name} ({ACCOUNT_TYPE_LABELS[g.type] ?? g.type})</option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label>کد حساب<input value={code} onChange={(e) => setCode(e.target.value)} placeholder="مثلاً 1103" /></label>
              <label>نام حساب<input value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً بانک ملت شعبه…" /></label>
            </div>
            <label className="cal-check-inline">
              <input type="checkbox" checked={isGroup} onChange={(e) => setIsGroup(e.target.checked)} />
              این یک سرفصل است (گروه‌بندی؛ سند مستقیم روی آن ثبت نمی‌شود)
            </label>
            {parentType && <p className="hint">نوعِ حساب از سرفصل به ارث می‌رسد: <strong>{ACCOUNT_TYPE_LABELS[parentType] ?? parentType}</strong></p>}
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> ثبت حساب</button>
            </div>
            {message && <div className="hint">{message}</div>}
          </form>
        ) : (
          <p className="hint">کد پس از ساخت ثابت می‌ماند (روی اسناد نشسته)؛ نام بعداً قابلِ تغییر است. حسابِ دارای سند حذف نمی‌شود — «غیرفعال» کنید.</p>
        )}
      </SectionCard>

      <SectionCard
        icon={ListTree}
        title="چارتِ حساب‌ها"
        description={accounts ? `${accounts.length.toLocaleString('fa-IR')} حساب` : ''}
        actions={
          <div className="check-actions">
            <input type="text" placeholder="جستجو نام یا کد…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <button onClick={() => void refresh()}><RefreshCw size={13} /></button>
          </div>
        }
      >
        {error && <div className="error">{error}</div>}
        {accounts == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : filtered.length === 0 ? (
          <EmptyState icon={ListTree} text="حسابی یافت نشد." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table chart-table">
              <thead>
                <tr><th>کد</th><th>نام</th><th>نوع</th><th>وضعیت</th><th></th></tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={a.id} className={a.is_group ? 'group-row' : ''}>
                    <td data-label="کد" className="ltr-cell">{a.code}</td>
                    <td data-label="نام" className={a.is_group ? 'chart-group-name' : 'entity-name'}>
                      {a.is_group && <FolderTree size={13} className="chart-group-icon" />}
                      {a.name}
                      {a.system_role && <span className="chart-sys-tag">سیستمی</span>}
                    </td>
                    <td data-label="نوع">
                      <span className={`status-badge tone-${TYPE_TONE[a.type] ?? 'default'}`}>{ACCOUNT_TYPE_LABELS[a.type] ?? a.type}</span>
                    </td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${a.is_active ? 'tone-success' : 'tone-warning'}`}>{a.is_active ? 'فعال' : 'غیرفعال'}</span>
                    </td>
                    <td className="check-actions">
                      {!a.is_group && (
                        <button type="button" onClick={() => setLedger({ id: a.id, code: a.code, name: a.name })}>
                          <BookOpen size={13} /> کارتِ حساب
                        </button>
                      )}
                      <button type="button" onClick={() => void rename(a)}><Pencil size={13} /> نام</button>
                      {!a.system_role && (
                        <button type="button" onClick={() => void toggleActive(a)}>{a.is_active ? 'غیرفعال' : 'فعال'}</button>
                      )}
                      {!a.system_role && (
                        <button type="button" className="icon-btn-danger" onClick={() => void remove(a)} aria-label="حذف حساب"><Trash2 size={13} /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {ledger && <AccountLedgerDrawer token={token} account={ledger} onClose={() => setLedger(null)} />}
    </div>
  )
}
