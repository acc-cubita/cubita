import { createPortal } from 'react-dom'

/**
 * رسیدِ فروشِ حرارتی (۸۰م‌م) برای صندوقِ فروشگاهی.
 *
 * روی صفحه مخفی است و فقط هنگامِ چاپ دیده می‌شود (قاعده‌های `@media print` در App.css
 * همه‌چیز جز `.pos-receipt-print` را پنهان و این را تمام‌عرضِ ۸۰م‌م می‌کنند). با پورتال
 * مستقیم به `document.body` رندر می‌شود تا هیچ ancestorی (overflow/transform/position)
 * موقعِ چاپ آن را نبُرد یا جابه‌جا نکند. همین یک روش روی دسکتاپ (الکترون) و وب یکسان کار
 * می‌کند و به پرینترِ حرارتی‌ای که پرینترِ پیش‌فرض/کاغذِ ۸۰م‌م تنظیم شده می‌رود.
 */

export interface ReceiptLine {
  name: string
  unit?: string
  qty: number
  unitPrice: number
  total: number
}

export interface ReceiptData {
  storeName: string
  cashier: string
  date: string
  time: string
  invoiceNumber: string
  customer: string
  lines: ReceiptLine[]
  subtotal: number
  discount: number
  taxRate: number
  tax: number
  rounding: number
  total: number
  received: number | null
  change: number | null
  payment: 'cash' | 'card'
  reference?: string | null
}

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
const faQty = (n: number) => n.toLocaleString('fa-IR')

export function PosReceipt({ data }: { data: ReceiptData }) {
  return createPortal(
    <div className="pos-receipt-print" dir="rtl">
      <div className="rc-store">{data.storeName}</div>
      <div className="rc-title">رسیدِ فروش</div>

      <div className="rc-meta">
        <div><span>فاکتور:</span><span>{data.invoiceNumber}</span></div>
        <div><span>تاریخ:</span><span>{data.date} — {data.time}</span></div>
        <div><span>صندوق‌دار:</span><span>{data.cashier}</span></div>
        <div><span>مشتری:</span><span>{data.customer}</span></div>
      </div>

      <div className="rc-sep" />

      <table className="rc-items">
        <thead>
          <tr>
            <th className="rc-name">کالا</th>
            <th className="rc-qty">تعداد</th>
            <th className="rc-price">قیمت</th>
            <th className="rc-sum">جمع</th>
          </tr>
        </thead>
        <tbody>
          {data.lines.map((l, i) => (
            <tr key={i}>
              <td className="rc-name">{l.name}{l.unit && l.unit !== 'عدد' ? ` (${l.unit})` : ''}</td>
              <td className="rc-qty">{faQty(l.qty)}</td>
              <td className="rc-price">{fa(l.unitPrice)}</td>
              <td className="rc-sum">{fa(l.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="rc-sep" />

      <div className="rc-totals">
        <div><span>جمع کالاها</span><span>{fa(data.subtotal)}</span></div>
        {data.discount > 0 && <div><span>تخفیف</span><span>−{fa(data.discount)}</span></div>}
        {data.tax > 0 && <div><span>مالیات ({data.taxRate.toLocaleString('fa-IR')}٪)</span><span>{fa(data.tax)}</span></div>}
        {data.rounding !== 0 && <div><span>گِرد کردن</span><span>{fa(data.rounding)}</span></div>}
        <div className="rc-grand"><span>مبلغ قابل پرداخت</span><span>{fa(data.total)} ریال</span></div>
      </div>

      <div className="rc-sep" />

      <div className="rc-pay">
        {data.payment === 'card' ? (
          <>
            <div><span>پرداخت</span><span>کارتی</span></div>
            {data.reference && <div><span>مرجعِ پرداخت</span><span>{data.reference}</span></div>}
          </>
        ) : (
          <>
            <div><span>پرداخت</span><span>نقدی</span></div>
            {data.received != null && <div><span>دریافتی</span><span>{fa(data.received)}</span></div>}
            {data.change != null && data.change > 0 && <div><span>باقی‌مانده</span><span>{fa(data.change)}</span></div>}
          </>
        )}
      </div>

      <div className="rc-foot">
        <div>از خریدِ شما سپاسگزاریم</div>
        <div className="rc-brand">کوبیتا</div>
      </div>
    </div>,
    document.body,
  )
}
