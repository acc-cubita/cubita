/**
 * تطبیقِ بارکد با ردیفِ جلسه.
 *
 * سه نتیجه‌ی متفاوت لازم است، چون سه کارِ متفاوت از انباردار می‌خواهند. ادغامشان
 * در یک «پیدا نشد» یعنی کالایی که بعد از شروعِ جلسه ساخته شده، بی‌سروصدا از
 * انبارگردانی جا می‌ماند و کسی نمی‌فهمد چرا.
 */
import type { Item, StockCountLine } from '../../api/types'
import { barcodeIndex, resolveScan } from '../scanResolve'

const item = (id: string, name: string, barcode: string | null): Item =>
  ({ id, sku: `SKU-${id}`, name, unit: 'عدد', sales_price: '0', is_active: true, barcode }) as Item

const line = (id: string, itemId: string): StockCountLine =>
  ({
    id,
    item_id: itemId,
    item_name: 'x',
    item_sku: 'x',
    unit: 'عدد',
    system_qty: '10',
    counted_qty: '10',
    unit_cost: '0',
    variance: '0',
    variance_value: '0',
  }) as StockCountLine

const ITEMS = [
  item('i1', 'ماست', '6260100120017'),
  item('i2', 'پنیر', '6260100120024'),
  item('i3', 'خدماتِ حمل', null),
]
const INDEX = barcodeIndex(ITEMS)
const LINES = [line('l1', 'i1')]

describe('سه نتیجه', () => {
  it('بارکدِ کالای داخلِ جلسه → ردیف', () => {
    const r = resolveScan('6260100120017', INDEX, LINES)
    expect(r.kind).toBe('line')
    if (r.kind === 'line') {
      expect(r.line.id).toBe('l1')
      expect(r.item.name).toBe('ماست')
    }
  })

  it('کالا هست ولی در جلسه نیست → notInSession', () => {
    // این همان کالایی است که بعد از عکس‌برداریِ جلسه ساخته شده. اگر «پیدا نشد»
    // بگوییم، انباردار فکر می‌کند بارکد خراب است و از کنارش رد می‌شود.
    const r = resolveScan('6260100120024', INDEX, LINES)
    expect(r.kind).toBe('notInSession')
    if (r.kind === 'notInSession') expect(r.item.name).toBe('پنیر')
  })

  it('بارکدِ ناشناس → unknown', () => {
    expect(resolveScan('0000000000000', INDEX, LINES).kind).toBe('unknown')
  })
})

describe('ایندکسِ بارکد', () => {
  it('کالای بی‌بارکد وارد ایندکس نمی‌شود', () => {
    // وگرنه رشته‌ی خالی یک «کالا» می‌شد و هر اسکنِ ناموفق به آن می‌خورد.
    expect(INDEX.has('')).toBe(false)
    expect(INDEX.size).toBe(2)
  })

  it('فاصله‌ی اضافه‌ی دو طرف اهمیت ندارد', () => {
    const idx = barcodeIndex([item('i9', 'کره', ' 12345 ')])
    expect(resolveScan('12345', idx, []).kind).toBe('notInSession')
  })

  it('فاصله در ورودیِ اسکن هم نادیده گرفته می‌شود', () => {
    expect(resolveScan('  6260100120017  ', INDEX, LINES).kind).toBe('line')
  })

  it('بارکدِ تکراری اولی را نگه می‌دارد و نمی‌شکند', () => {
    const idx = barcodeIndex([item('a', 'اولی', '111'), item('b', 'دومی', '111')])
    const r = resolveScan('111', idx, [])
    expect(r.kind).toBe('notInSession')
    if (r.kind === 'notInSession') expect(r.item.name).toBe('اولی')
  })
})
