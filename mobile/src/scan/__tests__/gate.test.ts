/**
 * دروازه‌ی اسکن — چیزی که اگر نباشد، یک بار گرفتنِ گوشی جلوی جعبه «۳۰ عدد»
 * می‌شود و هیچ خطایی هم دیده نمی‌شود.
 */
import { createScanGate } from '../gate'

describe('اسکنِ تکراری', () => {
  it('شلیکِ پشتِ‌سرِ همِ یک بارکد فقط یک بار شمرده می‌شود', () => {
    const g = createScanGate()
    expect(g.accept('6260100120017', 1000)).toBe(true)
    // دوربین در ۳۰۰ میلی‌ثانیه‌ی بعد ده بار دیگر همین را می‌دهد.
    for (const t of [1030, 1060, 1090, 1120, 1300]) {
      expect(g.accept('6260100120017', t)).toBe(false)
    }
  })

  it('همان بارکد پس از مهلت دوباره شمرده می‌شود', () => {
    // انباردار عمداً دو جعبه‌ی یکسان را پشتِ‌سرِ هم می‌زند — این باید کار کند.
    const g = createScanGate({ sameCodeMs: 2_000 })
    expect(g.accept('A', 0)).toBe(true)
    expect(g.accept('A', 2_100)).toBe(true)
  })

  it('بارکدِ متفاوت لازم نیست مهلتِ بلند را صبر کند', () => {
    const g = createScanGate({ anyScanMs: 500, sameCodeMs: 5_000 })
    expect(g.accept('A', 0)).toBe(true)
    expect(g.accept('B', 600)).toBe(true)
  })

  it('ولی مهلتِ کوتاهِ عمومی برای همه هست', () => {
    // بدونِ این، دو بارکدِ کنارِ هم روی یک برچسب هر دو در یک لحظه می‌افتند و
    // کاربر نمی‌فهمد کدام شمرده شد.
    const g = createScanGate({ anyScanMs: 700 })
    expect(g.accept('A', 0)).toBe(true)
    expect(g.accept('B', 300)).toBe(false)
  })

  it('بارکدِ خالی هرگز پذیرفته نمی‌شود', () => {
    expect(createScanGate().accept('', 0)).toBe(false)
  })

  it('reset تاریخچه را پاک می‌کند', () => {
    const g = createScanGate()
    expect(g.accept('A', 0)).toBe(true)
    g.reset()
    expect(g.accept('A', 10)).toBe(true)
  })
})
