import { useEffect, useMemo, useState } from 'react'
import { PackageSearch, Package, RefreshCw, Warehouse, ClipboardList, ClipboardCheck, ArrowLeftRight, Boxes, PackageX } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { StockAdjustmentForm } from '../components/StockAdjustmentForm'
import { StockCountPanel } from '../components/StockCountPanel'
import { TransferForm } from '../components/TransferForm'
import { fetchStockLevels, type StockLevel } from '../api'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

const faMoney = (n: number) => n.toLocaleString('fa-IR')

export function InventoryPage({
  token,
  warehouses,
  items,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
}) {
  const [stock, setStock] = useState<StockLevel[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refreshStock() {
    setError(null)
    try {
      setStock(await fetchStockLevels(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refreshStock()
  }, [])

  // شاخص‌های بالای صفحه — از همان داده‌ی موجود (موجودی + کالاها) محاسبه می‌شوند
  const kpis = useMemo(() => {
    const totalByItem = new Map<string, number>()
    for (const s of stock) totalByItem.set(s.item_id, (totalByItem.get(s.item_id) ?? 0) + Number(s.qty))
    const totalUnits = stock.reduce((sum, s) => sum + Number(s.qty), 0)
    const outOfStock = items.filter((i) => (totalByItem.get(i.id) ?? 0) <= 0).length
    return { itemCount: items.length, warehouseCount: warehouses.length, totalUnits, outOfStock }
  }, [stock, items, warehouses])

  return (
    <div className="page">
      <PageHeader
        icon={Warehouse}
        title="انبار"
        description="موجودی زنده‌ی هر کالا در هر انبار را ببینید و در صورت اختلاف با شمارش فیزیکی، با «انبارگردانی» تعدیل کنید."
      />

      <div className="stat-grid">
        <StatCard icon={<Package size={18} />} label="کل کالاها" value={faMoney(kpis.itemCount)} />
        <StatCard icon={<Warehouse size={18} />} label="انبارها" value={faMoney(kpis.warehouseCount)} />
        <StatCard icon={<Boxes size={18} />} label="مجموع موجودی" value={faMoney(kpis.totalUnits)} hint="تعداد کل واحد" />
        <StatCard
          icon={<PackageX size={18} />}
          label="اقلام ناموجود"
          value={faMoney(kpis.outOfStock)}
          tone={kpis.outOfStock > 0 ? 'warning' : 'default'}
        />
      </div>

      <Tabs
        tabs={[
          {
            key: 'stock',
            label: 'موجودی و کالاها',
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
                      <table className="entity-table">
                        <thead>
                          <tr>
                            <th>کد کالا</th>
                            <th>نام</th>
                            <th>انبار</th>
                            <th>موجودی</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stock.map((s) => (
                            <tr key={`${s.item_id}-${s.warehouse_id}`}>
                              <td className="ltr-cell">{s.item_sku}</td>
                              <td className="entity-name">{s.item_name}</td>
                              <td>{s.warehouse_name}</td>
                              <td className="money-cell">
                                {Number(s.qty) <= 0 ? (
                                  <span className="status-badge tone-warning">{faMoney(Number(s.qty))}</span>
                                ) : (
                                  faMoney(Number(s.qty))
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
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
        ]}
      />
    </div>
  )
}
