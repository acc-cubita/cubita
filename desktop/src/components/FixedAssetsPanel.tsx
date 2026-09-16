import { useEffect, useState } from 'react'
import { ArrowLeftRight, Building2, Plus, Pencil, X, Save, Trash2, PackageX, Landmark, TrendingDown, UserCheck, Wallet, Play, History } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { Tabs } from './Tabs'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'
import { useFixedAssetDraft, type FixedAssetDraft } from '../lib/fixedAssetDraft'
import { FixedAssetWizardFlow } from './wizard/FixedAssetWizard'
import {
  fetchAssetAssignments,
  fetchContacts,
  fetchCostCenters,
  placeFixedAsset,
  transferFixedAsset,
  type AssetAssignmentRecord,
  type FixedAssetRecord,
} from '../api'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

/** «دارایی ثابت» (پوسته‌های تیره/روشن) — ماژولِ تب‌دار: ثبت و کارتِ دارایی،
 *  تحویل/استقرار، جابه‌جایی، تاریخچه‌ی تحویل‌ها، و استهلاکِ دوره.
 *  منطقِ فرم در هوکِ مشترکِ [useFixedAssetDraft]. */
export function FixedAssetsPanel({ token, guided = false }: { token: string; guided?: boolean }) {
  const d = useFixedAssetDraft({ token })
  const [assignRefresh, setAssignRefresh] = useState(0)
  const bumpAssignments = () => setAssignRefresh((n) => n + 1)

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Landmark size={18} />} label="تعداد دارایی فعال" value={fa(d.active.length)} hint="واگذارنشده" />
        <StatCard icon={<Building2 size={18} />} label="بهای تمام‌شده" value={fa(d.totalCost)} tone="default" />
        <StatCard icon={<TrendingDown size={18} />} label="استهلاک انباشته" value={fa(d.totalAccum)} tone="warning" />
        <StatCard icon={<Wallet size={18} />} label="ارزش دفتری" value={fa(d.totalBook)} tone="success" />
      </div>

      <Tabs
        syncPage="fixedassets"
        tabs={[
          { key: 'assets', label: 'کارت دارایی', icon: Landmark, content: <AssetsTab d={d} guided={guided} /> },
          { key: 'placement', label: 'تحویل و استقرار', icon: UserCheck, content: <AssignmentTab token={token} d={d} kind="placement" onDone={bumpAssignments} /> },
          { key: 'transfer', label: 'جابه‌جایی دارایی', icon: ArrowLeftRight, content: <AssignmentTab token={token} d={d} kind="transfer" onDone={bumpAssignments} /> },
          { key: 'assignments', label: 'جابه‌جایی‌ها و تحویل‌ها', icon: History, content: <AssignmentsListTab token={token} assets={d.assets} refreshKey={assignRefresh} /> },
          { key: 'depreciation', label: 'استهلاک دوره', icon: Play, content: <DepreciationRun d={d} /> },
        ]}
      />
    </>
  )
}

/** تبِ ثبت/ویرایشِ دارایی + کارتِ دارایی‌ها.
 *  در پوسته‌ی «راهنما» فرمِ گام‌به‌گام می‌آید، در بقیه فرمِ کلاسیک — همان درفت،
 *  پس فهرست در هر دو حالت بعدِ ثبت به‌روز می‌شود. */
function AssetsTab({ d, guided }: { d: FixedAssetDraft; guided: boolean }) {
  if (guided) {
    return (
      <>
        <FixedAssetWizardFlow d={d} />
        <SectionCard icon={Landmark} title="کارتِ دارایی‌ها" description={`${fa(d.assets.length)} قلم دارایی — شناسه، ارزشِ دفتری و محلِ استقرار`}>
          <FixedAssetsList d={d} />
        </SectionCard>
      </>
    )
  }
  return (
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

      <SectionCard icon={Landmark} title="کارتِ دارایی‌ها" description={`${fa(d.assets.length)} قلم دارایی — شناسه، ارزشِ دفتری و محلِ استقرار`}>
        <FixedAssetsList d={d} />
      </SectionCard>
    </div>
  )
}

/** تحویل/استقرار و جابه‌جایی — یک فرم، دو معنا. مبدأ از وضعیتِ فعلیِ دارایی
 *  خوانده می‌شود (سرور همین کار را می‌کند)، پس فقط مقصد پرسیده می‌شود. */
function AssignmentTab({
  token,
  d,
  kind,
  onDone,
}: {
  token: string
  d: FixedAssetDraft
  kind: 'placement' | 'transfer'
  onDone: () => void
}) {
  const [assetId, setAssetId] = useState('')
  const [date, setDate] = useState(todayIso())
  const [custodianId, setCustodianId] = useState('')
  const [location, setLocation] = useState('')
  const [costCenterId, setCostCenterId] = useState('')
  const [notes, setNotes] = useState('')
  const [contacts, setContacts] = useState<{ id: string; name: string }[]>([])
  const [centers, setCenters] = useState<{ id: string; name: string }[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void fetchContacts(token).then((rows) => setContacts(rows.map((c) => ({ id: c.id, name: c.name })))).catch(() => {})
    void fetchCostCenters(token).then((rows) => setCenters(rows.map((c) => ({ id: c.id, name: c.name })))).catch(() => {})
  }, [token])

  const placing = kind === 'placement'
  const available = d.assets.filter((a) => !a.is_disposed)
  const asset = available.find((a) => a.id === assetId)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!assetId) {
      setMsg('دارایی را انتخاب کنید.')
      return
    }
    if (!custodianId && !location.trim() && !costCenterId) {
      setMsg('حداقل یکی از تحویل‌گیرنده، محلِ استقرار یا مرکزِ هزینه را مشخص کنید.')
      return
    }
    setBusy(true)
    try {
      const body = {
        assignment_date: date,
        to_custodian_id: custodianId || null,
        to_location: location.trim(),
        to_cost_center_id: costCenterId || null,
        notes,
      }
      const fn = placing ? placeFixedAsset : transferFixedAsset
      const out = await fn(token, assetId, body)
      setCustodianId('')
      setLocation('')
      setCostCenterId('')
      setNotes('')
      setMsg(`${placing ? 'تحویل' : 'جابه‌جایی'} ثبت شد ✓ «${out.name}» اکنون ${out.custodian_name || '—'}${out.location ? ` · ${out.location}` : ''}`)
      await d.refresh()
      onDone()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={placing ? UserCheck : ArrowLeftRight}
        title={placing ? 'تحویل و استقرارِ دارایی' : 'جابه‌جاییِ دارایی'}
        description={
          placing
            ? 'ورودِ دارایی به مجموعه و تخصیصش به شخص، محلِ استقرار یا مرکزِ هزینه.'
            : 'انتقالِ دارایی بینِ جمعداران، محل‌ها یا مراکزِ هزینه. مبدأ خودکار از وضعیتِ فعلی برداشته می‌شود.'
        }
      >
        {available.length === 0 ? (
          <p className="hint">دارایی فعالی برای {placing ? 'تحویل' : 'جابه‌جایی'} نیست.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              دارایی
              <select value={assetId} onChange={(e) => setAssetId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {available.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}{a.custodian_name ? ` (دستِ ${a.custodian_name})` : ''}
                  </option>
                ))}
              </select>
              {asset && (asset.custodian_name || asset.location) && (
                <span className="field-hint">
                  وضعیتِ فعلی: {asset.custodian_name || '—'}{asset.location ? ` · ${asset.location}` : ''}
                </span>
              )}
            </label>
            <div className="field-row">
              <label>
                تاریخ
                <JalaliDatePicker value={date} onChange={setDate} />
              </label>
              <label>
                تحویل‌گیرنده
                <select value={custodianId} onChange={(e) => setCustodianId(e.target.value)}>
                  <option value="">— بدونِ تغییر —</option>
                  {contacts.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                </select>
              </label>
            </div>
            <div className="field-row">
              <label>
                محلِ استقرار
                <input type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="مثلاً کارگاهِ شماره ۲" />
              </label>
              <label>
                مرکزِ هزینه
                <select value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                  <option value="">— بدونِ تغییر —</option>
                  {centers.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                </select>
              </label>
            </div>
            <label className="form-full">
              توضیحات
              <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="اختیاری" />
            </label>

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                {placing ? <UserCheck size={14} /> : <ArrowLeftRight size={14} />} {busy ? 'در حال ثبت…' : placing ? 'ثبتِ تحویل' : 'ثبتِ جابه‌جایی'}
              </button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={Landmark} title="وضعیتِ استقرارِ دارایی‌ها" description="الان هر دارایی دستِ کیست و کجاست">
        {available.length === 0 ? (
          <EmptyState icon={Landmark} text="دارایی فعالی ثبت نشده." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>دارایی</th>
                  <th>تحویل‌گیرنده</th>
                  <th>محل</th>
                  <th>مرکزِ هزینه</th>
                </tr>
              </thead>
              <tbody>
                {available.map((a) => (
                  <tr key={a.id}>
                    <td className="card-title" data-label="دارایی">{a.name}</td>
                    <td data-label="تحویل‌گیرنده">{a.custodian_name || '—'}</td>
                    <td data-label="محل">{a.location || '—'}</td>
                    <td data-label="مرکزِ هزینه">{a.cost_center_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

/** فهرستِ جابه‌جایی‌ها و تحویل‌ها — تاریخچه‌ی محلِ استقرار و تحویل‌گیرندگان. */
function AssignmentsListTab({
  token,
  assets,
  refreshKey,
}: {
  token: string
  assets: FixedAssetRecord[]
  refreshKey: number
}) {
  const [assetFilter, setAssetFilter] = useState('')
  const [rows, setRows] = useState<AssetAssignmentRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fetchAssetAssignments(token, assetFilter || undefined)
      .then((r) => { if (alive) setRows(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [token, assetFilter, refreshKey])

  const pg = usePagination(rows, 12, assetFilter)

  return (
    <SectionCard
      icon={History}
      title="جابه‌جایی‌ها و تحویل‌ها"
      description="تاریخچه‌ی محلِ استقرار و تحویل‌گیرندگانِ اموال — هر ردیف مبدأ و مقصدِ خودش را دارد."
    >
      <div className="invoice-form">
        <label>
          دارایی
          <select value={assetFilter} onChange={(e) => setAssetFilter(e.target.value)}>
            <option value="">همه‌ی دارایی‌ها</option>
            {assets.map((a) => (<option key={a.id} value={a.id}>{a.name}</option>))}
          </select>
        </label>
      </div>

      {error && <div className="error">{error}</div>}
      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={History} text="هنوز تحویل یا جابه‌جایی ثبت نشده." />
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>تاریخ</th>
                <th>نوع</th>
                <th>دارایی</th>
                <th>از</th>
                <th>به</th>
                <th>توضیحات</th>
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((r) => (
                <tr key={r.id}>
                  <td className="card-title" data-label="تاریخ">{formatJalali(r.assignment_date)}</td>
                  <td data-label="نوع">
                    <span className={`status-badge ${r.kind === 'placement' ? 'tone-success' : ''}`}>
                      {r.kind === 'placement' ? 'تحویل' : 'جابه‌جایی'}
                    </span>
                  </td>
                  <td data-label="دارایی">{r.asset_name}</td>
                  <td data-label="از">{[r.from_custodian_name, r.from_location].filter(Boolean).join(' · ') || '—'}</td>
                  <td data-label="به">{[r.to_custodian_name, r.to_location, r.to_cost_center_name].filter(Boolean).join(' · ') || '—'}</td>
                  <td className="card-wide" data-label="توضیحات">{r.notes || '—'}</td>
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
            <th>محلِ استقرار</th>
            <th>وضعیت</th>
            <th>عملیات</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((a) => (
            <tr key={a.id} style={a.is_disposed ? { opacity: 0.55 } : undefined}>
              <td className="card-title" data-label="نام">{a.name}</td>
              <td data-label="تحصیل">{formatJalali(a.acquired_date)}</td>
              <td data-label="بها">{fa(a.cost)}</td>
              <td data-label="ماهانه">{fa(a.monthly_depreciation)}</td>
              <td data-label="انباشته">{fa(a.accumulated_depreciation)}</td>
              <td data-label="ارزش دفتری">{fa(a.book_value)}</td>
              <td data-label="محلِ استقرار">{[a.custodian_name, a.location].filter(Boolean).join(' · ') || '—'}</td>
              <td data-label="وضعیت">
                <span className={`status-badge ${a.is_disposed ? 'tone-danger' : a.fully_depreciated ? 'tone-warning' : 'tone-success'}`}>
                  {a.is_disposed ? 'واگذارشده' : a.fully_depreciated ? 'مستهلک کامل' : 'فعال'}
                </span>
              </td>
              <td className="card-actions" data-label="عملیات">
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
                  <td className="card-title" data-label="دارایی">{e.asset_name}</td>
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
