import { useState } from 'react'
import { BarChart3, Search } from 'lucide-react'
import {
  fetchAging,
  fetchBalanceSheet,
  fetchBudgetReport,
  fetchCashFlow,
  fetchContacts,
  fetchContactStatement,
  fetchCostCenterReport,
  fetchInventoryReport,
  fetchGeneralLedger,
  fetchIncomeStatement,
  fetchTrialBalance,
  fetchVatReport,
  type AgingReport,
  type BalanceSheet,
  type BudgetReport,
  type CashFlow,
  type ContactRecord,
  type ContactStatement,
  type CostCenterReport,
  type GeneralLedger,
  type InventoryReport,
  type IncomeStatement,
  type TrialBalanceRow,
  type VatReport,
} from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { formatJalali } from '../lib/jalali'

type ReportKind =
  | 'trial-balance'
  | 'income-statement'
  | 'balance-sheet'
  | 'general-ledger'
  | 'vat'
  | 'budget'
  | 'cash-flow'
  | 'cost-center'
  | 'receivable-aging'
  | 'payable-aging'
  | 'contact-statement'
  | 'inventory'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

export function Reports({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const [active, setActive] = useState<ReportKind>('trial-balance')
  const [trialBalance, setTrialBalance] = useState<TrialBalanceRow[] | null>(null)
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatement | null>(null)
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null)
  const [vatReport, setVatReport] = useState<VatReport | null>(null)
  const [budgetReport, setBudgetReport] = useState<BudgetReport | null>(null)
  const [cashFlow, setCashFlow] = useState<CashFlow | null>(null)
  const [costCenterReport, setCostCenterReport] = useState<CostCenterReport | null>(null)
  const [aging, setAging] = useState<AgingReport | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [statementContactId, setStatementContactId] = useState('')
  const [contactStatement, setContactStatement] = useState<ContactStatement | null>(null)
  const [inventory, setInventory] = useState<InventoryReport | null>(null)
  const [ledgerAccountId, setLedgerAccountId] = useState('')
  const [generalLedger, setGeneralLedger] = useState<GeneralLedger | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const postableAccounts = accounts.filter((a) => !a.is_group)

  async function load(kind: ReportKind) {
    setActive(kind)
    setError(null)
    if (kind === 'general-ledger') return // نیاز به انتخاب حساب دارد؛ با دکمه‌ی جدا بارگذاری می‌شود
    if (kind === 'contact-statement') {
      // نیاز به انتخاب طرف‌حساب دارد؛ فهرست اشخاص را زنده می‌گیریم، خودِ گزارش با دکمه
      if (contacts.length === 0) {
        try {
          setContacts(await fetchContacts(token))
        } catch (err) {
          setError(err instanceof Error ? err.message : 'خطای ناشناخته')
        }
      }
      return
    }
    setLoading(true)
    try {
      if (kind === 'trial-balance') setTrialBalance(await fetchTrialBalance(token))
      if (kind === 'income-statement') setIncomeStatement(await fetchIncomeStatement(token))
      if (kind === 'balance-sheet') setBalanceSheet(await fetchBalanceSheet(token))
      if (kind === 'vat') setVatReport(await fetchVatReport(token))
      if (kind === 'budget') setBudgetReport(await fetchBudgetReport(token))
      if (kind === 'cash-flow') setCashFlow(await fetchCashFlow(token))
      if (kind === 'cost-center') setCostCenterReport(await fetchCostCenterReport(token))
      if (kind === 'receivable-aging') setAging(await fetchAging(token, 'receivable'))
      if (kind === 'payable-aging') setAging(await fetchAging(token, 'payable'))
      if (kind === 'inventory') setInventory(await fetchInventoryReport(token))
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

  async function loadContactStatement() {
    if (!statementContactId) {
      setError('ابتدا یک طرف‌حساب انتخاب کنید.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      setContactStatement(await fetchContactStatement(token, statementContactId))
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
    { key: 'vat', label: 'مالیات بر ارزش افزوده' },
    { key: 'budget', label: 'بودجه در برابر عملکرد' },
    { key: 'cash-flow', label: 'جریان وجوه نقد' },
    { key: 'cost-center', label: 'سود پروژه/مرکز هزینه' },
    { key: 'receivable-aging', label: 'سنی مطالبات' },
    { key: 'payable-aging', label: 'سنی بدهی‌ها' },
    { key: 'contact-statement', label: 'صورت‌حساب اشخاص' },
    { key: 'inventory', label: 'ارزش موجودی انبار' },
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

      {active === 'contact-statement' && (
        <div className="check-actions">
          <select value={statementContactId} onChange={(e) => setStatementContactId(e.target.value)}>
            <option value="">— انتخاب طرف‌حساب —</option>
            {contacts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => void loadContactStatement()}>
            <Search size={13} /> نمایش
          </button>
        </div>
      )}

      {active === 'contact-statement' && contactStatement && (
        <div>
          <h3>{contactStatement.contact_name}</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>شرح</th>
                  <th>شماره</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th>مانده</th>
                </tr>
              </thead>
              <tbody>
                <tr className="muted-row">
                  <td colSpan={5}>مانده ابتدای دوره</td>
                  <td>{fa(contactStatement.opening_balance)}</td>
                </tr>
                {contactStatement.lines.map((l, i) => (
                  <tr key={i}>
                    <td>{formatJalali(l.txn_date)}</td>
                    <td>{l.description}</td>
                    <td>{l.number != null ? fa(l.number) : '—'}</td>
                    <td>{Number(l.debit) ? fa(l.debit) : ''}</td>
                    <td>{Number(l.credit) ? fa(l.credit) : ''}</td>
                    <td>{fa(l.balance)}</td>
                  </tr>
                ))}
                <tr>
                  <td colSpan={3}>جمع</td>
                  <td>{fa(contactStatement.total_debit)}</td>
                  <td>{fa(contactStatement.total_credit)}</td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="invoice-total">
            {Number(contactStatement.closing_balance) >= 0
              ? `مانده‌ی پایان دوره (بدهکار — به ما بدهکار است): ${fa(contactStatement.closing_balance)}`
              : `مانده‌ی پایان دوره (بستانکار — ما به او بدهکاریم): ${fa(Math.abs(Number(contactStatement.closing_balance)))}`}
          </p>
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

      {active === 'vat' && vatReport && (
        <div>
          <p className="hint">خلاصه‌ی مالیات بر ارزش افزوده از ابتدای فعالیت تا امروز — مبنای اظهارنامه و تسویه با سازمان.</p>
          <table>
            <tbody>
              <tr>
                <td>جمع خالص فروش</td>
                <td>{fa(vatReport.sales_net)}</td>
              </tr>
              <tr>
                <td>مالیات فروش، پس از کسرِ برگشت</td>
                <td>{fa(vatReport.output_vat)}</td>
              </tr>
              {Number(vatReport.sales_returns_vat) > 0 && (
                <tr className="muted-row">
                  <td>— از این میان، مالیاتِ برگشت از فروش (کسرشده)</td>
                  <td>{fa(vatReport.sales_returns_vat)}</td>
                </tr>
              )}
              <tr>
                <td>جمع خالص خرید</td>
                <td>{fa(vatReport.purchase_net)}</td>
              </tr>
              <tr>
                <td>اعتبار مالیاتی خرید، پس از کسرِ برگشت</td>
                <td>{fa(vatReport.input_vat)}</td>
              </tr>
              {Number(vatReport.purchase_returns_vat) > 0 && (
                <tr className="muted-row">
                  <td>— از این میان، اعتبارِ برگشت از خرید (کسرشده)</td>
                  <td>{fa(vatReport.purchase_returns_vat)}</td>
                </tr>
              )}
            </tbody>
          </table>
          <p className="invoice-total">
            {Number(vatReport.net_vat) >= 0
              ? 'مالیات قابل پرداخت به سازمان'
              : 'اعتبار مالیاتی (انتقالی به دوره‌ی بعد)'}
            : {fa(Math.abs(Number(vatReport.net_vat)))}
          </p>
        </div>
      )}

      {active === 'budget' && budgetReport && (
        <div>
          <p className="hint">
            مبلغِ برنامه‌ریزی‌شده در برابر عملکردِ واقعی، فقط برای حساب‌هایی که بودجه دارند. «مطلوب» یعنی درآمدِ بیشتر
            یا هزینه‌ی کمتر از برنامه.
          </p>
          {budgetReport.rows.length === 0 ? (
            <p className="hint">هنوز بودجه‌ای تعریف نشده. از «حسابداری ← بودجه‌بندی» بودجه اضافه کنید.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>نام حساب</th>
                    <th>بودجه</th>
                    <th>عملکرد</th>
                    <th>انحراف</th>
                    <th>درصد</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {budgetReport.rows.map((r) => (
                    <tr key={r.account_id}>
                      <td>{r.account_code}</td>
                      <td>{r.account_name}</td>
                      <td>{fa(r.budget)}</td>
                      <td>{fa(r.actual)}</td>
                      <td>{fa(r.variance)}</td>
                      <td>{r.variance_pct != null ? `${fa(r.variance_pct)}٪` : '—'}</td>
                      <td>
                        <span className={`status-badge ${r.favorable ? 'tone-success' : 'tone-danger'}`}>
                          {r.favorable ? 'مطلوب' : 'نامطلوب'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={2}>جمع</td>
                    <td>{fa(budgetReport.total_budget)}</td>
                    <td>{fa(budgetReport.total_actual)}</td>
                    <td>{fa(budgetReport.total_variance)}</td>
                    <td colSpan={2}></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {active === 'cash-flow' && cashFlow && (() => {
        const groups = [
          { title: 'فعالیت‌های عملیاتی', lines: cashFlow.operating, total: cashFlow.net_operating },
          { title: 'فعالیت‌های سرمایه‌گذاری', lines: cashFlow.investing, total: cashFlow.net_investing },
          { title: 'فعالیت‌های تأمین مالی', lines: cashFlow.financing, total: cashFlow.net_financing },
        ]
        return (
          <div>
            <p className="hint">
              ورود (+) و خروج (−) نقد از ابتدای فعالیت تا امروز، به تفکیک سه فعالیت. جمعِ سه فعالیت با تغییرِ ماندهٔ نقد
              برابر است.
            </p>
            <p>ماندهٔ نقد ابتدای دوره: {fa(cashFlow.opening_cash)}</p>
            {groups.map((g) => (
              <div key={g.title}>
                <h3>{g.title}</h3>
                {g.lines.length === 0 ? (
                  <p className="hint">موردی در این فعالیت نبود.</p>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <tbody>
                        {g.lines.map((l) => (
                          <tr key={l.account_id}>
                            <td>{l.account_code} — {l.account_name}</td>
                            <td>{fa(l.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="invoice-total">جمع {g.title}: {fa(g.total)}</p>
              </div>
            ))}
            <p className="invoice-total">تغییر خالص نقد در دوره: {fa(cashFlow.net_change)}</p>
            <p className="invoice-total">ماندهٔ نقد پایان دوره: {fa(cashFlow.closing_cash)}</p>
          </div>
        )
      })()}

      {active === 'cost-center' && costCenterReport && (
        <div>
          <p className="hint">
            سود و زیانِ هر مرکز هزینه/پروژه از سندهای برچسب‌خورده. سطرِ «بدون مرکز هزینه» یعنی فعالیتی که به هیچ پروژه‌ای
            نسبت داده نشده.
          </p>
          {costCenterReport.rows.length === 0 ? (
            <p className="hint">هنوز هیچ سندی به مرکز هزینه‌ای برچسب نخورده. از «حسابداری ← مراکز هزینه» شروع کنید.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>مرکز / پروژه</th>
                    <th>درآمد</th>
                    <th>هزینه</th>
                    <th>سود/زیان</th>
                  </tr>
                </thead>
                <tbody>
                  {costCenterReport.rows.map((r) => (
                    <tr key={r.cost_center_id ?? 'none'} className={r.cost_center_id ? '' : 'muted-row'}>
                      <td>{r.cost_center_code || '—'}</td>
                      <td>{r.cost_center_name}</td>
                      <td>{fa(r.income)}</td>
                      <td>{fa(r.expense)}</td>
                      <td>{fa(r.profit)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={2}>جمع</td>
                    <td>{fa(costCenterReport.total_income)}</td>
                    <td>{fa(costCenterReport.total_expense)}</td>
                    <td>{fa(costCenterReport.total_profit)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {(active === 'receivable-aging' || active === 'payable-aging') && aging && (
        <div>
          <p className="hint">
            {aging.kind === 'receivable'
              ? 'مانده‌ی طلب از هر مشتری، به تفکیک سنِ فاکتورها. تسویه‌ها و برگشت‌ها اول به قدیمی‌ترین فاکتور اعمال می‌شوند.'
              : 'مانده‌ی بدهی به هر تأمین‌کننده، به تفکیک سنِ فاکتورها. پرداخت‌ها و برگشت‌ها اول به قدیمی‌ترین فاکتور اعمال می‌شوند.'}
          </p>
          {aging.rows.length === 0 ? (
            <p className="hint">
              {aging.kind === 'receivable' ? 'مطالبات بازی وجود ندارد.' : 'بدهی بازی وجود ندارد.'}
            </p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{aging.kind === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}</th>
                    <th>جاری (۰–۳۰)</th>
                    <th>۳۱–۶۰ روز</th>
                    <th>۶۱–۹۰ روز</th>
                    <th>بالای ۹۰ روز</th>
                    <th>جمع</th>
                  </tr>
                </thead>
                <tbody>
                  {aging.rows.map((r) => (
                    <tr key={r.contact_id}>
                      <td>{r.contact_name}</td>
                      <td>{fa(r.current)}</td>
                      <td>{fa(r.d31_60)}</td>
                      <td>{fa(r.d61_90)}</td>
                      <td>{Number(r.over_90) > 0 ? <span className="status-badge tone-danger">{fa(r.over_90)}</span> : fa(r.over_90)}</td>
                      <td>{fa(r.total)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td>جمع</td>
                    <td>{fa(aging.total_current)}</td>
                    <td>{fa(aging.total_31_60)}</td>
                    <td>{fa(aging.total_61_90)}</td>
                    <td>{fa(aging.total_over_90)}</td>
                    <td className="invoice-total">{fa(aging.grand_total)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {active === 'inventory' && inventory && (
        <div>
          <p className="hint">
            ارزش ریالیِ موجودیِ هر کالا = تعداد موجود × بهای میانگین موزون. جمعِ کل باید با ماندهٔ حسابِ «موجودی کالا» بخواند.
          </p>
          {inventory.rows.length === 0 ? (
            <p className="hint">موجودی کالایی برای نمایش نیست.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>کالا</th>
                    <th>واحد</th>
                    <th>موجودی</th>
                    <th>بهای واحد</th>
                    <th>ارزش</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.rows.map((r) => (
                    <tr key={r.item_id}>
                      <td>{r.sku}</td>
                      <td>{r.name}</td>
                      <td>{r.unit}</td>
                      <td>{Number(r.qty_on_hand) < 0 ? <span className="status-badge tone-danger">{fa(r.qty_on_hand)}</span> : fa(r.qty_on_hand)}</td>
                      <td>{fa(r.unit_cost)}</td>
                      <td>{fa(r.stock_value)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={5}>جمع ارزش موجودی ({fa(inventory.item_count)} قلم)</td>
                    <td className="invoice-total">{fa(inventory.total_value)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
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
