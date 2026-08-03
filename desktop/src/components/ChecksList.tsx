import { useEffect, useMemo, useState } from 'react'
import { Landmark, RefreshCw } from 'lucide-react'
import { fetchChecks, updateCheckStatus, type CheckRecord } from '../api'
import type { BankAccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { formatJalali } from '../lib/jalali'

const STATUS_LABELS: Record<string, string> = {
  in_hand: 'نزد صندوق', deposited: 'در جریان وصول', cleared: 'وصول‌شده',
  bounced: 'برگشتی', endorsed: 'خرج‌شده', issued: 'صادرشده',
}
const STATUS_TONE: Record<string, string> = {
  in_hand: 'default', issued: 'default', deposited: 'warning',
  cleared: 'success', bounced: 'danger', endorsed: 'default',
}
const OPEN_STATUSES = new Set(['in_hand', 'deposited', 'issued'])
const fa = (n: number) => n.toLocaleString('fa-IR')
const todayStr = () => new Date().toISOString().slice(0, 10)
const soonStr = () => new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10)

export function ChecksList({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [checks, setChecks] = useState<CheckRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [pendingBankSelection, setPendingBankSelection] = useState<Record<string, string>>({})
  const [typeFilter, setTypeFilter] = useState<'all' | 'receivable' | 'payable'>('all')
  const [openOnly, setOpenOnly] = useState(true)

  async function refresh() {
    setError(null)
    try { setChecks(await fetchChecks(token)) }
    catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }
  useEffect(() => { void refresh() }, [])

  const filtered = useMemo(() => checks.filter((c) => {
    if (typeFilter !== 'all' && c.type !== typeFilter) return false
    if (openOnly && !OPEN_STATUSES.has(c.status)) return false
    return true
  }), [checks, typeFilter, openOnly])

  async function handleStatusChange(check: CheckRecord, newStatus: string, needsBank: boolean) {
    setError(null)
    const bankAccountId = needsBank ? pendingBankSelection[check.id] : undefined
    if (needsBank && !bankAccountId) { setError('ابتدا حساب بانکی را انتخاب کنید.'); return }
    try { await updateCheckStatus(token, check.id, newStatus, bankAccountId); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  function BankSelect({ checkId }: { checkId: string }) {
    return (
      <select value={pendingBankSelection[checkId] ?? ''} onChange={(e) => setPendingBankSelection((p) => ({ ...p, [checkId]: e.target.value }))}>
        <option value="">— انتخاب حساب بانکی —</option>
        {bankAccounts.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select>
    )
  }

  function dueBadge(c: CheckRecord) {
    if (!OPEN_STATUSES.has(c.status)) return null
    if (c.due_date < todayStr()) return <span className="status-badge tone-danger">سررسید گذشته</span>
    if (c.due_date <= soonStr()) return <span className="status-badge tone-warning">نزدیکِ سررسید</span>
    return null
  }

  function actions(c: CheckRecord) {
    if (c.type === 'receivable' && c.status === 'in_hand') return (
      <div className="check-actions">
        <BankSelect checkId={c.id} />
        <button type="button" onClick={() => void handleStatusChange(c, 'deposited', true)}>واریز به بانک</button>
        <button type="button" onClick={() => void handleStatusChange(c, 'endorsed', false)}>خرج کردن</button>
      </div>
    )
    if (c.type === 'receivable' && c.status === 'deposited') return (
      <div className="check-actions">
        <button type="button" onClick={() => void handleStatusChange(c, 'cleared', false)}>وصول شد</button>
        <button type="button" className="icon-btn-danger" onClick={() => void handleStatusChange(c, 'bounced', false)}>برگشت خورد</button>
      </div>
    )
    if (c.type === 'payable' && c.status === 'issued') return (
      <div className="check-actions">
        <BankSelect checkId={c.id} />
        <button type="button" onClick={() => void handleStatusChange(c, 'cleared', true)}>کسر از حساب</button>
        <button type="button" className="icon-btn-danger" onClick={() => void handleStatusChange(c, 'bounced', false)}>برگشت خورد</button>
      </div>
    )
    return <span className="muted">—</span>
  }

  return (
    <SectionCard
      icon={Landmark}
      title="لیست چک‌ها (زنده از سرور)"
      description="از ثبت تا وصول/خرج؛ چک‌های سررسیدشده و نزدیک به سررسید علامت می‌خورند."
      actions={
        <div className="check-actions checks-filters">
          <div className="seg-toggle">
            <button type="button" className={typeFilter === 'all' ? 'active' : ''} onClick={() => setTypeFilter('all')}>همه</button>
            <button type="button" className={typeFilter === 'receivable' ? 'active' : ''} onClick={() => setTypeFilter('receivable')}>دریافتنی</button>
            <button type="button" className={typeFilter === 'payable' ? 'active' : ''} onClick={() => setTypeFilter('payable')}>پرداختنی</button>
          </div>
          <label className="checks-openonly"><input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} /> فقط باز</label>
          <button onClick={() => void refresh()}><RefreshCw size={13} /></button>
        </div>
      }
    >
      {error && <div className="error">{error}</div>}
      {filtered.length === 0 ? (
        <EmptyState icon={Landmark} text="چکی با این فیلتر نیست." />
      ) : (
        <div className="entity-table-wrap">
          <table className="entity-table checks-table">
            <thead>
              <tr><th>نوع</th><th>شماره / بانک</th><th>مبلغ</th><th>سررسید</th><th>وضعیت</th><th>اقدام</th></tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id}>
                  <td data-label="نوع" className="entity-name">
                    {c.type === 'receivable' ? 'دریافتنی' : 'پرداختنی'}
                    {c.contact_name ? <div className="entity-sub">{c.contact_name}</div> : null}
                  </td>
                  <td data-label="شماره / بانک" className="ltr-cell">{c.number}{c.bank_name ? <div className="entity-sub">{c.bank_name}</div> : null}</td>
                  <td data-label="مبلغ" className="money-cell">{fa(Number(c.amount))}</td>
                  <td data-label="سررسید">{formatJalali(c.due_date)} {dueBadge(c)}</td>
                  <td data-label="وضعیت"><span className={`status-badge tone-${STATUS_TONE[c.status] ?? 'default'}`}>{STATUS_LABELS[c.status] ?? c.status}</span></td>
                  <td className="checks-action-cell">{actions(c)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}
