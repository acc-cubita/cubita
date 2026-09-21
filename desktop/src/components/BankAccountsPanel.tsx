import { useCallback, useEffect, useMemo, useState } from 'react'
import { Landmark, Save, Pencil, X, RefreshCw, BookOpen, Plus, Trash2, Wallet } from 'lucide-react'
import {
  fetchBankAccountsAdmin, createBankAccount, updateBankAccount, deleteBankAccount,
  createBankTransaction, fetchAnalytics,
  type BankAccountRecord, type BankAccountInput,
} from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Metric } from '../pages/accounting/kit'
import { Pager, usePagination } from './Pager'
import { AccountLedgerDrawer } from './AccountLedgerDrawer'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'
import { SearchSelect } from '../components/SearchSelect'
import { FormField } from './form/FormKit'

//: میان‌بُر، نه فهرستِ کامل — ارزهای تعریف‌شده در تنظیماتِ ارز می‌آیند.
const CURRENCIES = ['IRR', 'USD', 'EUR', 'AED']

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
/** صفر خط تیره می‌شود تا چشم از ارقامِ واقعی منحرف نشود. */
const faAmount = (s: string | number) => {
  const n = Math.round(Number(s) || 0)
  if (n === 0) return '—'
  return n < 0 ? `(${Math.abs(n).toLocaleString('fa-IR')})` : n.toLocaleString('fa-IR')
}

interface Draft {
  name: string; name2: string; bank_name: string; branch_name: string
  account_number: string; account_type: string; card_number: string; iban: string
  analytic_id: string; currency_code: string; opening_date: string
  holder_name: string; holder_name2: string; blocked_amount: string; cheque_print_format: string
}

const EMPTY: Draft = {
  name: '', name2: '', bank_name: '', branch_name: '',
  account_number: '', account_type: '', card_number: '', iban: '',
  analytic_id: '', currency_code: 'IRR', opening_date: '',
  holder_name: '', holder_name2: '', blocked_amount: '', cheque_print_format: '',
}

/**
 * حساب‌های بانکی — تعریف و دفترِ مانده، **در یک صفحه**.
 *
 * پیش از این دو نما وجود داشت: همین پنل (ساخت/ویرایش) و یک «فهرستِ حساب‌های
 * بانکی»ِ خواندنی که همان جدول را با ستون‌های دیگری نشان می‌داد. طبقِ قاعده‌ی
 * «هرگز دو نمای یک داده نساز» یکی شدند.
 *
 * **مانده‌ها همه مشتق‌اند** و از سرور می‌آیند: مانده از گردشِ جفتِ (معین، تفصیلی)
 * در دفتر، و «قابل استفاده» از مانده منهای بلوکه. تنها عددِ ذخیره‌شده، خودِ
 * مبلغِ بلوکه است — چون واقعیتی است که بانک اعلام می‌کند، نه حاصلِ تراکنش.
 */
export function BankAccountsPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const postable = accounts.filter((a) => !a.is_group)
  const [banks, setBanks] = useState<BankAccountRecord[] | null>(null)
  const [analytics, setAnalytics] = useState<{ id: string; code: string; name: string }[]>([])
  const pg = usePagination(banks ?? [], 10)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState<Draft>(EMPTY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [ledger, setLedger] = useState<{
    account: { id: string; code: string; name: string }
    analyticId: string | null
  } | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setBanks(await fetchBankAccountsAdmin(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    fetchAnalytics(token).then(setAnalytics).catch(() => setAnalytics([]))
  }, [token])

  const rows = useMemo(() => banks ?? [], [banks])

  //: جمع فقط **درونِ هر ارز** (§۲۱). یک «جمعِ کلِ حساب‌ها» بینِ ریال و دلار عددی
  //: می‌سازد که هیچ معنایی ندارد و بدتر از نبودنش است.
  const perCurrency = useMemo(() => {
    const acc = new Map<string, number>()
    for (const b of rows) acc.set(b.currency_code, (acc.get(b.currency_code) ?? 0) + Number(b.balance || 0))
    return [...acc.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [rows])

  //: حسابی که تفصیلی دارد ولی هیچ گردشی — معمولاً یعنی سابقه‌اش روی حسابِ
  //: تفکیک‌نشده مانده. اگر چنین حسابی هست، راهنما نشان داده می‌شود.
  const hasUntagged = rows.some((b) => b.analytic_id === null)
  const someTaggedEmpty = rows.some((b) => b.analytic_id !== null && Number(b.balance || 0) === 0)

  function startEdit(b: BankAccountRecord) {
    setEditingId(b.id)
    setForm({
      name: b.name, name2: b.name2, bank_name: b.bank_name, branch_name: b.branch_name,
      account_number: b.account_number, account_type: b.account_type,
      card_number: b.card_number, iban: b.iban,
      analytic_id: b.analytic_id ?? '', currency_code: b.currency_code,
      opening_date: b.opening_date ?? '', holder_name: b.holder_name, holder_name2: b.holder_name2,
      blocked_amount: String(Number(b.blocked_amount) || ''), cheque_print_format: b.cheque_print_format,
    })
    setMessage(null)
  }
  function resetForm() { setForm(EMPTY); setEditingId(null); setMessage(null) }

  function payload(): BankAccountInput {
    return {
      name: form.name.trim(), name2: form.name2.trim(),
      bank_name: form.bank_name.trim(), branch_name: form.branch_name.trim(),
      account_number: form.account_number.trim(), account_type: form.account_type.trim(),
      card_number: form.card_number.trim(), iban: form.iban.trim(),
      analytic_id: form.analytic_id || null,
      currency_code: form.currency_code,
      opening_date: form.opening_date || null,
      holder_name: form.holder_name.trim(), holder_name2: form.holder_name2.trim(),
      blocked_amount: Number(form.blocked_amount) || 0,
      cheque_print_format: form.cheque_print_format.trim(),
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setMessage(null)
    if (!form.name.trim()) { setMessage('نام حساب الزامی است.'); return }
    setSaving(true)
    try {
      if (editingId) {
        await updateBankAccount(token, editingId, payload())
        setMessage('حساب بانکی ویرایش شد.')
      } else {
        await createBankAccount(token, payload())
        setMessage('حساب بانکی ساخته شد.')
      }
      resetForm(); await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally { setSaving(false) }
  }

  async function toggleActive(b: BankAccountRecord) {
    try { await updateBankAccount(token, b.id, { is_active: !b.is_active }); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  async function remove(b: BankAccountRecord) {
    if (!window.confirm(`حساب «${b.name}» حذف شود؟ اگر سابقه داشته باشد رد می‌شود.`)) return
    try { await deleteBankAccount(token, b.id); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  return (
    <div className="page-block">
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<Landmark size={14} />} label="حساب‌ها" value={fa(rows.length)} />
          <Metric
            icon={<Landmark size={14} />}
            label="فعال"
            value={fa(rows.filter((b) => b.is_active).length)}
            tone="in"
          />
          {perCurrency.map(([code, total]) => (
            <Metric
              key={code}
              icon={<Wallet size={14} />}
              label={`مانده ${code}`}
              value={fa(total)}
              tone={total < 0 ? 'out' : 'in'}
            />
          ))}
        </div>
      </section>

      <div className="workspace-split">
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایش حساب بانکی' : 'حساب بانکیِ جدید'}
          description={
            editingId
              ? 'اطلاعاتِ این حساب را به‌روزرسانی کنید.'
              : 'تفصیلی همان چیزی است که مانده‌ی این حساب را از بقیه جدا می‌کند.'
          }
          actions={editingId ? <button onClick={resetForm}><X size={13} /> انصراف</button> : undefined}
        >
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <div className="field-row">
              <label>نام حساب
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="مثلاً جاری ملت" />
              </label>
              <label>عنوان دوم
                <input value={form.name2} onChange={(e) => setForm({ ...form, name2: e.target.value })} />
              </label>
            </div>
            <div className="field-row">
              <label>نام بانک
                <input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} placeholder="ملت" />
              </label>
              <label>شعبه
                <input value={form.branch_name} onChange={(e) => setForm({ ...form, branch_name: e.target.value })} placeholder="ونک" />
              </label>
            </div>
            <div className="field-row">
              <label>شماره حساب
                <input value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} dir="ltr" inputMode="numeric" />
              </label>
              <label>نوع حساب
                <input value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value })} placeholder="جاری" />
              </label>
            </div>
            <div className="field-row">
              <FormField label="شماره کارت" tip="۱۶ رقم — با شبا و شماره حساب یکی نیست.">
                {(id) => <input id={id} value={form.card_number} onChange={(e) => setForm({ ...form, card_number: e.target.value })} dir="ltr" inputMode="numeric" />}
              </FormField>
              <FormField label="شماره شبا" tip="با IR شروع می‌شود.">
                {(id) => <input id={id} value={form.iban} onChange={(e) => setForm({ ...form, iban: e.target.value })} dir="ltr" />}
              </FormField>
            </div>
            <FormField
              label="تفصیلی"
              tip="بدونِ تفصیلی، مانده‌ی این حساب از بقیه جدا نمی‌شود. حسابِ باسابقه تفصیلی‌اش عوض نمی‌شود."
            >
              {(id) => (
                <SearchSelect id={id} value={form.analytic_id} onChange={(e) => setForm({ ...form, analytic_id: e.target.value })}>
                  <option value="">— بدونِ تفصیلی (فقط برای حسابِ اول) —</option>
                  {analytics.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                </SearchSelect>
              )}
            </FormField>
            <div className="field-row">
              <FormField label="ارز" tip="یک حساب، یک ارز. برای ارزِ دیگر حسابِ جدا بسازید.">
                {(id) => (
                  <SearchSelect id={id} value={form.currency_code} onChange={(e) => setForm({ ...form, currency_code: e.target.value })}>
                    {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </SearchSelect>
                )}
              </FormField>
              <FormField label="تاریخ افتتاح" tip="از چه زمانی این حساب واقعاً باز شده — نه تاریخِ ثبتش در کوبیتا.">
                {(id) => <JalaliDatePicker id={id} value={form.opening_date} onChange={(v) => setForm({ ...form, opening_date: v })} />}
              </FormField>
            </div>
            <div className="field-row">
              <FormField label="نام صاحب حساب" tip="می‌تواند با نامِ شرکت فرق داشته باشد.">
                {(id) => <input id={id} value={form.holder_name} onChange={(e) => setForm({ ...form, holder_name: e.target.value })} />}
              </FormField>
              <label>نام دوم صاحب حساب
                <input value={form.holder_name2} onChange={(e) => setForm({ ...form, holder_name2: e.target.value })} />
              </label>
            </div>
            <div className="field-row">
              <FormField label="مبلغ بلوکه‌شده" tip="از مانده کم نمی‌شود؛ فقط «قابل استفاده» را پایین می‌آورد.">
                {(id) => <NumberInput id={id} value={form.blocked_amount} onChange={(v) => setForm({ ...form, blocked_amount: v })} />}
              </FormField>
              <label>فرمت چاپ چک
                <input value={form.cheque_print_format} onChange={(e) => setForm({ ...form, cheque_print_format: e.target.value })} />
              </label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={saving}>
                <Save size={14} /> {editingId ? 'ذخیره' : 'ثبت حساب'}
              </button>
            </div>
            {message && <div className="hint">{message}</div>}
          </form>
        </SectionCard>

        <SectionCard
          icon={Landmark}
          title="حساب‌های بانکی"
          description={banks ? `${fa(banks.length)} حساب` : ''}
          actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
        >
          {error && <div className="error">{error}</div>}
          {banks == null ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : banks.length === 0 ? (
            <EmptyState icon={Landmark} text="هنوز حساب بانکی‌ای ثبت نشده." />
          ) : (
            <div className="entity-table-wrap">
              {hasUntagged && someTaggedEmpty && (
                <p className="field-hint">
                  حسابی که مانده‌اش صفر است، گردشِ پیش از تفکیک را روی حسابِ بدونِ تفصیلی دارد.
                  برای انتقالش از «اصلاح طبقه‌بندی مانده» استفاده کنید تا اسنادِ گذشته دست‌نخورده بمانند.
                </p>
              )}
              <div className="table-scroll">
                <table className="entity-table bank-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>کد تفصیلی</th>
                      <th>حساب</th>
                      <th>نوع</th>
                      <th>موجودی اولیه</th>
                      <th>مانده</th>
                      <th>بلوکه</th>
                      <th>قابل استفاده</th>
                      <th>ارز</th>
                      <th>تاریخ افتتاح</th>
                      <th>وضعیت</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {pg.pageItems.map((b) => (
                      <tr key={b.id} className={b.is_active ? '' : 'acc-row--idle'}>
                        <td data-label="کد تفصیلی" dir="ltr">{b.analytic_code ?? '—'}</td>
                        <td data-label="حساب" className="card-title entity-name">
                          {b.name}
                          {b.bank_name && <span className="unit-suffix"> · {b.bank_name}</span>}
                          {b.branch_name && <span className="unit-suffix"> · {b.branch_name}</span>}
                          {b.account_number && <div className="entity-sub" dir="ltr">{b.account_number}</div>}
                        </td>
                        <td data-label="نوع">{b.account_type || '—'}</td>
                        <td data-label="موجودی اولیه" className="num">{faAmount(b.opening_balance)}</td>
                        <td data-label="مانده" className="num"><strong>{faAmount(b.balance)}</strong></td>
                        <td data-label="بلوکه" className="num">{faAmount(b.blocked_amount)}</td>
                        <td data-label="قابل استفاده" className="num">{faAmount(b.available_balance)}</td>
                        <td data-label="ارز" dir="ltr">{b.currency_code}</td>
                        <td data-label="تاریخ افتتاح">{b.opening_date ? formatJalali(b.opening_date) : '—'}</td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${b.is_active ? 'tone-success' : 'tone-warning'}`}>
                            {b.is_active ? 'فعال' : 'غیرفعال'}
                          </span>
                        </td>
                        <td className="check-actions card-actions">
                          <button
                            type="button"
                            onClick={() => setLedger({
                              account: { id: b.gl_account_id, code: b.analytic_code ?? b.account_number, name: b.name },
                              analyticId: b.analytic_id,
                            })}
                          >
                            <BookOpen size={13} /> کارتِ حساب
                          </button>
                          <button type="button" onClick={() => startEdit(b)}><Pencil size={13} /> ویرایش</button>
                          <button type="button" onClick={() => void toggleActive(b)}>{b.is_active ? 'غیرفعال' : 'فعال'}</button>
                          <button type="button" onClick={() => void remove(b)}><Trash2 size={13} /> حذف</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          )}
        </SectionCard>
      </div>

      <BankTransactionForm token={token} banks={(banks ?? []).filter((b) => b.is_active)} accounts={postable} onDone={() => void refresh()} />

      {ledger && (
        //: دفتر با **تفصیلیِ همین حساب** فیلتر می‌شود. پیش از این معینِ مشترک باز
        //: می‌شد، یعنی برای «بانک سامان» گردشِ همه‌ی بانک‌ها نشان داده می‌شد.
        <AccountLedgerDrawer
          token={token}
          account={ledger.account}
          filters={ledger.analyticId ? { analyticId: ledger.analyticId } : undefined}
          onClose={() => setLedger(null)}
        />
      )}
    </div>
  )
}

function BankTransactionForm({
  token, banks, accounts, onDone,
}: {
  token: string
  banks: BankAccountRecord[]
  accounts: AccountCache[]
  onDone: () => void
}) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [direction, setDirection] = useState<'deposit' | 'withdraw'>('deposit')
  const [amount, setAmount] = useState('')
  const [counterAccountId, setCounterAccountId] = useState('')
  const [description, setDescription] = useState('')
  const [transactionDate, setTransactionDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setMessage(null)
    if (!bankAccountId || !counterAccountId || Number(amount) <= 0) { setMessage('حساب بانکی، حساب مقابل و مبلغ (بزرگ‌تر از صفر) الزامی است.'); return }
    try {
      await createBankTransaction(token, {
        bank_account_id: bankAccountId, transaction_date: transactionDate,
        amount: direction === 'deposit' ? Number(amount) : -Number(amount),
        counter_account_id: counterAccountId, description,
      })
      setAmount(''); setDescription(''); setMessage('تراکنش بانکی ثبت شد.'); onDone()
    } catch (err) { setMessage(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  return (
    <SectionCard icon={Save} title="واریز / برداشتِ بانکی" description="جابه‌جاییِ دستیِ وجه بین بانک و حسابِ مقابل (مثلاً صندوق).">
      <form className="invoice-form" onSubmit={handleSubmit}>
        <label>حساب بانکی
          <SearchSelect value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {banks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </SearchSelect>
        </label>
        <label>نوع
          <SearchSelect value={direction} onChange={(e) => setDirection(e.target.value as 'deposit' | 'withdraw')}>
            <option value="deposit">واریز</option>
            <option value="withdraw">برداشت</option>
          </SearchSelect>
        </label>
        <label>مبلغ<NumberInput value={amount} onChange={setAmount} /></label>
        <label>حساب مقابل (مثلاً صندوق)
          <SearchSelect value={counterAccountId} onChange={(e) => setCounterAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </SearchSelect>
        </label>
        <label>توضیحات<input type="text" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>تاریخ<JalaliDatePicker value={transactionDate} onChange={setTransactionDate} /></label>
        <div className="invoice-form-footer"><button type="submit" className="btn-primary"><Save size={14} /> ثبت تراکنش</button></div>
        {message && <div className="hint">{message}</div>}
      </form>
    </SectionCard>
  )
}
