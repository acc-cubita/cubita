import { useEffect, useState } from 'react'
import { PackageSearch, Package, RefreshCw, Warehouse, ClipboardList, ClipboardCheck, ArrowLeftRight } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { StockAdjustmentForm } from '../components/StockAdjustmentForm'
import { StockCountPanel } from '../components/StockCountPanel'
import { TransferForm } from '../components/TransferForm'
import { fetchStockLevels, type StockLevel } from '../api'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

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

  return (
    <div className="page">
      <PageHeader
        icon={Warehouse}
        title="انبار"
        description="موجودی زنده‌ی هر کالا در هر انبار را ببینید و در صورت اختلاف با شمارش فیزیکی، با «انبارگردانی» تعدیل کنید."
      />
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
                    <table>
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
                            <td>{s.item_sku}</td>
                            <td>{s.item_name}</td>
                            <td>{s.warehouse_name}</td>
                            <td>{Number(s.qty).toLocaleString('fa-IR')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
                    <table>
                      <thead>
                        <tr>
                          <th>کد کالا</th>
                          <th>نام</th>
                          <th>واحد</th>
                          <th>قیمت فروش</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((i) => (
                          <tr key={i.id}>
                            <td>{i.sku}</td>
                            <td>{i.name}</td>
                            <td>{i.unit}</td>
                            <td>{Number(i.sales_price).toLocaleString('fa-IR')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
