import { useEffect, useState } from 'react'
import { AlertTriangle, Check, CheckCircle2, Trash2, Wallet } from 'lucide-react'
import {
  createOpeningBalances,
  fetchAccountsLive,
  fetchItemsLive,
  fetchOpeningStatus,
  fetchWarehousesLive,
  type OpeningStatus,
} from '../../api'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import {
  ActionBar,
  AddRowButton,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
  RowAction,
} from '../../components/form/FormKit'
import { toNumber } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import { fa, OpsPage, type Msg } from './kit'

/**
 * مانده‌های اول دوره — سندِ افتتاحیه‌ی نقطه‌ی شروعِ کار با کوبیتا.
 *
 * این صفحه پیش‌تر تبِ «فرآیند راه‌اندازی» بود، ولی خروجی‌اش یک **سندِ حسابداری** است و
 * جایش دفترداری است نه یک ماژولِ راه‌اندازیِ جداگانه: همان‌جا که کاربر چارت را می‌سازد و
 * سندِ اختتامیه/افتتاحیه‌ی سالِ بعد را صادر می‌کند. مجوزِ سرور هم از قبل `accounting` بود.
 *
 * فقط **یک** سندِ افتتاحیه مجاز است؛ اگر ثبت شده باشد صفحه به‌جای فرم، وضعیت را نشان
 * می‌دهد — اصلاح از راهِ سندِ دستی انجام می‌شود تا نقطه‌ی شروعِ دفتر دوباره‌نویسی نشود.
 */

type AccLine = { account_id: string; debit: string; credit: string }
type StockLine = { item_id: string; warehouse_id: string; qty: string; unit_cost: string }

export function OpeningBalancePage({ token }: { token: string }) {
  const [status, setStatus] = useState<OpeningStatus | null>(null)
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [items, setItems] = useState<{ id: string; sku: string; name: string; is_service: boolean }[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [date, setDate] = useState(todayIso())
  const [lines, setLines] = useState<AccLine[]>([{ account_id: '', debit: '', credit: '' }])
  const [stock, setStock] = useState<StockLine[]>([])
  const [balancingId, setBalancingId] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)

  async function refresh() {
    try {
      const [st, accs, its, whs] = await Promise.all([
        fetchOpeningStatus(token),
        fetchAccountsLive(token),
        fetchItemsLive(token),
        fetchWarehousesLive(token),
      ])
      setStatus(st)
      setAccounts(accs)
      setItems(its.filter((i) => !i.is_service))
      setWarehouses(whs)
      const capital = accs.find((a) => a.code === '3101')
      if (capital) setBalancingId(capital.id)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const postable = accounts.filter((a) => !a.is_group)
  const stockValue = stock.reduce((s, r) => s + toNumber(r.qty) * toNumber(r.unit_cost), 0)
  const totalDebit = lines.reduce((s, r) => s + toNumber(r.debit), 0) + stockValue
  const totalCredit = lines.reduce((s, r) => s + toNumber(r.credit), 0)
  const diff = totalDebit - totalCredit

  async function submit() {
    const filled = lines.filter((l) => l.account_id && (toNumber(l.debit) > 0 || toNumber(l.credit) > 0))
    if (filled.length === 0 && stock.length === 0) {
      setMsg({ text: 'دست‌کم یک مانده‌ی حساب یا یک ردیفِ موجودی وارد کنید.', kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      await createOpeningBalances(token, {
        entry_date: date,
        lines: filled.map((l) => ({
          account_id: l.account_id,
          debit: toNumber(l.debit),
          credit: toNumber(l.credit),
        })),
        stock: stock
          .filter((s) => s.item_id && s.warehouse_id && toNumber(s.qty) > 0)
          .map((s) => ({
            item_id: s.item_id,
            warehouse_id: s.warehouse_id,
            qty: toNumber(s.qty),
            unit_cost: toNumber(s.unit_cost),
          })),
        balancing_account_id: balancingId || null,
      })
      setMsg({ text: 'سند افتتاحیه با موفقیت ثبت شد.', kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  if (status?.exists) {
    return (
      <OpsPage
        canvas
        icon={Wallet}
        title="مانده اول دوره"
        description="مانده‌ی حساب‌ها و موجودیِ انبار در لحظه‌ی شروعِ کار با کوبیتا — از همین‌جا سندِ افتتاحیه ساخته می‌شود."
      >
        <SectionCard icon={Wallet} title="مانده‌های اول دوره">
          <div className="ef-callout">
            <CheckCircle2 size={18} />
            <p>
              سند افتتاحیه‌ی این کسب‌وکار قبلاً ثبت شده است (شماره {fa(status.entry_number ?? 0)}، تاریخ{' '}
              {status.entry_date ? formatJalali(status.entry_date) : '—'}). برای جلوگیری از دوباره‌کاری فقط یک سندِ
              افتتاحیه مجاز است؛ اصلاحات را با «سند حسابداری» انجام دهید.
            </p>
          </div>
        </SectionCard>
      </OpsPage>
    )
  }

  return (
    <OpsPage
      canvas
      icon={Wallet}
      title="مانده اول دوره"
      description="مانده‌ی حساب‌ها و موجودیِ انبار در لحظه‌ی شروعِ کار با کوبیتا — از همین‌جا سندِ افتتاحیه ساخته می‌شود."
    >
      <SectionCard
        icon={Wallet}
        title="سندِ افتتاحیه"
        tip="اختلافِ تراز خودکار به حسابِ سرمایه بسته می‌شود؛ اگر حسابِ تراز را خالی بگذارید، سند باید خودش متوازن باشد."
      >
        <FormGrid cols={2}>
          <FormField label="تاریخِ افتتاحیه" required>
            {(id) => <JalaliDatePicker id={id} value={date} onChange={setDate} />}
          </FormField>
          <FormField label="حسابِ تراز (سرمایه)">
            {(id) => (
              <SearchSelect id={id} value={balancingId} onChange={(e) => setBalancingId(e.target.value)}>
                <option value="">— بدون تراز خودکار (باید متوازن باشد) —</option>
                {postable.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            )}
          </FormField>
        </FormGrid>

        <div className="ef-block">
          <h3 className="ef-block-title">مانده‌ی حساب‌ها</h3>
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table ef-table--edit">
              <thead>
                <tr>
                  <th className="ef-col-min">ردیف</th>
                  <th>حساب</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th className="ef-col-min" aria-label="حذف" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td className="card-title ef-col-min" data-label="ردیف">
                      ردیف {fa(i + 1)}
                    </td>
                    <td className="card-wide ef-col-wide" data-label="حساب">
                      <SearchSelect
                        aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
                        value={l.account_id}
                        onChange={(e) =>
                          setLines(lines.map((x, j) => (j === i ? { ...x, account_id: e.target.value } : x)))
                        }
                      >
                        <option value="">— انتخاب حساب —</option>
                        {postable.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </option>
                        ))}
                      </SearchSelect>
                    </td>
                    <td className="card-wide" data-label="بدهکار">
                      <InputAffix unit="ریال">
                        <NumberInput
                          aria-label={`بدهکارِ ردیفِ ${fa(i + 1)}`}
                          value={l.debit}
                          onChange={(v) =>
                            setLines(lines.map((x, j) => (j === i ? { ...x, debit: v, credit: '' } : x)))
                          }
                        />
                      </InputAffix>
                    </td>
                    <td className="card-wide" data-label="بستانکار">
                      <InputAffix unit="ریال">
                        <NumberInput
                          aria-label={`بستانکارِ ردیفِ ${fa(i + 1)}`}
                          value={l.credit}
                          onChange={(v) =>
                            setLines(lines.map((x, j) => (j === i ? { ...x, credit: v, debit: '' } : x)))
                          }
                        />
                      </InputAffix>
                    </td>
                    <td className="card-actions ef-col-min">
                      <RowAction
                        icon={Trash2}
                        label="حذف ردیف"
                        danger
                        disabled={lines.length === 1}
                        title={lines.length === 1 ? 'دست‌کم یک ردیف لازم است.' : undefined}
                        onClick={() => setLines(lines.filter((_, j) => j !== i))}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <AddRowButton onClick={() => setLines([...lines, { account_id: '', debit: '', credit: '' }])}>
            افزودن ردیف
          </AddRowButton>
        </div>

        {warehouses.length > 0 && (
          <div className="ef-block">
            <h3 className="ef-block-title">موجودیِ اول دوره</h3>
            <p className="ef-message ef-block-note">
              ارزشِ موجودی خودکار به‌عنوانِ بدهکارِ «موجودی کالا» به سند اضافه می‌شود — حسابِ موجودی را دستی وارد نکنید.
            </p>
            {stock.length > 0 && (
              <div className="table-scroll ef-table-wrap">
                <table className="cards-on-mobile ef-table ef-table--edit">
                  <thead>
                    <tr>
                      <th className="ef-col-min">ردیف</th>
                      <th>کالا</th>
                      <th>انبار</th>
                      <th>تعداد</th>
                      <th>بهای واحد</th>
                      <th>ارزش</th>
                      <th className="ef-col-min" aria-label="حذف" />
                    </tr>
                  </thead>
                  <tbody>
                    {stock.map((s, i) => (
                      <tr key={i}>
                        <td className="card-title ef-col-min" data-label="ردیف">
                          ردیف {fa(i + 1)}
                        </td>
                        <td className="card-wide ef-col-wide" data-label="کالا">
                          <SearchSelect
                            aria-label={`کالای ردیفِ ${fa(i + 1)}`}
                            value={s.item_id}
                            onChange={(e) =>
                              setStock(stock.map((x, j) => (j === i ? { ...x, item_id: e.target.value } : x)))
                            }
                          >
                            <option value="">— انتخاب کالا —</option>
                            {items.map((it) => (
                              <option key={it.id} value={it.id}>
                                {it.sku} — {it.name}
                              </option>
                            ))}
                          </SearchSelect>
                        </td>
                        <td className="card-wide" data-label="انبار">
                          <SearchSelect
                            aria-label={`انبارِ ردیفِ ${fa(i + 1)}`}
                            value={s.warehouse_id}
                            onChange={(e) =>
                              setStock(stock.map((x, j) => (j === i ? { ...x, warehouse_id: e.target.value } : x)))
                            }
                          >
                            <option value="">— انبار —</option>
                            {warehouses.map((w) => (
                              <option key={w.id} value={w.id}>
                                {w.name}
                              </option>
                            ))}
                          </SearchSelect>
                        </td>
                        <td className="card-wide" data-label="تعداد">
                          <NumberInput
                            aria-label={`تعدادِ ردیفِ ${fa(i + 1)}`}
                            value={s.qty}
                            onChange={(v) => setStock(stock.map((x, j) => (j === i ? { ...x, qty: v } : x)))}
                          />
                        </td>
                        <td className="card-wide" data-label="بهای واحد">
                          <InputAffix unit="ریال">
                            <NumberInput
                              aria-label={`بهای واحدِ ردیفِ ${fa(i + 1)}`}
                              value={s.unit_cost}
                              onChange={(v) => setStock(stock.map((x, j) => (j === i ? { ...x, unit_cost: v } : x)))}
                            />
                          </InputAffix>
                        </td>
                        <td className="money-cell" data-label="ارزش">
                          {fa(toNumber(s.qty) * toNumber(s.unit_cost))}
                        </td>
                        <td className="card-actions ef-col-min">
                          <RowAction
                            icon={Trash2}
                            label="حذف ردیف"
                            danger
                            onClick={() => setStock(stock.filter((_, j) => j !== i))}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <AddRowButton
              onClick={() =>
                setStock([...stock, { item_id: '', warehouse_id: warehouses[0]?.id ?? '', qty: '', unit_cost: '' }])
              }
            >
              افزودن موجودی
            </AddRowButton>
          </div>
        )}
      </SectionCard>

      <ActionBar
        status={
          <FormStatus
            msg={msg}
            idle={
              <span className={diff === 0 ? 'is-ok' : 'is-err'}>
                {diff === 0 ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />} بدهکار {fa(totalDebit)} ·
                بستانکار {fa(totalCredit)}
                {diff === 0
                  ? ' — متوازن'
                  : ` — اختلاف ${fa(Math.abs(diff))}${balancingId ? ' (به سرمایه بسته می‌شود)' : ''}`}
              </span>
            }
          />
        }
      >
        <button type="button" className="btn-primary" onClick={() => void submit()} disabled={busy}>
          <Check size={16} /> {busy ? 'در حال ثبت…' : 'ثبتِ سند افتتاحیه'}
        </button>
      </ActionBar>
    </OpsPage>
  )
}
