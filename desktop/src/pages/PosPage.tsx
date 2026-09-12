import { useEffect, useMemo, useRef, useState } from 'react'
import { ScanLine, Plus, Minus, Trash2, ShoppingCart, Wallet, CheckCircle2, Store, Camera, Printer } from 'lucide-react'
import {
  createSalesInvoiceDirect,
  fetchContacts,
  fetchItemsLive,
  fetchSaleTypes,
  fetchStockLevels,
  fetchWarehousesLive,
  newIdempotencyKey,
  resolvePrice,
  type ContactRecord,
  type ItemRecord,
  type MeResponse,
  type SaleType,
  type StockLevel,
  type TreasuryTransactionRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { NumberInput } from '../components/NumberInput'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { ItemPicker } from '../components/ItemPicker'
import { BarcodeScanner } from '../components/BarcodeScanner'
import { CardPaymentButton } from '../components/CardPaymentDialog'
import { PosReceipt, type ReceiptData } from '../components/PosReceipt'
import { todayIso, formatJalali } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

interface CartLine {
  item: ItemRecord
  qty: number
  unitPrice: number
}

export function PosPage({ token, me }: { token: string; me: MeResponse }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [warehouseId, setWarehouseId] = useState('')
  const [contactId, setContactId] = useState('') // '' = مشتریِ گذری (فروشِ نقدی)
  //: **نوعِ فروش جای «لیستِ قیمت» را گرفت (§۴ §۵۴).**
  //:
  //: صندوق تا امروز یک لیستِ قیمت را دستی انتخاب می‌کرد و از رویش نگاشتِ
  //: `item_id → price` می‌ساخت — بی‌اعتنا به تاریخِ اجرا، فعال‌بودن و بقیه‌ی
  //: ابعاد. یعنی موتورِ سومِ قیمت، که با آن دو تای دیگر جوابِ یکسان نمی‌داد.
  //: نوعِ فروش همان نیازِ واقعیِ صندوقدار را برمی‌آورد («برو روی قیمتِ عمده»)
  //: ولی از همان حل‌کننده‌ای می‌گذرد که سرور اعتبارسنجی می‌کند.
  const [saleTypes, setSaleTypes] = useState<SaleType[]>([])
  const [saleTypeId, setSaleTypeId] = useState('')
  const [priceMap, setPriceMap] = useState<Map<string, number>>(new Map())
  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])
  const [taxRate, setTaxRate] = useState('10')
  const [discount, setDiscount] = useState('')
  const [discountMode, setDiscountMode] = useState<'amount' | 'percent'>('amount')
  const [roundStep, setRoundStep] = useState(0)
  const [cart, setCart] = useState<CartLine[]>([])
  const [scan, setScan] = useState('')
  const [scanning, setScanning] = useState(false) // نمای دوربینِ اسکن باز است؟
  const [pick, setPick] = useState('')
  const [received, setReceived] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // آخرین رسیدِ چاپ‌شدنی (برای چاپِ خودکار بعد از فروش و دکمه‌ی چاپِ دوباره)
  const [receipt, setReceipt] = useState<ReceiptData | null>(null)
  const [autoPrint, setAutoPrint] = useState(() => localStorage.getItem('pos_auto_print') !== '0')
  const scanRef = useRef<HTMLInputElement>(null)
  const idem = useRef(newIdempotencyKey())

  function toggleAutoPrint() {
    setAutoPrint((v) => {
      localStorage.setItem('pos_auto_print', v ? '0' : '1')
      return !v
    })
  }

  // چاپ: رسید در یک بلوکِ مخفی رندر می‌شود و فقط هنگامِ چاپ دیده می‌شود (@media print).
  // یک tick صبر می‌کنیم تا DOM به‌روز شود، بعد window.print — روی دسکتاپ (الکترون) و وب یکسان.
  function printReceipt(data: ReceiptData) {
    setReceipt(data)
    setTimeout(() => window.print(), 60)
  }

  function buildReceipt(
    num: number | null | undefined,
    cashier: string | null | undefined,
    payment: 'cash' | 'card',
    reference?: string | null,
  ): ReceiptData {
    const now = new Date()
    return {
      storeName: me.tenant_name,
      cashier: cashier || me.name,
      date: formatJalali(todayIso()),
      time: now.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' }),
      invoiceNumber: num != null ? num.toLocaleString('fa-IR') : '—',
      customer: contacts.find((c) => c.id === contactId)?.name ?? 'مشتریِ نقدی',
      lines: cart.map((l) => ({ name: l.item.name, unit: l.item.unit, qty: l.qty, unitPrice: l.unitPrice, total: l.qty * l.unitPrice })),
      subtotal,
      discount: discountAmount,
      taxRate: taxRateNum,
      tax,
      rounding: roundAdjust,
      total,
      received: payment === 'cash' && Number(received) > 0 ? Number(received) : null,
      change: payment === 'cash' && Number(received) > 0 ? change : null,
      payment,
      reference: reference ?? null,
    }
  }

  useEffect(() => {
    fetchItemsLive(token).then((its) => setItems(its.filter((i) => i.is_active && !i.is_service))).catch(() => {})
    fetchWarehousesLive(token)
      .then((ws) => {
        setWarehouses(ws)
        if (ws[0]) setWarehouseId(ws[0].id)
      })
      .catch(() => {})
    fetchContacts(token).then((cs) => setContacts(cs.filter((c) => c.type !== 'supplier'))).catch(() => {})
    fetchSaleTypes(token).then((ts) => setSaleTypes(ts.filter((t) => t.is_active))).catch(() => {})
    fetchStockLevels(token).then(setStockLevels).catch(() => setStockLevels([]))
    scanRef.current?.focus()
  }, [token])

  // موجودیِ در دسترسِ یک کالا در انبارِ انتخاب‌شده — تا فروشنده کسری را همان لحظه ببیند.
  function availableStock(itemId: string): number | null {
    if (!warehouseId) return null
    const row = stockLevels.find((s) => s.item_id === itemId && s.warehouse_id === warehouseId)
    return row ? Number(row.qty) : 0
  }

  // فیِ کالاهای سبد از حل‌کننده‌ی مشترک می‌آید — با نوعِ فروش و مشتریِ همین لحظه.
  // تنها کالاهایی حل می‌شوند که در سبدند یا تازه اسکن شده‌اند؛ کلِ فهرست نه، چون
  // یک صندوقِ چندهزارکالایی نباید سرِ هر تغییرِ نوعِ فروش هزار درخواست بفرستد.
  const [pricedKey, setPricedKey] = useState('')
  useEffect(() => {
    const key = `${saleTypeId}|${contactId}`
    if (key === pricedKey) return
    const ids = [...new Set(cart.map((l) => l.item.id))]
    setPricedKey(key)
    if (ids.length === 0) {
      setPriceMap(new Map())
      return
    }
    let cancelled = false
    void Promise.all(
      ids.map(async (id) => {
        const got = await resolvePrice(token, id, {
          saleTypeId: saleTypeId || null,
          contactId: contactId || null,
        }).catch(() => null)
        return [id, got ? Number(got.unit_price) : null] as const
      }),
    ).then((pairs) => {
      if (cancelled) return
      const next = new Map(pairs.filter(([, p]) => p != null) as [string, number][])
      setPriceMap(next)
      setCart((prev) =>
        prev.map((l) => ({ ...l, unitPrice: next.get(l.item.id) ?? (Number(l.item.sales_price) || 0) })),
      )
    })
    return () => {
      cancelled = true
    }
  }, [token, saleTypeId, contactId, cart, pricedKey])

  /** فیِ یک کالا: از اعلامیه اگر قاعده‌ای بخواند، وگرنه قیمتِ پایه (§۵۸). */
  async function priceFor(it: ItemRecord): Promise<number> {
    const cached = priceMap.get(it.id)
    if (cached != null) return cached
    const got = await resolvePrice(token, it.id, {
      saleTypeId: saleTypeId || null,
      contactId: contactId || null,
    }).catch(() => null)
    if (got) {
      const value = Number(got.unit_price)
      setPriceMap((prev) => new Map(prev).set(it.id, value))
      return value
    }
    return Number(it.sales_price) || 0
  }

  // نگاشتِ بارکد و کدِ کالا برای جست‌وجوی فوریِ سمتِ کلاینت (بدونِ رفت‌وبرگشتِ شبکه در هر اسکن)
  const codeMap = useMemo(() => {
    const m = new Map<string, ItemRecord>()
    for (const it of items) {
      if (it.barcode) m.set(it.barcode, it)
      m.set(it.sku, it)
    }
    return m
  }, [items])

  function addItem(it: ItemRecord) {
    let isNew = false
    setCart((prev) => {
      const idx = prev.findIndex((l) => l.item.id === it.id)
      if (idx >= 0) {
        const copy = [...prev]
        copy[idx] = { ...copy[idx], qty: copy[idx].qty + 1 }
        return copy
      }
      isNew = true
      // قیمتِ پایه فوراً می‌نشیند تا اسکن کُند نشود؛ فیِ مصوب پشتِ سر می‌رسد.
      return [...prev, { item: it, qty: 1, unitPrice: Number(it.sales_price) || 0 }]
    })
    if (!isNew) return
    void priceFor(it).then((price) =>
      setCart((prev) => prev.map((l) => (l.item.id === it.id ? { ...l, unitPrice: price } : l))),
    )
  }

  // جست‌وجوی کد (بارکد/SKU) و افزودن به سبد — مشترکِ ورودِ دستی و دوربین.
  function lookupAndAdd(code: string): boolean {
    const c = code.trim()
    if (!c) return false
    const it = codeMap.get(c)
    if (it) {
      addItem(it)
      setFlash(`«${it.name}» افزوده شد`)
      return true
    }
    setFlash(`کالایی با بارکد/کد «${c}» یافت نشد`)
    return false
  }

  function handleScan(e: React.FormEvent) {
    e.preventDefault()
    lookupAndAdd(scan)
    setScan('')
    scanRef.current?.focus()
  }

  function setQty(id: string, qty: number) {
    setCart((prev) => prev.map((l) => (l.item.id === id ? { ...l, qty: Math.max(0, qty) } : l)).filter((l) => l.qty > 0))
  }
  function setPrice(id: string, price: number) {
    setCart((prev) => prev.map((l) => (l.item.id === id ? { ...l, unitPrice: Math.max(0, price) } : l)))
  }
  function remove(id: string) {
    setCart((prev) => prev.filter((l) => l.item.id !== id))
  }

  const subtotal = cart.reduce((s, l) => s + l.qty * l.unitPrice, 0)
  const taxRateNum = Math.min(Math.max(Number(taxRate) || 0, 0), 100)
  const discountInput = Number(discount) || 0
  const discountAmount = Math.min(
    discountMode === 'percent' ? Math.round((subtotal * discountInput) / 100) : discountInput,
    subtotal,
  )
  const netAfterDiscount = subtotal - discountAmount
  const tax = Math.round((netAfterDiscount * taxRateNum) / 100)
  const grandBeforeRound = netAfterDiscount + tax
  // رند فقط به پایین (به نفعِ مشتری)
  const roundAdjust = roundStep > 0 ? Math.floor(grandBeforeRound / roundStep) * roundStep - grandBeforeRound : 0
  const total = grandBeforeRound + roundAdjust
  const change = Number(received) ? Number(received) - total : 0
  const itemCount = cart.reduce((s, l) => s + l.qty, 0)

  async function complete() {
    setMessage(null)
    if (cart.length === 0) {
      setMessage('سبد خالی است.')
      return
    }
    if (!warehouseId) {
      setMessage('انبار را انتخاب کنید.')
      return
    }
    setBusy(true)
    try {
      const res = (await createSalesInvoiceDirect(
        token,
        {
          invoice_date: todayIso(),
          warehouse_id: warehouseId,
          tax_rate: taxRateNum,
          contact_id: contactId || null,
          //: بدونِ این، صندوق فیِ «عمده» را پر می‌کرد و سرور آن را در زمینه‌ی
          //: پیش‌فرض اعتبارسنجی می‌کرد — همان ناهم‌خوانی‌ای که این فصل می‌بندد.
          sale_type_id: saleTypeId || null,
          invoice_discount: discountAmount,
          rounding: roundAdjust,
          lines: cart.map((l) => ({ item_id: l.item.id, qty: l.qty, unit_price: l.unitPrice })),
        },
        idem.current,
      )) as { number?: number; created_by_name?: string | null }
      idem.current = newIdempotencyKey()
      const num = res?.number != null ? res.number.toLocaleString('fa-IR') : '—'
      // رسید را پیش از خالی‌کردنِ سبد بساز (snapshot می‌گیرد)
      const data = buildReceipt(res?.number, res?.created_by_name, 'cash')
      setMessage(`فروش ثبت شد ✓ فاکتور شماره ${num}${change > 0 ? ` — بازگردانده به مشتری: ${fa(change)} ریال` : ''}`)
      if (autoPrint) printReceipt(data)
      else setReceipt(data)
      setCart([])
      setReceived('')
      setDiscount('')
      setRoundStep(0)
      scanRef.current?.focus()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  // پرداختِ کارتی: رسیدِ بانکی از قبل (در مودال) ثبت شده؛ حالا فاکتورِ فروش را علیهِ
  // همان طرف‌حساب (انتخاب‌شده یا طرف‌حسابِ گذریِ برگشتی) می‌سازیم تا دریافتنی صفر شود.
  async function completeAfterCard(txn: TreasuryTransactionRecord) {
    if (cart.length === 0 || !warehouseId) return
    setBusy(true)
    setMessage(null)
    try {
      const res = (await createSalesInvoiceDirect(
        token,
        {
          invoice_date: todayIso(),
          warehouse_id: warehouseId,
          tax_rate: taxRateNum,
          contact_id: contactId || txn.contact_id,
          sale_type_id: saleTypeId || null,
          invoice_discount: discountAmount,
          rounding: roundAdjust,
          lines: cart.map((l) => ({ item_id: l.item.id, qty: l.qty, unit_price: l.unitPrice })),
        },
        idem.current,
      )) as { number?: number; created_by_name?: string | null }
      idem.current = newIdempotencyKey()
      const num = res?.number != null ? res.number.toLocaleString('fa-IR') : '—'
      const data = buildReceipt(res?.number, res?.created_by_name, 'card', txn.reference_no)
      setMessage(`فروشِ کارتی ثبت شد ✓ فاکتور شماره ${num} — مرجعِ پرداخت: ${txn.reference_no ?? '—'}`)
      if (autoPrint) printReceipt(data)
      else setReceipt(data)
      setCart([])
      setReceived('')
      setDiscount('')
      setRoundStep(0)
      scanRef.current?.focus()
    } catch (err) {
      setMessage(
        `پرداخت ثبت شد (مرجع ${txn.reference_no ?? '—'}) اما ثبتِ فاکتور خطا داد: ${err instanceof Error ? err.message : 'خطای ناشناخته'} — لطفاً فاکتور را دستی تکمیل کنید.`,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={Store}
        title="صندوق فروشگاهی"
        description="بارکد کالا را اسکن کنید یا از فهرست انتخاب کنید؛ با یک کلیک، فروش ثبت و سند حسابداری و کسر موجودی خودکار انجام می‌شود."
      />

      <div className="pos-toolbar">
        <label>
          انبار
          <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </label>
        <label>
          مشتری
          <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
            <option value="">مشتریِ گذری (نقدی)</option>
            {contacts.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        {saleTypes.length > 0 && (
          <label>
            نوع فروش
            <select value={saleTypeId} onChange={(e) => setSaleTypeId(e.target.value)}>
              <option value="">عادی</option>
              {saleTypes.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </label>
        )}
        <label>
          مالیات (٪)
          <NumberInput allowDecimal value={taxRate} onChange={setTaxRate} style={{ width: 80 }} />
        </label>
      </div>

      <div className="pos-grid">
        <SectionCard icon={ScanLine} title="اسکن و سبد خرید" description={`${fa(itemCount)} قلم در سبد`}>
          <form className="pos-scan" onSubmit={handleScan}>
            <ScanLine size={18} />
            <input
              ref={scanRef}
              type="text"
              value={scan}
              onChange={(e) => setScan(e.target.value)}
              placeholder="بارکد را اسکن یا تایپ کنید و Enter بزنید…"
              inputMode="numeric"
              autoFocus
            />
            <button type="button" className="pos-cam-btn" onClick={() => setScanning(true)} title="اسکن با دوربین">
              <Camera size={15} /> دوربین
            </button>
            <button type="submit" className="btn-primary"><Plus size={15} /> افزودن</button>
          </form>

          {scanning && (
            <BarcodeScanner
              onDetected={(code) => lookupAndAdd(code)}
              onClose={() => { setScanning(false); scanRef.current?.focus() }}
            />
          )}

          <div className="pos-pick">
            <ItemPicker
              items={items}
              value={pick}
              onChange={(id) => { const it = items.find((i) => i.id === id); if (it) addItem(it); setPick('') }}
              placeholder="— افزودن از فهرست کالاها —"
            />
          </div>

          {flash && <div className="pos-flash">{flash}</div>}

          {cart.length === 0 ? (
            <EmptyState icon={ShoppingCart} text="سبد خالی است — یک بارکد اسکن کنید." />
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table pos-cart cards-on-mobile">
                  <thead>
                    <tr>
                      <th>کالا</th>
                      <th>تعداد</th>
                      <th>قیمت واحد</th>
                      <th>جمع</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {cart.map((l) => {
                      const avail = availableStock(l.item.id)
                      const over = avail != null && l.qty > avail
                      return (
                      <tr key={l.item.id}>
                        <td className="entity-name" data-label="کالا">
                          {l.item.name}
                          {l.item.unit && l.item.unit !== 'عدد' && <span className="unit-suffix"> / {l.item.unit}</span>}
                          {avail != null && (
                            <div className={over ? 'stock-warn' : 'unit-suffix'}>
                              موجودی: {avail.toLocaleString('fa-IR')}{over ? ' — بیش از موجودی' : ''}
                            </div>
                          )}
                        </td>
                        <td data-label="تعداد">
                          <div className="pos-qty">
                            <button type="button" onClick={() => setQty(l.item.id, l.qty - 1)} aria-label="کم"><Minus size={13} /></button>
                            <NumberInput allowDecimal value={l.qty} onChange={(v) => setQty(l.item.id, Number(v))} />
                            <button type="button" onClick={() => setQty(l.item.id, l.qty + 1)} aria-label="زیاد"><Plus size={13} /></button>
                          </div>
                        </td>
                        <td data-label="قیمت واحد">
                          <NumberInput className="pos-price" value={l.unitPrice} onChange={(v) => setPrice(l.item.id, Number(v))} />
                        </td>
                        <td data-label="جمع" className="money-cell">{fa(l.qty * l.unitPrice)}</td>
                        <td className="pos-remove-cell card-actions">
                          <button type="button" className="icon-btn-danger" onClick={() => remove(l.item.id)} aria-label="حذف"><Trash2 size={13} /> <span className="pos-remove-text">حذف</span></button>
                        </td>
                      </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard icon={Wallet} title="تسویه">
          <div className="pos-adjust">
            <label>
              تخفیف
              <div className="qty-with-unit">
                <NumberInput value={discount} onChange={setDiscount} placeholder="۰" />
                <div className="seg-toggle">
                  <button type="button" className={discountMode === 'amount' ? 'active' : ''} onClick={() => setDiscountMode('amount')}>مبلغ</button>
                  <button type="button" className={discountMode === 'percent' ? 'active' : ''} onClick={() => setDiscountMode('percent')}>٪</button>
                </div>
              </div>
            </label>
            <label>
              رند (به پایین)
              <div className="seg-toggle">
                {[0, 1000, 5000, 10000].map((s) => (
                  <button key={s} type="button" className={roundStep === s ? 'active' : ''} onClick={() => setRoundStep(s)}>
                    {s === 0 ? 'بدون' : s.toLocaleString('fa-IR')}
                  </button>
                ))}
              </div>
            </label>
          </div>

          <div className="pos-summary">
            <div className="pos-row"><span>جمع کالاها</span><strong>{fa(subtotal)}</strong></div>
            {discountAmount > 0 && <div className="pos-row"><span>تخفیف</span><strong>−{fa(discountAmount)}</strong></div>}
            <div className="pos-row"><span>مالیات ({taxRateNum.toLocaleString('fa-IR')}٪)</span><strong>{fa(tax)}</strong></div>
            {roundAdjust !== 0 && <div className="pos-row"><span>گِرد کردن</span><strong>{fa(roundAdjust)}</strong></div>}
            <div className="pos-row pos-total"><span>مبلغ قابل پرداخت</span><strong>{fa(total)}</strong></div>
          </div>

          <label className="pos-received">
            مبلغ دریافتی از مشتری (ریال)
            <NumberInput value={received} onChange={setReceived} placeholder="برای محاسبه‌ی باقی‌مانده" />
          </label>
          {Number(received) > 0 && (
            <div className={`pos-change ${change < 0 ? 'neg' : ''}`}>
              {change >= 0 ? `باقی‌مانده به مشتری: ${fa(change)} ریال` : `کسری: ${fa(-change)} ریال`}
            </div>
          )}

          <div className="pos-checkout-actions">
            <button type="button" className="btn-primary pos-checkout" onClick={() => void complete()} disabled={busy || cart.length === 0}>
              <CheckCircle2 size={16} /> تکمیل فروش (نقدی)
            </button>
            <CardPaymentButton
              token={token}
              amount={total}
              contactId={contactId || null}
              description="فروشِ صندوقِ فروشگاهی — پرداختِ کارتی"
              className="btn-ghost pos-card-btn"
              disabled={busy || cart.length === 0 || !warehouseId}
              onPaid={(txn) => void completeAfterCard(txn)}
            />
          </div>

          <div className="pos-print-row">
            <label className="pos-autoprint" title="بعد از هر فروش، رسید روی پرینترِ حرارتی چاپ می‌شود">
              <input type="checkbox" checked={autoPrint} onChange={toggleAutoPrint} />
              چاپِ خودکارِ رسید بعد از فروش
            </label>
            {receipt && (
              <button type="button" className="btn-ghost pos-reprint" onClick={() => window.print()}>
                <Printer size={14} /> چاپِ رسیدِ آخر
              </button>
            )}
          </div>
          {message && <div className="hint">{message}</div>}
          <p className="hint pos-note">
            بدون انتخاب مشتری، فروش «نقدی» ثبت می‌شود و مبلغ به صندوق می‌رود. با انتخاب مشتری، فروش به حساب او (نسیه) ثبت می‌شود.
          </p>
        </SectionCard>
      </div>

      {/* رسیدِ حرارتی — فقط هنگامِ چاپ دیده می‌شود (@media print در App.css) */}
      {receipt && <PosReceipt data={receipt} />}
    </div>
  )
}
