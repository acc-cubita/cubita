import { useState } from 'react'
import { BarChart3, Search } from 'lucide-react'
import {
  fetchBalanceSheet,
  fetchGeneralLedger,
  fetchIncomeStatement,
  fetchTrialBalance,
  type BalanceSheet,
  type GeneralLedger,
  type IncomeStatement,
  type TrialBalanceRow,
} from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { formatJalali } from '../lib/jalali'

type ReportKind = 'trial-balance' | 'income-statement' | 'balance-sheet' | 'general-ledger'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

export function Reports({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const [active, setActive] = useState<ReportKind>('trial-balance')
  const [trialBalance, setTrialBalance] = useState<TrialBalanceRow[] | null>(null)
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatement | null>(null)
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null)
  const [ledgerAccountId, setLedgerAccountId] = useState('')
  const [generalLedger, setGeneralLedger] = useState<GeneralLedger | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const postableAccounts = accounts.filter((a) => !a.is_group)

  async function load(kind: ReportKind) {
    setActive(kind)
    setError(null)
    if (kind === 'general-ledger') return // نیاز به انتخاب حساب دارد؛ با دکمه‌ی جدا بارگذاری می‌شود
    setLoading(true)
    try {
      if (kind === 'trial-balance') setTrialBalance(await fetchTrialBalance(token))
      if (kind === 'income-statement') setIncomeStatement(await fetchIncomeStatement(token))
      if (kind === 'balance-sheet') setBalanceSheet(await fetchBalanceSheet(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  async function loadGeneralLedger() {
    if (!ledgerAccountId) {
      setError('ابتدا یک حساب انتخاب کنید.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      setGeneralLedger(await fetchGeneralLedger(token, ledgerAccountId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  const tabs: { key: ReportKind; label: string }[] = [
    { key: 'trial-balance', label: 'تراز آزمایشی' },
    { key: 'income-statement', label: 'سود و زیان' },
    { key: 'balance-sheet', label: 'ترازنامه' },
    { key: 'general-ledger', label: 'دفتر کل' },
  ]

  return (
    <SectionCard icon={BarChart3} title="گزارش‌های حسابداری">
      <p className="hint">این گزارش‌ها همیشه مستقیم و زنده از سرور خوانده می‌شوند (نیاز به اتصال اینترنت دارند).</p>
      <div className="report-tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={active === t.key ? 'btn-primary' : ''}
            onClick={() => void load(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && <p className="hint">در حال بارگذاری...</p>}
      {error && <div className="error">{error}</div>}

      {active === 'general-ledger' && (
        <div className="check-actions">
          <select value={ledgerAccountId} onChange={(e) => setLedgerAccountId(e.target.value)}>
            <option value="">— انتخاب حساب —</option>
            {postableAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => void loadGeneralLedger()}>
            <Search size={13} /> نمایش
          </button>
        </div>
      )}

      {active === 'general-ledger' && generalLedger && (
        <div>
          <h3>
            {generalLedger.account_code} — {generalLedger.account_name}
          </h3>
          <table>
            <thead>
              <tr>
                <th>شماره سند</th>
                <th>تاریخ</th>
                <th>شرح</th>
                <th>بدهکار</th>
                <th>بستانکار</th>
                <th>مانده</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={5}>مانده ابتدای دوره</td>
                <td>{fa(generalLedger.opening_balance)}</td>
              </tr>
              {generalLedger.lines.map((line) => (
                <tr key={line.entry_id}>
                  <td>{line.entry_number ?? '—'}</td>
                  <td>{formatJalali(line.entry_date)}</td>
                  <td>{line.description}</td>
                  <td>{fa(line.debit)}</td>
                  <td>{fa(line.credit)}</td>
                  <td>{fa(line.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="invoice-total">مانده پایان دوره: {fa(generalLedger.closing_balance)}</p>
        </div>
      )}

      {active === 'trial-balance' && trialBalance && (
        <table>
          <thead>
            <tr>
              <th>کد</th>
              <th>نام حساب</th>
              <th>بدهکار</th>
              <th>بستانکار</th>
              <th>مانده</th>
            </tr>
          </thead>
          <tbody>
            {trialBalance.map((row) => (
              <tr key={row.account_id}>
                <td>{row.account_code}</td>
                <td>{row.account_name}</td>
                <td>{fa(row.total_debit)}</td>
                <td>{fa(row.total_credit)}</td>
                <td>{fa(row.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {active === 'income-statement' && incomeStatement && (
        <div>
          <h3>درآمدها</h3>
          <table>
            <tbody>
              {incomeStatement.income.map((r) => (
                <tr key={r.account_id}>
                  <td>{r.account_name}</td>
                  <td>{fa(r.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>هزینه‌ها</h3>
          <table>
            <tbody>
              {incomeStatement.expenses.map((r) => (
                <tr key={r.account_id}>
                  <td>{r.account_name}</td>
                  <td>{fa(r.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="invoice-total">سود/زیان خالص: {fa(incomeStatement.net_profit)}</p>
        </div>
      )}

      {active === 'balance-sheet' && balanceSheet && (
        <div>
          <h3>دارایی‌ها</h3>
          <table>
            <tbody>
              {balanceSheet.assets.map((r) => (
                <tr key={r.account_id}>
                  <td>{r.account_name}</td>
                  <td>{fa(r.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>جمع دارایی‌ها: {fa(balanceSheet.total_assets)}</p>

          <h3>بدهی‌ها</h3>
          <table>
            <tbody>
              {balanceSheet.liabilities.map((r) => (
                <tr key={r.account_id}>
                  <td>{r.account_name}</td>
                  <td>{fa(r.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>جمع بدهی‌ها: {fa(balanceSheet.total_liabilities)}</p>

          <h3>حقوق صاحبان سرمایه</h3>
          <table>
            <tbody>
              {balanceSheet.equity.map((r) => (
                <tr key={r.account_id}>
                  <td>{r.account_name}</td>
                  <td>{fa(r.balance)}</td>
                </tr>
              ))}
              <tr>
                <td>سود/زیان دوره جاری</td>
                <td>{fa(balanceSheet.current_period_profit)}</td>
              </tr>
            </tbody>
          </table>
          <p className="invoice-total">جمع حقوق صاحبان سرمایه: {fa(balanceSheet.total_equity)}</p>
        </div>
      )}
    </SectionCard>
  )
}
