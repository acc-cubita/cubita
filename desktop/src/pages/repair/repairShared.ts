export const REPAIR_STATES: Record<string, string> = { accepted:'پذیرش‌شده', diagnosing:'عیب‌یابی', awaiting_customer:'منتظر مشتری', repairing:'در حال تعمیر', awaiting_part:'منتظر قطعه', testing:'در حال آزمون', ready:'آماده تحویل', unrepairable:'غیرقابل تعمیر', cancelled:'لغوشده', delivered:'تحویل‌شده', closed:'بسته' }
export const asciiNumber = (value: string) => value.replace(/[۰-۹]/g,c => String(c.charCodeAt(0)-1776)).replace(/[٠-٩]/g,c => String(c.charCodeAt(0)-1632)).replace(/[٬,]/g,'').trim()
export function rial(value: string, unit: 'rial' | 'toman'): string {
  const text = asciiNumber(value)
  if(!/^\d+$/.test(text)) throw new Error('مبلغ صحیح و غیرمنفی وارد کنید؛ واحد پول کنار مبلغ مشخص است.')
  return String(BigInt(text) * (unit === 'toman' ? 10n : 1n))
}
export const faRial = (value: string | null | undefined) => value ? BigInt(value).toLocaleString('fa-IR') + ' ریال' : '—'
