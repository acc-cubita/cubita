import { useEffect, useMemo, useState } from 'react'
import { HandCoins, Landmark, Wallet } from 'lucide-react'
import {
  createOwnerTransaction,
  fetchBankAccountsAdmin,
  fetchCashboxes,
  fetchContacts,
  fetchOwnerTransactions,
  fetchPartnerBalances,
  type BankAccountRecord,
  type CashboxRecord,
  type ContactRecord,
  type OwnerTransactionRecord,
  type PartnerBalanceRecord,
} from '../../api'
import { OpsPage, Note, type Msg } from '../accounting/kit'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { formatJalali, todayIso } from '../../lib/jalali'

const fa = (n: number) => Number(n || 0).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

/** شش نوعِ صریح — همان چیزی که بک‌اند با CHECK نگه می‌دارد.
 *
 *  **ترتیب عمدی است و گروه‌بندی هم.** قاعده‌ی ۵۲ می‌گوید جهتِ پول به‌تنهایی نوعِ
 *  حسابداری را تعیین نکند؛ اگر این فهرست بر اساسِ «پولِ ورودی / پولِ خروجی» چیده
 *  می‌شد، رابط همان حدسی را القا می‌کرد که قاعده منعش می‌کند. پس بر اساسِ
 *  **ماهیتِ رویداد** چیده شده: سرمایه، وام، بازپرداخت. */
const TYPE_GROUPS: { label: string; items: { key: string; label: string; hint: string }[] }[] = [
  {
    label: 'سرمایه',
    items: [
      { key: 'capital_contribution', label: 'آورده‌ی سرمایه', hint: 'شریک پول آورد و سهمش از شرکت بیشتر شد. درآمد نیست.' },
      { key: 'capital_withdrawal', label: 'کاهشِ سرمایه', hint: 'برداشتِ دائمی — سهمِ شریک کم می‌شود. هزینه نیست.' },
    ],
  },
  {
    label: 'وام',
    items: [
      { key: 'loan_to_entity', label: 'وامِ شریک به شرکت', hint: 'پول آورد ولی سرمایه نیست؛ شرکت به او بدهکار می‌شود.' },
      { key: 'loan_from_entity', label: 'برداشتِ قابلِ بازپرداخت', hint: 'برداشت کرد و قرار است برگرداند؛ به شرکت بدهکار می‌شود.' },
    ],
  },
  {
    label: 'بازپرداخت',
    items: [
      { key: 'repayment_to_partner', label: 'بازپرداخت به شریک', hint: 'شرکت بدهی‌اش به شریک را می‌دهد.' },
      { key: 'repayment_from_partner', label: 'بازپرداختِ شریک', hint: 'شریک بدهی‌اش به شرکت را می‌دهد.' },
    ],
  },
]

const ALL_TYPES = TYPE_GROUPS.flatMap((g) => g.items)

const EMPTY_FORM = {
  type: '',
  transactionDate: todayIso(),
  contactId: '',
  amount: '',
  method: 'cash' as 'cash' | 'bank',
  bankAccountId: '',
  cashboxId: '',
  description: '',
  evidenceRef: '',
}

/** ماندهٔ جاری شرکا با علامتِ خوانا. صفر خط تیره می‌شود (§۱۰ قراردادِ صفحه). */
function balanceText(value: string | number): string {
  const n = Number(value || 0)
  if (n === 0) return '—'
  return n > 0 ? `${fa(n)} طلبکار` : `${fa(Math.abs(n))} بدهکار`
}

export function OwnerTransactionPage({ token }: { token: string }) {
  const [partners, setPartners] = useState<ContactRecord[]>([])
  const [cashboxes, setCashboxes] = useState<CashboxRecord[]>([])
  const [banks, setBanks] = useState<BankAccountRecord[]>([])
  const [recent, setRecent] = useState<OwnerTransactionRecord[]>([])
  const [balances, setBalances] = useState<PartnerBalanceRecord[]>([])
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [msg, setMsg] = useState<Msg>(null)
  //: جدا از `msg` — همان درسِ PR #90: خطای بارگذاری نباید پیامِ «ثبت شد» را پاک
  //: کند، وگرنه کاربر دوباره می‌فرستد و آورده‌ی سرمایه دوبار ثبت می‌شود.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setLoadError(null)
    try {
      const [cs, boxes, bs, txns, bals] = await Promise.all([
        fetchContacts(token),
        fetchCashboxes(token),
        fetchBankAccountsAdmin(token),
        fetchOwnerTransactions(token),
        fetchPartnerBalances(token),
      ])
      setPartners(cs.filter((c) => c.is_shareholder))
      setCashboxes(boxes)
      setBanks(bs)
      setRecent(txns.slice(0, 8))
      setBalances(bals)
    } catch (err) {
      setLoadError(`${errText(err)} — فهرست‌های این صفحه پر نشد؛ صفحه را دوباره باز کنید.`)
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  const set = (patch: Partial<typeof EMPTY_FORM>) => setForm({ ...form, ...patch })
  const chosen = useMemo(() => ALL_TYPES.find((t) => t.key === form.type) ?? null, [form.type])

  async function submit() {
    setMsg(null)
    if (!form.type) {
      setMsg({ kind: 'err', text: 'نوعِ تراکنش را انتخاب کنید — از روی جهتِ پول حدس زده نمی‌شود.' })
      return
    }
    if (!form.contactId) {
      setMsg({ kind: 'err', text: 'شریک را انتخاب کنید.' })
      return
    }
    if (!(Number(form.amount) > 0)) {
      setMsg({ kind: 'err', text: 'مبلغ باید بزرگ‌تر از صفر باشد.' })
      return
    }
    setBusy(true)
    try {
      await createOwnerTransaction(
        token,
        {
          type: form.type,
          transaction_date: form.transactionDate,
          contact_id: form.contactId,
          amount: Number(form.amount),
          method: form.method,
          bank_account_id: form.method === 'bank' ? form.bankAccountId || null : null,
          cashbox_id: form.method === 'cash' ? form.cashboxId || null : null,
          description: form.description,
          evidence_ref: form.evidenceRef,
        },
        `ownertxn-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setMsg({ kind: 'ok', text: 'تراکنشِ شریک ثبت شد.' })
      setForm({ ...EMPTY_FORM })
      void refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={HandCoins}
      title="تراکنش شریک"
      description="آورده، برداشت، وام و بازپرداختِ مالکان — با نوعِ صریح، نه حدس از روی جهتِ پول."
    >
      <div className="workspace-split">
        <SectionCard icon={HandCoins} title="تراکنشِ تازه">
          {partners.length === 0 && !loadError && (
            <p className="hint">
              هنوز کسی «سهامدار» علامت نخورده است. در «طرف حساب جدید» گزینه‌ی سهامدار را فعال کنید.
            </p>
          )}
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <label className="form-full">
              نوعِ تراکنش
              <select value={form.type} onChange={(e) => set({ type: e.target.value })} required>
                <option value="">— انتخابِ نوع —</option>
                {TYPE_GROUPS.map((group) => (
                  <optgroup key={group.label} label={group.label}>
                    {group.items.map((t) => (
                      <option key={t.key} value={t.key}>{t.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
              {chosen && <span className="field-hint">{chosen.hint}</span>}
            </label>
            <label>
              شریک
              <select value={form.contactId} onChange={(e) => set({ contactId: e.target.value })} required>
                <option value="">— انتخابِ شریک —</option>
                {partners.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>
            <label>
              مبلغ
              <NumberInput value={form.amount} onChange={(v) => set({ amount: v })} required />
            </label>
            <label>
              تاریخ
              <JalaliDatePicker value={form.transactionDate} onChange={(iso) => set({ transactionDate: iso })} />
            </label>
            <label>
              از/به
              <select
                value={form.method}
                onChange={(e) => set({ method: e.target.value as 'cash' | 'bank', bankAccountId: '', cashboxId: '' })}
              >
                <option value="cash">صندوق</option>
                <option value="bank">بانک</option>
              </select>
            </label>
            {form.method === 'cash' ? (
              <label>
                صندوق
                <select value={form.cashboxId} onChange={(e) => set({ cashboxId: e.target.value })}>
                  <option value="">— صندوقِ پیش‌فرض —</option>
                  {cashboxes.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </label>
            ) : (
              <label>
                حسابِ بانکی
                <select value={form.bankAccountId} onChange={(e) => set({ bankAccountId: e.target.value })} required>
                  <option value="">— انتخابِ حساب —</option>
                  {banks.map((b) => (
                    <option key={b.id} value={b.id}>{b.name} — {b.bank_name}</option>
                  ))}
                </select>
              </label>
            )}
            <label>
              شماره‌ی مدرک
              <input
                value={form.evidenceRef}
                onChange={(e) => set({ evidenceRef: e.target.value })}
                placeholder="اختیاری"
              />
            </label>
            <label className="form-full">
              شرح
              <input value={form.description} onChange={(e) => set({ description: e.target.value })} placeholder="اختیاری" />
            </label>
            <div className="form-full">
              <button type="submit" disabled={busy}>{busy ? 'در حال ثبت…' : 'ثبتِ تراکنش'}</button>
            </div>
          </form>
          <Note msg={loadError ? { kind: 'err', text: loadError } : null} />
          <Note msg={msg} />
        </SectionCard>

        <SectionCard
          icon={Wallet}
          title="ماندهٔ جاری شرکا"
          description="فقط وام و بازپرداخت. آورده‌ی سرمایه بدهیِ شرکت به شریک نمی‌سازد."
        >
          {balances.length === 0 ? (
            <EmptyState icon={Wallet} text="هنوز سهامداری ثبت نشده است." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr><th>شریک</th><th>سهم</th><th>مانده</th></tr>
                </thead>
                <tbody>
                  {balances.map((b) => (
                    <tr key={b.contact_id}>
                      <td className="card-title" data-label="شریک">{b.contact_name}</td>
                      <td className="num" data-label="سهم">{fa(Number(b.share_percent))}٪</td>
                      <td className="num" data-label="مانده">{balanceText(b.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h4 className="vr-heading">تراکنش‌های اخیر</h4>
          {recent.length === 0 ? (
            <EmptyState icon={Landmark} text="هنوز تراکنشی ثبت نشده است." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr><th>تاریخ</th><th>شریک</th><th>نوع</th><th>مبلغ</th></tr>
                </thead>
                <tbody>
                  {recent.map((t) => (
                    <tr key={t.id}>
                      <td data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                      <td className="card-title" data-label="شریک">{t.contact_name}</td>
                      <td data-label="نوع">{t.type_label}</td>
                      <td className="num" data-label="مبلغ">{fa(Number(t.amount))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </OpsPage>
  )
}
