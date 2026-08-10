import { useCallback, useEffect, useMemo, useState } from 'react'
import { PackageSearch, Package, RefreshCw, Warehouse, ClipboardList, ClipboardCheck, ArrowLeftRight, Boxes, PackageX, Tags, CalendarClock, Coins, History, AlertTriangle } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { StockAdjustmentForm } from '../components/StockAdjustmentForm'
import { StockCountPanel } from '../components/StockCountPanel'
import { PriceListsPanel } from '../components/PriceListsPanel'
import { BatchesPanel } from '../components/BatchesPanel'
import { TransferForm } from '../components/TransferForm'
import { ProductsPanel } from '../components/ProductsPanel'
import { LowStockPanel } from '../components/LowStockPanel'
import { WarehousesPanel } from '../components/WarehousesPanel'
import { KardexDrawer } from '../components/KardexDrawer'
import { KardexPanel } from '../components/KardexPanel'
import { fetchStockLevels, fetchLowStock, type StockLevel, type LowStockRow } from '../api'
import { SectionCard } from '../components/SectionCard'
import { Pager, usePagination } from '../components/Pager'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

const faMoney = (n: number) => n.toLocaleString('fa-IR')
const faQty = (s: string) => (Number(s) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

type KardexTarget = { id: string; name: string; sku: string }

export function InventoryPage({
  token,
  warehouses,
  items,
  onChanged,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  /** بعد از ثبت/ویرایشِ کالا صدا زده می‌شود تا کشِ سراسریِ کالاها هم تازه شود. */
  onChanged?: () => void
}) {
  const [stock, setStock] = useState<StockLevel[]>([])
  const stockPg = usePagination(stock, 10)
  const [lowStock, setLowStock] = useState<LowStockRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [kardex, setKardex] = useState<KardexTarget | null>(null)

  const refreshStock = useCallback(async () => {
    setError(null)
    try {
      const [levels, low] = await Promise.all([fetchStockLevels(token), fetchLowStock(token)])
      setStock(levels)
      setLowStock(low)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => {
    void refreshStock()
  }, [refreshStock])

  // شاخص‌های بالای صفحه — از همان داده‌ی موجود (موجودی + کالاها) محاسبه می‌شوند
  const kpis = useMemo(() => {
    const totalByItem = new Map<string, number>()
    for (const s of stock) totalByItem.set(s.item_id, (totalByItem.get(s.item_id) ?? 0) + Number(s.qty))
    const totalUnits = stock.reduce((sum, s) => sum + Number(s.qty), 0)
    const totalValue = stock.reduce((sum, s) => sum + Number(s.stock_value), 0)
    const outOfStock = items.filter((i) => (totalByItem.get(i.id) ?? 0) <= 0).length
    return { itemCount: items.length, warehouseCount: warehouses.length, totalUnits, totalValue, outOfStock, lowCount: lowStock.length }
  }, [stock, items, warehouses, lowStock])

  // شناسه‌ی کالاهایی که هشدارِ کسری دارند — برای نشانِ «سفارش» در جدولِ موجودی
  const lowIds = useMemo(() => new Set(lowStock.map((r) => r.item_id)), [lowStock])

  return (
    <div className="page">
      <PageHeader
        icon={Warehouse}
        title="انبار"
        description="موجودی زنده‌ی هر کالا در هر انبار را ببینید و در صورت اختلاف با شمارش فیزیکی، با «انبارگردانی» تعدیل کنید."
      />

      <div className="stat-grid">
        <StatCard icon={<Package size={18} />} label="کل کالاها" value={faMoney(kpis.itemCount)} />
        <StatCard icon={<Coins size={18} />} label="ارزشِ موجودی" value={faMoney(Math.round(kpis.totalValue))} hint="ریال، به بهای میانگین" />
        <StatCard icon={<Boxes size={18} />} label="مجموع موجودی" value={faMoney(kpis.totalUnits)} hint="تعداد کل واحد" />
        <StatCard
          icon={<AlertTriangle size={18} />}
          label="نیازمندِ سفارش"
          value={faMoney(kpis.lowCount)}
          tone={kpis.lowCount > 0 ? 'warning' : 'default'}
        />
        <StatCard
          icon={<PackageX size={18} />}
          label="اقلام ناموجود"
          value={faMoney(kpis.outOfStock)}
          tone={kpis.outOfStock > 0 ? 'danger' : 'default'}
        />
      </div>

      <Tabs
        syncPage="inventory"
        tabs={[
          {
            key: 'products',
            label: 'کالاها',
            icon: Package,
            content: <ProductsPanel token={token} onChanged={onChanged} />,
          },
          {
            key: 'stock',
            label: 'موجودی',
            icon: PackageSearch,
            content: (
              <div className="split-2col">
                <SectionCard
                  icon={PackageSearch}
                  title="موجودی فعلی (زنده از سرور)"
                  description="عدد لحظه‌ای موجودی، مستقیم از سرور خوانده می‌شود."
                  actions={
                    <button onClick={() => void refreshStock()}>
                      <RefreshCw size={13} /> به‌روزرسانی
                    </button>
                  }
                >
                  {error && <div className="error">{error}</div>}
                  {stock.length === 0 ? (
                    <EmptyState icon={PackageSearch} text="موجودی ثبت‌شده‌ای نیست." />
                  ) : (
                    <div className="entity-table-wrap">
                      <table className="entity-table inv-stock-table">
                        <thead>
                          <tr>
                            <th>کالا</th>
                            <th>انبار</th>
                            <th>موجودی</th>
                            <th>بهای واحد</th>
                            <th>ارزش</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {stockPg.pageItems.map((s) => (
                            <tr key={`${s.item_id}-${s.warehouse_id}`}>
                              <td data-label="کالا" className="entity-name">
                                <span>{s.item_name}</span>
                                <div className="entity-sub ltr-cell">{s.item_sku}</div>
                                {lowIds.has(s.item_id) && <span className="status-badge tone-warning inv-low-badge">نیازمندِ سفارش</span>}
                              </td>
                              <td data-label="انبار">{s.warehouse_name}</td>
                              <td data-label="موجودی" className="money-cell">
                                {Number(s.qty) <= 0 ? (
                                  <span className="status-badge tone-danger">{faQty(s.qty)}</span>
                                ) : (
                                  faQty(s.qty)
                                )}
                              </td>
                              <td data-label="بهای واحد" className="money-cell">{faMoney(Number(s.unit_cost))}</td>
                              <td data-label="ارزش" className="money-cell"><strong>{faMoney(Math.round(Number(s.stock_value)))}</strong></td>
                              <td className="lowstock-action">
                                <button type="button" onClick={() => setKardex({ id: s.item_id, name: s.item_name, sku: s.item_sku })}>
                                  <History size={13} /> کاردکس
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <Pager page={stockPg.page} pageCount={stockPg.pageCount} onChange={stockPg.setPage} />
                    </div>
                  )}
                </SectionCard>

                <SectionCard
                  icon={Package}
                  title={isElectron ? 'کالاها (کش محلی)' : 'کالاها'}
                  description={
                    isElectron ? 'کپی محلی از فهرست کالاها؛ همیشه در دسترس است، حتی بدون اینترنت.' : 'فهرست کالاهای ثبت‌شده.'
                  }
                >
                  {items.length === 0 ? (
                    <EmptyState
                      icon={Package}
                      text={isElectron ? 'برای دریافت لیست کالاها، دکمه‌ی «هم‌گام‌سازی» را بزنید.' : 'کالایی ثبت نشده.'}
                    />
                  ) : (
                    <div className="entity-table-wrap">
                      <table className="entity-table">
                        <thead>
                          <tr>
                            <th>کالا</th>
                            <th>واحد</th>
                            <th>قیمت فروش</th>
                          </tr>
                        </thead>
                        <tbody>
                          {items.map((i) => (
                            <tr key={i.id}>
                              <td>
                                <div className="entity-cell">
                                  <div className="entity-avatar">{i.name.trim().charAt(0) || '؟'}</div>
                                  <div>
                                    <div className="entity-name">{i.name}</div>
                                    <div className="entity-sub ltr-cell">{i.sku}</div>
                                  </div>
                                </div>
                              </td>
                              <td>{i.unit}</td>
                              <td className="money-cell">{faMoney(Number(i.sales_price))}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </SectionCard>
              </div>
            ),
          },
          {
            key: 'kardex',
            label: 'کاردکس',
            icon: History,
            content: <KardexPanel token={token} items={items} />,
          },
          {
            key: 'low',
            label: 'نیازمندِ سفارش',
            icon: AlertTriangle,
            content: <LowStockPanel token={token} onKardex={setKardex} />,
          },
          {
            key: 'warehouses',
            label: 'انبارها',
            icon: Warehouse,
            content: <WarehousesPanel token={token} onChanged={() => void refreshStock()} />,
          },
          {
            key: 'count',
            label: 'انبارگردانی',
            icon: ClipboardCheck,
            content: <StockCountPanel token={token} warehouses={warehouses} />,
          },
          {
            key: 'adjust',
            label: 'تعدیل دستی',
            icon: ClipboardList,
            content: (
              <StockAdjustmentForm token={token} warehouses={warehouses} items={items} onAdjusted={() => void refreshStock()} />
            ),
          },
          {
            key: 'transfer',
            label: 'انتقال بین انبار',
            icon: ArrowLeftRight,
            content: <TransferForm token={token} warehouses={warehouses} items={items} />,
          },
          {
            key: 'pricelists',
            label: 'لیست قیمت',
            icon: Tags,
            content: <PriceListsPanel token={token} />,
          },
          {
            key: 'batches',
            label: 'بچ و انقضا',
            icon: CalendarClock,
            content: <BatchesPanel token={token} />,
          },
        ]}
      />

      {kardex && <KardexDrawer token={token} item={kardex} onClose={() => setKardex(null)} />}
    </div>
  )
}
