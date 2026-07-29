import { useEffect, useMemo, useRef, useState } from 'react'
import { ScanLine, Plus, Minus, Trash2, ShoppingCart, Wallet, CheckCircle2, Store } from 'lucide-react'
import {
  createSalesInvoiceDirect,
  fetchContacts,
  fetchItemsLive,
  fetchWarehousesLive,
  newIdempotencyKey,
  type ContactRecord,
  type ItemRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { todayIso } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

interface CartLine {
  item: ItemRecord
  qty: number
  unitPrice: number
}

export function PosPage({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [warehouseId, setWarehouseId] = useState('')
  const [contactId, setContactId] = useState('') // '' = مشتریِ گذری (فروشِ نقدی)
  const [taxRate, setTaxRate] = useState('10')
  const [cart, setCart] = useState<CartLine[]>([])
  const [scan, setScan] = useState('')
  const [pick, setPick] = useState('')
  const [received, setReceived] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const scanRef = useRef<HTMLInputElement>(null)
  const idem = useRef(newIdempotencyKey())

  useEffect(() => {
    fetchItemsLive(token).then((its) => setItems(its.filter((i) => i.is_active && !i.is_service))).catch(() => {})
    fetchWarehousesLive(token)
      .then((ws) => {
        setWarehouses(ws)
        if (ws[0]) setWarehouseId(ws[0].id)
      })
      .catch(() => {})
    fetchContacts(token).then((cs) => setContacts(cs.filter((c) => c.type !== 'supplier'))).catch(() => {})
    scanRef.current?.focus()
  }, [token])

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
    setCart((prev) => {
      const idx = prev.findIndex((l) => l.item.id === it.id)
      if (idx >= 0) {
        const copy = [...prev]
        copy[idx] = { ...copy[idx], qty: copy[idx].qty + 1 }
        return copy
      }
      return [...prev, { item: it, qty: 1, unitPrice: Number(it.sales_price) || 0 }]
    })
  }

  function handleScan(e: React.FormEvent) {
    e.preventDefault()
    const code = scan.trim()
    if (!code) return
    const it = codeMap.get(code)
    if (it) {
      addItem(it)
      setFlash(null)
    } else {
      setFlash(`کالایی با بارکد/کد «${code}» یافت نشد`)
    }
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
  const tax = Math.round((subtotal * taxRateNum) / 100)
  const total = subtotal + tax
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
          lines: cart.map((l) => ({ item_id: l.item.id, qty: l.qty, unit_price: l.unitPrice })),
        },
        idem.current,
      )) as { number?: number }
      idem.current = newIdempotencyKey()
      const num = res?.number != null ? res.number.toLocaleString('fa-IR') : '—'
      setMessage(`فروش ثبت شد ✓ فاکتور شماره ${num}${change > 0 ? ` — بازگردانده به مشتری: ${fa(change)} تومان` : ''}`)
      setCart([])
      setReceived('')
      scanRef.current?.focus()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
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
        <label>
          مالیات (٪)
          <input type="number" min="0" max="100" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} style={{ width: 80 }} />
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
            <button type="submit" className="btn-primary"><Plus size={15} /> افزودن</button>
          </form>

          <div className="pos-pick">
            <select value={pick} onChange={(e) => { const it = items.find((i) => i.id === e.target.value); if (it) addItem(it); setPick('') }}>
              <option value="">— افزودن از فهرست کالاها —</option>
              {items.map((i) => (
                <option key={i.id} value={i.id}>{i.name}{i.barcode ? ` (${i.barcode})` : ''}</option>
              ))}
            </select>
          </div>

          {flash && <div className="pos-flash">{flash}</div>}

          {cart.length === 0 ? (
            <EmptyState icon={ShoppingCart} text="سبد خالی است — یک بارکد اسکن کنید." />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table pos-cart">
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
                  {cart.map((l) => (
                    <tr key={l.item.id}>
                      <td className="entity-name">{l.item.name}</td>
                      <td>
                        <div className="pos-qty">
                          <button type="button" onClick={() => setQty(l.item.id, l.qty - 1)} aria-label="کم"><Minus size={13} /></button>
                          <input type="number" min="0" value={l.qty} onChange={(e) => setQty(l.item.id, Number(e.target.value))} />
                          <button type="button" onClick={() => setQty(l.item.id, l.qty + 1)} aria-label="زیاد"><Plus size={13} /></button>
                        </div>
                      </td>
                      <td>
                        <input className="pos-price" type="number" min="0" value={l.unitPrice} onChange={(e) => setPrice(l.item.id, Number(e.target.value))} />
                      </td>
                      <td className="money-cell">{fa(l.qty * l.unitPrice)}</td>
                      <td>
                        <button type="button" className="icon-btn-danger" onClick={() => remove(l.item.id)} aria-label="حذف"><Trash2 size={13} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard icon={Wallet} title="تسویه">
          <div className="pos-summary">
            <div className="pos-row"><span>جمع کالاها</span><strong>{fa(subtotal)}</strong></div>
            <div className="pos-row"><span>مالیات ({taxRateNum.toLocaleString('fa-IR')}٪)</span><strong>{fa(tax)}</strong></div>
            <div className="pos-row pos-total"><span>مبلغ قابل پرداخت</span><strong>{fa(total)}</strong></div>
          </div>

          <label className="pos-received">
            مبلغ دریافتی از مشتری (تومان)
            <input type="number" min="0" value={received} onChange={(e) => setReceived(e.target.value)} placeholder="برای محاسبه‌ی باقی‌مانده" />
          </label>
          {Number(received) > 0 && (
            <div className={`pos-change ${change < 0 ? 'neg' : ''}`}>
              {change >= 0 ? `باقی‌مانده به مشتری: ${fa(change)} تومان` : `کسری: ${fa(-change)} تومان`}
            </div>
          )}

          <button type="button" className="btn-primary pos-checkout" onClick={() => void complete()} disabled={busy || cart.length === 0}>
            <CheckCircle2 size={16} /> تکمیل فروش
          </button>
          {message && <div className="hint">{message}</div>}
          <p className="hint pos-note">
            بدون انتخاب مشتری، فروش «نقدی» ثبت می‌شود و مبلغ به صندوق می‌رود. با انتخاب مشتری، فروش به حساب او (نسیه) ثبت می‌شود.
          </p>
        </SectionCard>
      </div>
    </div>
  )
}
