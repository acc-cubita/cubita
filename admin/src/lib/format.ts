// فرمتِ فشرده‌ی اعدادِ بزرگِ ریالی برای محورها و برچسب‌های نمودار.
//
// روی داشبورد اعداد به میلیارد می‌رسند و اگر کامل نوشته شوند محور شلوغ و ناخوانا
// می‌شود. راهنمای فاصله‌ها (tooltip) عددِ کامل را نشان می‌دهد، پس دقت گم نمی‌شود.

const faFull = (v: number) => Math.round(v).toLocaleString('fa-IR')

export function faCompact(value: number): string {
  const n = Math.abs(value)
  const sign = value < 0 ? '−' : ''
  if (n >= 1_000_000_000) return `${sign}${(n / 1_000_000_000).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} میلیارد`
  if (n >= 1_000_000) return `${sign}${(n / 1_000_000).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} م`
  if (n >= 1_000) return `${sign}${(n / 1_000).toLocaleString('fa-IR', { maximumFractionDigits: 0 })} هزار`
  return faFull(value)
}

export { faFull }
