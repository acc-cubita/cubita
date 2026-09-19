import { useCallback, useEffect, useMemo, useState } from 'react'
import { Warehouse, Plus, Save, Pencil, X, RefreshCw, AlertTriangle } from 'lucide-react'
import {
  fetchAccountsLive,
  fetchWarehouseStock,
  fetchWarehousesAdmin,
  createWarehouse,
  updateWarehouse,
  type WarehouseInput,
  type WarehouseRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { SearchSelect } from '../components/SearchSelect'

/**
 * مدیریتِ انبارها — مشخصات، معینِ حسابداری، و فعال/غیرفعال‌سازی.
 *
 * **انبار حساب نیست و موجودی هم ندارد.** این فرم عمداً هیچ فیلدِ موجودی ندارد:
 * مانده همیشه از حرکاتِ انبار می‌آید و «درست‌کردنِ موجودی با ویرایشِ انبار»
 * نباید ممکن باشد. «معینِ انبار» هم فقط یک *نگاشت* به حسابی است که از قبل در
 * چارت هست — این‌جا حسابِ تازه‌ای ساخته نمی‌شود.
 *
 * کد پس از ساخت ثابت می‌ماند (روی حرکاتِ انبار نشسته)؛ بقیه‌ی مشخصات قابلِ
 * ویرایش‌اند و تغییرشان هیچ حرکتِ انباری را عوض نمی‌کند.
 */
export function WarehousesPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [rows, setRows] = useState<WarehouseRecord[] | null>(null)
  const pg = usePagination(rows ?? [], 10)
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [draft, setDraft] = useState<WarehouseInput>({ code: '', name: '' })
  const [saving, setSaving] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [edit, setEdit] = useState<WarehouseInput>({ code: '', name: '' })

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setRows(await fetchWarehousesAdmin(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    //: فقط حساب‌های برگی می‌توانند معینِ انبار باشند — حسابِ گروه ردیفِ سند
    //: نمی‌پذیرد و سرور هم ردش می‌کند؛ نیاوردنش در فهرست یعنی کاربر اصلاً به
    //: آن خطا نمی‌خورد.
    void (async () => {
      try {
        setAccounts((await fetchAccountsLive(token)).filter((a) => !a.is_group))
      } catch {
        setAccounts([])
      }
    })()
  }, [token])

  const accountOptions = useMemo(
    () => accounts.map((a) => ({ id: a.id, label: `${a.code} — ${a.name}` })),
    [accounts],
  )

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!draft.code.trim() || !draft.name.trim()) { setMessage('کد و عنوان انبار الزامی است.'); return }
    setSaving(true)
    try {
      await createWarehouse(token, { ...draft, code: draft.code.trim(), name: draft.name.trim() })
      setDraft({ code: '', name: '' })
      setMessage('انبار ساخته شد.')
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  function startEdit(w: WarehouseRecord) {
    setEditId(w.id)
    setEdit({
      code: w.code,
      name: w.name,
      name2: w.name2,
      responsible: w.responsible,
      phone: w.phone,
      address: w.address,
      address2: w.address2,
      gl_account_id: w.gl_account_id,
    })
  }

  async function saveEdit() {
    if (!editId || !edit.name.trim()) return
    setError(null)
    try {
      const { code: _code, ...patch } = edit
      await updateWarehouse(token, editId, { ...patch, name: edit.name.trim() })
      setEditId(null)
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  /**
   * غیرفعال‌سازی — **قبل** از تلاش، موجودی پرسیده می‌شود.
   *
   * سرور انبارِ دارای موجودی را رد می‌کند؛ ولی دیدنِ «۲۳ قلم کالا» پیش از فشردنِ
   * دکمه بهتر از خوردنِ خطا بعدش است. کالا در انبارِ غیرفعال گیر می‌افتد: نه
   * خارج می‌شود نه وارد.
   */
  async function toggleActive(w: WarehouseRecord) {
    setError(null)
    try {
      if (w.is_active) {
        const stock = await fetchWarehouseStock(token, w.id)
        if (stock.item_count > 0) {
          const names = stock.items.slice(0, 3).map((i) => i.item_name).join('، ')
          setError(
            `انبار «${w.name}» هنوز ${stock.item_count.toLocaleString('fa-IR')} قلم کالا با موجودیِ غیرصفر دارد` +
              `${names ? ` (${names}${stock.items.length > 3 ? ' و…' : ''})` : ''}. ` +
              'اول کالاها را به انبارِ دیگری منتقل کنید یا از انبار خارجشان کنید.',
          )
          return
        }
      }
      await updateWarehouse(token, w.id, { is_active: !w.is_active })
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const fields = (value: WarehouseInput, set: (next: WarehouseInput) => void, withCode: boolean) => (
    <>
      <div className="field-row">
        {withCode && (
          <label>کد انبار<input value={value.code} onChange={(e) => set({ ...value, code: e.target.value })} placeholder="مثلاً ۲" /></label>
        )}
        <label>عنوان<input value={value.name} onChange={(e) => set({ ...value, name: e.target.value })} placeholder="مثلاً انبار مواد اولیه" /></label>
        <label>عنوان دوم<input value={value.name2 ?? ''} onChange={(e) => set({ ...value, name2: e.target.value })} /></label>
      </div>
      <div className="field-row">
        <label>مسئول<input value={value.responsible ?? ''} onChange={(e) => set({ ...value, responsible: e.target.value })} /></label>
        <label>تلفن<input value={value.phone ?? ''} onChange={(e) => set({ ...value, phone: e.target.value })} dir="ltr" /></label>
      </div>
      <div className="field-row">
        <label>آدرس<input value={value.address ?? ''} onChange={(e) => set({ ...value, address: e.target.value })} /></label>
        <label>آدرس دوم<input value={value.address2 ?? ''} onChange={(e) => set({ ...value, address2: e.target.value })} /></label>
      </div>
      <div className="field-row">
        <label>
          معین انبار
          <SearchSelect
            value={value.gl_account_id ?? ''}
            onChange={(e) => set({ ...value, gl_account_id: e.target.value || null })}
          >
            <option value="">— حساب پیش‌فرضِ موجودی کالا —</option>
            {accountOptions.map((a) => (
              <option key={a.id} value={a.id}>{a.label}</option>
            ))}
          </SearchSelect>
        </label>
      </div>
    </>
  )

  return (
    <div className="workspace-split">
      <SectionCard icon={Plus} title="انبارِ جدید" description="انبار فقط ظرفِ نگهداری است؛ ساختنش هیچ موجودی و سندی نمی‌سازد.">
        <form className="invoice-form form-full" onSubmit={handleCreate}>
          {fields(draft, setDraft, true)}
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> ثبت انبار</button>
          </div>
          {message && <div className="hint">{message}</div>}
          <p className="hint">
            کد پس از ساخت ثابت می‌ماند (روی حرکاتِ انبار نشسته). «معین انبار» اختیاری است — خالی
            یعنی همان حسابِ پیش‌فرضِ موجودی کالا، و انتخابش فقط روی ثبت‌های آینده اثر دارد.
          </p>
        </form>
      </SectionCard>

      <SectionCard
        icon={Warehouse}
        title="انبارها"
        description={rows ? `${rows.length.toLocaleString('fa-IR')} انبار` : ''}
        actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
      >
        {error && <div className="error"><AlertTriangle size={13} /> {error}</div>}
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Warehouse} text="هنوز انباری ساخته نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table wh-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>عنوان</th>
                    <th>مسئول</th>
                    <th>تلفن</th>
                    <th>معین انبار</th>
                    <th>وضعیت</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((w) => (
                    <tr key={w.id}>
                      <td data-label="کد" className="ltr-cell">{w.code}</td>
                      <td data-label="عنوان" className="entity-name">
                        {w.name}
                        {w.name2 ? <div className="entity-sub">{w.name2}</div> : null}
                      </td>
                      <td data-label="مسئول">{w.responsible || '—'}</td>
                      <td data-label="تلفن" className="ltr-cell">{w.phone || '—'}</td>
                      <td data-label="معین انبار">
                        {w.gl_account_code} — {w.gl_account_name}
                        {w.gl_account_is_default ? <div className="entity-sub">پیش‌فرض</div> : null}
                      </td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${w.is_active ? 'tone-success' : 'tone-warning'}`}>
                          {w.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td className="check-actions card-actions">
                        <button type="button" onClick={() => startEdit(w)}><Pencil size={13} /> ویرایش</button>
                        <button type="button" onClick={() => void toggleActive(w)}>
                          {w.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}

        {editId && (
          <form className="invoice-form form-full" onSubmit={(e) => { e.preventDefault(); void saveEdit() }}>
            <h4>ویرایشِ انبار {edit.code}</h4>
            {fields(edit, setEdit, false)}
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={13} /> ذخیره</button>
              <button type="button" onClick={() => setEditId(null)}><X size={13} /> انصراف</button>
            </div>
            <p className="hint">
              تغییرِ عنوان، مسئول و آدرس هیچ حرکتِ انباری را عوض نمی‌کند. تغییرِ معین هم سندهای
              گذشته را بازنویسی نمی‌کند — فقط ثبت‌های بعدی را می‌برد.
            </p>
          </form>
        )}
      </SectionCard>
    </div>
  )
}
