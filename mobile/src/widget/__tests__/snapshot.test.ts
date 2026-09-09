/**
 * عکسِ ویجت.
 *
 * این‌ها بی‌صدا غلط می‌دهند: ویجت هیچ خطایی نشان نمی‌دهد — فقط عددِ غلط را روی
 * صفحه‌ی خانه می‌گذارد و کاربر باورش می‌کند.
 */
import { buildSnapshot } from '../snapshot'

const base = {
  tenant: 'نرم افزار حسابداری کوبیتا',
  sales30: '12375000.00',
  netProfit: '-326500000.00',
  alerts: 3,
  showAmounts: true,
  now: 1_757_000_000_000,
}

describe('ساختِ عکس', () => {
  it('همه‌ی میدان‌ها پر می‌شوند', () => {
    const s = buildSnapshot(base)
    expect(s).toEqual({
      v: 1,
      saved_at: base.now,
      tenant: base.tenant,
      sales_30: '12375000.00',
      net_profit: '-326500000.00',
      alerts: 3,
      show_amounts: true,
    })
  })

  it('مبلغ رشته می‌ماند', () => {
    // مبالغِ ریالی از `Number.MAX_SAFE_INTEGER` رد می‌شوند. تبدیل به عدد رقمِ
    // آخر را بی‌صدا گرد می‌کند — روی ویجتی که کسی با آن مقایسه نمی‌کند، این
    // خطا هرگز دیده نمی‌شود.
    const s = buildSnapshot({ ...base, sales30: '9007199254740993' })
    expect(s.sales_30).toBe('9007199254740993')
    expect(typeof s.sales_30).toBe('string')
  })

  it('نبودِ داده «—» می‌شود نه صفر', () => {
    // «۰ ریال» روی ویجت یعنی «فروش نداشتی»، که با «هنوز داده‌ای نگرفته‌ام» فرق
    // دارد. رشته‌ی خالی را کوتلین به «—» ترجمه می‌کند.
    const s = buildSnapshot({ ...base, sales30: null, netProfit: undefined })
    expect(s.sales_30).toBe('')
    expect(s.net_profit).toBe('')
  })

  it('علامتِ منفی حفظ می‌شود', () => {
    // رنگِ قرمزِ ویجت از همین علامت می‌آید؛ اگر گم شود، زیان سبز نشان داده می‌شود.
    expect(buildSnapshot(base).net_profit.startsWith('-')).toBe(true)
  })

  it('شمارِ هشدار هرگز منفی یا اعشاری نیست', () => {
    expect(buildSnapshot({ ...base, alerts: -2 }).alerts).toBe(0)
    expect(buildSnapshot({ ...base, alerts: 2.7 }).alerts).toBe(2)
    expect(buildSnapshot({ ...base, alerts: null }).alerts).toBe(0)
  })

  it('تاگلِ کاربر منتقل می‌شود', () => {
    expect(buildSnapshot({ ...base, showAmounts: false }).show_amounts).toBe(false)
  })

  it('زمانِ عکس نوشته می‌شود', () => {
    // بدونِ آن ویجت نمی‌تواند بگوید داده‌اش مالِ کِی است، و عددِ دیروز امروزی
    // به‌نظر می‌رسد.
    expect(buildSnapshot(base).saved_at).toBe(base.now)
    expect(buildSnapshot({ ...base, now: undefined }).saved_at).toBeGreaterThan(0)
  })

  it('نسخه‌ی قالب همان عددی است که کوتلین می‌شناسد', () => {
    // عمداً عددِ خام و نه ثابتِ ماژول: `SUPPORTED_VERSION` در
    // `widget/CubitaWidget.kt` هم ۱ است و این دو سوی یک قرارداد در دو زبان‌اند.
    // مقایسه با نماد، تغییرِ هم‌زمانِ هر دو را می‌بلعد؛ عددِ خام آن را قرمز
    // می‌کند و یادآوری می‌شود که سمتِ کوتلین هم باید عوض شود.
    expect(buildSnapshot(base).v).toBe(1)
  })
})
