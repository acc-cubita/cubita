import { describe, expect, it } from 'vitest'
import {
  allocationError,
  allocationTotal,
  fefoOrder,
  fefoPlan,
  totalSellable,
  type AllocatableBatch,
} from './batchAllocation'

const batch = (
  id: string,
  batch_number: string,
  expiry_date: string | null,
  sellable_qty: string,
): AllocatableBatch => ({ id, batch_number, expiry_date, sellable_qty })

describe('ترتیبِ FEFO', () => {
  it('نزدیک‌ترین انقضا اول می‌آید', () => {
    const rows = [
      batch('b', 'B', '1405-09-01', '10'),
      batch('a', 'A', '1405-06-01', '10'),
      batch('c', 'C', '1405-07-01', '10'),
    ]
    expect(fefoOrder(rows).map((r) => r.id)).toEqual(['a', 'c', 'b'])
  })

  it('بارِ بدونِ تاریخِ انقضا **آخر** می‌آید، نه اول', () => {
    // «نمی‌دانم» نباید جلوی باری بیفتد که تاریخش دارد می‌گذرد.
    const rows = [batch('none', 'N', null, '5'), batch('soon', 'S', '1405-06-01', '5')]
    expect(fefoOrder(rows).map((r) => r.id)).toEqual(['soon', 'none'])
  })

  it('ورودی را تغییر نمی‌دهد', () => {
    const rows = [batch('b', 'B', '1405-09-01', '1'), batch('a', 'A', '1405-06-01', '1')]
    fefoOrder(rows)
    expect(rows.map((r) => r.id)).toEqual(['b', 'a'])
  })
})

describe('پیشنهادِ پیش‌فرض', () => {
  it('مقدار را بینِ بارها به ترتیبِ انقضا تقسیم می‌کند', () => {
    const rows = [batch('a', 'A', '1405-06-01', '10'), batch('b', 'B', '1405-09-01', '10')]
    expect(fefoPlan(rows, 15)).toEqual([
      { batch_id: 'a', qty: 10 },
      { batch_id: 'b', qty: 5 },
    ])
  })

  it('بارِ بدونِ موجودیِ قابلِ فروش را رد می‌کند', () => {
    const rows = [batch('empty', 'E', '1405-06-01', '0'), batch('ok', 'O', '1405-09-01', '7')]
    expect(fefoPlan(rows, 5)).toEqual([{ batch_id: 'ok', qty: 5 }])
  })

  it('اگر کافی نباشد، هرچه هست را می‌دهد — تصمیم با فراخوان است', () => {
    const rows = [batch('a', 'A', '1405-06-01', '3')]
    expect(allocationTotal(fefoPlan(rows, 10))).toBe(3)
  })
})

describe('اعتبارسنجی', () => {
  const rows = [batch('a', 'A', '1405-06-01', '10'), batch('b', 'B', '1405-09-01', '4')]

  it('جمعِ برابر با مقدارِ ردیف را می‌پذیرد', () => {
    expect(allocationError([{ batch_id: 'a', qty: 6 }], 6, rows)).toBeNull()
  })

  it('جمعِ نابرابر را رد می‌کند', () => {
    expect(allocationError([{ batch_id: 'a', qty: 4 }], 6, rows)).toMatch('برابرِ مقدارِ ردیف')
  })

  it('برداشتِ بیشتر از موجودیِ یک بار را رد می‌کند', () => {
    expect(allocationError([{ batch_id: 'b', qty: 5 }], 5, rows)).toMatch('«B»')
  })

  it('مقدارِ صفر یا منفی را رد می‌کند', () => {
    expect(allocationError([{ batch_id: 'a', qty: 0 }], 0, rows)).toMatch('بزرگ‌تر از صفر')
  })

  it('بارِ ناشناس را رد می‌کند', () => {
    expect(allocationError([{ batch_id: 'zzz', qty: 1 }], 1, rows)).toMatch('دیگر در این انبار نیست')
  })
})

describe('جمعِ قابلِ فروش', () => {
  it('مقدارِ نامعتبر را صفر می‌شمارد، نه NaN', () => {
    const rows = [batch('a', 'A', null, '5'), batch('b', 'B', null, '')]
    expect(totalSellable(rows)).toBe(5)
  })
})
