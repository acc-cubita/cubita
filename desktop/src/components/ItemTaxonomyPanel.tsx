import { useCallback, useEffect, useState } from 'react'
import { Tags, SlidersHorizontal, Plus, Save, Pencil, X, RefreshCw, Trash2, AlertTriangle } from 'lucide-react'
import {
  createItemAttribute,
  createItemGroup,
  deleteItemAttribute,
  deleteItemGroup,
  fetchItemAttributes,
  fetchItemGroups,
  updateItemAttribute,
  updateItemGroup,
  type ItemAttributeRecord,
  type ItemGroupRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'

const faMoney = (n: number) => n.toLocaleString('fa-IR')

/**
 * گروه‌بندیِ کالا و تعریفِ مشخصات — دو داده‌ی پایه‌ی کنارِ هم.
 *
 * **گروه یک رکورد است، نه یک متن.** تا امروز دسته‌ی کالا یک رشته‌ی آزاد بود، پس
 * «لوازم خانگی» و «لوازم‌خانگی» دو گروهِ متفاوت می‌شدند و گزارشِ گروهی قابلِ
 * اعتماد نبود. تغییرِ نامِ گروه حالا روی همه‌ی کالاهایش دیده می‌شود.
 *
 * **مشخصه‌ها ستونِ ثابتِ کالا نیستند.** اگر امروز «رنگ» لازم است و فردا «توان
 * موتور»، نباید برای هرکدام ستونِ تازه‌ای روی جدولِ کالا بنشیند: مشخصه یک‌بار
 * تعریف می‌شود و هر کالا مقدارِ خودش را می‌گیرد.
 */
export function ItemTaxonomyPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [groups, setGroups] = useState<ItemGroupRecord[] | null>(null)
  const [attributes, setAttributes] = useState<ItemAttributeRecord[] | null>(null)
  const groupPg = usePagination(groups ?? [], 10)
  const [error, setError] = useState<string | null>(null)
  const [groupDraft, setGroupDraft] = useState({ code: '', name: '', name2: '' })
  const [attrDraft, setAttrDraft] = useState({ name: '', name2: '' })
  const [editGroupId, setEditGroupId] = useState<string | null>(null)
  const [editGroup, setEditGroup] = useState({ code: '', name: '', name2: '' })

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [g, a] = await Promise.all([fetchItemGroups(token), fetchItemAttributes(token)])
      setGroups(g)
      setAttributes(a)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={Tags}
        title="گروه‌بندی کالا"
        description={groups ? `${faMoney(groups.length)} گروه` : ''}
        actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
      >
        {error && <div className="error"><AlertTriangle size={13} /> {error}</div>}
        <form
          className="invoice-form form-full"
          onSubmit={(e) => {
            e.preventDefault()
            if (!groupDraft.name.trim()) return
            void run(async () => {
              await createItemGroup(token, {
                code: groupDraft.code.trim(),
                name: groupDraft.name.trim(),
                name2: groupDraft.name2.trim(),
              })
              setGroupDraft({ code: '', name: '', name2: '' })
            })
          }}
        >
          <div className="field-row">
            <label>کد<input value={groupDraft.code} onChange={(e) => setGroupDraft({ ...groupDraft, code: e.target.value })} placeholder="اختیاری" /></label>
            <label>نام گروه<input value={groupDraft.name} onChange={(e) => setGroupDraft({ ...groupDraft, name: e.target.value })} placeholder="مثلاً لوازم خانگی" /></label>
            <label>عنوان دوم<input value={groupDraft.name2} onChange={(e) => setGroupDraft({ ...groupDraft, name2: e.target.value })} /></label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Plus size={13} /> افزودن گروه</button>
          </div>
        </form>

        {groups == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : groups.length === 0 ? (
          <EmptyState icon={Tags} text="هنوز گروهی تعریف نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>گروه</th>
                    <th>کالاها</th>
                    <th>وضعیت</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {groupPg.pageItems.map((g) => (
                    <tr key={g.id}>
                      <td className="card-title" data-label="گروه">
                        <div className="entity-name">{g.name}</div>
                        {(g.code || g.name2) && (
                          <div className="entity-sub">{[g.code, g.name2].filter(Boolean).join(' · ')}</div>
                        )}
                      </td>
                      <td data-label="کالاها">{g.item_count ? faMoney(g.item_count) : '—'}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${g.is_active ? 'tone-success' : 'tone-warning'}`}>
                          {g.is_active ? 'باز' : 'بسته'}
                        </span>
                      </td>
                      <td className="check-actions card-actions">
                        <button
                          type="button"
                          onClick={() => { setEditGroupId(g.id); setEditGroup({ code: g.code, name: g.name, name2: g.name2 }) }}
                        >
                          <Pencil size={13} /> ویرایش
                        </button>
                        <button type="button" onClick={() => void run(() => updateItemGroup(token, g.id, { is_active: !g.is_active }))}>
                          {g.is_active ? 'بستن' : 'بازکردن'}
                        </button>
                        {g.item_count === 0 && (
                          <button
                            type="button"
                            className="icon-btn-danger"
                            onClick={() => { if (window.confirm(`گروهِ «${g.name}» حذف شود؟`)) void run(() => deleteItemGroup(token, g.id)) }}
                            aria-label="حذف گروه"
                          >
                            <Trash2 size={13} /> حذف
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={groupPg.page} pageCount={groupPg.pageCount} onChange={groupPg.setPage} />
          </div>
        )}

        {editGroupId && (
          <form
            className="invoice-form form-full"
            onSubmit={(e) => {
              e.preventDefault()
              void run(async () => {
                await updateItemGroup(token, editGroupId, {
                  code: editGroup.code.trim(),
                  name: editGroup.name.trim(),
                  name2: editGroup.name2.trim(),
                })
                setEditGroupId(null)
              })
            }}
          >
            <h4>ویرایشِ گروه</h4>
            <div className="field-row">
              <label>کد<input value={editGroup.code} onChange={(e) => setEditGroup({ ...editGroup, code: e.target.value })} /></label>
              <label>نام گروه<input value={editGroup.name} onChange={(e) => setEditGroup({ ...editGroup, name: e.target.value })} /></label>
              <label>عنوان دوم<input value={editGroup.name2} onChange={(e) => setEditGroup({ ...editGroup, name2: e.target.value })} /></label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={13} /> ذخیره</button>
              <button type="button" onClick={() => setEditGroupId(null)}><X size={13} /> انصراف</button>
            </div>
            <p className="hint">تغییرِ نامِ گروه روی همه‌ی کالاهای همان گروه هم دیده می‌شود.</p>
          </form>
        )}
      </SectionCard>

      <SectionCard
        icon={SlidersHorizontal}
        title="مشخصات کالا"
        description="یک‌بار تعریف، روی هر کالا یک مقدار — مثلِ رنگ، سایز، جنس یا کشور سازنده."
      >
        <form
          className="invoice-form form-full"
          onSubmit={(e) => {
            e.preventDefault()
            if (!attrDraft.name.trim()) return
            void run(async () => {
              await createItemAttribute(token, { name: attrDraft.name.trim(), name2: attrDraft.name2.trim() })
              setAttrDraft({ name: '', name2: '' })
            })
          }}
        >
          <div className="field-row">
            <label>نام مشخصه<input value={attrDraft.name} onChange={(e) => setAttrDraft({ ...attrDraft, name: e.target.value })} placeholder="مثلاً رنگ" /></label>
            <label>عنوان دوم<input value={attrDraft.name2} onChange={(e) => setAttrDraft({ ...attrDraft, name2: e.target.value })} /></label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Plus size={13} /> افزودن مشخصه</button>
          </div>
          <p className="hint">
            مشخصه‌ها ستونِ ثابتِ کالا نیستند: اگر فردا «توان موتور» لازم شد، همین‌جا اضافه
            می‌شود بی‌آنکه ساختارِ کالا عوض شود.
          </p>
        </form>

        {attributes == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : attributes.length === 0 ? (
          <EmptyState icon={SlidersHorizontal} text="هنوز مشخصه‌ای تعریف نشده." />
        ) : (
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>مشخصه</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {attributes.map((a) => (
                  <tr key={a.id}>
                    <td className="card-title" data-label="مشخصه">
                      <div className="entity-name">{a.name}</div>
                      {a.name2 ? <div className="entity-sub">{a.name2}</div> : null}
                    </td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${a.is_active ? 'tone-success' : 'tone-warning'}`}>
                        {a.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td className="check-actions card-actions">
                      <button type="button" onClick={() => void run(() => updateItemAttribute(token, a.id, { is_active: !a.is_active }))}>
                        {a.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                      </button>
                      <button
                        type="button"
                        className="icon-btn-danger"
                        onClick={() => {
                          if (window.confirm(`مشخصه‌ی «${a.name}» و مقدارش روی همه‌ی کالاها حذف شود؟`)) {
                            void run(() => deleteItemAttribute(token, a.id))
                          }
                        }}
                        aria-label="حذف مشخصه"
                      >
                        <Trash2 size={13} /> حذف
                      </button>
                    </td>
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
