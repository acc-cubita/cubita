// سیستمِ طراحیِ اپ اندروید — «تیره‌ی برندی/فینتک». کاملاً مستقل از وب/دسکتاپ.
// نزدیک-مشکی + لهجه‌ی طلایی؛ فقط رنگِ برند (طلایی) مشترک است، نه هیچ چیدمانِ وب.

export const colors = {
  bg: '#0b0b0d', // پس‌زمینه‌ی اصلی، نزدیک-مشکی
  surface: '#15151a', // کارت/سطحِ برجسته
  surfaceAlt: '#1d1d25', // سطحِ ثانویه (ردیف‌ها، ورودی)
  border: '#2a2a34',
  borderStrong: '#3a3a46',

  text: '#f3f3f6',
  textMuted: '#9a9aa9',
  textFaint: '#6b6b7a',

  accent: '#ffc72c', // طلاییِ برند
  accentSoft: 'rgba(255, 199, 44, 0.14)',
  onAccent: '#1a1400', // متن روی طلایی

  violet: '#a78bfa', // لهجه‌ی دوم (برند)

  success: '#34d399',
  successSoft: 'rgba(52, 211, 153, 0.14)',
  warning: '#fbbf24',
  warningSoft: 'rgba(251, 191, 36, 0.14)',
  danger: '#f87171',
  dangerSoft: 'rgba(248, 113, 113, 0.14)',

  overlay: 'rgba(0, 0, 0, 0.6)',
} as const

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
} as const

export const font = {
  // Vazirmatn در فازِ بعدی به‌عنوان فونتِ سفارشی بار می‌شود؛ فعلاً فونتِ سیستم
  // (اندروید فارسی را با Noto درست رندر می‌کند).
  family: undefined as string | undefined,
  size: { xs: 11, sm: 13, md: 15, lg: 18, xl: 22, xxl: 28, display: 34 },

  /**
   * سقفِ بزرگ‌نماییِ فونتِ سیستم، فقط برای جاهایی که کادرشان **نمی‌تواند** رشد کند.
   *
   * اندروید اجازه می‌دهد کاربر فونت را تا ۲ برابر بزرگ کند و کاربرِ این اپ —
   * صاحبِ کسب‌وکارِ میان‌سال — واقعاً این کار را می‌کند. جاهای معمولی باید همراهش
   * بزرگ شوند؛ ولی سه جا هست که هندسه‌شان ثابت است و متنِ دو برابر یا از کادر
   * بیرون می‌زند یا بریده می‌شود:
   *
   * - `dense`: نشانِ عددِ روی آیکون، چیپِ فیلتر — عرضشان به تعدادِ گزینه‌ها
   *   گره خورده، پس متن جایی برای رفتن ندارد.
   * - `tab`: برچسبِ نوارِ تب — پنج ستونِ مساوی؛ در ۲ برابر «انبارگر…» می‌شود.
   *
   * سقف است نه خاموشی: در ۱٫۳ (پرکاربردترین تنظیم) هیچ‌کدام محدود نمی‌شوند.
   */
  maxScale: { dense: 1.3, tab: 1.2 },
  weight: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
    black: '800' as const,
  },
} as const

export const theme = { colors, spacing, radius, font } as const
export type Theme = typeof theme

// ارقامِ فارسی — همه‌جای اپ از این استفاده می‌شود تا اعداد بومی دیده شوند.
export const faNum = (v: number | string): string =>
  Number(v).toLocaleString('fa-IR')

export const faMoney = (v: number | string): string =>
  Math.round(Number(v)).toLocaleString('fa-IR')
