import { useEffect, useState } from 'react'
import { Landmark, RefreshCw } from 'lucide-react'
import { fetchChecks, updateCheckStatus, type CheckRecord } from '../api'
import type { BankAccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { formatJalali } from '../lib/jalali'

const STATUS_LABELS: Record<string, string> = {
  in_hand: 'نزد صندوق',
  deposited: 'در جریان وصول',
  cleared: 'وصول‌شده',
  bounced: 'برگشتی',
  endorsed: 'خرج‌شده',
  issued: 'صادرشده',
}

const STATUS_TONE: Record<string, string> = {
  in_hand: 'default',
  issued: 'default',
  deposited: 'warning',
  cleared: 'success',
  bounced: 'danger',
  endorsed: 'default',
}

export function ChecksList({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [checks, setChecks] = useState<CheckRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [pendingBankSelection, setPendingBankSelection] = useState<Record<string, string>>({})

  async function refresh() {
    setError(null)
    try {
      setChecks(await fetchChecks(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function handleStatusChange(check: CheckRecord, newStatus: string, needsBank: boolean) {
    setError(null)
    const bankAccountId = needsBank ? pendingBankSelection[check.id] : undefined
    if (needsBank && !bankAccountId) {
      setError('ابتدا حساب بانکی را انتخاب کنید.')
      return
    }
    try {
      await updateCheckStatus(token, check.id, newStatus, bankAccountId)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  function BankSelect({ checkId }: { checkId: string }) {
    return (
      <select
        value={pendingBankSelection[checkId] ?? ''}
        onChange={(e) => setPendingBankSelection((prev) => ({ ...prev, [checkId]: e.target.value }))}
      >
        <option value="">— انتخاب حساب بانکی —</option>
        {bankAccounts.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
    )
  }

  return (
    <SectionCard
      icon={Landmark}
      title="لیست چک‌ها (زنده از سرور)"
      actions={
        <button onClick={() => void refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      <p className="hint">این لیست و اقدام‌های تغییر وضعیت نیاز به اتصال اینترنت دارند.</p>
      {error && <div className="error">{error}</div>}
      {checks.length === 0 ? (
        <EmptyState icon={Landmark} text="چکی ثبت نشده." />
      ) : (
        <table>
          <thead>
            <tr>
              <th>نوع</th>
              <th>شماره</th>
              <th>بانک</th>
              <th>مبلغ</th>
              <th>سررسید</th>
              <th>وضعیت</th>
              <th>اقدام</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((c) => (
              <tr key={c.id}>
                <td>{c.type === 'receivable' ? 'دریافتنی' : 'پرداختنی'}</td>
                <td>{c.number}</td>
                <td>{c.bank_name}</td>
                <td>{Number(c.amount).toLocaleString('fa-IR')}</td>
                <td>{formatJalali(c.due_date)}</td>
                <td>
                  <span className={`status-badge tone-${STATUS_TONE[c.status] ?? 'default'}`}>
                    {STATUS_LABELS[c.status] ?? c.status}
                  </span>
                </td>
                <td>
                  {c.type === 'receivable' && c.status === 'in_hand' && (
                    <div className="check-actions">
                      <BankSelect checkId={c.id} />
                      <button type="button" onClick={() => void handleStatusChange(c, 'deposited', true)}>
                        واریز به بانک
                      </button>
                      <button type="button" onClick={() => void handleStatusChange(c, 'endorsed', false)}>
                        خرج کردن
                      </button>
                    </div>
                  )}
                  {c.type === 'receivable' && c.status === 'deposited' && (
                    <div className="check-actions">
                      <button type="button" onClick={() => void handleStatusChange(c, 'cleared', false)}>
                        وصول شد
                      </button>
                      <button type="button" onClick={() => void handleStatusChange(c, 'bounced', false)}>
                        برگشت خورد
                      </button>
                    </div>
                  )}
                  {c.type === 'payable' && c.status === 'issued' && (
                    <div className="check-actions">
                      <BankSelect checkId={c.id} />
                      <button type="button" onClick={() => void handleStatusChange(c, 'cleared', true)}>
                        کسر از حساب
                      </button>
                      <button type="button" onClick={() => void handleStatusChange(c, 'bounced', false)}>
                        برگشت خورد
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  )
}
