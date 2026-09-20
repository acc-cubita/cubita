import { useEffect, useMemo, useState } from 'react'
import { Check, HandCoins, Landmark, Wallet } from 'lucide-react'
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
import { OpsPage, type Msg } from '../accounting/kit'
import { SectionCard } from '../../components/SectionCard'
import {
  ActionBar,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { formatJalali, todayIso } from '../../lib/jalali'
import { SearchSelect } from '../../components/SearchSelect'

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
    const missing = firstMissing([
      [form.type, 'ot-type', 'نوعِ تراکنش را انتخاب کنید.'],
      [form.contactId, 'ot-contact', 'شریک را انتخاب کنید.'],
      [form.amount, 'ot-amount', 'مبلغ را وارد کنید.'],
      [form.method === 'bank' ? form.bankAccountId : 'نقدی', 'ot-bank', 'حسابِ بانکی را انتخاب کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      canvas
      icon={HandCoins}
      title="تراکنش شریک"
      description="آورده، برداشت، وام و بازپرداختِ مالکان — با نوعِ صریح، نه حدس از روی جهتِ پول."
    >
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <SectionCard
          icon={HandCoins}
          title="تراکنشِ تازه"
          tip="نوعِ تراکنش سندِ حسابداری را تعیین می‌کند؛ آورده‌ی سرمایه با وامِ شریک یکی نیست."
        >
          {partners.length === 0 && !loadError && (
            <p className="ef-message ef-message--warn ef-block-note">
              هنوز کسی «سهامدار» علامت نخورده است. در «طرف حساب جدید» گزینه‌ی سهامدار را فعال کنید.
            </p>
          )}
          <FormGrid>
            <FormField
              id="ot-type"
              label="نوعِ تراکنش"
              required
              span="full"
              message={chosen ? chosen.hint : undefined}
            >
              {(id) => (
                <SearchSelect id={id} value={form.type} onChange={(e) => set({ type: e.target.value })}>
                  <option value="">— انتخابِ نوع —</option>
                  {TYPE_GROUPS.map((group) => (
                    <optgroup key={group.label} label={group.label}>
                      {group.items.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField id="ot-contact" label="شریک" required>
              {(id) => (
                <SearchSelect id={id} value={form.contactId} onChange={(e) => set({ contactId: e.target.value })}>
                  <option value="">— انتخابِ شریک —</option>
                  {partners.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField id="ot-amount" label="مبلغ" required>
              {(id) => (
                <InputAffix unit="ریال">
                  <NumberInput id={id} value={form.amount} onChange={(v) => set({ amount: v })} />
                </InputAffix>
              )}
            </FormField>
            <FormField label="تاریخ" required>
              {(id) => (
                <JalaliDatePicker
                  id={id}
                  value={form.transactionDate}
                  onChange={(iso) => set({ transactionDate: iso })}
                />
              )}
            </FormField>
            <FormField label="از / به" required>
              {(id) => (
                <SearchSelect
                  id={id}
                  value={form.method}
                  onChange={(e) =>
                    set({ method: e.target.value as 'cash' | 'bank', bankAccountId: '', cashboxId: '' })
                  }
                >
                  <option value="cash">صندوق</option>
                  <option value="bank">بانک</option>
                </SearchSelect>
              )}
            </FormField>
            {form.method === 'cash' ? (
              <FormField label="صندوق">
                {(id) => (
                  <SearchSelect id={id} value={form.cashboxId} onChange={(e) => set({ cashboxId: e.target.value })}>
                    <option value="">— صندوقِ پیش‌فرض —</option>
                    {cashboxes.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
            ) : (
              <FormField id="ot-bank" label="حسابِ بانکی" required>
                {(id) => (
                  <SearchSelect
                    id={id}
                    value={form.bankAccountId}
                    onChange={(e) => set({ bankAccountId: e.target.value })}
                  >
                    <option value="">— انتخابِ حساب —</option>
                    {banks.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name} — {b.bank_name}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
            )}
            <FormField label="شماره‌ی مدرک" optional>
              {(id) => (
                <input id={id} value={form.evidenceRef} onChange={(e) => set({ evidenceRef: e.target.value })} />
              )}
            </FormField>
            <FormField label="شرح" optional span="full">
              {(id) => (
                <input id={id} value={form.description} onChange={(e) => set({ description: e.target.value })} />
              )}
            </FormField>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg ?? (loadError ? { text: loadError, kind: 'err' } : null)} />}>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Check size={16} /> {busy ? 'در حال ثبت…' : 'ثبتِ تراکنش'}
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={Wallet}
        title="ماندهٔ جاری شرکا"
        tip="فقط وام و بازپرداخت. آورده‌ی سرمایه بدهیِ شرکت به شریک نمی‌سازد."
        badge={balances.length > 0 ? <CountBadge accent>{fa(balances.length)} شریک</CountBadge> : undefined}
      >
          {balances.length === 0 ? (
            <EmptyState icon={Wallet} text="هنوز سهامداری ثبت نشده است." />
          ) : (
            <div className="table-scroll ef-table-wrap">
              <table className="cards-on-mobile ef-table">
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

      </SectionCard>

      <SectionCard
        icon={Landmark}
        title="تراکنش‌های اخیر"
        badge={recent.length > 0 ? <CountBadge>{fa(recent.length)} تراکنش</CountBadge> : undefined}
      >
          {recent.length === 0 ? (
            <EmptyState icon={Landmark} text="هنوز تراکنشی ثبت نشده است." />
          ) : (
            <div className="table-scroll ef-table-wrap">
              <table className="cards-on-mobile ef-table">
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
    </OpsPage>
  )
}
