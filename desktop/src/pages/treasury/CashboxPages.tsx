import { useMemo, useState } from 'react'
import { PiggyBank, Plus, RefreshCw, Save, Trash2 } from 'lucide-react'
import {
  createCashbox,
  deleteCashbox,
  fetchAnalytics,
  fetchCashboxes,
  updateCashbox,
  type CashboxRecord,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'
import { FormField } from '../../components/form/FormKit'

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

/** ارزهای رایج. فهرست کامل از تنظیماتِ ارز می‌آید؛ این‌ها میان‌بُرند. */
const CURRENCIES = ['IRR', 'USD', 'EUR', 'AED']

/**
 * تعریف و مدیریت صندوق.
 *
 * **صندوق حسابِ حسابداری نیست.** تا پیش از این بود — تنها تعریفش یک
 * `if method === 'cash'` بود، پس بیش از یک صندوق ممکن نبود. حالا موجودیتِ
 * عملیاتی است که با *تفصیلی* به حسابداری وصل می‌شود، مثلِ حسابِ بانکی که با
 * معین وصل می‌شود.
 *
 * **موجودیِ اولیه و مانده دو ستونِ جدا هستند و هر دو مشتق‌اند.** هیچ‌کدام در جدول
 * ذخیره نمی‌شوند؛ از دفتر خوانده می‌شوند. همین است که نمی‌گذارد صندوق با تراز
 * واگرا شود.
 */
export function CashboxesPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [form, setForm] = useState({
    name: '',
    name2: '',
    analytic_id: '',
    currency_code: 'IRR',
    opening_date: '',
  })

  const boxes = useAsync(() => fetchCashboxes(token), [token, reloadKey])
  const analytics = useAsync(() => fetchAnalytics(token), [token])
  //: با useMemo تثبیت می‌شود تا وابستگیِ perCurrency هر رندر عوض نشود.
  const rows = useMemo(() => boxes.data ?? [], [boxes.data])
  const pg = usePagination(rows, 12)

  //: جمع فقط درونِ هر ارز. ریالی و دلاری بدونِ نرخ و تاریخ جمع‌شدنی نیستند، و
  //: یک عددِ «جمعِ صندوق‌ها» بیشتر گمراه می‌کند تا کمک.
  const perCurrency = useMemo(() => {
    const map = new Map<string, number>()
    for (const r of rows) map.set(r.currency_code, (map.get(r.currency_code) ?? 0) + Number(r.balance))
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [rows])

  const done = (m: Msg) => {
    setMsg(m)
    if (m?.kind === 'ok') setReloadKey((k) => k + 1)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await createCashbox(token, {
        name: form.name,
        name2: form.name2,
        analytic_id: form.analytic_id || null,
        currency_code: form.currency_code,
        opening_date: form.opening_date || null,
      })
      setForm({ name: '', name2: '', analytic_id: '', currency_code: 'IRR', opening_date: '' })
      done({ text: 'صندوق ساخته شد.', kind: 'ok' })
    } catch (err) {
      done({ text: errText(err), kind: 'err' })
    }
  }

  async function toggle(box: CashboxRecord) {
    try {
      await updateCashbox(token, box.id, { is_active: !box.is_active })
      done({ text: box.is_active ? 'صندوق غیرفعال شد.' : 'صندوق فعال شد.', kind: 'ok' })
    } catch (err) {
      done({ text: errText(err), kind: 'err' })
    }
  }

  async function remove(box: CashboxRecord) {
    if (!window.confirm(`صندوق «${box.name}» حذف شود؟`)) return
    try {
      await deleteCashbox(token, box.id)
      done({ text: 'صندوق حذف شد.', kind: 'ok' })
    } catch (err) {
      done({ text: errText(err), kind: 'err' })
    }
  }

  return (
    <OpsPage
      icon={PiggyBank}
      title="تعریف صندوق"
      description="صندوق جایی است که پولِ نقد نگه داشته می‌شود — یک موجودیتِ عملیاتی که با تفصیلی به حسابداری وصل می‌شود، نه خودِ حسابِ معین."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<PiggyBank size={14} />} label="صندوق‌ها" value={faInt(rows.length)} />
            {perCurrency.map(([code, total]) => (
              <Metric key={code} icon={<PiggyBank size={14} />} label={`مانده ${code}`} value={fa(total)} tone={total < 0 ? 'out' : 'in'} />
            ))}
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={Plus}
        title="صندوقِ تازه"
        description="تفصیلی همان چیزی است که مانده‌ی این صندوق را از بقیه جدا می‌کند؛ بدونِ آن، صندوقِ دوم مانده‌ی مستقل ندارد."
      >
        <form className="invoice-form" onSubmit={submit}>
          <label>
            عنوان
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </label>
          <label>
            عنوان دوم
            <input
              type="text"
              value={form.name2}
              onChange={(e) => setForm({ ...form, name2: e.target.value })}
            />
          </label>
          <label>
            تفصیلی
            <SearchSelect
              value={form.analytic_id}
              onChange={(e) => setForm({ ...form, analytic_id: e.target.value })}
            >
              <option value="">— بدونِ تفصیلی (فقط برای صندوقِ اول) —</option>
              {(analytics.data ?? []).map((a: { id: string; code: string; name: string }) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name}
                </option>
              ))}
            </SearchSelect>
          </label>
          <FormField label="ارز" tip="یک صندوق، یک ارز. برای ارزِ دیگر صندوقِ جدا بسازید.">
            {(id) => (
              <SearchSelect
                id={id}
                value={form.currency_code}
                onChange={(e) => setForm({ ...form, currency_code: e.target.value })}
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </SearchSelect>
            )}
          </FormField>
          <FormField label="تاریخ افتتاح" tip="از چه زمانی این صندوق واقعاً باز شده — نه تاریخِ ثبتش در کوبیتا.">
            {(id) => (
              <JalaliDatePicker
                id={id}
                value={form.opening_date}
                onChange={(v) => setForm({ ...form, opening_date: v })}
              />
            )}
          </FormField>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Save size={14} /> ساختِ صندوق
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        icon={PiggyBank}
        title="صندوق‌ها"
        description="موجودیِ اولیه ابتدای سالِ مالی است و مانده نتیجه‌ی هرچه بعدش افتاده — هر دو از دفتر خوانده می‌شوند."
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <AsyncBlock
          loading={boxes.loading}
          error={boxes.error}
          empty={rows.length === 0}
          emptyText="هنوز صندوقی تعریف نشده — اولین دریافتِ نقدی خودکار «صندوق اصلی» را می‌سازد."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کد تفصیلی</th>
                  <th>عنوان</th>
                  <th>عنوان دوم</th>
                  <th>موجودی اولیه</th>
                  <th>مانده</th>
                  <th>ارز</th>
                  <th>تاریخ افتتاح</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((box) => (
                  <tr key={box.id} className={box.is_active ? '' : 'acc-row--idle'}>
                    <td data-label="کد تفصیلی" dir="ltr">
                      {box.analytic_code ?? '—'}
                    </td>
                    <td className="card-title" data-label="عنوان">
                      {box.name}
                    </td>
                    <td data-label="عنوان دوم">{box.name2 || '—'}</td>
                    <td className="num" data-label="موجودی اولیه">
                      {fa(box.opening_balance)}
                    </td>
                    <td className="num" data-label="مانده">
                      <strong>{fa(box.balance)}</strong>
                    </td>
                    <td data-label="ارز" dir="ltr">
                      {box.currency_code}
                    </td>
                    <td data-label="تاریخ افتتاح">
                      {box.opening_date ? formatJalali(box.opening_date) : '—'}
                    </td>
                    <td data-label="وضعیت">{box.is_active ? 'فعال' : 'غیرفعال'}</td>
                    <td className="card-actions">
                      <button type="button" onClick={() => void toggle(box)}>
                        {box.is_active ? 'غیرفعال کن' : 'فعال کن'}
                      </button>
                      <button type="button" onClick={() => void remove(box)}>
                        <Trash2 size={13} /> حذف
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
