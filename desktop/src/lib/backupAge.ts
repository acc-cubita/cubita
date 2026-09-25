import { toFaDigits } from './jalali'

/** «۳ ساعت پیش» / «۲ روز پیش» — کهنگیِ پشتیبانِ سرور باید با یک نگاه خوانده شود، نه با حسابِ تاریخ. */
export function backupAge(hours: number | null): string {
  if (hours == null) return 'هیچ‌وقت'
  if (hours < 1) return 'کمتر از یک ساعت پیش'
  if (hours < 48) return `${toFaDigits(Math.round(hours))} ساعت پیش`
  return `${toFaDigits(Math.floor(hours / 24))} روز پیش`
}
