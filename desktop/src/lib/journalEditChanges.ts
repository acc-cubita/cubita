import type { JournalEditEvent } from '../api'
import { formatJalali, toFaDigits } from './jalali'

type Snapshot = Record<string, unknown>
type Change = { label: string; before: string; after: string }
const LINE_LABELS: Record<string, string> = {
  account_id: 'حساب', analytic_id: 'تفصیلی', cost_center_id: 'مرکز هزینه',
  debit: 'بدهکار', credit: 'بستانکار', description: 'شرح', currency_code: 'ارز',
  fx_amount: 'مبلغ ارزی', fx_rate: 'نرخ ارز', tracking_no: 'شماره پیگیری', tracking_date: 'تاریخ پیگیری', seq: 'ترتیب',
}
const HEADER_LABELS: Record<string, string> = {
  entry_date: 'تاریخ سند', description: 'شرح سند', sub_number: 'شماره فرعی', number: 'شماره سند',
}

function display(field: string, value: unknown, snapshot?: Snapshot): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field === 'entry_date' || field === 'tracking_date') return formatJalali(String(value))
  if (field === 'account_id' || field === 'analytic_id' || field === 'cost_center_id') {
    const prefix = field.slice(0, -3)
    const code = snapshot?.[`${prefix}_code`]
    const name = snapshot?.[`${prefix}_name`]
    return name ? `${code ? `${toFaDigits(String(code))} — ` : ''}${name}` : String(value)
  }
  if (field === 'debit' || field === 'credit' || field === 'fx_amount' || field === 'fx_rate') {
    // Number رقم‌های بزرگِ مالی را گرد می‌کند؛ نمایشِ قبل/بعد باید دقیق بماند.
    const raw = String(value)
    if (/^-?\d+(?:\.\d+)?$/.test(raw)) {
      const negative = raw.startsWith('-')
      const [integer, fraction] = (negative ? raw.slice(1) : raw).split('.')
      const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, '٬')
      return `${negative ? '−' : ''}${toFaDigits(grouped)}${fraction === undefined ? '' : `٫${toFaDigits(fraction)}`}`
    }
    return toFaDigits(raw)
  }
  return toFaDigits(String(value))
}

export function journalEditChanges(event: JournalEditEvent): Change[] {
  const changes = event.changes ?? {}
  const result: Change[] = []
  for (const [field, label] of Object.entries(HEADER_LABELS)) {
    const diff = changes[field]
    if (diff) result.push({ label, before: display(field, diff.from), after: display(field, diff.to) })
  }
  const lines = changes.lines
  if (lines && Array.isArray(lines.from) && Array.isArray(lines.to)) {
    const previous = new Map((lines.from as Snapshot[]).map((line) => [String(line.id), line]))
    const next = new Map((lines.to as Snapshot[]).map((line) => [String(line.id), line]))
    for (const [index, oldLine] of (lines.from as Snapshot[]).entries()) {
      const current = next.get(String(oldLine.id))
      const prefix = `ردیف ${toFaDigits(index + 1)}`
      if (!current) {
        result.push({ label: prefix, before: `${display('account_id', oldLine.account_id, oldLine)} · ${display('debit', oldLine.debit)} / ${display('credit', oldLine.credit)}`, after: 'حذف شد' })
        continue
      }
      for (const [field, label] of Object.entries(LINE_LABELS)) {
        if (String(oldLine[field] ?? '') !== String(current[field] ?? '')) {
          result.push({ label: `${prefix} / ${label}`, before: display(field, oldLine[field], oldLine), after: display(field, current[field], current) })
        }
      }
    }
    for (const [index, line] of (lines.to as Snapshot[]).entries()) {
      if (!previous.has(String(line.id))) result.push({
        label: `ردیف ${toFaDigits(index + 1)}`,
        before: '—', after: `افزوده شد: ${display('account_id', line.account_id, line)} · ${display('debit', line.debit)} / ${display('credit', line.credit)}`,
      })
    }
  }
  return result
}
