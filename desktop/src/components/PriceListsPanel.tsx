import { useEffect, useMemo, useState } from 'react'
import { Tags, Plus, Save, Trash2 } from 'lucide-react'
import {
  createPriceList,
  deletePriceList,
  fetchItemsLive,
  fetchPriceListItems,
  fetchPriceLists,
  setPriceListItems,
  updatePriceList,
  type ItemRecord,
  type PriceListRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'

const fa = (n: number) => n.toLocaleString('fa-IR')

export function PriceListsPanel({ token }: { token: string }) {
  const [lists, setLists] = useState<PriceListRecord[]>([])
  const [items, setItems] = useState<ItemRecord[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [prices, setPrices] = useState<Record<string, string>>({})
  const [newName, setNewName] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const listsPg = usePagination(lists, 10)
  const itemsPg = usePagination(items, 10, selectedId)

  async function refresh() {
    setError(null)
    try {
      const [ls, its] = await Promise.all([fetchPriceLists(token), fetchItemsLive(token)])
      setLists(ls)
      setItems(its.filter((i) => i.is_active))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  // با انتخابِ لیست، قیمت‌های ثبت‌شده‌اش را بار می‌زنیم
  useEffect(() => {
    if (!selectedId) {
      setPrices({})
      return
    }
    fetchPriceListItems(token, selectedId)
      .then((rows) => setPrices(Object.fromEntries(rows.map((r) => [r.item_id, String(Number(r.price) || '')]))))
      .catch(() => setPrices({}))
  }, [token, selectedId])

  const selected = useMemo(() => lists.find((l) => l.id === selectedId), [lists, selectedId])

  async function addList(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!newName.trim()) return
    try {
      const pl = await createPriceList(token, { name: newName.trim() })
      setNewName('')
      await refresh()
      setSelectedId(pl.id)
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function savePrices() {
    if (!selectedId) return
    setMsg(null)
    const payload = Object.entries(prices)
      .filter(([, v]) => Number(v) > 0)
      .map(([item_id, v]) => ({ item_id, price: Number(v) }))
    try {
      await setPriceListItems(token, selectedId, payload)
      setMsg('قیمت‌های لیست ذخیره شد.')
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function removeList(id: string) {
    if (!window.confirm('این لیستِ قیمت حذف شود؟')) return
    await deletePriceList(token, id)
    if (selectedId === id) setSelectedId('')
    await refresh()
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={Tags} title="لیست‌های قیمت" description="لیست‌های قیمتِ مختلف (عمده، خرده، ویژه) بسازید.">
        <form className="invoice-form form-full" onSubmit={addList}>
          <label>
            نامِ لیستِ جدید
            <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="مثلاً قیمت عمده" />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Plus size={14} /> ساختِ لیست</button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
        {lists.length === 0 ? (
          <EmptyState icon={Tags} text="لیستی ساخته نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr><th>لیست</th><th>وضعیت</th><th></th></tr>
              </thead>
              <tbody>
                {listsPg.pageItems.map((l) => (
                  <tr key={l.id} className={l.id === selectedId ? 'row-selected' : ''}>
                    <td className="card-title">
                      <button type="button" className="link-like" onClick={() => setSelectedId(l.id)}>
                        <strong className="entity-name">{l.name}</strong>
                      </button>
                    </td>
                    <td data-label="وضعیت">
                      <button type="button" onClick={() => void updatePriceList(token, l.id, { is_active: !l.is_active }).then(refresh)}>
                        <span className={`status-badge ${l.is_active ? 'tone-success' : 'tone-warning'}`}>{l.is_active ? 'فعال' : 'غیرفعال'}</span>
                      </button>
                    </td>
                    <td className="card-actions">
                      <button type="button" className="icon-btn-danger" onClick={() => void removeList(l.id)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={listsPg.page} pageCount={listsPg.pageCount} onChange={listsPg.setPage} />
          </div>
        )}
      </SectionCard>

      <SectionCard
        icon={Tags}
        title={selected ? `قیمت‌های «${selected.name}»` : 'قیمتِ کالاها'}
        description={selected ? 'قیمتِ هر کالا در این لیست (خالی = بدونِ قیمتِ ویژه، از قیمتِ پایه استفاده می‌شود).' : 'یک لیست را از سمتِ راست انتخاب کنید.'}
        actions={selected ? <button className="btn-primary" onClick={() => void savePrices()}><Save size={13} /> ذخیره</button> : undefined}
      >
        {!selected ? (
          <EmptyState icon={Tags} text="لیستی انتخاب نشده." />
        ) : items.length === 0 ? (
          <EmptyState icon={Tags} text="کالایی برای قیمت‌گذاری نیست." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr><th>کالا</th><th>قیمتِ پایه</th><th>قیمتِ این لیست</th></tr>
              </thead>
              <tbody>
                {itemsPg.pageItems.map((it) => (
                  <tr key={it.id}>
                    <td className="entity-name card-title">{it.name}</td>
                    <td className="money-cell" data-label="قیمتِ پایه">{fa(Number(it.sales_price))}</td>
                    <td data-label="قیمتِ این لیست">
                      <NumberInput
                        value={prices[it.id] ?? ''}
                        onChange={(v) => setPrices((p) => ({ ...p, [it.id]: v }))}
                        placeholder="—"
                        style={{ width: 130 }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={itemsPg.page} pageCount={itemsPg.pageCount} onChange={itemsPg.setPage} />
          </div>
        )}
        {msg && <div className="hint">{msg}</div>}
      </SectionCard>
    </div>
  )
}
