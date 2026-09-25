/**
 * وضعیتِ توازنِ یک سند: `empty` هنوز مبلغی نیست، `ok` متوازن، `err` نامتوازن، و `auto` نامتوازن ولی
 * اختلاف **خودکار** به حسابی بسته می‌شود (سندِ افتتاحیه ← سرمایه) — آن‌جا اختلاف خبر است، نه خطا.
 */
export type BalanceState = 'empty' | 'ok' | 'err' | 'auto'

export function balanceState(totalDebit: number, totalCredit: number, balanced: boolean, autoClose = false): BalanceState {
  if (totalDebit === 0 && totalCredit === 0) return 'empty'
  if (balanced) return 'ok'
  return autoClose ? 'auto' : 'err'
}
