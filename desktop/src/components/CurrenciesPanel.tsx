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
import { SearchSelect } from './SearchSelect'
import {
  ActionBar,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
  RowAction,
} from './form/FormKit'

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
    <>
      <form noValidate onSubmit={handleAddCurrency}>
        <SectionCard
          icon={Coins}
          title="ارزها"
          tip="ارزهای خارجی را تعریف کنید؛ ریال ارزِ پایه است و لازم نیست اضافه شود."
          badge={<CountBadge accent>{fa(currencies.length)} ارز</CountBadge>}
        >
          <FormGrid>
            <FormField label="کد ارز" required tip="کدِ سه‌حرفیِ استاندارد، مثلِ USD یا EUR.">
              {(id) => (
                <input
                  id={id}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  maxLength={3}
                  dir="ltr"
                  placeholder="USD"
                />
              )}
            </FormField>
            <FormField label="نماد" optional>
              {(id) => <input id={id} value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="$" />}
            </FormField>
            <FormField label="نام" required>
              {(id) => (
                <input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder="دلار آمریکا" />
              )}
            </FormField>
          </FormGrid>

          <div className="ef-block">
            <h3 className="ef-block-title">ارزهای تعریف‌شده</h3>
          {currencies.length === 0 ? (
            <EmptyState icon={Coins} text="ارزی تعریف نشده." />
          ) : (
            <div className="table-scroll ef-table-wrap">
              <table className="entity-table cards-on-mobile ef-table">
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>نام</th>
                    <th>نماد</th>
                    <th className="ef-col-min">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {curPg.pageItems.map((c) => (
                    <tr key={c.id}>
                      <td className="entity-name card-title" data-label="کد" dir="ltr">
                        {c.code}
                      </td>
                      <td data-label="نام">{c.name}</td>
                      <td data-label="نماد">{c.symbol || '—'}</td>
                      <td className="card-actions ef-col-min">
                        <div className="row-actions ef-row-actions">
                          <RowAction
                            icon={Trash2}
                            label="حذف"
                            danger
                            onClick={() => void handleDeleteCurrency(c.id)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={curPg.page} pageCount={curPg.pageCount} onChange={curPg.setPage} />
            </div>
          )}
          </div>
          {error && <p className="ef-message ef-message--warn ef-block-note">{error}</p>}
        </SectionCard>
        <ActionBar status={<FormStatus msg={message ? { text: message, kind: 'ok' } : null} />}>
          <button type="submit" className="btn-primary">
            <Plus size={16} /> افزودن ارز
          </button>
        </ActionBar>
      </form>

      <form noValidate onSubmit={handleAddRate}>
        <SectionCard
          icon={TrendingUp}
          title="نرخ برابری"
          tip="چند ریال به‌ازای یک واحد ارز. فرمِ فاکتور آخرین نرخ را پیشنهاد می‌دهد."
          badge={<CountBadge>{fa(rates.length)} نرخ</CountBadge>}
        >
          {currencies.length === 0 ? (
            <div className="ef-empty">ابتدا یک ارز تعریف کنید.</div>
          ) : (
            <FormGrid>
              <FormField label="ارز" required>
                {(id) => (
                  <SearchSelect id={id} value={rateCode} onChange={(e) => setRateCode(e.target.value)}>
                    {currencies.map((c) => (
                      <option key={c.id} value={c.code}>
                        {c.code} — {c.name}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
              <FormField label="تاریخ" required>
                {(id) => <JalaliDatePicker id={id} value={rateDate} onChange={setRateDate} />}
              </FormField>
              <FormField label="نرخ" required tip="ریال به‌ازای یک واحد ارز.">
                {(id) => (
                  <InputAffix unit="ریال">
                    <NumberInput id={id} allowDecimal value={rateValue} onChange={setRateValue} placeholder="۸۰۰۰۰۰" />
                  </InputAffix>
                )}
              </FormField>
            </FormGrid>
          )}

          <div className="ef-block">
            <h3 className="ef-block-title">نرخ‌های ثبت‌شده</h3>
          {rates.length === 0 ? (
            <EmptyState icon={TrendingUp} text="نرخی ثبت نشده." />
          ) : (
            <div className="table-scroll ef-table-wrap">
              <table className="entity-table cards-on-mobile ef-table">
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
                      <td className="entity-name card-title" data-label="ارز" dir="ltr">
                        {r.currency_code}
                      </td>
                      <td data-label="تاریخ">{formatJalali(r.rate_date)}</td>
                      <td data-label="نرخ (ریال)" className="money-cell">
                        {fa(r.rate)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={ratePg.page} pageCount={ratePg.pageCount} onChange={ratePg.setPage} />
            </div>
          )}
          </div>
        </SectionCard>
        {currencies.length > 0 && (
          <ActionBar>
            <button type="submit" className="btn-primary">
              <Save size={16} /> ثبت نرخ
            </button>
          </ActionBar>
        )}
      </form>
    </>
  )
}
