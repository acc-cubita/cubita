import type { JournalDraftLine } from './journalDraftTypes'

type JsonObject = Record<string, unknown>
export interface QueuedJournalDraft {
  original: JsonObject
  description: string
  entryDate: string
  subNumber: string
  status: 'temporary' | 'permanent'
  costCenterId: string
  analyticId: string
  currencyCode: string
  fxRate: string
  lines: JournalDraftLine[]
}

const object = (value: unknown): value is JsonObject => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown) => value == null ? '' : String(value)

/** دادهٔ صف هیچ‌وقت با یک فرم خالی جایگزین نمی‌شود، حتی اگر JSON قدیمی خراب باشد. */
export function parseQueuedJournalDraft(raw: string): QueuedJournalDraft {
  let data: unknown
  try { data = JSON.parse(raw) } catch { throw new Error('اطلاعات سند صف‌شده خوانده نشد؛ صف را حفظ کنید و با پشتیبانی هماهنگ کنید.') }
  if (!object(data) || typeof data.entry_date !== 'string' || typeof data.description !== 'string'
    || !Array.isArray(data.lines) || data.lines.length < 2 || data.lines.some((line) => !object(line) || typeof line.account_id !== 'string'
      || !Number.isFinite(Number(line.debit ?? 0)) || !Number.isFinite(Number(line.credit ?? 0)))) {
    throw new Error('ساختار سند صف‌شده معتبر نیست؛ اطلاعات اصلی حفظ شده است. برای بررسی با پشتیبانی هماهنگ کنید.')
  }
  const rows = data.lines as JsonObject[]
  const fx = rows.filter((line) => line.currency_code)
  if (new Set(fx.map((line) => `${line.currency_code}:${line.fx_rate}`)).size > 1) {
    throw new Error('این سند چند ارز یا چند نرخ دارد و با فرم تک‌ارزی ویرایش نمی‌شود؛ برای اصلاح با پشتیبانی هماهنگ کنید. صف حفظ شده است.')
  }
  return {
    original: data,
    description: data.description, entryDate: data.entry_date, subNumber: text(data.sub_number),
    status: data.status === 'permanent' ? 'permanent' : 'temporary',
    costCenterId: text(data.cost_center_id), analyticId: text(data.analytic_id),
    currencyCode: text(fx[0]?.currency_code), fxRate: text(fx[0]?.fx_rate),
    lines: rows.map((line, originIndex) => ({
      originIndex, accountId: text(line.account_id), debit: text(line.debit ?? 0), credit: text(line.credit ?? 0),
      description: text(line.description), analyticId: text(line.analytic_id), costCenterId: text(line.cost_center_id),
      fxAmount: text(line.fx_amount), trackingNo: text(line.tracking_no), trackingDate: text(line.tracking_date),
    })),
  }
}

/** ترتیبِ جدید ردیف‌ها حفظ است؛ فیلدهای ناشناخته و دقت عددِ دست‌نخورده گم نمی‌شوند. */
export function mergeQueuedJournalPayload(original: JsonObject, edited: JsonObject, lines: JournalDraftLine[], fxRate?: string): JsonObject {
  const oldLines = original.lines as JsonObject[]
  const updated = edited.lines as JsonObject[]
  return { ...original, ...edited, lines: updated.map((line, index) => {
    const origin = lines[index].originIndex
    const old = origin === undefined ? {} : oldLines[origin] ?? {}
    const result: JsonObject = { ...old, ...line,
      analytic_id: line.analytic_id ?? null, cost_center_id: line.cost_center_id ?? null,
      tracking_no: line.tracking_no ?? null, tracking_date: line.tracking_date ?? null,
      currency_code: line.currency_code ?? null, fx_amount: line.fx_amount ?? null, fx_rate: line.fx_rate ?? null,
    }
    for (const key of ['debit', 'credit', 'fx_amount', 'fx_rate']) {
      const draft = lines[index]
      const exact = key === 'debit' ? draft.debit : key === 'credit' ? draft.credit : key === 'fx_amount' ? draft.fxAmount : fxRate
      if (line[key] == null) continue
      const value = exact ?? text(line[key])
      result[key] = old[key] != null && decimalText(old[key]) === decimalText(value) ? old[key] : value
    }
    return result
  }) }
}

function decimalText(value: unknown): string {
  const raw = text(value).trim()
  const match = /^([+-]?)(\d+)(?:\.(\d*))?$/.exec(raw)
  if (!match) return raw
  const whole = match[2].replace(/^0+(?=\d)/, '')
  const fraction = (match[3] ?? '').replace(/0+$/, '')
  return `${match[1] === '-' && (whole !== '0' || fraction) ? '-' : ''}${whole}${fraction ? `.${fraction}` : ''}`
}
