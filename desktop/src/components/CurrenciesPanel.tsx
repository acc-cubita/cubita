import { useEffect, useState } from 'react'
import { Coins, Plus, Trash2, TrendingUp, Save } from 'lucide-react'
import {
  createCurrency,
  deleteCurrency,
  fetchCurrencies,
  fetchRates,
  upsertRate,
  type Currency,
  type ExchangeRate,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

export function CurrenciesPanel({ token }: { token: string }) {
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [rates, setRates] = useState<ExchangeRate[]>([])
  const curPg = usePagination(currencies, 10)
  const ratePg = usePagination(rates, 10)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  // فرم ارز
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('')

  // فرم نرخ
  const [rateCode, setRateCode] = useState('')
  const [rateDate, setRateDate] = useState(todayIso())
  const [rateValue, setRateValue] = useState('')

  async function refresh() {
    try {
      const [cs, rs] = await Promise.all([fetchCurrencies(token), fetchRates(token)])
      setCurrencies(cs)
      setRates(rs)
      if (!rateCode && cs.length > 0) setRateCode(cs[0].code)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function handleAddCurrency(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!code.trim() || !name.trim()) {
      setMessage('کد و نام ارز الزامی است.')
      return
    }
    try {
      await createCurrency(token, { code: code.trim().toUpperCase(), name: name.trim(), symbol: symbol.trim() })
      setCode('')
      setName('')
      setSymbol('')
      setMessage('ارز افزوده شد.')
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDeleteCurrency(id: string) {
    try {
      await deleteCurrency(token, id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleAddRate(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!rateCode || !(Number(rateValue) > 0)) {
      setMessage('ارز و نرخ (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      await upsertRate(token, { currency_code: rateCode, rate_date: rateDate, rate: Number(rateValue) })
      setRateValue('')
      setMessage('نرخ ثبت شد.')
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="split-2col">
      <SectionCard
        icon={Coins}
        title="ارزها"
        description="ارزهای خارجی را تعریف کنید؛ ریال ارزِ پایه است و لازم نیست اضافه شود."
      >
        <form className="invoice-form form-full" onSubmit={handleAddCurrency}>
          <div className="field-row">
            <label>
              کد (مثل USD)
              <input type="text" value={code} onChange={(e) => setCode(e.target.value)} maxLength={3} placeholder="USD" />
            </label>
            <label>
              نماد
              <input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="$" />
            </label>
          </div>
          <label>
            نام
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="دلار آمریکا" />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Plus size={14} /> افزودن ارز
            </button>
          </div>
          {message && <div className="hint">{message}</div>}
        </form>

        {currencies.length === 0 ? (
          <EmptyState icon={Coins} text="ارزی تعریف نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>نام</th>
                    <th>نماد</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {curPg.pageItems.map((c) => (
                    <tr key={c.id}>
                      <td className="entity-name card-title" data-label="کد">{c.code}</td>
                      <td data-label="نام">{c.name}</td>
                      <td data-label="نماد">{c.symbol || '—'}</td>
                      <td className="card-actions">
                        <button type="button" className="icon-btn-danger" onClick={() => void handleDeleteCurrency(c.id)} aria-label="حذف">
                          <Trash2 size={13} /> حذف
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={curPg.page} pageCount={curPg.pageCount} onChange={curPg.setPage} />
          </div>
        )}
        {error && <div className="error">{error}</div>}
      </SectionCard>

      <SectionCard icon={TrendingUp} title="نرخ برابری" description="چند ریال به‌ازای یک واحد ارز. فرم فاکتور آخرین نرخ را پیشنهاد می‌دهد.">
        {currencies.length === 0 ? (
          <p className="hint">ابتدا یک ارز تعریف کنید.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={handleAddRate}>
            <div className="field-row">
              <label>
                ارز
                <select value={rateCode} onChange={(e) => setRateCode(e.target.value)}>
                  {currencies.map((c) => (
                    <option key={c.id} value={c.code}>
                      {c.code} — {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                تاریخ
                <JalaliDatePicker value={rateDate} onChange={setRateDate} />
              </label>
            </div>
            <label>
              نرخ (ریال به‌ازای ۱ واحد)
              <NumberInput allowDecimal value={rateValue} onChange={setRateValue} placeholder="۸۰۰۰۰۰" />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary">
                <Save size={14} /> ثبت نرخ
              </button>
            </div>
          </form>
        )}

        {rates.length === 0 ? (
          <EmptyState icon={TrendingUp} text="نرخی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>ارز</th>
                    <th>تاریخ</th>
                    <th>نرخ (ریال)</th>
                  </tr>
                </thead>
                <tbody>
                  {ratePg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="entity-name card-title" data-label="ارز">{r.currency_code}</td>
                      <td data-label="تاریخ">{formatJalali(r.rate_date)}</td>
                      <td data-label="نرخ (ریال)" className="money-cell">{fa(r.rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={ratePg.page} pageCount={ratePg.pageCount} onChange={ratePg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
