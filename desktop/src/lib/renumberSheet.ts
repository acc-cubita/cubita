import type { RenumberPreview } from '../api'

/**
 * منطقِ خالصِ «شماره‌گذاری مجدد اسناد».
 *
 * دو پیش‌نمایش از سرور: **کلِ بازه** (فهرستی که از آن انتخاب می‌شود) و، اگر سندی انتخاب شده، **نقشه‌ی همان انتخاب** —
 * چون انتخابِ دستی جای بازه می‌نشیند و شماره‌ی تازه‌ی هر سند به انتخاب بستگی دارد. شماره‌ی تازه‌ای که برگه نشان می‌دهد
 * همیشه از نقشه‌ی واقعی است، نه حسابِ رابط.
 */

/** شماره‌ی تازه‌ی هر سند در نقشه‌ای که اجرا می‌شود؛ سندِ بیرونِ نقشه در این نگاشت نیست. */
export function planNumbers(plan: Pick<RenumberPreview, 'rows'> | null): Map<string, number> {
  return new Map((plan?.rows ?? []).map((r) => [r.id, r.new_number]))
}

/**
 * حالِ نوار:
 * * `clash` — شماره‌ای از نقشه را سندی بیرونِ آن دارد؛ اجرا رد می‌شود؛
 * * `none` — سندِ موقتی در نقشه نیست؛
 * * `same` — شماره‌ی هیچ سندی عوض نمی‌شود؛
 * * `ready` — اجراشدنی.
 */
export type RenumberState = 'clash' | 'none' | 'same' | 'ready'

export function renumberState(plan: Pick<RenumberPreview, 'count' | 'changed_count' | 'first_clash'>): RenumberState {
  if (plan.first_clash != null) return 'clash'
  if (plan.count === 0) return 'none'
  return plan.changed_count === 0 ? 'same' : 'ready'
}

/** بازه‌ی شماره‌های تازه: از شروع تا شروع + شمار − ۱. */
export const numberSpan = (start: number, count: number): [number, number] | null =>
  count > 0 ? [start, start + count - 1] : null
