import { Building2, Plus, Pencil, X, Save, Trash2, PackageX, Landmark, TrendingDown, Wallet, Play } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { useFixedAssetDraft, type FixedAssetDraft } from '../lib/fixedAssetDraft'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

/** «دارایی ثابت» (پوسته‌های تیره/روشن) — فرمِ ثبت/ویرایش + فهرست + اجرای استهلاک.
 *  منطق در هوکِ مشترکِ [useFixedAssetDraft]. */
export function FixedAssetsPanel({ token }: { token: string }) {
  const d = useFixedAssetDraft({ token })

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Landmark size={18} />} label="تعداد دارایی فعال" value={fa(d.active.length)} hint="واگذارنشده" />
        <StatCard icon={<Building2 size={18} />} label="بهای تمام‌شده" value={fa(d.totalCost)} tone="default" />
        <StatCard icon={<TrendingDown size={18} />} label="استهلاک انباشته" value={fa(d.totalAccum)} tone="warning" />
        <StatCard icon={<Wallet size={18} />} label="ارزش دفتری" value={fa(d.totalBook)} tone="success" />
      </div>

      <div className="workspace-split">
        <SectionCard
          icon={d.editingId ? Pencil : Plus}
          title={d.editingId ? 'ویرایش دارایی' : 'دارایی ثابت جدید'}
          description="خودرو، تجهیزات، ساختمان و ... — استهلاک خط مستقیم بر پایه‌ی عمر مفید."
          actions={d.editingId ? <button onClick={d.resetForm}><X size={13} /> انصراف</button> : undefined}
        >
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void d.submit()
            }}
          >
            <FixedAssetFields d={d} />
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={d.submitting}><Save size={14} /> {d.editingId ? 'ذخیره' : 'ثبت دارایی'}</button>
            </div>
            {d.formMsg && <div className="hint">{d.formMsg}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={Landmark} title="فهرست دارایی‌ها" description={`${fa(d.assets.length)} قلم دارایی`}>
          <FixedAssetsList d={d} />
        </SectionCard>
      </div>

      <DepreciationRun d={d} />
    </>
  )
}

/** فیلدهای فرمِ دارایی (بدون فوتر) — مشترکِ فرمِ کلاسیک و ویزارد. */
export function FixedAssetFields({ d, splitStep }: { d: FixedAssetDraft; splitStep?: 'identity' | 'valuation' }) {
  const showIdentity = splitStep !== 'valuation'
  const showValuation = splitStep !== 'identity'
  return (
    <>
      {showIdentity && (
        <>
          <label>
            نام دارایی
            <input value={d.form.name} onChange={(e) => d.setFormField('name', e.target.value)} placeholder="مثلاً وانت نیسان" />
          </label>
          <label>
            دسته
            <input value={d.form.category} onChange={(e) => d.setFormField('category', e.target.value)} placeholder="وسیله نقلیه" />
          </label>
          <label>
            تاریخ تحصیل
            <JalaliDatePicker value={d.form.acquired_date} onChange={(v) => d.setFormField('acquired_date', v)} />
          </label>
          <label>
            توضیحات
            <input value={d.form.notes} onChange={(e) => d.setFormField('notes', e.target.value)} />
          </label>
        </>
      )}
      {showValuation && (
        <>
          <label>
            بهای تمام‌شده
            <NumberInput value={d.form.cost} onChange={(v) => d.setFormField('cost', v)} />
          </label>
          <label>
            ارزش اسقاط
            <NumberInput value={d.form.salvage_value} onChange={(v) => d.setFormField('salvage_value', v)} />
          </label>
          <label>
            عمر مفید (ماه)
            <NumberInput value={d.form.useful_life_months} onChange={(v) => d.setFormField('useful_life_months', v)} />
          </label>
          {!d.editingId && (
            <label>
              پرداخت از
              <select value={d.form.funding_account_id} onChange={(e) => d.setFormField('funding_account_id', e.target.value)}>
                <option value="">— بدون سند (آورده / قبلاً در دفاتر) —</option>
                {d.fundingAccounts.map((a) => (<option key={a.id} value={a.id}>{a.name}</option>))}
              </select>
            </label>
          )}
        </>
      )}
    </>
  )
}

/** جدولِ فهرستِ دارایی‌ها با اکشن‌ها — مشترکِ فرم و ویزارد. */
export function FixedAssetsList({ d }: { d: FixedAssetDraft }) {
  const pg = usePagination(d.assets, 10)
  if (d.assets.length === 0) {
    return <EmptyState icon={Landmark} text="هنوز دارایی ثابتی ثبت نشده." />
  }
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr>
            <th>نام</th>
            <th>تحصیل</th>
            <th>بها</th>
            <th>ماهانه</th>
            <th>انباشته</th>
            <th>ارزش دفتری</th>
            <th>وضعیت</th>
            <th>عملیات</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((a) => (
            <tr key={a.id} style={a.is_disposed ? { opacity: 0.55 } : undefined}>
              <td className="card-title">{a.name}</td>
              <td data-label="تحصیل">{formatJalali(a.acquired_date)}</td>
              <td data-label="بها">{fa(a.cost)}</td>
              <td data-label="ماهانه">{fa(a.monthly_depreciation)}</td>
              <td data-label="انباشته">{fa(a.accumulated_depreciation)}</td>
              <td data-label="ارزش دفتری">{fa(a.book_value)}</td>
              <td data-label="وضعیت">
                <span className={`status-badge ${a.is_disposed ? 'tone-danger' : a.fully_depreciated ? 'tone-warning' : 'tone-success'}`}>
                  {a.is_disposed ? 'واگذارشده' : a.fully_depreciated ? 'مستهلک کامل' : 'فعال'}
                </span>
              </td>
              <td className="card-actions">
                <div className="check-actions">
                  <button type="button" onClick={() => d.startEdit(a)} aria-label="ویرایش"><Pencil size={13} /></button>
                  {!a.is_disposed && (
                    <button type="button" onClick={() => void d.handleDispose(a)} aria-label="واگذاری"><PackageX size={13} /></button>
                  )}
                  <button type="button" className="icon-btn-danger" onClick={() => void d.handleDelete(a)} aria-label="حذف"><Trash2 size={13} /></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

/** بخشِ «اجرای استهلاک دوره» با تاریخچه — مشترکِ فرم و ویزارد. */
export function DepreciationRun({ d }: { d: FixedAssetDraft }) {
  const pg = usePagination(d.entries, 10)
  return (
    <SectionCard
      icon={Play}
      title="اجرای استهلاک دوره"
      description="یک تاریخ (معمولاً پایان ماه) انتخاب کنید؛ برای همه‌ی دارایی‌های فعال یک سند استهلاک ثبت می‌شود. هر دوره فقط یک‌بار."
    >
      <div className="check-actions">
        <div style={{ maxWidth: 220, flex: '1 1 180px' }}>
          <JalaliDatePicker value={d.periodDate} onChange={d.setPeriodDate} />
        </div>
        <button type="button" className="btn-primary" onClick={() => void d.handleRun()}><Play size={14} /> ثبت استهلاک این دوره</button>
      </div>
      {d.runMsg && <div className="hint">{d.runMsg}</div>}

      {d.entries.length > 0 && (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>دوره</th>
                <th>دارایی</th>
                <th>مبلغ استهلاک</th>
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((e) => (
                <tr key={e.id}>
                  <td data-label="دوره">{formatJalali(e.period_date)}</td>
                  <td className="card-title">{e.asset_name}</td>
                  <td data-label="مبلغ استهلاک">{fa(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
  )
}
