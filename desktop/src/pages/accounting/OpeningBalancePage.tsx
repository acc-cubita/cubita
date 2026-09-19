import { useEffect, useState } from 'react'
import { Save, Trash2, Wallet } from 'lucide-react'
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
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { toNumber } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import { fa, Note, OpsPage, type Msg } from './kit'
import { SearchSelect } from '../../components/SearchSelect'

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
    setBusy(true)
    setMsg(null)
    try {
      await createOpeningBalances(token, {
        entry_date: date,
        lines: lines
          .filter((l) => l.account_id && (toNumber(l.debit) > 0 || toNumber(l.credit) > 0))
          .map((l) => ({ account_id: l.account_id, debit: toNumber(l.debit), credit: toNumber(l.credit) })),
        stock: stock
          .filter((s) => s.item_id && s.warehouse_id && toNumber(s.qty) > 0)
          .map((s) => ({ item_id: s.item_id, warehouse_id: s.warehouse_id, qty: toNumber(s.qty), unit_cost: toNumber(s.unit_cost) })),
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

  return (
    <OpsPage
      icon={Wallet}
      title="مانده اول دوره"
      description="مانده‌ی حساب‌ها و موجودیِ انبار در لحظه‌ی شروعِ کار با کوبیتا — از همین‌جا سندِ افتتاحیه ساخته می‌شود."
    >
      <Note msg={msg} />

      {status?.exists ? (
        <SectionCard icon={Wallet} title="مانده‌های اول دوره">
          <p className="hint">
            سند افتتاحیه‌ی این کسب‌وکار قبلاً ثبت شده است (شماره {fa(status.entry_number ?? 0)}، تاریخ{' '}
            {status.entry_date ? formatJalali(status.entry_date) : '—'}). برای جلوگیری از دوباره‌کاری، فقط یک سند
            افتتاحیه مجاز است؛ اصلاحات را با «سند حسابداری» انجام دهید.
          </p>
        </SectionCard>
      ) : (
        <SectionCard
          icon={Wallet}
          title="مانده‌های اول دوره (سند افتتاحیه)"
          description="اختلافِ تراز به‌طور خودکار به حسابِ سرمایه بسته می‌شود."
        >
          <div className="invoice-form form-full">
            <label>
              تاریخِ افتتاحیه
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              حسابِ تراز (سرمایه)
              <SearchSelect value={balancingId} onChange={(e) => setBalancingId(e.target.value)}>
                <option value="">— بدون تراز خودکار (باید متوازن باشد) —</option>
                {postable.map((a) => (
                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                ))}
              </SearchSelect>
            </label>
          </div>

          <h4 style={{ marginTop: 12 }}>مانده‌ی حساب‌ها</h4>
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr><th>حساب</th><th>بدهکار</th><th>بستانکار</th><th></th></tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td className="card-wide" data-label="حساب">
                      <SearchSelect value={l.account_id} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, account_id: e.target.value } : x))}>
                        <option value="">— انتخاب حساب —</option>
                        {postable.map((a) => (
                          <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                        ))}
                      </SearchSelect>
                    </td>
                    <td data-label="بدهکار"><NumberInput value={l.debit} onChange={(v) => setLines(lines.map((x, j) => j === i ? { ...x, debit: v, credit: '' } : x))} /></td>
                    <td data-label="بستانکار"><NumberInput value={l.credit} onChange={(v) => setLines(lines.map((x, j) => j === i ? { ...x, credit: v, debit: '' } : x))} /></td>
                    <td className="card-actions"><button type="button" onClick={() => setLines(lines.filter((_, j) => j !== i))}><Trash2 size={13} /> حذف</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" onClick={() => setLines([...lines, { account_id: '', debit: '', credit: '' }])}>+ افزودن ردیف</button>

          <h4 style={{ marginTop: 16 }}>موجودیِ اول دوره (اختیاری)</h4>
          <p className="hint">ارزشِ موجودی خودکار به‌عنوانِ بدهکارِ «موجودی کالا» به سند اضافه می‌شود — حسابِ موجودی را دستی وارد نکنید.</p>
          {warehouses.length > 0 && (
            <>
              <div className="table-scroll">
                <table className="cards-on-mobile">
                  <thead>
                    <tr><th>کالا</th><th>انبار</th><th>تعداد</th><th>بهای واحد</th><th>ارزش</th><th></th></tr>
                  </thead>
                  <tbody>
                    {stock.map((s, i) => (
                      <tr key={i}>
                        <td className="card-wide" data-label="کالا">
                          <SearchSelect value={s.item_id} onChange={(e) => setStock(stock.map((x, j) => j === i ? { ...x, item_id: e.target.value } : x))}>
                            <option value="">— انتخاب کالا —</option>
                            {items.map((it) => (<option key={it.id} value={it.id}>{it.sku} — {it.name}</option>))}
                          </SearchSelect>
                        </td>
                        <td className="card-wide" data-label="انبار">
                          <SearchSelect value={s.warehouse_id} onChange={(e) => setStock(stock.map((x, j) => j === i ? { ...x, warehouse_id: e.target.value } : x))}>
                            <option value="">— انبار —</option>
                            {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
                          </SearchSelect>
                        </td>
                        <td data-label="تعداد"><NumberInput value={s.qty} onChange={(v) => setStock(stock.map((x, j) => j === i ? { ...x, qty: v } : x))} /></td>
                        <td data-label="بهای واحد"><NumberInput value={s.unit_cost} onChange={(v) => setStock(stock.map((x, j) => j === i ? { ...x, unit_cost: v } : x))} /></td>
                        <td className="money-cell" data-label="ارزش">{fa(toNumber(s.qty) * toNumber(s.unit_cost))}</td>
                        <td className="card-actions"><button type="button" onClick={() => setStock(stock.filter((_, j) => j !== i))}><Trash2 size={13} /> حذف</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" onClick={() => setStock([...stock, { item_id: '', warehouse_id: warehouses[0]?.id ?? '', qty: '', unit_cost: '' }])}>+ افزودن موجودی</button>
            </>
          )}

          <div className="opening-totals" style={{ marginTop: 12 }}>
            <span>جمع بدهکار: <b>{fa(totalDebit)}</b></span>
            {'  '}| جمع بستانکار: <b>{fa(totalCredit)}</b>
            {'  '}| {diff === 0 ? <b style={{ color: 'var(--success, green)' }}>متوازن ✓</b> : <b style={{ color: 'var(--danger, crimson)' }}>اختلاف: {fa(Math.abs(diff))}</b>}
            {diff !== 0 && balancingId && <span className="hint"> (به سرمایه بسته می‌شود)</span>}
          </div>

          <div className="invoice-form-footer">
            <button type="button" className="btn-primary" onClick={() => void submit()} disabled={busy}>
              <Save size={14} /> ثبتِ سند افتتاحیه
            </button>
          </div>
        </SectionCard>
      )}
    </OpsPage>
  )
}
