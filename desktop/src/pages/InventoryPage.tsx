import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowLeftRight, BadgeDollarSign, Boxes, Calculator, CalendarClock, ClipboardCheck, ClipboardList, Coins, FileStack, FileUp, FolderTree, History, ListChecks, Package, PackageMinus, PackageSearch, PackageX, RefreshCw, RotateCcw, Ruler, ScanSearch, Tag, Tags, Warehouse } from 'lucide-react'
import { InventoryValuationPanel } from '../components/InventoryValuationPanel'
import { WarehouseIssuesTab } from '../components/WarehouseIssuesTab'
import { WarehouseReceiptsTab } from '../components/WarehouseReceiptsTab'
import { useNavSection } from '../components/navContext'
import { IssueReturnsTab } from '../components/IssueReturnsTab'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { StockAdjustmentForm } from '../components/StockAdjustmentForm'
import { StockAdjustmentWizard } from '../components/wizard/StockAdjustmentWizard'
import { TransferWizard } from '../components/wizard/TransferWizard'
import { useTheme } from '../lib/theme'
import { StockCountPanel } from '../components/StockCountPanel'
import { PriceListsPanel } from '../components/PriceListsPanel'
import { BatchesPanel } from '../components/BatchesPanel'
import { TransferForm } from '../components/TransferForm'
import { ProductsPanel } from '../components/ProductsPanel'
import { BulkImportPanel } from '../components/BulkImportPanel'
import { LowStockPanel, OverStockPanel } from '../components/LowStockPanel'
import { ItemTaxonomyPanel } from '../components/ItemTaxonomyPanel'
import { UnitsPanel } from '../components/UnitsPanel'
import { WarehousesPanel } from '../components/WarehousesPanel'
import { KardexDrawer } from '../components/KardexDrawer'
import { KardexPanel } from '../components/KardexPanel'
import {
  fetchStockLevels,
  fetchLowStock,
  type IssueInvoiceContext,
  type LowStockRow,
  type MeResponse,
  type ReceiptPaymentContext,
  type StockLevel,
} from '../api'
import { SectionCard } from '../components/SectionCard'
import { Pager, usePagination } from '../components/Pager'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { SerialSearchTab } from '../components/SerialSearchTab'
import { UnpricedOutputsTab } from '../components/UnpricedOutputsTab'
import { isElectron } from '../platform'

const faMoney = (n: number) => n.toLocaleString('fa-IR')
const faQty = (s: string) => (Number(s) || 0).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

type KardexTarget = { id: string; name: string; sku: string }

export function InventoryPage({
  token,
  me,
  warehouses,
  items,
  onChanged,
  onCreateInvoiceFromIssue,
  onCreateReceiptPayment,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  items: ItemCache[]
  /** بعد از ثبت/ویرایشِ کالا صدا زده می‌شود تا کشِ سراسریِ کالاها هم تازه شود. */
  onChanged?: () => void
  /** «صدور فاکتور فروش» از روی خروج — فقط زمینه را به فرمِ فاکتور می‌برد (§۱۶). */
  onCreateInvoiceFromIssue: (context: IssueInvoiceContext) => void
  /** میان‌برِ «اعلامیه پرداخت» از ردیفِ رسید — دفترِ رسیدها حالا این‌جا هم هست. */
  onCreateReceiptPayment: (context: ReceiptPaymentContext) => void
}) {
  const nav = useNavSection()
  //: جلسه‌ای که از «تگ انبارگردانی» یا «فهرست انبارگردانی‌ها» برای شمارش باز شده.
  const [countSession, setCountSession] = useState<string | null>(null)
  const openCountSession = (id: string) => {
    setCountSession(id)
    nav?.setSection('count')
  }
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
  const guided = useTheme().theme.content === 'guided'

  return (
    <div className="page panels">
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
            label: 'مرور انبار / موجودی کالا',
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
                      <div className="table-scroll">
                        <table className="entity-table inv-stock-table cards-on-mobile">
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
                                <td data-label="بهای واحد" className="money-cell">{faMoney(Math.round(Number(s.unit_cost)))}</td>
                                <td data-label="ارزش" className="money-cell"><strong>{faMoney(Math.round(Number(s.stock_value)))}</strong></td>
                                <td className="lowstock-action card-actions">
                                  <button type="button" onClick={() => setKardex({ id: s.item_id, name: s.item_name, sku: s.item_sku })}>
                                    <History size={13} /> کاردکس
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
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
                      <div className="table-scroll">
                        <table className="entity-table cards-on-mobile">
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
                                <td className="card-title" data-label="کالا">
                                  <div className="entity-cell">
                                    <div className="entity-avatar">{i.name.trim().charAt(0) || '؟'}</div>
                                    <div>
                                      <div className="entity-name">{i.name}</div>
                                      <div className="entity-sub ltr-cell">{i.sku}</div>
                                    </div>
                                  </div>
                                </td>
                                <td data-label="واحد">{i.unit}</td>
                                <td className="money-cell" data-label="قیمت فروش">{faMoney(Number(i.sales_price))}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </SectionCard>
              </div>
            ),
          },
          {
            key: 'kardex',
            label: 'کاردکس کالا',
            icon: History,
            content: <KardexPanel token={token} items={items} />,
          },
          {
            key: 'low',
            label: 'گزارش نقطه سفارش',
            icon: AlertTriangle,
            content: (
              <div className="split-2col">
                <LowStockPanel token={token} onKardex={setKardex} />
                <OverStockPanel token={token} onKardex={setKardex} />
              </div>
            ),
          },
          {
            key: 'warehouses',
            label: 'انبارها',
            icon: Warehouse,
            content: <WarehousesPanel token={token} onChanged={() => void refreshStock()} />,
          },
          {
            key: 'units',
            label: 'واحدها',
            icon: Ruler,
            content: <UnitsPanel token={token} onChanged={onChanged} />,
          },
          {
            key: 'taxonomy',
            label: 'گروه و مشخصات',
            icon: FolderTree,
            content: <ItemTaxonomyPanel token={token} onChanged={onChanged} />,
          },
          {
            key: 'count-tags',
            label: 'تگ انبارگردانی',
            icon: Tag,
            content: <StockCountPanel token={token} warehouses={warehouses} mode="tags" onOpenSession={openCountSession} />,
          },
          {
            //: کلید `count` ماند تا پیوندهای قبلی («انبارگردانی» از داشبوردِ شرکت) همین‌جا بیایند.
            key: 'count',
            label: 'ثبت مغایرت انبارگردانی',
            icon: ClipboardCheck,
            content: <StockCountPanel token={token} warehouses={warehouses} mode="variance" sessionId={countSession} />,
          },
          {
            key: 'adjust',
            label: 'تعدیل دستی',
            icon: ClipboardList,
            content: guided ? (
              <StockAdjustmentWizard token={token} warehouses={warehouses} items={items} onAdjusted={() => void refreshStock()} />
            ) : (
              <StockAdjustmentForm token={token} warehouses={warehouses} items={items} onAdjusted={() => void refreshStock()} />
            ),
          },
          {
            //: خروجِ فروش، مصرف و سایر — و فهرستی که انتقال‌ها را هم کنارشان دارد.
            key: 'issues',
            label: 'حواله انبار',
            icon: PackageMinus,
            content: (
              <WarehouseIssuesTab
                token={token}
                me={me}
                warehouses={warehouses}
                items={items}
                onChanged={() => void refreshStock()}
                onCreateInvoice={onCreateInvoiceFromIssue}
                view="form"
              />
            ),
          },
          {
            //: کالایی که با یک خروج رفته و برمی‌گردد — فرمِ «مبنا» و دفترِ برگشت‌ها.
            key: 'issue-returns',
            label: 'برگشت خروج انبار',
            icon: RotateCcw,
            content: (
              <IssueReturnsTab token={token} me={me} warehouses={warehouses} onChanged={() => void refreshStock()} view="form" />
            ),
          },
          {
            //: فقط فرم. انتقال‌های ثبت‌شده همان حواله‌های نوعِ «انتقال»اند و در «فهرست
            //: رسیدها و حواله‌های انبار» با فیلترِ نوع دیده می‌شوند — نه نمای دومی از حواله‌ها.
            key: 'transfer',
            label: 'رسید/حواله انتقال بین انبارها',
            icon: ArrowLeftRight,
            content: guided ? (
              <TransferWizard token={token} warehouses={warehouses} items={items} onCreated={() => void refreshStock()} />
            ) : (
              <TransferForm token={token} warehouses={warehouses} items={items} onCreated={() => void refreshStock()} />
            ),
          },
          {
            //: کالایی که وارد انبار شده ولی بهایش هنوز معلوم نیست — تا فی نخورَد
            //: ارزشش صفر است و بهای فروش‌رفته‌اش هم صفر درمی‌آید.
            key: 'unpriced',
            label: 'قیمت‌گذاری ورودی‌ها',
            icon: BadgeDollarSign,
            content: (
              <UnpricedOutputsTab
                token={token}
                warehouses={warehouses}
                onChanged={() => void refreshStock()}
              />
            ),
          },
          {
            //: اصلاحِ بهای حرکاتِ منقضی با یک سندِ اصلاحی — فصلِ «قیمت‌گذاری اسناد انبار».
            key: 'valuation',
            label: 'قیمت‌گذاری اسناد انبار',
            icon: Calculator,
            content: <InventoryValuationPanel token={token} warehouses={warehouses} items={items} />,
          },
          {
            key: 'pricelists',
            label: 'لیست قیمت',
            icon: Tags,
            content: <PriceListsPanel token={token} />,
          },
          {
            //: ردیابیِ میان‌سندیِ سریال — «کجاست و به چه کسی رفت؟»
            key: 'serials',
            label: 'جستجوی سریال',
            icon: ScanSearch,
            content: <SerialSearchTab token={token} />,
          },
          {
            key: 'batches',
            label: 'بچ و انقضا',
            icon: CalendarClock,
            content: <BatchesPanel token={token} />,
          },
          {
            key: 'import',
            label: 'ورود گروهی کالا',
            icon: FileUp,
            content: <BulkImportPanel token={token} kind="items" />,
          },
          {
            //: دفترِ مشترکِ رسیدها و حواله‌ها — همان دو دفتری که پیش‌تر زیرِ فرمِ «رسید انبار»
            //: (صفحه‌ی خرید) و «خروج انبار» بودند، حالا یک‌جا در «فهرست».
            key: 'documents',
            label: 'فهرست رسیدها و حواله‌های انبار',
            icon: FileStack,
            content: (
              <>
                <WarehouseReceiptsTab
                  token={token}
                  me={me}
                  warehouses={warehouses}
                  items={items}
                  onChanged={() => void refreshStock()}
                  onCreatePayment={onCreateReceiptPayment}
                  view="ledger"
                />
                <WarehouseIssuesTab
                  token={token}
                  me={me}
                  warehouses={warehouses}
                  items={items}
                  onChanged={() => void refreshStock()}
                  onCreateInvoice={onCreateInvoiceFromIssue}
                  view="ledger"
                />
              </>
            ),
          },
          {
            key: 'count-list',
            label: 'فهرست انبارگردانی‌ها',
            icon: ListChecks,
            content: <StockCountPanel token={token} warehouses={warehouses} mode="list" onOpenSession={openCountSession} />,
          },
          {
            key: 'issue-return-list',
            label: 'برگشت‌های خروج انبار',
            icon: RotateCcw,
            content: (
              <IssueReturnsTab token={token} me={me} warehouses={warehouses} onChanged={() => void refreshStock()} view="ledger" />
            ),
          },
        ]}
      />

      {kardex && <KardexDrawer token={token} item={kardex} onClose={() => setKardex(null)} />}
    </div>
  )
}
